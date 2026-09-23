# Production Handoff — Content Tagging & Competency Mapping

This document is for whoever operates this system after Team 7 hands it off — most likely BeamData ops staff who have not seen this repo before. It explains how to run, switch, monitor, and troubleshoot the tagging models day to day. It assumes no prior context beyond basic kubectl familiarity.

## 1. System Overview

Five tagging models are available:

- **Model A** (Qwen2.5-VL-7B-Instruct) — self-hosted on Kubernetes, deployment `model-a-qwen`, service `model-a-qwen-svc`.
- **Model C** (Llama-3.2-11B-Vision-Instruct) — self-hosted on Kubernetes, deployment `model-c-llama`, service `model-c-llama-svc`.
- **Model D** (Qwen3.5-4B) — self-hosted on Kubernetes, deployment `model-d-qwen35`, service `model-d-qwen35-svc`. **This is the model the project runs in production** (see `reports/benchmark_report.md` for why it was selected).
- **Model E** (Qwen3.5-9B) — self-hosted on Kubernetes, deployment `model-e-qwen35-9b`, service `model-e-qwen35-9b-svc`. Benchmarked as a larger alternative to Model D; not used in production.
- **Model B** (gpt-4o) — called directly over the OpenAI API, no Kubernetes resources of our own.

All Kubernetes resources for this project live in namespace **`contentmap`**.

**Critical constraint: Models A, C, D, and E share a single physical GPU** (one NVIDIA RTX A6000, ~49 GB VRAM) and cannot run at full capacity at the same time on the current cluster. In normal operation, exactly one of the four self-hosted deployments should be scaled to `1/1` and the other three scaled to `0/0`. Model B needs no GPU and can run at the same time as any of them.

**Preferred way to switch models:** use the project's own `./switch_model.sh <key>` script from the repo root (for example `./switch_model.sh d` for Model D) instead of the raw `kubectl scale` steps below. The script wraps exactly those steps for whichever model key is registered in its `MODEL_REGISTRY`, and also keeps `app/interface/vite.config.js`'s proxy port in sync. Section 4 documents the manual steps the script performs, useful for troubleshooting when the script itself fails.

Current state, as of this document being last updated:

```
kubectl get deployments -n contentmap
NAME                READY   UP-TO-DATE   AVAILABLE   AGE
model-a-qwen        0/0     0            0           4d21h
model-c-llama       0/0     0            0           4d8h
model-d-qwen35      1/1     1            1           3d5h
model-e-qwen35-9b   0/0     0            0           2d6h
```

Model D is the active model on the GPU (production). Models A, C, and E are scaled down.

## 2. Prerequisites

- `kubectl` configured with access to the cluster and the `contentmap` namespace.
- The tagging code checked out (this repo), with the Python virtual environment set up (`venv`).
- The `MODEL_API_KEY` environment variable set in your shell when calling Model B. This is never stored in the repo or in Kubernetes — see Section 5.

## 3. Checking Current State

Before doing anything, always check what's actually running:

```
kubectl get deployments -n contentmap
kubectl get pods -n contentmap
kubectl get svc -n contentmap
```

`kubectl get pods` should show exactly one of the self-hosted models' pods (`model-a-qwen-...`, `model-c-llama-...`, `model-d-qwen35-...`, or `model-e-qwen35-9b-...`) in `Running` state with `1/1` ready, never more than one at once, and never zero (unless the system is intentionally fully down).

## 4. Switching the Active Model on the Shared GPU

This is the single most common operation. **Day to day, prefer `./switch_model.sh <key>` (see Section 1)** — it performs exactly the steps below for you. Use the manual steps here to understand what the script does, or when troubleshooting a failure. Follow every step in order if doing it manually — skipping the readiness check or the sanity check is the most common cause of failed requests (we hit this ourselves during benchmarking).

### Example: switching from Model A to Model C

```
# 1. Scale down the currently active model
kubectl scale deployment model-a-qwen -n contentmap --replicas=0

# 2. Scale up the target model
kubectl scale deployment model-c-llama -n contentmap --replicas=1

# 3. Wait until the pod is actually ready (do not skip this)
kubectl get pods -n contentmap -w
# wait for the model-c-llama-... pod to show 1/1 and STATUS Running, then Ctrl+C

# 4. Confirm the server itself has finished loading the model (readiness of the pod is not the same as the model being loaded)
kubectl logs -n contentmap deployment/model-c-llama --tail=50
# look for a line confirming the server is up and serving (vLLM prints something like "Uvicorn running on http://0.0.0.0:8000")

# 5. Port-forward the service to a local port
kubectl port-forward -n contentmap svc/model-c-llama-svc 8001:8000

# 6. In a separate terminal, sanity-check before running anything real
curl http://localhost:8001/v1/models
```

