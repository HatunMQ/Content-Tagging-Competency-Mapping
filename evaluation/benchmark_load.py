"""
Load-test a deployed model's OpenAI-compatible /v1/chat/completions endpoint
and measure the infra metrics the project guide requires: Time to First
Token (TTFT), End-to-End Latency, Throughput, and behavior across increasing
Concurrency.

Works against ANY OpenAI-compatible endpoint by pointing --base-url at it:
  - Model A (local vLLM, via your existing port-forward): http://localhost:8000/v1
  - Model B (OpenAI API): https://api.openai.com/v1  (pass --api-key)
  - Model C (once deployed): same pattern as Model A, different port/URL

For each concurrency level in --concurrency, it fires --requests-per-level
requests (at most that many in flight at once), streams each response, and
records per-request:
  - ttft_s     : time from request sent to first content token received
  - e2e_s      : time from request sent to the response finishing
  - n_tokens   : completion tokens generated (from the API's usage field
                 when the server sends one, else counted from stream chunks)

Writes (per model, see --tag below — files are named per model so three
people benchmarking three different models never overwrite each other):
  evaluation/results_<tag>.csv          one row per request (raw data)
  evaluation/metrics_summary_<tag>.json aggregated per concurrency level:
                                         mean/p50/p95/p99 TTFT and E2E
                                         latency, throughput (tokens/sec),
                                         requests/sec, and (optional) SLO
                                         pass/fail — see --slo-* below.

Usage (Model A, matches the port-forward you already have running):
    python evaluation/benchmark_load.py \\
        --base-url http://localhost:8000/v1 \\
        --model Qwen2.5-VL-7B-Instruct \\
        --concurrency 1 2 4 8 \\
        --requests-per-level 20 \\
        --tag modelA

Prompts: by default a small built-in set of representative prompts is used.
To benchmark with your real content instead, pass --prompts-from-csv
pointing at evaluation/eval_sample.csv — it reads the text_preview column
and turns each row into a "tag this content" prompt, same shape as what
tag_chunks.py actually sends in production.

SLO / SLI, in this script's terms:
  - SLI (what you MEASURE) = every number this script already outputs:
    p50/p95/p99 TTFT, p50/p95/p99 E2E latency, throughput, error rate.
  - SLO (what you DECIDE) = a target you set for one of those numbers,
    e.g. "p95 TTFT must stay under 3s". This script can't invent that
    number for you — pick it after looking at a real run's numbers, or
    from what the use case needs — but once you have it, pass it with
    --slo-ttft-p95 / --slo-e2e-p95 and every level's summary gets a
    "slo" block telling you pass/fail at that concurrency, so you don't
    have to eyeball the json yourself.
"""
import argparse
import asyncio
import csv
import json
import re
import statistics
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sanitize_tag(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "model"

DEFAULT_PROMPTS = [
    "Summarize the key idea of this lecture slide in two sentences: "
    "'Decision trees split data recursively on the feature that most reduces impurity.'",
    "Classify this content chunk's competency Field, Learning_type, Level and Competency: "
    "'A hands-on SQL lab covering window functions: ROW_NUMBER, RANK, and PARTITION BY.'",
    "Explain in one paragraph what a confusion matrix is used for in classification evaluation.",
    "Given this notebook cell, describe what it teaches: "
    "'df.groupby(\"category\")[\"sales\"].sum().sort_values(ascending=False).plot(kind=\"bar\")'",
    "Tag the following slide content with the most relevant competency area: "
    "'Overfitting occurs when a model learns noise in the training data instead of the signal.'",
]


def load_prompts_from_csv(path: Path, limit: int = 20) -> list[str]:
    prompts = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            text = (row.get("text_preview") or "").strip()
            if text:
                prompts.append(f"Classify the Field, Learning_type, Level and Competency of: {text}")
            if len(prompts) >= limit:
                break
    if not prompts:
        raise SystemExit(f"No usable text_preview rows found in {path}")
    return prompts


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile, no numpy dependency."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


async def stream_one_request(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    api_key: str | None,
    max_tokens: int,
    timeout_s: float,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    t_start = time.perf_counter()
    ttft = None
    n_tokens = 0
    error = None

    try:
        async with client.stream(
            "POST", f"{base_url.rstrip('/')}/chat/completions",
            headers=headers, json=payload, timeout=timeout_s,
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(f"HTTP {resp.status_code}: {body[:300]!r}")

            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue

                choices = obj.get("choices") or []
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        if ttft is None:
                            ttft = time.perf_counter() - t_start
                        n_tokens += 1  # fallback count if no usage field arrives

                usage = obj.get("usage")
                if usage and usage.get("completion_tokens") is not None:
                    n_tokens = usage["completion_tokens"]
    except Exception as e:  # noqa: BLE001
        error = str(e)

    e2e = time.perf_counter() - t_start
    return {
        "ttft_s": ttft if ttft is not None else e2e,  # fell over before any token
        "e2e_s": e2e,
        "n_tokens": n_tokens,
        "error": error,
    }


async def run_level(
    base_url: str, model: str, prompts: list[str], concurrency: int,
    n_requests: int, api_key: str | None, max_tokens: int, timeout_s: float,
) -> list[dict]:
    sem = asyncio.Semaphore(concurrency)
    results = []

    async def worker(i: int):
        async with sem:
            prompt = prompts[i % len(prompts)]
            async with httpx.AsyncClient() as client:
                r = await stream_one_request(client, base_url, model, prompt, api_key, max_tokens, timeout_s)
                r["concurrency"] = concurrency
                r["request_index"] = i
                results.append(r)

    level_start = time.perf_counter()
    await asyncio.gather(*(worker(i) for i in range(n_requests)))
    level_wall_s = time.perf_counter() - level_start
    for r in results:
        r["level_wall_s"] = level_wall_s
    return results


def summarize(
    level_results: list[dict], concurrency: int,
    slo_ttft_p95: float | None = None, slo_e2e_p95: float | None = None,
) -> dict:
    ok = [r for r in level_results if not r["error"]]
    failed = len(level_results) - len(ok)
    ttfts = [r["ttft_s"] for r in ok]
    e2es = [r["e2e_s"] for r in ok]
    total_tokens = sum(r["n_tokens"] for r in ok)
    wall_s = level_results[0]["level_wall_s"] if level_results else 0.0

    ttft_p95 = round(percentile(ttfts, 95), 4) if ttfts else None
    e2e_p95 = round(percentile(e2es, 95), 4) if e2es else None

    summary = {
        "concurrency": concurrency,
        "requests": len(level_results),
        "failed": failed,
        "ttft_s": {
            "mean": round(statistics.fmean(ttfts), 4) if ttfts else None,
            "p50": round(percentile(ttfts, 50), 4) if ttfts else None,
            "p95": ttft_p95,
            "p99": round(percentile(ttfts, 99), 4) if ttfts else None,
        },
        "e2e_latency_s": {
            "mean": round(statistics.fmean(e2es), 4) if e2es else None,
            "p50": round(percentile(e2es, 50), 4) if e2es else None,
            "p95": e2e_p95,
            "p99": round(percentile(e2es, 99), 4) if e2es else None,
        },
        "throughput_tokens_per_s": round(total_tokens / wall_s, 2) if wall_s > 0 else None,
        "requests_per_s": round(len(ok) / wall_s, 2) if wall_s > 0 else None,
        "wall_time_s": round(wall_s, 2),
    }

    # SLO = a target YOU chose for one of the SLIs above. Only shown when
    # you actually pass a threshold in — this script won't guess one.
    if slo_ttft_p95 is not None or slo_e2e_p95 is not None:
        slo = {}
        if slo_ttft_p95 is not None:
            slo["ttft_p95_target_s"] = slo_ttft_p95
            slo["ttft_p95_met"] = ttft_p95 is not None and ttft_p95 <= slo_ttft_p95
        if slo_e2e_p95 is not None:
            slo["e2e_p95_target_s"] = slo_e2e_p95
            slo["e2e_p95_met"] = e2e_p95 is not None and e2e_p95 <= slo_e2e_p95
        summary["slo"] = slo

    return summary


async def main_async(args):
    prompts = (
        load_prompts_from_csv(Path(args.prompts_from_csv), limit=args.requests_per_level)
        if args.prompts_from_csv else DEFAULT_PROMPTS
    )

    tag = _sanitize_tag(args.tag) if args.tag else _sanitize_tag(args.model)
    results_csv = REPO_ROOT / "evaluation" / f"results_{tag}.csv"
    summary_json = REPO_ROOT / "evaluation" / f"metrics_summary_{tag}.json"

    all_rows = []
    summaries = []
    for c in args.concurrency:
        print(f"[level] concurrency={c} requests={args.requests_per_level} ...")
        level_results = await run_level(
            args.base_url, args.model, prompts, c, args.requests_per_level,
            args.api_key, args.max_tokens, args.timeout,
        )
        all_rows.extend(level_results)
        s = summarize(level_results, c, args.slo_ttft_p95, args.slo_e2e_p95)
        summaries.append(s)
        line = (
            f"  ttft p50={s['ttft_s']['p50']}s p95={s['ttft_s']['p95']}s | "
            f"e2e p50={s['e2e_latency_s']['p50']}s p95={s['e2e_latency_s']['p95']}s | "
            f"throughput={s['throughput_tokens_per_s']} tok/s | failed={s['failed']}"
        )
        if "slo" in s:
            line += f" | slo={s['slo']}"
        print(line)

    results_csv.parent.mkdir(parents=True, exist_ok=True)
    with results_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "concurrency", "request_index", "ttft_s", "e2e_s", "n_tokens", "error", "level_wall_s",
        ])
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    summary_doc = {
        "model": args.model,
        "tag": tag,
        "base_url": args.base_url,
        "requests_per_level": args.requests_per_level,
        "levels": summaries,
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary_doc, f, ensure_ascii=False, indent=2)

    print(f"\nWritten: {results_csv}")
    print(f"Written: {summary_json}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=True, help="e.g. http://localhost:8000/v1")
    ap.add_argument("--model", required=True, help="model name as the server expects it")
    ap.add_argument("--api-key", default=None, help="only needed for real OpenAI (Model B)")
    ap.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--requests-per-level", type=int, default=20)
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--prompts-from-csv", default=None,
                     help="path to evaluation/eval_sample.csv to benchmark with real content")
    ap.add_argument("--tag", default=None,
                     help="labels the output files, e.g. --tag modelA -> results_modelA.csv. "
                          "Defaults to the --model name if omitted. Use a different tag per "
                          "model so teammates' runs never overwrite each other.")
    ap.add_argument("--slo-ttft-p95", type=float, default=None,
                     help="optional target in seconds, e.g. 2.0 -> flags pass/fail per level")
    ap.add_argument("--slo-e2e-p95", type=float, default=None,
                     help="optional target in seconds, e.g. 5.0 -> flags pass/fail per level")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()