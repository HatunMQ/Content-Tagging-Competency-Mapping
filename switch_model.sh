#!/usr/bin/env bash
# switch_model.sh - swap the active model on the shared GPU, or check an
# API model. One command instead of the manual scale/wait/port-forward/curl
# steps every time.
#
# Usage (from repo root, venv active):
#   ./switch_model.sh a          start Model A, stops other GPU models in its group
#   ./switch_model.sh c          start Model C
#   ./switch_model.sh b          check Model B (API, no GPU)
#   ./switch_model.sh status     current state + active port-forwards
#   ./switch_model.sh stop       stop all forwards, scale GPU models to 0
#   ./switch_model.sh sync-data  copy result JSON files into the interface
#
# To add a model, add one line to MODEL_REGISTRY below.

set -uo pipefail

NAMESPACE="contentmap"
PIDDIR=".model_pids"
mkdir -p "$PIDDIR"

# key | deploy | svc | local_port | remote_port | gpu_group | type | display_name | api_key_env
# type is "gpu" (self-hosted) or "api" (external, leave deploy/svc/ports/gpu_group blank)
# models sharing a gpu_group are mutually exclusive - starting one scales the others to 0
MODEL_REGISTRY=(
  "a|model-a-qwen|model-a-qwen-svc|8000|8000|shared-gpu-1|gpu|Qwen2.5-VL-7B-Instruct|"
  "c|model-c-llama|model-c-llama-svc|8001|8000|shared-gpu-1|gpu|Llama-3.2-11B-Vision-Instruct|"
  "b||||||api|gpt-4o|MODEL_API_KEY"
  "d|model-d-qwen35|model-d-qwen35-svc|8002|8000|shared-gpu-1|gpu|Qwen3.5-4B|"
  "e|model-e-qwen35-9b|model-e-qwen35-9b-svc|8003|8000|shared-gpu-1|gpu|Qwen3.5-9B|"
)

READY_TIMEOUT=300   # seconds to wait for a model to finish loading
CURL_TIMEOUT=120    # seconds to wait for /v1/models to respond

log()  { echo -e "\033[1;36m[switch_model]\033[0m $*"; }
warn() { echo -e "\033[1;33m[switch_model]\033[0m $*"; }
err()  { echo -e "\033[1;31m[switch_model]\033[0m $*" >&2; }

# looks up a registry entry, sets M_KEY M_DEPLOY M_SVC M_LOCAL_PORT M_REMOTE_PORT
# M_GPU_GROUP M_TYPE M_NAME M_APIKEY_ENV
find_model() {
  local key=$1
  local entry
  for entry in "${MODEL_REGISTRY[@]}"; do
    IFS='|' read -r M_KEY M_DEPLOY M_SVC M_LOCAL_PORT M_REMOTE_PORT M_GPU_GROUP M_TYPE M_NAME M_APIKEY_ENV <<< "$entry"
    if [[ "$M_KEY" == "$key" ]]; then
      return 0
    fi
  done
  return 1
}

# clears a stale port-forward that died without cleaning up (address already in use)
free_local_port() {
  local port=$1
  local pid
  pid=$(ss -ltnp 2>/dev/null | grep ":$port " | grep -oP '(?<=pid=)\d+' | head -1 || true)
  if [[ -n "${pid:-}" ]]; then
    warn "stale process on port $port (pid=$pid), killing it"
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
  fi
}

scale() {
  local deploy=$1 replicas=$2
  log "kubectl scale deployment $deploy --replicas=$replicas"
  kubectl scale deployment "$deploy" -n "$NAMESPACE" --replicas="$replicas"
}

stop_forward() {
  local tag=$1
  if [[ -f "$PIDDIR/${tag}.pid" ]]; then
    local pid
    pid=$(cat "$PIDDIR/${tag}.pid")
    kill "$pid" 2>/dev/null || true
    rm -f "$PIDDIR/${tag}.pid"
    log "stopped port-forward for $tag (pid=$pid)"
  fi
}

# if a pod is already up and has been Ready a while, skip the log wait - an
# old pod's startup line can scroll past --tail once it's served enough
# traffic, which used to cause a false timeout on a model that was fine
wait_for_model_ready() {
  local deploy=$1
  local waited=0

  local pod_name
  pod_name=$(kubectl get pods -n "$NAMESPACE" -o name 2>/dev/null | sed 's#pod/##' | grep "^${deploy}-" | head -1 || true)
  if [[ -n "$pod_name" ]]; then
    local ready_status ready_time ready_epoch now_epoch age_s
    ready_status=$(kubectl get pod "$pod_name" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null || true)
    ready_time=$(kubectl get pod "$pod_name" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].lastTransitionTime}' 2>/dev/null || true)
    if [[ "$ready_status" == "true" && -n "$ready_time" ]]; then
      ready_epoch=$(date -d "$ready_time" +%s 2>/dev/null || echo 0)
      now_epoch=$(date +%s)
      age_s=$(( now_epoch - ready_epoch ))
      if (( age_s > 90 )); then
        log "$deploy already has a pod Ready for ${age_s}s ($pod_name), skipping log-wait"
        return 0
      fi
    fi
  fi

  log "waiting for $deploy to finish loading into GPU memory (roughly 1-3 min)"
  while (( waited < READY_TIMEOUT )); do
    if kubectl logs -n "$NAMESPACE" "deployment/$deploy" --tail=3000 2>/dev/null | grep -q "Application startup complete"; then
      echo
      log "$deploy is ready and listening"
      return 0
    fi
    sleep 5
    waited=$((waited + 5))
    echo -n "."
  done
  echo
  err "timed out after ${READY_TIMEOUT}s waiting for the ready line, check manually:"
  err "  kubectl logs -n $NAMESPACE deployment/$deploy --tail=80"
  return 1
}