Only once step 6 returns a valid JSON model list — not a connection error — should you run any benchmark, tagging job, or send real traffic. The same six steps apply to switching to or from Model D (`model-d-qwen35` / `model-d-qwen35-svc`) or Model E (`model-e-qwen35-9b` / `model-e-qwen35-9b-svc`) — just substitute the deployment and service names.

### Model B (no switching needed)

Model B does not live on the cluster. It's called directly at `https://api.openai.com/v1` whenever it's needed, independent of whatever is running on the GPU. It only needs `MODEL_API_KEY` set in the calling shell.

## 5. Secrets

- **`hf-token`** — a Kubernetes Secret (type Opaque) in the `contentmap` namespace, holding the Hugging Face access token Model C needs to pull its gated model weights. If this ever needs to be rotated, create a new token on Hugging Face and update the secret with `kubectl create secret generic hf-token -n contentmap --from-literal=token=<new_token> --dry-run=client -o yaml | kubectl apply -f -`, then restart the `model-c-llama` deployment. **Models D and E do not require this token** — their checkpoints are not gated, so nothing extra needs to be configured for them.
- **`MODEL_API_KEY`** — the OpenAI API key for Model B. This is an environment variable set in the operator's shell (for example via `export MODEL_API_KEY="..."`), never committed to the repo, never stored in a Kubernetes Secret in this project, and never pasted into a chat, ticket, or screenshot. Whoever takes over operations needs their own valid key.

## 6. Monitoring

To watch GPU utilization, power draw, and memory while a model is under load, use the project's own monitor:

```
python evaluation/gpu_monitor.py --output /tmp/gpu_watch.csv --interval 1
```

This prints a live line per second and writes the same data to CSV. Useful for confirming a model is actually receiving traffic (utilization should rise from idle/0% when requests come in) and for catching GPU saturation early — this is exactly how we discovered that Model C's deployment saturates and stops scaling past concurrency 4 (see `reports/benchmark_report.md`, Section 6).

## 7. Known Failure Modes (all real incidents hit during this project)

**Pod doesn't exist / `kubectl get pods` shows nothing for a model.** Usually means it was previously scaled to `0` and never scaled back up. Fix: `kubectl scale deployment <name> -n contentmap --replicas=1`, then follow Section 4 from step 3.

**`port-forward` fails with "connection refused" or "lost connection to pod".** The pod is still loading the model into GPU memory; port-forwarding started before the server was actually ready. Fix: stop, check `kubectl logs` for the real ready line, and only then retry port-forward.

**`port-forward` fails with "Unable to listen on port XXXX: address already in use".** A stale port-forward process from an earlier session is still holding that local port. Fix:

```
ss -ltnp | grep <port>
# note the real PID in the output (the pid= value, not the Recv-Q/Send-Q numbers)
kill -9 <that PID>
```

**`tag_chunks.py` fails with `error: argument --api-key: expected one argument`.** `MODEL_API_KEY` is unset or empty in the current shell. Fix: `export MODEL_API_KEY="..."` in that shell before running (get the value from wherever the team stores it — never paste the actual key value into a chat tool or screenshot).

**A long run shows repeated `Connection refused` errors that suddenly clear up after a restart.** Almost always means the command was pointed at a local port with nothing listening behind it (for example, a stale or wrong `--base-url`/`--endpoint` value), not a real problem with the model itself. Fix: confirm the exact command being run, and confirm with `curl .../v1/models` on that same port before trusting the run.

## 8. Quick Reference

```
# Preferred: switch the active model with the project's own script
./switch_model.sh d      # scales up Model D, scales down the other three

# Manual equivalent (what the script does under the hood) --
# Check what's running
kubectl get deployments -n contentmap
kubectl get pods -n contentmap

# Switch active model (example: to Model A)
kubectl scale deployment model-d-qwen35 -n contentmap --replicas=0
kubectl scale deployment model-a-qwen -n contentmap --replicas=1
kubectl get pods -n contentmap -w
kubectl logs -n contentmap deployment/model-a-qwen --tail=50
kubectl port-forward -n contentmap svc/model-a-qwen-svc 8000:8000
curl http://localhost:8000/v1/models

# Monitor GPU
python evaluation/gpu_monitor.py --output /tmp/gpu_watch.csv --interval 1
```
