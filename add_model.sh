#!/usr/bin/env bash
# add_model.sh — discovers a model's real Kubernetes deployment/service
# names, port, and served model name, and writes (or updates) its line in
# switch_model.sh's MODEL_REGISTRY automatically, so you never hand-type
# a registry line again.
#
# Usage:
#   ./add_model.sh <key> <deployment-name-or-search-term> [gpu_group]
#
# Examples:
#   ./add_model.sh d model-d-qwen
#   ./add_model.sh d model-d-qwen shared-gpu-1
#
# What it does, step by step:
#   1. Finds the exact Deployment name in the cluster (exact match, or a
#      case-insensitive substring search if no exact match — e.g. passing
#      just "d" will match "model-d-qwen" if that's the only deployment
#      with "d" in its name).
#   2. Finds its matching Service ("<deployment>-svc" by convention, or
#      searches if that guess doesn't exist).
#   3. Reads the Service's port to use as remote_port.
#   4. Picks a free local_port automatically — one higher than the
#      largest local_port already used in switch_model.sh.
#   5. Tries to read the model's real served name from its running pod's
#      logs (the "served_model_name" line vLLM prints at startup). If the
#      pod isn't running yet (0 replicas), this is skipped and the
#      deployment name is used as a placeholder instead — edit it by hand
#      once you've seen the real name.
#   6. Reuses the existing gpu_group from switch_model.sh automatically if
#      there's only one so far (your cluster's single shared GPU) — pass
#      one explicitly as the 3rd argument to override.
#   7. Inserts (or updates, if the key already exists) the resulting line
#      directly inside switch_model.sh's MODEL_REGISTRY array.
#
# This script only EDITS switch_model.sh — it never scales anything or
# touches the cluster's running state. Run `git diff switch_model.sh`
# afterward to review exactly what it changed before committing.

set -uo pipefail

NAMESPACE="contentmap"
SCRIPT_FILE="switch_model.sh"

log()  { echo -e "\033[1;36m[add_model]\033[0m $*"; }
warn() { echo -e "\033[1;33m[add_model]\033[0m $*"; }
err()  { echo -e "\033[1;31m[add_model]\033[0m $*" >&2; }

KEY="${1:-}"
SEARCH="${2:-}"
GPU_GROUP_ARG="${3:-}"

if [[ -z "$KEY" || -z "$SEARCH" ]]; then
  echo "Usage: $0 <key> <deployment-name-or-search-term> [gpu_group]"
  exit 1
fi

if [[ ! -f "$SCRIPT_FILE" ]]; then
  err "$SCRIPT_FILE not found in the current directory — run this from the repo root."
  exit 1
fi

# --- 1. find the deployment ---
if kubectl get deployment "$SEARCH" -n "$NAMESPACE" >/dev/null 2>&1; then
  DEPLOY="$SEARCH"
else
  MATCHES=$(kubectl get deployments -n "$NAMESPACE" -o name 2>/dev/null | sed 's#deployment.apps/##' | grep -i "$SEARCH" || true)
  COUNT=$(printf '%s\n' "$MATCHES" | grep -c . || true)
  if [[ "$COUNT" -eq 1 ]]; then
    DEPLOY="$MATCHES"
  elif [[ "$COUNT" -eq 0 ]]; then
    err "No deployment matching '$SEARCH' found in namespace $NAMESPACE."
    err "Run: kubectl get deployments -n $NAMESPACE"
    exit 1
  else
    err "Multiple deployments match '$SEARCH':"
    echo "$MATCHES"
    err "Re-run with the exact deployment name."
    exit 1
  fi
fi
log "Deployment: $DEPLOY"

# --- 2. find the matching service ---
if kubectl get svc "${DEPLOY}-svc" -n "$NAMESPACE" >/dev/null 2>&1; then
  SVC="${DEPLOY}-svc"
else
  MATCHES=$(kubectl get svc -n "$NAMESPACE" -o name 2>/dev/null | sed 's#service/##' | grep -i "$DEPLOY" || true)
  COUNT=$(printf '%s\n' "$MATCHES" | grep -c . || true)
  if [[ "$COUNT" -eq 1 ]]; then
    SVC="$MATCHES"
  else
    err "Couldn't confidently find a matching Service for $DEPLOY."
    err "Existing services in $NAMESPACE:"
    kubectl get svc -n "$NAMESPACE"
    exit 1
  fi
