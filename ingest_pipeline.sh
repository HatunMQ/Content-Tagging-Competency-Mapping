#!/usr/bin/env bash
set -e

# ingest_pipeline.sh -- one-command content ingestion pipeline.
#
# Run this any time a file is added to or changed in data/raw/ (a lecture,
# notebook, quiz -- anything supported by src/extractors/). It:
#   1. Re-extracts every file in data/raw/ (run_extract.py)
#   2. Re-tags every extracted chunk with the AI model (tag_chunks.py, full
#      run -- NOT --eval-only, so this covers everything, not just the
#      90-chunk evaluation sample)
#   3. Rebuilds app/interface/public/data/content.json from the extracted +
#      tagged output (build_content_export.py)
#
# Usage:
#   ./ingest_pipeline.sh [model_key]
#
# model_key defaults to "d". It must be a key switch_model.sh already
# knows about, AND have its port/served-name mirrored in MODEL_ENDPOINTS
# below -- same reason vite.config.js keeps its own copy of Model D's
# port: this script talks to the model directly over its port-forward,
# not through switch_model.sh, so it needs its own copy of that mapping.
# Keep both in sync whenever add_model.sh registers a new model or a
# port changes.
MODEL_KEY="${1:-d}"

declare -A MODEL_ENDPOINTS=(
  [d]="8002:Qwen3.5-4B"
)

ENTRY="${MODEL_ENDPOINTS[$MODEL_KEY]:-}"
if [ -z "$ENTRY" ]; then
  echo "No endpoint mapping for model '$MODEL_KEY' in MODEL_ENDPOINTS -- add it to ingest_pipeline.sh first."
  exit 1
fi
LOCAL_PORT="${ENTRY%%:*}"
SERVED_NAME="${ENTRY##*:}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "=== Step 0: make sure model '$MODEL_KEY' is the active one on the GPU ==="
./switch_model.sh "$MODEL_KEY"

echo "Using model '$SERVED_NAME' at http://localhost:${LOCAL_PORT}/v1"

source venv/bin/activate

echo "=== Step 1: extract every file in data/raw/ ==="
(cd src/extractors && python3 run_extract.py)

echo "=== Step 2: tag every extracted chunk (full run, not --eval-only) ==="
TAGGED_OUT="data/tagged/tagged_chunks_${MODEL_KEY}_full.jsonl"
python3 src/tagging/tag_chunks.py \
  --endpoint "http://localhost:${LOCAL_PORT}/v1" \
  --model "$SERVED_NAME" \
  --input data/extracted/extracted_chunks.jsonl \
  --output "$TAGGED_OUT"

echo "=== Step 3: rebuild content.json for the interface ==="
python3 evaluation/build_content_export.py \
  --extracted data/extracted/extracted_chunks.jsonl \
  --tagged "$TAGGED_OUT" \
  --output app/interface/public/data/content.json

echo "=== Step 4: convert non-quiz files to PDF for the preview panel ==="
"$REPO_ROOT/convert_previews.sh"

echo ""
echo "=== Done. content.json rebuilt and PDF previews refreshed from the full dataset. ==="
