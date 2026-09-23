"""
estimate_cost.py — Estimates GPU electricity cost and energy per request,
using the same methodology as the Agromind team's Phase 1 report:
peak power draw (W) x time for N requests (s) / 3600 / 1000 = energy (kWh).

Requires:
  - a metrics_summary_model*.json from benchmark_load.py (for requests_per_s)
  - a gpu_load_monitor CSV from gpu_monitor.py, sampled during the SAME
    benchmark run (for peak power draw)

Only applies to self-hosted models (A and C) — Model B runs on OpenAI's
infrastructure, which we cannot instrument.

Usage:
  python evaluation/estimate_cost.py \
      --metrics evaluation/metrics_summary_modelA.json \
      --gpu-csv evaluation/gpu_load_monitor_modelA.csv \
      --tariff 0.18
"""
import argparse
import csv
import json


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--gpu-csv", required=True)
    ap.add_argument("--concurrency", type=int, default=None,
                     help="Which concurrency level's requests_per_s to use (default: highest tested)")
    ap.add_argument("--tariff", type=float, default=0.18, help="SAR per kWh")
    args = ap.parse_args()

    with open(args.metrics) as f:
        metrics = json.load(f)

    levels = metrics["levels"]
    level = max(levels, key=lambda l: l["concurrency"]) if args.concurrency is None \
        else next(l for l in levels if l["concurrency"] == args.concurrency)

    with open(args.gpu_csv) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"No samples found in {args.gpu_csv} — was gpu_monitor.py actually running during the benchmark?")
    peak_power_w = max(float(r["power_draw_w"]) for r in rows)
    peak_util_pct = max(float(r["gpu_utilization_pct"]) for r in rows)
    peak_mem_mib = max(float(r["memory_used_mib"]) for r in rows)

    requests_per_s = level["requests_per_s"]
    time_for_1000_s = 1000 / requests_per_s
    time_for_1m_s = 1_000_000 / requests_per_s

    energy_per_1000_kwh = peak_power_w * time_for_1000_s / 3600 / 1000
    energy_per_1m_kwh = peak_power_w * time_for_1m_s / 3600 / 1000

    cost_per_hour = peak_power_w / 1000 * args.tariff
    cost_per_1000 = energy_per_1000_kwh * args.tariff
    cost_per_1m = energy_per_1m_kwh * args.tariff

    print(f"Model: {metrics.get('model')}")
    print(f"Concurrency level used: {level['concurrency']} (requests_per_s = {requests_per_s})")
    print(f"Peak GPU utilization: {peak_util_pct:.1f}%")
    print(f"Peak GPU memory used: {peak_mem_mib:.0f} MiB")
    print(f"Peak GPU power draw: {peak_power_w:.2f} W")
    print()
    print(f"Time for 1,000 requests: {time_for_1000_s:.2f} s")
    print(f"Estimated GPU energy per 1,000 requests: {energy_per_1000_kwh:.6f} kWh")
    print(f"Estimated GPU energy per 1,000,000 requests: {energy_per_1m_kwh:.4f} kWh")
    print()
    print(f"Tariff assumed: {args.tariff} SAR/kWh")
    print(f"Estimated GPU electricity cost per hour: {cost_per_hour:.4f} SAR")
    print(f"Estimated GPU electricity cost per 1,000 requests: {cost_per_1000:.6f} SAR")
    print(f"Estimated GPU electricity cost per 1,000,000 requests: {cost_per_1m:.4f} SAR")
    print()
    print("This estimate represents GPU electricity only. It does not include CPU, system")
    print("memory, storage, networking, cooling, server capital cost/depreciation,")
    print("maintenance, or idle infrastructure consumption.")


if __name__ == "__main__":
    main()