fi
log "Service: $SVC"

# --- 3. read the service's port ---
REMOTE_PORT=$(kubectl get svc "$SVC" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || true)
if [[ -z "$REMOTE_PORT" ]]; then
  err "Couldn't read a port from service $SVC."
  exit 1
fi
log "Remote port: $REMOTE_PORT"

# --- 4. pick a free local port (highest already-used local_port + 1) ---
USED_PORTS=$(grep -oP '^\s*"[^|]*\|[^|]*\|[^|]*\|\K[0-9]+' "$SCRIPT_FILE" 2>/dev/null || true)
if [[ -z "$USED_PORTS" ]]; then
  LOCAL_PORT=8000
else
  LOCAL_PORT=$(( $(printf '%s\n' "$USED_PORTS" | sort -n | tail -1) + 1 ))
fi
log "Local port: $LOCAL_PORT (auto-picked)"

# --- 5. try to read the real served model name from the pod's logs ---
DISPLAY_NAME=$(kubectl logs -n "$NAMESPACE" "deployment/$DEPLOY" --tail=500 2>/dev/null \
  | grep -oP "'served_model_name': \['\K[^']+" | head -1 || true)
if [[ -z "$DISPLAY_NAME" ]]; then
  warn "Couldn't read the served model name from logs (pod may not be running yet)."
  warn "Using '$DEPLOY' as a placeholder — edit the display_name by hand once you know it."
  DISPLAY_NAME="$DEPLOY"
else
  log "Served model name (from logs): $DISPLAY_NAME"
fi

# --- 6. figure out the gpu_group ---
if [[ -n "$GPU_GROUP_ARG" ]]; then
  GPU_GROUP="$GPU_GROUP_ARG"
else
  EXISTING_GROUPS=$(grep -oP '^\s*"[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\K[^|]+' "$SCRIPT_FILE" 2>/dev/null | sort -u || true)
  GROUP_COUNT=$(printf '%s\n' "$EXISTING_GROUPS" | grep -c . || true)
  if [[ "$GROUP_COUNT" -eq 1 ]]; then
    GPU_GROUP="$EXISTING_GROUPS"
    log "Reusing existing gpu_group: $GPU_GROUP"
  else
    err "Found $GROUP_COUNT existing gpu_group(s) ($EXISTING_GROUPS) — pass one explicitly as the 3rd argument."
    exit 1
  fi
fi

# --- 7. build the line and insert (or update) it in switch_model.sh ---
NEW_LINE="  \"$KEY|$DEPLOY|$SVC|$LOCAL_PORT|$REMOTE_PORT|$GPU_GROUP|gpu|$DISPLAY_NAME|\""

if grep -qE "^[[:space:]]*\"$KEY\|" "$SCRIPT_FILE"; then
  log "Key '$KEY' already exists in the registry — replacing its line."
  awk -v key="\"$KEY|" -v newline="$NEW_LINE" '
  {
    trimmed = $0
    sub(/^[ \t]+/, "", trimmed)
    if (index(trimmed, key) == 1) { print newline } else { print }
  }' "$SCRIPT_FILE" > "${SCRIPT_FILE}.tmp" && mv "${SCRIPT_FILE}.tmp" "$SCRIPT_FILE"
else
  log "Adding new key '$KEY' to the registry."
  awk -v newline="$NEW_LINE" '
  /^MODEL_REGISTRY=\(/ { inreg=1 }
  inreg && /^\)/ { print newline; inreg=0 }
  { print }
  ' "$SCRIPT_FILE" > "${SCRIPT_FILE}.tmp" && mv "${SCRIPT_FILE}.tmp" "$SCRIPT_FILE"
fi

chmod +x "$SCRIPT_FILE"

echo
log "Written to $SCRIPT_FILE:"
echo "$NEW_LINE"
echo
log "Review the change: git diff $SCRIPT_FILE"
log "Then run:           ./switch_model.sh $KEY"