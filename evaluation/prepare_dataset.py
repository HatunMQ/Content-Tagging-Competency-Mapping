"""
Build a small human-labeling sample from the extracted chunks.

Stratified by file: every file gets a share proportional to its chunk
count, with a floor of at least 1 chunk per file, capped at TARGET_SIZE
total. Sampling is random but reproducible (fixed seed).

Writes TWO files every run:
  - evaluation/eval_sample.csv   plain data, read by the pipeline scripts
  - evaluation/eval_sample.xlsx  same data, formatted for human review
                                  (teal header, yellow-highlighted label
                                  columns, left-to-right, no Labeled_by)

text_preview skips any leading decorative lines (ASCII banners, "===="
separator lines, comment markers) so the preview starts at real content
instead of e.g. a figlet banner — see make_smart_preview().

Run from the repo root:
    python evaluation/prepare_dataset.py
"""
import csv
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

REPO_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = REPO_ROOT / "data" / "extracted" / "extracted_chunks.jsonl"
CSV_OUT_PATH = REPO_ROOT / "evaluation" / "eval_sample.csv"
XLSX_OUT_PATH = REPO_ROOT / "evaluation" / "eval_sample.xlsx"

TARGET_SIZE = 90
SEED = 42

COLUMNS = [
    "file_name", "chunk_id", "content_type", "source_location",
    "section_title", "text_preview",
    "Field", "Learning_type", "Level", "Competency",
]

# --- xlsx styling, matches the look the team reviews the sample in ---
HEADER_FILL = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
SUGGESTED_FILL = PatternFill(start_color="FFF7E0", end_color="FFF7E0", fill_type="solid")
SUGGESTED_COLS = {"Field", "Learning_type", "Level", "Competency"}
COLUMN_WIDTHS = {
    "file_name": 30, "chunk_id": 12, "content_type": 16, "source_location": 14,
    "section_title": 24, "text_preview": 60, "Field": 16, "Learning_type": 14,
    "Level": 13, "Competency": 24,
}

_COMMENT_PREFIXES = ("--", "/*", "*", "#", "```")


def clean(value) -> str:
    """Collapse any whitespace (including embedded newlines) into single spaces."""
    return " ".join(str(value).split())


def make_smart_preview(text: str, limit: int = 200) -> str:
    """Preview starting at the first real line of content, skipping any
    leading decoration: blank lines, comment markers (--, /*, *, #, ```),
    or short/symbol-heavy lines (ASCII banners, "====" separators)."""
    lines = text.split("\n")
    start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith(_COMMENT_PREFIXES):
            continue
        alpha = sum(c.isalpha() for c in s)
        if len(s) >= 8 and alpha / len(s) > 0.3:
            start = i
            break
    else:
        start = 0
    body = " ".join(l.strip() for l in lines[start:] if l.strip())
    return re.sub(r"\s+", " ", body).strip()[:limit]


def write_xlsx(rows: list[dict], path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "eval_sample"
    ws.sheet_view.rightToLeft = False  # force left-to-right regardless of Excel locale

    for j, col in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=j, value=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for i, r in enumerate(rows, start=2):
        for j, col in enumerate(COLUMNS, start=1):
            cell = ws.cell(row=i, column=j, value=r.get(col, ""))
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=(col == "text_preview"))
            if col in SUGGESTED_COLS:
                cell.fill = SUGGESTED_FILL

    for j, col in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(j)].width = COLUMN_WIDTHS.get(col, 16)

    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 22
    wb.save(path)


def main():
    chunks = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))

    by_file = defaultdict(list)
    for c in chunks:
        by_file[c["file_name"]].append(c)

    total = len(chunks)
    raw_quota = {name: max(1, TARGET_SIZE * len(items) / total) for name, items in by_file.items()}
    quota = {name: int(q) for name, q in raw_quota.items()}
    remainder = TARGET_SIZE - sum(quota.values())
    fractional = sorted(raw_quota.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True)
    i = 0
    while remainder > 0 and fractional:
        name = fractional[i % len(fractional)][0]
        if quota[name] < len(by_file[name]):
            quota[name] += 1
            remainder -= 1
        i += 1

    rng = random.Random(SEED)
    sample = []
    for name, items in by_file.items():
        n = min(quota[name], len(items))
        sample.extend(rng.sample(items, n))

    rows = []
    for c in sample:
        rows.append({
            "file_name": clean(c["file_name"]),
            "chunk_id": clean(c["chunk_id"]),
            "content_type": clean(c["content_type"]),
            "source_location": clean(c["metadata"].get("source_location", "")),
            "section_title": clean(c["metadata"].get("section_title", "")),
            "text_preview": make_smart_preview(c["text"]),
            "Field": "", "Learning_type": "", "Level": "", "Competency": "",
        })

    CSV_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    write_xlsx(rows, XLSX_OUT_PATH)

    print(f"Sample size: {len(sample)} / {total} total chunks")
    print("Per-file breakdown:")
    counts = defaultdict(int)
    for c in sample:
        counts[c["file_name"]] += 1
    for name, n in sorted(counts.items()):
        print(f"  {name}: {n}")
    print(f"\nWritten to: {CSV_OUT_PATH}")
    print(f"Written to: {XLSX_OUT_PATH}")


if __name__ == "__main__":
    main()