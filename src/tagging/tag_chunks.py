"""
tag_chunks.py — Automatically tag extracted content chunks using a deployed
AI model (Model A: Qwen2.5-VL-7B via vLLM, Model B: GPT-4o, or Model C).

This is the real "AI-powered content tagging" step of the pipeline. It is
NOT the same thing as evaluation/eval_sample.csv, which stays human-labeled
on purpose — that file is the ground truth used to MEASURE how accurate
this script's output is. If this script tagged eval_sample.csv too, there
would be nothing independent left to compare against.

Usage
-----
  # Model A / Model C served locally via vLLM (OpenAI-compatible):
  python src/tagging/tag_chunks.py \
      --endpoint http://localhost:8000/v1 \
      --model Qwen2.5-VL-7B-Instruct

  # Model B — GPT-4o via OpenAI's API directly:
  python src/tagging/tag_chunks.py \
      --endpoint https://api.openai.com/v1 \
      --model gpt-4o \
      --api-key $OPENAI_API_KEY

  # Quick smoke test on the first 5 chunks only:
  python src/tagging/tag_chunks.py --limit 5 --endpoint ... --model ...

  # Tag ONLY the 90 chunks that are in evaluation/eval_sample.csv, so you
  # can diff the model's tags against the team's human ground truth
  # (this is the actual benchmark comparison):
  python src/tagging/tag_chunks.py --eval-only --endpoint ... --model ...

Output: one JSON object per line, written to --output (default
data/tagged/tagged_chunks.jsonl), with the model's tags plus per-request
latency — the latency numbers feed straight into the Step 5 infra
benchmark (mean latency, p95, etc.) so you don't have to measure it twice.

Each record also includes "first_attempt_failed": true/false, so you can
measure a no-retry failure rate separately from the final (post-retry)
failure rate reported in the summary line at the end.

Each successful record also includes "prompt_tokens", "completion_tokens",
and "total_tokens", read directly from the model's own "usage" field in
its response (confirmed present on both the vLLM-served models and the
OpenAI API), so token usage doesn't need a separate measurement pass.
"""
import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# EDIT THIS to match your team's finalized taxonomy. Field / Learning_type /
# Level below match what's already been agreed on; the Competency list is a
# placeholder — replace it with your team's real 10 fixed values before you
# run this for real.
# ---------------------------------------------------------------------------
TAXONOMY = {
    "Field": ["Data Science", "Machine Learning", "SQL", "Generative AI"],
    "Learning_type": ["Visual", "Read/Write", "Kinesthetic"],
    "Level": ["Beginner", "Intermediate", "Advanced"],
    "Competency": [
        "Python Basics",
        "Pandas & Data Wrangling",
        "Machine Learning Workflow",
        "Decision Tree Modeling",
        "SQL Foundations",
        "Window Functions",
        "Prompt Engineering",
        "RAG Systems",
        "Data Visualization",
        "Statistics Foundations",
    ],
}
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are a content-tagging assistant for an educational platform.
Given one chunk of lecture/notebook/notes content, classify it using EXACTLY
this taxonomy and return ONLY a JSON object — no prose, no markdown fences.

Field (pick exactly one): {TAXONOMY['Field']}
Learning_type (pick exactly one, based on the VARK model — how the content
is best absorbed):
  - Visual: diagrams, charts, slides, visual structure
  - Read/Write: prose explanations, definitions, written notes
  - Kinesthetic: hands-on code, exercises, step-by-step practice
Level (pick exactly one): {TAXONOMY['Level']}
Competency (pick exactly one, the closest match): {TAXONOMY['Competency']}

IMPORTANT: Do not show your reasoning or thinking process.
Return ONLY the JSON object.
No explanations, no markdown, no extra text.

