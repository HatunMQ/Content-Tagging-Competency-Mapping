"""
gpu_monitor.py — Samples GPU utilization, power draw, and memory usage
every second via nvidia-smi, and writes the samples to a CSV.

Run this in a SEPARATE terminal, in parallel with benchmark_load.py,
so the CSV covers the same time window as the load test. Stop it with
Ctrl+C right after the load test finishes.

Usage:
  python evaluation/gpu_monitor.py --output evaluation/gpu_load_monitor_modelA.csv
"""
import argparse
import csv
import subprocess
import time
from datetime import datetime, timezone


def sample():
    out = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,power.draw,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True, text=True, check=True,
    )
    util, power, mem_used, mem_total = [x.strip() for x in out.stdout.strip().split(",")]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gpu_utilization_pct": float(util),
        "power_draw_w": float(power),
        "memory_used_mib": float(mem_used),
        "memory_total_mib": float(mem_total),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True)
    ap.add_argument("--interval", type=float, default=1.0, help="Seconds between samples")
    args = ap.parse_args()

    fieldnames = ["timestamp", "gpu_utilization_pct", "power_draw_w", "memory_used_mib", "memory_total_mib"]
    print(f"Sampling GPU every {args.interval}s -> {args.output}. Press Ctrl+C to stop.")
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        try:
            while True:
                row = sample()
                writer.writerow(row)
                f.flush()
                print(f"{row['timestamp']}  util={row['gpu_utilization_pct']:>5.1f}%  power={row['power_draw_w']:>6.2f}W  mem={row['memory_used_mib']:.0f}/{row['memory_total_mib']:.0f} MiB")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()