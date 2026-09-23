# Content Tagging & Competency Mapping

AI Data Center Bootcamp (SDA) — Team 7 Capstone
*Powered by WeCloudData Academy, in collaboration with BeamData*

A real content-tagging and competency-mapping pipeline for BeamData's learning platform. Course content (slides, notebooks, markdown lectures, quiz spreadsheets) is automatically extracted, tagged against a fixed taxonomy (Field, Learning_type, Level, Competency) by a self-hosted LLM, and served through a React learning-platform frontend with interactive scored quizzes, real PDF previews, a competency-gap progress dashboard, and on-demand Arabic translation. Choosing which model does the tagging was the core technical decision of the project and is fully benchmarked in `reports/benchmark_report.md` — see "Benchmark & Model Selection" below.

## Project Structure

```
.
├── add_model.sh                    # register a new model into switch_model.sh's shared registry
├── switch_model.sh                 # switch the active self-hosted model on the shared GPU
├── ingest_pipeline.sh              # one-command pipeline: switch model → extract → tag → export → convert previews
├── convert_previews.sh             # convert raw lesson files to PDF for the in-app preview panel
├── setup_github_tasks.sh
├── PRODUCTION_HANDOFF.md           # day-to-day ops runbook: model switching, secrets, monitoring, known failure modes
├── prompts/
│   └── extraction_prompt.txt       # the single tagging prompt, used identically by all five benchmarked models
├── src/
│   ├── extractors/                 # per-file-type content extractors (pptx, ipynb, md, xlsx) + run_extract.py orchestrator
│   └── tagging/
│       └── tag_chunks.py           # LLM-based tagging against the fixed taxonomy
├── evaluation/                     # benchmark scripts and raw results for all 5 candidate models (A-E)
│   ├── benchmark_load.py           # concurrency / latency / throughput load test
│   ├── gpu_monitor.py              # nvidia-smi power and utilization sampling
│   ├── estimate_cost.py            # electricity cost per request, from GPU power draw + measured throughput
│   ├── compare_results.py          # scores model predictions against human ground truth
│   ├── analyze_results.py          # pulls qualitative correct/incorrect examples
│   ├── eval_sample.csv             # 85-row human-labeled ground truth
│   └── metrics_summary_model*.json, accuracy_summary_model*.json, results_model*.csv, gpu_load_monitor_model*.csv
├── reports/
│   └── benchmark_report.md         # full benchmark write-up: accuracy, latency, cost, model selection
├── finetune/                       # optional LoRA fine-tuning experiment (Qwen3.5-4B) — see finetune/README.md to reproduce
├── k8s/                            # Kubernetes Deployment manifests for models A, C, D, E
├── docker/
│   └── Dockerfile
├── data/
│   ├── raw/                        # source lesson files (pptx, ipynb, md, xlsx quizzes)
│   ├── extracted/                  # extracted_chunks.jsonl / excluded_chunks.jsonl, from run_extract.py
│   └── tagged/                     # tagged_chunks_*.jsonl, one set per model
└── app/interface/                  # the React + Vite learning-platform frontend
    ├── src/
    ├── public/data/                # content.json, quizzes.json, pdf_previews.json — real generated data only
    └── public/raw_pdf/             # converted lesson PDFs, from convert_previews.sh
```

## Requirements

- Python 3.10+ with a virtual environment (`venv`)
- Node.js LTS, for `app/interface`
- `kubectl` access to the shared-GPU cluster, namespace `contentmap` (see `PRODUCTION_HANDOFF.md`)
- `tmux`, since the frontend dev server runs inside a dedicated session
- LibreOffice, pandoc, wkhtmltopdf, and nbconvert — only needed to regenerate lesson PDFs via `convert_previews.sh`

## Getting Started

### 1. Activate the environment

```bash
cd ~/aidc/Content-Tagging-Competency-Mapping
source venv/bin/activate
```

### 2. Run the full content pipeline

One command re-extracts, re-tags, rebuilds `content.json`, and regenerates PDF previews for every file under `data/raw`:

```bash
./ingest_pipeline.sh d
```

`d` selects Model D on the shared GPU — the model this project runs in production (see Benchmark & Model Selection below). Swap in another key registered in `switch_model.sh`'s `MODEL_REGISTRY` to tag with a different model.

Internally this runs, in order: `switch_model.sh` (scales the chosen model up on the shared GPU) → `run_extract.py` (walks `data/raw`, writes `data/extracted/extracted_chunks.jsonl`) → `tag_chunks.py` (tags every chunk against the fixed taxonomy) → `build_content_export.py` (joins extracted + tagged data into `app/interface/public/data/content.json`) → `convert_previews.sh` (renders lesson files to PDF for the in-app preview panel).

### 3. Run the frontend

The dev server runs inside a dedicated tmux session so it survives disconnects:

```bash
tmux attach -t frontend    # or: tmux new -s frontend
cd app/interface
npm install
npm run dev
```

Detach with `Ctrl+B` then `D` to leave it running in the background.

`app/interface/vite.config.js` proxies model API calls to whichever local port `switch_model.sh`'s `MODEL_REGISTRY` currently assigns to the active model — keep the two in sync whenever the active model changes.

## What the App Does

- **Content library** — browse tagged course material by Field, Learning_type, Level, and Competency, with a real PDF preview for every non-quiz file. A file only shows a preview once it has actually been converted by `convert_previews.sh`; it never shows a placeholder pretending to be a real preview.
- **Interactive quizzes** — real questions sourced 1:1 from the team's quiz spreadsheets, scored attempts, a per-question timer, and a camera-gate plus tab-lock anti-cheat check enforced during the quiz.
- **Progress dashboard** — competency-gap percentages and quiz results computed entirely from a learner's real recorded activity and quiz attempts. Any feature not yet backed by real data (such as the Personalized Learning Plan section) is shown honestly as a "coming soon" placeholder, never with fabricated numbers.
- **Arabic translation** — on-demand translation of lesson content to Arabic through the self-hosted model, chunked so long files translate completely without truncation.

## Benchmark & Model Selection

Five candidate models were benchmarked against an identical 85-row human-labeled ground-truth set (`evaluation/eval_sample.csv`), using the same tagging prompt (`prompts/extraction_prompt.txt`) and decoding settings for all five. Full methodology, per-field accuracy, qualitative error examples, and GPU/cost analysis are in `reports/benchmark_report.md`.

| Model | Type | Full exact-match accuracy | Infra SLO (TTFT p95 < 0.3s, E2E p95 < 4.0s) | Cost / 1M requests |
|---|---|---|---|---|
| A — Qwen2.5-VL-7B-Instruct | self-hosted | 57.6% | meets both at every concurrency level (1-8) | 5.05 SAR |
| B — GPT-4o | OpenAI API | 52.9% | meets E2E; TTFT never meets (network-bound API call) | not computed — API token pricing not yet applied |
| C — Llama-3.2-11B-Vision-Instruct | self-hosted | 56.5% | meets both only through concurrency 2, then saturates and fails | 25.02 SAR |
| **D — Qwen3.5-4B (chosen)** | self-hosted | **58.8% (highest)** | meets both through concurrency 4; E2E still met at concurrency 8, TTFT marginally over (~6.9%, about 7%) | **4.98 SAR (lowest)** |
| E — Qwen3.5-9B | self-hosted | 57.6% | same pattern as D, marginal TTFT overshoot at concurrency 8 | 8.06 SAR (62% more than D) |

**Why Model D:** highest full exact-match accuracy of all five models, ties for perfect Field accuracy (100%), is the cheapest self-hosted model to run per request, and scales cleanly through concurrency 8 — E2E stays within SLO at every level, with only a marginal ~7% TTFT overshoot at concurrency 8. Model E, a larger 9B model tested specifically to check whether more parameters would close that gap, did not: it is 38% slower, 62% more expensive per request, and has no accuracy advantage over D. Level classification is the weakest field across all five models (61-67%); a separate validation exercise scoring GPT-4o's own tagging against the same human labels traces this to an ambiguous taxonomy definition, not a weakness specific to any one model.

Model D — Qwen3.5-4B — is the model this project runs in production, and the model used for the optional fine-tuning experiment described in `reports/benchmark_report.md`. That experiment did not beat the base model on the reserved benchmark (50/85 exact matches for both), and the report notes the honest caveat that this benchmark is not a fully blind test since it shares source documents with some training data. The experiment's full training and evaluation scripts and prepared data are in `finetune/` — see `finetune/README.md` to reproduce it.

## Operations

Day-to-day model switching, Kubernetes secrets, GPU monitoring, and known failure modes are documented in full in `PRODUCTION_HANDOFF.md`. In short:

```bash
./switch_model.sh d      # switch the active self-hosted model on the shared GPU
./add_model.sh           # register a new model into the shared registry
```

Only one self-hosted model can hold the shared GPU at full capacity at a time — always confirm with `kubectl get pods -n contentmap` before assuming which one is live.

## Known Limitations

- The evaluation set (85 rows) is within the course's guideline of no more than 100 datapoints, but small relative to the full 231-chunk corpus; benchmark accuracy figures should be read as directional rather than final.
- Self-hosted benchmark numbers reflect each model running alone on the shared GPU, not under real multi-model contention.
- Level classification remains the weakest tagged field across every model tested (61-67%), traced to an ambiguous taxonomy definition rather than a model-specific limitation.
- The optional fine-tuning experiment did not improve accuracy over the base Model D, and its benchmark comparison is not a fully independent blind test.
- The Progress Dashboard's Personalized Learning Plan section is a placeholder for a planned future feature and intentionally carries no data yet.
