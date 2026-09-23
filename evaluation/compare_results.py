"""
compare_results.py — this is where "accuracy" actually comes from.

benchmark_load.py (already built) only measures SPEED: TTFT, latency,
throughput. It never checks whether the model's tags were actually
CORRECT. This script is the other half: it scores a model's predicted
tags (produced by tag_chunks.py --eval-only) against your team's human
ground truth in evaluation/eval_sample.csv, field by field.

Pipeline for ONE model:
  1. python src/tagging/tag_chunks.py --eval-only \
         --endpoint <model's endpoint> --model <model name> \
         --output data/tagged/tagged_chunks_<tag>.jsonl
     -> produces the model's PREDICTED tags for the 90 eval chunks.

  2. python evaluation/compare_results.py \
         --predictions data/tagged/tagged_chunks_<tag>.jsonl \
         --tag <tag>
     -> scores those predictions against evaluation/eval_sample.csv
        (the human-labeled ground truth) and writes:
          evaluation/scored_results_<tag>.csv     one row per chunk
          evaluation/accuracy_summary_<tag>.json  per-field + overall accuracy

Comparison is normalized (case/whitespace-insensitive) so "Machine
Learning" vs "machine learning " still counts as a match — real human
labeling isn't perfectly consistent, and a good model shouldn't be
penalized for that. A row where tag_chunks.py itself failed (bad JSON,
API error) is counted separately as "unscored" (a reliability problem),
not folded into wrong-answer accuracy.

IMPORTANT: pass a different --output to tag_chunks.py (and --tag here)
for every model — modelA / modelB / modelC — same reason as
benchmark_load.py's --tag: so three people's runs don't overwrite the
same file.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["Field", "Learning_type", "Level", "Competency"]


def norm(v) -> str:
    return " ".join(str(v or "").split()).casefold()


def load_ground_truth(path: Path) -> dict:
    gt = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["file_name"], row["chunk_id"])
            gt[key] = {field: row.get(field, "") for field in FIELDS}
    return gt


def load_predictions(path: Path) -> dict:
    preds = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key = (rec["file_name"], rec["chunk_id"])
            preds[key] = rec
    return preds


def score(ground_truth: dict, predictions: dict, model_name: str) -> tuple[list[dict], dict]:
    rows = []
    field_correct = defaultdict(int)
    field_scored = defaultdict(int)
    full_match = 0
    unscored = 0
    missing_from_predictions = 0

    for key, gt in ground_truth.items():
        file_name, chunk_id = key
        pred = predictions.get(key)

        if pred is None:
            missing_from_predictions += 1
            rows.append({
                "file_name": file_name, "chunk_id": chunk_id, "status": "missing",
                **{f"{f}_ground_truth": gt[f] for f in FIELDS},
                **{f"{f}_predicted": "" for f in FIELDS},
                **{f"{f}_match": "" for f in FIELDS},
                "all_fields_match": "",
            })
            continue

        if pred.get("error"):
            unscored += 1
            rows.append({
                "file_name": file_name, "chunk_id": chunk_id, "status": f"error: {pred['error'][:120]}",
                **{f"{f}_ground_truth": gt[f] for f in FIELDS},
                **{f"{f}_predicted": "" for f in FIELDS},
                **{f"{f}_match": "" for f in FIELDS},
                "all_fields_match": "",
            })
            continue

        row = {"file_name": file_name, "chunk_id": chunk_id, "status": "scored"}
        all_match = True
        for f in FIELDS:
            gt_val = gt[f]
            pred_val = pred.get(f, "")
            is_match = bool(gt_val) and norm(gt_val) == norm(pred_val)
            row[f"{f}_ground_truth"] = gt_val
            row[f"{f}_predicted"] = pred_val
            row[f"{f}_match"] = is_match
            if gt_val:  # only score fields that actually have a human label
                field_scored[f] += 1
                if is_match:
                    field_correct[f] += 1
            all_match = all_match and is_match
        row["all_fields_match"] = all_match
        if all_match:
            full_match += 1
        rows.append(row)

    scored_total = len(ground_truth) - unscored - missing_from_predictions
    summary = {
        "model": model_name,
        "total_ground_truth_rows": len(ground_truth),
        "scored": scored_total,
        "unscored_errors": unscored,
        "missing_from_predictions": missing_from_predictions,
        "per_field_accuracy": {
            f: {
                "correct": field_correct[f],
                "scored": field_scored[f],
                "accuracy_pct": round(100 * field_correct[f] / field_scored[f], 1) if field_scored[f] else None,
            }
            for f in FIELDS
        },
        "full_exact_match": {
            "correct": full_match,
            "scored": scored_total,
            "accuracy_pct": round(100 * full_match / scored_total, 1) if scored_total else None,
        },
    }
    return rows, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--predictions", required=True, help="path to tag_chunks.py --eval-only output (.jsonl)")
    ap.add_argument("--eval-sample", default=str(REPO_ROOT / "evaluation" / "eval_sample.csv"))
    ap.add_argument("--tag", required=True, help="labels the output files, e.g. modelA")
    ap.add_argument("--model-name", default=None, help="defaults to --tag if omitted, just for the summary label")
    args = ap.parse_args()

    ground_truth = load_ground_truth(Path(args.eval_sample))
    predictions = load_predictions(Path(args.predictions))

    rows, summary = score(ground_truth, predictions, args.model_name or args.tag)

    out_csv = REPO_ROOT / "evaluation" / f"scored_results_{args.tag}.csv"
    out_json = REPO_ROOT / "evaluation" / f"accuracy_summary_{args.tag}.json"

    fieldnames = ["file_name", "chunk_id", "status"] + [
        f"{f}_{suffix}" for f in FIELDS for suffix in ("ground_truth", "predicted", "match")
    ] + ["all_fields_match"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Ground truth rows: {summary['total_ground_truth_rows']}")
    print(f"Scored: {summary['scored']}  |  API/parse errors: {summary['unscored_errors']}  "
          f"|  missing from predictions file: {summary['missing_from_predictions']}")
    print("Per-field accuracy:")
    for f in FIELDS:
        pf = summary["per_field_accuracy"][f]
        print(f"  {f}: {pf['accuracy_pct']}% ({pf['correct']}/{pf['scored']})")
    fm = summary["full_exact_match"]
    print(f"Full exact match (all 4 fields correct): {fm['accuracy_pct']}% ({fm['correct']}/{fm['scored']})")
    print(f"\nWritten: {out_csv}")
    print(f"Written: {out_json}")


if __name__ == "__main__":
    main()