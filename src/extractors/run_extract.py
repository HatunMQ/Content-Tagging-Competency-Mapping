"""
Walk data/raw/, dispatch each file to the right extractor, and write every
chunk to data/extracted/extracted_chunks.jsonl — the single unified input
every model (A/B/C) will read from during benchmarking.

Low-content/decorative chunks (ASCII art banners, separator lines —
e.g. the "/\\_/\\ Hands-On" banner in HandsOn1_Window_Functions.md) are
filtered out here, in ONE place, so the same rule applies to every
extractor's output the same way — see chunk_filters.py. They're not
silently dropped: they're written to data/extracted/excluded_chunks.jsonl
so the team can spot-check that nothing real got filtered by mistake.

Run from the repo root:
    python src/extractors/run_extract.py

Files that aren't learning content (README_STUDENTS.md — project
requirements, not something to tag) are skipped on purpose.
"""
import json
from pathlib import Path

from pptx_extractor import extract_pptx
from ipynb_extractor import extract_ipynb
from md_extractor import extract_md
from xlsx_extractor import extract_xlsx
from chunk_filters import is_low_content_chunk

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
OUT_PATH = REPO_ROOT / "data" / "extracted" / "extracted_chunks.jsonl"
EXCLUDED_PATH = REPO_ROOT / "data" / "extracted" / "excluded_chunks.jsonl"

DISPATCH = {
    ".pptx": extract_pptx,
    ".ipynb": extract_ipynb,
    ".md": extract_md,
    ".xlsx": extract_xlsx,
}

EXCLUDE_FILENAMES = {"README_STUDENTS.md"}


def main():
    if not RAW_DIR.exists():
        raise SystemExit(f"Raw folder not found: {RAW_DIR}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_chunks = []
    all_excluded = []
    skipped = []

    for file_path in sorted(RAW_DIR.iterdir()):
        if file_path.is_dir():
            continue
        if file_path.name in EXCLUDE_FILENAMES:
            print(f"[skip] {file_path.name} (excluded — not learning content)")
            continue

        ext = file_path.suffix.lower()
        extractor = DISPATCH.get(ext)
        if not extractor:
            skipped.append(file_path.name)
            continue

        try:
            chunks = extractor(file_path)
            kept, excluded = [], []
            for c in chunks:
                if is_low_content_chunk(c.get("text", "")):
                    excluded.append(c)
                else:
                    kept.append(c)
            all_chunks.extend(kept)
            all_excluded.extend(excluded)
            msg = f"[ok]   {file_path.name}: {len(kept)} chunk(s)"
            if excluded:
                msg += f" ({len(excluded)} filtered as low-content)"
            print(msg)
        except Exception as e:
            print(f"[FAIL] {file_path.name}: {e}")

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    with EXCLUDED_PATH.open("w", encoding="utf-8") as f:
        for chunk in all_excluded:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"\nTotal chunks written: {len(all_chunks)} -> {OUT_PATH}")
    print(f"Total excluded (low-content, review only): {len(all_excluded)} -> {EXCLUDED_PATH}")
    if skipped:
        print(f"Skipped (no extractor for this file type): {skipped}")


if __name__ == "__main__":
    main()