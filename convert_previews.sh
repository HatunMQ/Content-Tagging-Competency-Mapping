#!/usr/bin/env bash
set -e

# convert_previews.sh -- converts every non-quiz file in data/raw/ into a
# real PDF for the interface's file preview panel (the "Preview not
# connected yet" placeholder in FieldFileCard.jsx). Quiz .xlsx files are
# skipped entirely -- they get the real interactive quiz instead of a PDF.
# README_STUDENTS.md is skipped too (same exclusion run_extract.py already
# applies -- it's not learning content).
#
# Output: app/interface/public/raw_pdf/<same file name>.pdf, plus a real
# manifest at app/interface/public/data/pdf_previews.json listing exactly
# which files converted successfully. A file that fails to convert is left
# OUT of the manifest (never faked in), so the interface falls back to its
# honest "not connected yet" message for that one file only.
#
# Usage: ./convert_previews.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"
source venv/bin/activate

RAW_DIR="data/raw"
OUT_DIR="app/interface/public/raw_pdf"
MANIFEST="app/interface/public/data/pdf_previews.json"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$OUT_DIR"

EXCLUDE_FILES=("README_STUDENTS.md")

converted=()
failed=()

is_excluded() {
  local name="$1"
  for ex in "${EXCLUDE_FILES[@]}"; do
    [ "$name" = "$ex" ] && return 0
  done
  return 1
}

for f in "$RAW_DIR"/*.pptx; do
  [ -e "$f" ] || continue
  name=$(basename "$f")
  is_excluded "$name" && continue
  echo "[pptx] $name"
  if soffice --headless --convert-to pdf --outdir "$OUT_DIR" "$f" > /dev/null 2>&1; then
    converted+=("$name")
  else
    echo "  FAILED"
    failed+=("$name")
  fi
done

for f in "$RAW_DIR"/*.md; do
  [ -e "$f" ] || continue
  name=$(basename "$f")
  is_excluded "$name" && continue
  base="${name%.*}"
  echo "[md] $name"
  if pandoc "$f" -o "$OUT_DIR/$base.pdf" --pdf-engine=wkhtmltopdf > /dev/null 2>&1; then
    converted+=("$name")
  else
    echo "  FAILED"
    failed+=("$name")
  fi
done

for f in "$RAW_DIR"/*.ipynb; do
  [ -e "$f" ] || continue
  name=$(basename "$f")
  is_excluded "$name" && continue
  base="${name%.*}"
  echo "[ipynb] $name"
  if jupyter nbconvert --to html --output-dir "$TMP_DIR" "$f" > /dev/null 2>&1 \
     && wkhtmltopdf --quiet "$TMP_DIR/$base.html" "$OUT_DIR/$base.pdf" > /dev/null 2>&1; then
    converted+=("$name")
  else
    echo "  FAILED"
    failed+=("$name")
  fi
done

python3 - "$MANIFEST" "${converted[@]}" << 'PYEOF'
import json, sys
manifest_path = sys.argv[1]
files = sys.argv[2:]
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump({"files": files}, f, ensure_ascii=False, indent=2)
PYEOF

echo ""
echo "Converted: ${#converted[@]}"
echo "Failed: ${#failed[@]}"
if [ "${#failed[@]}" -gt 0 ]; then
  printf '  - %s\n' "${failed[@]}"
fi
echo "Manifest written to $MANIFEST"