start_forward() {
  local svc=$1 local_port=$2 remote_port=$3 tag=$4
  free_local_port "$local_port"
  log "starting port-forward: localhost:$local_port -> $svc:$remote_port"
  nohup kubectl port-forward -n "$NAMESPACE" "svc/$svc" "$local_port:$remote_port" \
      > "$PIDDIR/${tag}_portforward.log" 2>&1 &
  echo $! > "$PIDDIR/${tag}.pid"
  sleep 2

  local waited=0
  while (( waited < CURL_TIMEOUT )); do
    if curl -sf "http://localhost:$local_port/v1/models" > /dev/null 2>&1; then
      log "confirmed: http://localhost:$local_port/v1/models is responding"
      return 0
    fi
    sleep 3
    waited=$((waited + 3))
  done
  err "port-forward is up but /v1/models still isn't responding, check: cat $PIDDIR/${tag}_portforward.log"
  return 1
}

# scales every other gpu-type model in the same gpu_group to 0
free_gpu_group() {
  local group=$1 except_key=$2
  local entry
  for entry in "${MODEL_REGISTRY[@]}"; do
    IFS='|' read -r k deploy svc lp rp grp type name apikey <<< "$entry"
    if [[ "$type" == "gpu" && "$grp" == "$group" && "$k" != "$except_key" ]]; then
      scale "$deploy" 0
      stop_forward "model_$k"
    fi
  done
}

run_gpu_model() {
  local key=$1
  find_model "$key" || { err "unknown model key: $key"; return 1; }
  log "starting model ${key^^} ($M_NAME)"
  free_gpu_group "$M_GPU_GROUP" "$key"
  scale "$M_DEPLOY" 1
  wait_for_model_ready "$M_DEPLOY" || return 1
  start_forward "$M_SVC" "$M_LOCAL_PORT" "$M_REMOTE_PORT" "model_$key" || return 1
  log "model ${key^^} ready at http://localhost:$M_LOCAL_PORT/v1"
}

run_api_model() {
  local key=$1
  find_model "$key" || { err "unknown model key: $key"; return 1; }
  log "checking model ${key^^} ($M_NAME), API-based, no GPU"
  local apikey_value="${!M_APIKEY_ENV:-}"
  if [[ -z "$apikey_value" ]]; then
    err "$M_APIKEY_ENV is not set, run: export $M_APIKEY_ENV=\"...\" first"
    return 1
  fi
  if curl -sf https://api.openai.com/v1/models -H "Authorization: Bearer $apikey_value" > /dev/null; then
    log "model ${key^^} is reachable"
  else
    err "could not reach the OpenAI API, check that $M_APIKEY_ENV is valid"
    return 1
  fi
}

show_status() {
  log "deployments:"
  kubectl get deployments -n "$NAMESPACE"
  echo
  log "pods:"
  kubectl get pods -n "$NAMESPACE"
  echo
  log "port-forwards started by this script:"
  local any=0
  for f in "$PIDDIR"/*.pid; do
    [[ -e "$f" ]] || continue
    any=1
    tag=$(basename "$f" .pid)
    pid=$(cat "$f")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  $tag -> pid $pid (running)"
    else
      echo "  $tag -> pid $pid (dead, cleaning up)"
      rm -f "$f"
    fi
  done
  [[ $any -eq 0 ]] && echo "  (none running)"
}

cmd_stop() {
  log "stopping every port-forward and scaling every GPU model to 0"
  local entry
  for entry in "${MODEL_REGISTRY[@]}"; do
    IFS='|' read -r k deploy svc lp rp grp type name apikey <<< "$entry"
    if [[ "$type" == "gpu" ]]; then
      stop_forward "model_$k"
      scale "$deploy" 0
    fi
  done
  log "done, GPU is free"
}

# copies every model's result files from evaluation/ into the interface's
# data folder in one shot
sync_data() {
  local eval_dir="evaluation"
  local dest_dir="app/interface/public/data"
  if [[ ! -d "$eval_dir" ]]; then
    err "can't find $eval_dir, run this from the repo root"
    return 1
  fi
  if [[ ! -d "$dest_dir" ]]; then
    err "can't find $dest_dir, is app/interface set up here?"
    return 1
  fi
  local copied=0 f
  for f in "$eval_dir"/accuracy_summary_model*.json "$eval_dir"/metrics_summary_model*.json; do
    [[ -e "$f" ]] || continue
    cp "$f" "$dest_dir/"
    log "synced: $(basename "$f")"
    copied=$((copied + 1))
  done
  if (( copied == 0 )); then
    warn "no accuracy_summary_model*.json or metrics_summary_model*.json files found in $eval_dir"
  else
    log "done, $copied file(s) synced to $dest_dir"
  fi
}

list_keys() {
  local e
  for e in "${MODEL_REGISTRY[@]}"; do
    echo "$e" | cut -d'|' -f1
  done | tr '\n' ' '
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    status) show_status ;;
    stop) cmd_stop ;;
    sync-data) sync_data ;;
    "")
      echo "usage: $0 <model-key>|status|stop|sync-data"
      echo "known model keys: $(list_keys)"
      exit 1
      ;;
    *)
      if find_model "$cmd"; then
        if [[ "$M_TYPE" == "gpu" ]]; then
          run_gpu_model "$cmd"
        else
          run_api_model "$cmd"
        fi
      else
        err "unknown model key: $cmd"
        echo "known model keys: $(list_keys)"
        exit 1
      fi
      ;;
  esac
}

main "$@"