Return exactly this shape:
{{"Field": "...", "Learning_type": "...", "Level": "...", "Competency": "..."}}
"""

def build_user_prompt(chunk: dict) -> str:
    meta = chunk.get("metadata", {})
    text = (chunk.get("text") or "")[:2000]
    return (
        f"File: {chunk.get('file_name')}\n"
        f"Section: {meta.get('section_title', '')}\n"
        f"Content type: {chunk.get('content_type')}\n"
        f"---\n{text}"
    )


def parse_json_response(content: str) -> dict:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model response: {content[:200]!r}")
    return json.loads(match.group(0))


def call_model(endpoint: str, model: str, api_key: str, chunk: dict, timeout=60, retries=3):
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(chunk)},
        ],
        "temperature": 0,
        "max_tokens": 200,
        "chat_template_kwargs": {
    "enable_thinking": False
},
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_err = None
    first_attempt_failed = False
    for attempt in range(retries):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            latency = time.time() - t0
            content = body["choices"][0]["message"]["content"].strip()
            tags = parse_json_response(content)
            usage = body.get("usage") or {}
            token_counts = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
            return tags, latency, None, first_attempt_failed, token_counts
        except Exception as e:  # noqa: BLE001 - we want to record and retry any failure
            last_err = str(e)
            if attempt == 0:
                first_attempt_failed = True
            time.sleep(1.5 * (attempt + 1))
    return None, None, last_err, first_attempt_failed, None


def load_eval_keys(eval_sample_path: str) -> set:
    wanted = set()
    with open(eval_sample_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            wanted.add((row["file_name"], row["chunk_id"]))
    return wanted


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", required=True, help="Base URL, e.g. http://localhost:8000/v1 or https://api.openai.com/v1")
    ap.add_argument("--model", required=True, help="Model name exactly as the endpoint expects it")
    ap.add_argument("--api-key", default=os.environ.get("MODEL_API_KEY", ""), help="Or set MODEL_API_KEY env var")
    ap.add_argument("--input", default=str(REPO_ROOT / "data" / "extracted" / "extracted_chunks.jsonl"))
    ap.add_argument("--output", default=str(REPO_ROOT / "data" / "tagged" / "tagged_chunks.jsonl"))
    ap.add_argument("--eval-sample", default=str(REPO_ROOT / "evaluation" / "eval_sample.csv"),
                     help="Only read when --eval-only is set, to know which chunk_ids to tag")
    ap.add_argument("--eval-only", action="store_true",
                     help="Tag only the chunks that are in eval_sample.csv, for benchmarking against the human labels")
    ap.add_argument("--limit", type=int, default=None, help="Tag only the first N chunks (quick test run)")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]

    if args.eval_only:
        wanted = load_eval_keys(args.eval_sample)
        chunks = [c for c in chunks if (c["file_name"], c["chunk_id"]) in wanted]
        print(f"--eval-only: tagging {len(chunks)} chunks that match {args.eval_sample}")

    if args.limit:
        chunks = chunks[: args.limit]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ok, failed, first_attempt_failures = 0, 0, 0
    total_prompt_tokens, total_completion_tokens, total_tokens_sum = 0, 0, 0
    tokens_recorded = 0
    with out_path.open("w", encoding="utf-8") as out:
        for i, chunk in enumerate(chunks, 1):
            tags, latency, err, first_attempt_failed, token_counts = call_model(
                args.endpoint, args.model, args.api_key, chunk
            )
            if first_attempt_failed:
                first_attempt_failures += 1
            record = {
                "file_name": chunk["file_name"],
                "chunk_id": chunk["chunk_id"],
                "model": args.model,
                "first_attempt_failed": first_attempt_failed,
            }
            if err:
                record["error"] = err
                failed += 1
            else:
                record.update(tags)
                record["latency_sec"] = round(latency, 3)
                if token_counts:
                    record["prompt_tokens"] = token_counts["prompt_tokens"]
                    record["completion_tokens"] = token_counts["completion_tokens"]
                    record["total_tokens"] = token_counts["total_tokens"]
                    if token_counts["total_tokens"] is not None:
                        total_prompt_tokens += token_counts["prompt_tokens"] or 0
                        total_completion_tokens += token_counts["completion_tokens"] or 0
                        total_tokens_sum += token_counts["total_tokens"]
                        tokens_recorded += 1
                ok += 1
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            status = "OK" if not err else f"FAILED: {err}"
            retry_note = " (needed a retry)" if first_attempt_failed and not err else (" (retried, still failed)" if first_attempt_failed else "")
            print(f"[{i}/{len(chunks)}] {chunk['file_name']} / {chunk['chunk_id']} -> {status}{retry_note}")

    print(f"\nDone. {ok} tagged, {failed} failed (final, post-retry).")
    print(f"First-attempt failures (before any retry): {first_attempt_failures}/{len(chunks)} "
          f"({first_attempt_failures / len(chunks) * 100:.1f}%)")
    if tokens_recorded:
        print(
            f"Token usage over {tokens_recorded} successful calls: "
            f"avg prompt={total_prompt_tokens / tokens_recorded:.1f}, "
            f"avg completion={total_completion_tokens / tokens_recorded:.1f}, "
            f"avg total={total_tokens_sum / tokens_recorded:.1f} "
            f"(sum: prompt={total_prompt_tokens}, completion={total_completion_tokens}, total={total_tokens_sum})"
        )
    else:
        print("Token usage: no successful calls returned a usage field.")
    print(f"Output written to {out_path}")


if __name__ == "__main__":
    main()