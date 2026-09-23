#!/usr/bin/env bash
set -euo pipefail

ASSIGNEE_DATA="afbinmabrouk-stack"
ASSIGNEE_MODEL="ghalaalnasser-g"
ASSIGNEE_INFRA="HatunMQ"

gh auth status || { echo "Run 'gh auth login' first."; exit 1; }

echo "Creating labels..."
create_label () {
  local name="$1" color="$2"
  if gh api repos/:owner/:repo/labels -f name="$name" -f color="$color" >/dev/null 2>&1; then
    echo "  + label: $name"
  else
    echo "  (label '$name' already exists — skipping)"
  fi
}
create_label "step1-data" "c2e0c6"
create_label "step2-eval" "bfd4f2"
create_label "step3-models" "f9d0c4"
create_label "step4-experiments" "fde68a"
create_label "step5-benchmark" "fbcaca"
create_label "step6-deploy" "d8b4fe"

echo "Creating milestones..."
create_milestone () {
  gh api repos/:owner/:repo/milestones -f title="$1" >/dev/null 2>&1 || true
}
create_milestone "Step 1 - Understand the data"
create_milestone "Step 2 - Evaluation dataset"
create_milestone "Step 3 - Model selection"
create_milestone "Step 4 - Run experiments"
create_milestone "Step 5 - Benchmark"
create_milestone "Step 6 - Deploy final model"

mk_issue () {
  local title="$1" body="$2" label="$3" milestone="$4" assignee="$5"
  local args=(issue create --title "$title" --body "$body" --label "$label" --milestone "$milestone")
  [[ -n "$assignee" ]] && args+=(--assignee "$assignee")
  gh "${args[@]}"
  echo "  + $title"
}

echo "Creating issues..."
mk_issue "Inventory all files and classify by type (pptx/ipynb/md/xlsx)" "" "step1-data" "Step 1 - Understand the data" "$ASSIGNEE_DATA"
mk_issue "Identify languages present in the content (Arabic/English)" "" "step1-data" "Step 1 - Understand the data" "$ASSIGNEE_DATA"
mk_issue "Confirm no video/standalone images exist yet" "" "step1-data" "Step 1 - Understand the data" "$ASSIGNEE_DATA"
mk_issue "Run extractors on all files -> extracted_chunks.jsonl" "" "step2-eval" "Step 2 - Evaluation dataset" "$ASSIGNEE_DATA"
mk_issue "Select evaluation sample (<=100 chunks) covering all types/levels" "" "step2-eval" "Step 2 - Evaluation dataset" "$ASSIGNEE_DATA"
mk_issue "Human labeling of the sample + calibration meeting" "" "step2-eval" "Step 2 - Evaluation dataset" ""
mk_issue "Prepare Model A - Qwen2.5-VL-7B (open-weight, deployed)" "" "step3-models" "Step 3 - Model selection" "$ASSIGNEE_INFRA"
mk_issue "Prepare Model B - GPT (commercial API)" "" "step3-models" "Step 3 - Model selection" "$ASSIGNEE_MODEL"
mk_issue "Prepare Model C - Llama Vision (second open-weight)" "" "step3-models" "Step 3 - Model selection" "$ASSIGNEE_MODEL"
mk_issue "Write the unified prompt and output JSON schema" "" "step4-experiments" "Step 4 - Run experiments" "$ASSIGNEE_MODEL"
mk_issue "Script to run the same input on all three models" "" "step4-experiments" "Step 4 - Run experiments" "$ASSIGNEE_MODEL"
mk_issue "Quality scoring script (Correctness/Completeness/Relevance/Hallucination/Structured output)" "" "step5-benchmark" "Step 5 - Benchmark" "$ASSIGNEE_DATA"
mk_issue "Infrastructure scoring script (VRAM/Latency/Tokens/Cost)" "" "step5-benchmark" "Step 5 - Benchmark" "$ASSIGNEE_INFRA"
mk_issue "Final comparison report" "" "step5-benchmark" "Step 5 - Benchmark" ""
mk_issue "Dockerfile for the selected model" "" "step6-deploy" "Step 6 - Deploy final model" "$ASSIGNEE_INFRA"
mk_issue "Kubernetes deployment + service" "" "step6-deploy" "Step 6 - Deploy final model" "$ASSIGNEE_INFRA"
mk_issue "API endpoint - test and document" "" "step6-deploy" "Step 6 - Deploy final model" "$ASSIGNEE_INFRA"
mk_issue "AI Hub integration + evidence" "" "step6-deploy" "Step 6 - Deploy final model" "$ASSIGNEE_INFRA"
mk_issue "Lightweight testing UI (Deliverable 6)" "" "step6-deploy" "Step 6 - Deploy final model" ""

echo ""
echo "Done. Open the Issues tab in GitHub to see the full checklist."
