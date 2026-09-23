"""Extract qualitative correct/incorrect tagging examples from scored results.

Usage:
    python evaluation/analyze_results.py --csv evaluation/scored_results_modelA.csv --model "Model A"
"""
import argparse
import csv

FIELDS = [
    ("Field", "Field_ground_truth", "Field_predicted", "Field_match"),
    ("Learning Type", "Learning_type_ground_truth", "Learning_type_predicted", "Learning_type_match"),
    ("Level", "Level_ground_truth", "Level_predicted", "Level_match"),
    ("Competency", "Competency_ground_truth", "Competency_predicted", "Competency_match"),
]


def load_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def is_match(row):
    return row.get("all_fields_match", "").strip().lower() == "true"


def format_row(row):
    lines = [f"- **{row['file_name']} / {row['chunk_id']}**"]
    for label, gt_col, pred_col, match_col in FIELDS:
        gt = row.get(gt_col, "")
        pred = row.get(pred_col, "")
        match = row.get(match_col, "").strip().lower() == "true"
        marker = "match" if match else "MISMATCH"
        lines.append(f'  - {label}: ground truth = "{gt}", predicted = "{pred}" ({marker})')
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--model", required=True, help="Label to print, e.g. 'Model A'")
    ap.add_argument("--n-correct", type=int, default=3)
    ap.add_argument("--n-incorrect", type=int, default=3)
    args = ap.parse_args()

    rows = load_rows(args.csv)
    if not rows:
        raise SystemExit(f"No rows found in {args.csv}")

    correct = [r for r in rows if is_match(r)]
    incorrect = [r for r in rows if not is_match(r)]
    total = len(rows)

    print(f"=== {args.model} ({args.csv}) ===")
    print(f"Total scored rows: {total}")
    print(f"All-fields-match: {len(correct)} ({len(correct)/total*100:.1f}%)")
    print(f"At least one field mismatched: {len(incorrect)} ({len(incorrect)/total*100:.1f}%)")
    print()

    print(f"-- {min(args.n_correct, len(correct))} correct examples --")
    for row in correct[: args.n_correct]:
        print(format_row(row))
        print()

    if incorrect:
        print(f"-- {min(args.n_incorrect, len(incorrect))} incorrect examples --")
        for row in incorrect[: args.n_incorrect]:
            print(format_row(row))
            print()
    else:
        print("-- No incorrect examples found (0 mismatches in this file) --")


if __name__ == "__main__":
    main()