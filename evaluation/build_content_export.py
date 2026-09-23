"""
build_content_export.py — Joins the full extracted content chunks with a
model's real tagging output, and writes a grouped JSON file the React
interface can fetch directly (app/interface/public/data/content.json).

Only chunks that exist in BOTH files are included — that's the 85-chunk
evaluation set (the ones we actually tagged AND scored), so everything
the interface shows is content we have real, benchmarked model output for.
The team can widen this later by running tag_chunks.py (without --eval-only)
against the full extracted_chunks.jsonl.

Usage:
    python evaluation/build_content_export.py \
        --extracted data/extracted/extracted_chunks.jsonl \
        --tagged data/tagged/tagged_chunks_modelA.jsonl \
        --output app/interface/public/data/content.json
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extracted", required=True)
    ap.add_argument("--tagged", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    extracted = load_jsonl(args.extracted)
    tagged = load_jsonl(args.tagged)

    extracted_by_key = {(c["file_name"], c["chunk_id"]): c for c in extracted}

    fields = defaultdict(lambda: defaultdict(list))
    skipped_errors = 0
    skipped_missing_text = 0

    for row in tagged:
        if row.get("error"):
            skipped_errors += 1
            continue
        key = (row["file_name"], row["chunk_id"])
        src = extracted_by_key.get(key)
        if not src:
            skipped_missing_text += 1
            continue

        item = {
            "chunk_id": row["chunk_id"],
            "section_title": src.get("metadata", {}).get("section_title", ""),
            "source_location": src.get("metadata", {}).get("source_location", ""),
            "content_type": src.get("content_type", ""),
            "text": src.get("text", ""),
            "Learning_type": row.get("Learning_type"),
            "Level": row.get("Level"),
            "Competency": row.get("Competency"),
        }
        fields[row["Field"]][row["file_name"]].append(item)

    output = {"fields": []}
    for field_name, files in fields.items():
        file_list = []
        total_count = 0
        for file_name, items in files.items():
            items.sort(key=lambda i: i["chunk_id"])
            file_list.append({"file_name": file_name, "count": len(items), "items": items})
            total_count += len(items)
        file_list.sort(key=lambda f: f["file_name"])
        output["fields"].append({"field": field_name, "count": total_count, "files": file_list})

    output["fields"].sort(key=lambda f: -f["count"])

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_items = sum(f["count"] for f in output["fields"])
    print(f"Fields: {len(output['fields'])}")
    for f in output["fields"]:
        print(f"  {f['field']}: {f['count']} items across {len(f['files'])} files")
    print(f"Total items included: {total_items}")
    if skipped_errors:
        print(f"Skipped (tagging error): {skipped_errors}")
    if skipped_missing_text:
        print(f"Skipped (no matching extracted text): {skipped_missing_text}")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()