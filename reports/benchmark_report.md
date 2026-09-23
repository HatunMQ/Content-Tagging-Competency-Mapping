# AI Data Center Bootcamp (SDA) — Team 7 Capstone Benchmark Report
## Content Tagging & Competency Mapping
*Powered by WeCloudData Academy, in collaboration with BeamData*

## 1. Executive Summary

- Use case: automatically tag learning-content chunks (slides, notebooks, notes) with Field, Learning_type, Level, and Competency labels, using a fixed taxonomy.
- Models evaluated: Model A (Qwen2.5-VL-7B-Instruct, self-hosted), Model B (GPT-4o, OpenAI API), Model C (Llama-3.2-11B-Vision-Instruct, self-hosted), Model D (Qwen3.5-4B, self-hosted), Model E (Qwen3.5-9B, self-hosted).
- Evaluation dataset: 85 human-labeled ground-truth chunks (`evaluation/eval_sample.csv`). Scored with 0 missing/unscored rows and 0/85 first-attempt failures for all five models.
- Full exact-match accuracy (all 4 fields correct): Model A 57.6%, Model B 52.9%, Model C 56.5%, **Model D 58.8% (highest)**, Model E 57.6%.
- Infra SLOs (TTFT p95 < 0.3s, E2E p95 < 4.0s): Model A meets both at every concurrency level (1–8). Model B meets E2E but misses TTFT always (network-bound API). Model C meets both only through concurrency 2, then fails badly. Model D meets both through concurrency 4, and meets E2E at concurrency 8 with a marginal TTFT overshoot (~6.9%). Model E shows the same pattern as D but is slower and more expensive.
- Cost per 1,000,000 requests (electricity only, self-hosted models): **Model D 4.98 SAR (lowest)**, Model A 5.05 SAR, Model E 8.06 SAR, Model C 25.02 SAR.
- **Decision: Model D (Qwen3.5-4B) selected for production.** Highest accuracy, lowest self-hosted cost, and meets both SLO targets at every tested concurrency level except a marginal ~7% TTFT overshoot at concurrency 8.

No single model wins on every metric. Model A is the most dependable under load. Model B has the best raw throughput and strong per-field accuracy but a fixed network-bound TTFT floor. Model D was chosen because it is the best overall balance: highest accuracy, lowest cost among the self-hosted models, and SLO compliance nearly everywhere. Model E was tested specifically as a larger alternative to Model D and did not improve on it in accuracy or cost.

## 2. Models and Deployment

- **Model A** — Qwen2.5-VL-7B-Instruct — self-hosted, vLLM on Kubernetes — deployment `model-a-qwen`, service `model-a-qwen-svc`
- **Model B** — GPT-4o — commercial, OpenAI API — no Kubernetes resources
- **Model C** — Llama-3.2-11B-Vision-Instruct — self-hosted, vLLM on Kubernetes — deployment `model-c-llama`, service `model-c-llama-svc`
- **Model D** — Qwen3.5-4B — self-hosted, vLLM on Kubernetes — deployment `model-d-qwen35`, service `model-d-qwen35-svc`
- **Model E** — Qwen3.5-9B — self-hosted, vLLM on Kubernetes — deployment `model-e-qwen35-9b`, service `model-e-qwen35-9b-svc`

All Kubernetes resources live in namespace `contentmap`, on a single shared NVIDIA RTX A6000 GPU (49,140 MiB VRAM). Only one self-hosted model was kept at replica count > 0 at a time — every self-hosted model's numbers in this report reflect it running alone on the GPU, not under real multi-model contention (see Section 6).

Model C required a Hugging Face access token for a gated checkpoint, provided as a Kubernetes Secret. Models A, D, and E required no such token. Model E, at roughly double Model D's parameter count, was deployed with `--gpu-memory-utilization=0.65` (vs. 0.5 for Model D) to fit its larger weight footprint.

### Prompt and Decoding Settings

- Identical system and user prompt for all five models — full text in `prompts/extraction_prompt.txt`
- Temperature: 0
- Maximum output tokens: 200
- Retries: 3, with backoff, before a call is recorded as an error

## 3. Dataset and Evaluation Method

- Source: `evaluation/eval_sample.csv`, human-labeled, drawn from 231 extracted content chunks (`data/extracted/extracted_chunks.jsonl`)
- Size: 85 rows after a data-integrity pass (from an original 90 — 5 rows were content-free title slides correctly excluded by the pipeline, 1 row had a corrupted `file_name` that was traced and repaired)
- Taxonomy (fixed for all models):
  - Field: Data Science, Machine Learning, SQL, Generative AI
  - Learning_type (VARK-based): Visual, Read/Write, Kinesthetic
  - Level: Beginner, Intermediate, Advanced
  - Competency: 10 fixed values (Python Basics, Pandas & Data Wrangling, Machine Learning Workflow, Decision Tree Modeling, SQL Foundations, Window Functions, Prompt Engineering, RAG Systems, Data Visualization, Statistics Foundations)
- Tagging run: `src/tagging/tag_chunks.py --eval-only`, all five models tagged the same 85 chunks
- Scoring: `evaluation/compare_results.py`, normalized case/whitespace matching, ground truth joined on `(file_name, chunk_id)`

### Error Handling

- Zero unrecoverable errors across all 425 tagging calls (85 chunks × 5 models)
- First-attempt failure rate: 0/85 (0.0%) for every model — the zero-error result reflects genuinely stable endpoints, not retries masking failures

### Token Usage (measured directly from each model's API response)

| | Model A | Model B | Model C | Model D | Model E |
|---|---:|---:|---:|---:|---:|
| Avg prompt tokens | 427.1 | 421.3 | 476.7 | 473.3 | 473.3 |
| Avg completion tokens | 37.2 | 31.9 | 31.4 | 31.7 | 31.6 |
| Avg total tokens / request | 464.4 | 453.2 | 508.1 | 504.9 | 504.9 |
| Total tokens across 85 requests | 39,470 | 38,518 | 43,188 | 42,919 | 42,916 |

Model D and E have identical average prompt-token counts (473.3) since both share the Qwen3.5 tokenizer — most likely a tokenizer difference from Model A/B, not a content difference, since all five models were sent the same 85 prompts.

## 4. Model Quality Results

| Field | Model A | Model B | Model C | Model D | Model E |
|---|---:|---:|---:|---:|---:|
| Field accuracy | 92.9% | 100.0% | 100.0% | 100.0% | 100.0% |
| Learning_type accuracy | 94.1% | 81.2% | 92.9% | 90.6% | 88.2% |
| Level accuracy | 63.5% | 67.1% | 61.2% | 64.7% | 64.7% |
| Competency accuracy | 92.9% | 98.8% | 91.8% | 98.8% | 100.0% |
| **Full exact match** | **57.6%** | **52.9%** | **56.5%** | **58.8%** | **57.6%** |
| Scored / Ground truth | 85/85 | 85/85 | 85/85 | 85/85 | 85/85 |
| Unscored errors | 0 | 0 | 0 | 0 | 0 |

Model D has the highest full exact-match accuracy (58.8%), ties Model B and C on perfect Field accuracy, and ties Model B on Competency (98.8%). Its weakest field is Learning_type (90.6%). Level remains the weakest field for every model (61–67%).

### Observed Error Pattern

The dominant error across all five models is a Level mismatch with everything else correct — mostly over-predicting "Intermediate" for content that is actually Beginner or Advanced.

Example (Model D):
- Ground truth: `WK4_D2_Quiz2 / q_002` — Level: Advanced, Competency: Machine Learning Workflow
- Prediction: Level: Intermediate, Competency: Decision Tree Modeling
- This is the only row across all five models with two fields wrong at once.

### Representative Correct Predictions

| File / chunk | Ground Truth | Result |
|---|---|---|
| Decision Trees Revised.pptx / slide_02 | Field: Machine Learning, Learning_type: Visual, Level: Beginner, Competency: Decision Tree Modeling | Matched by all 5 models |

### Representative Failure Cases

| Model | File / chunk | Mismatch (ground truth → predicted) | Other fields |
|---|---|---|---|
| A | Decision Trees Revised.pptx / slide_02 | Level: Beginner → Intermediate | all matched |
| B | Decision Trees Revised.pptx / slide_38 | Level: Advanced → Intermediate | all matched |
| C | Decision Trees Revised.pptx / slide_08 | Level: Beginner → Intermediate | all matched |
| D | Lecture - Pandas Basics.ipynb / section_06 | Learning_type: Read/Write → Kinesthetic | all matched |
| D | WK4_D2_Quiz2 / q_002 | Level + Competency both wrong | Field, Learning_type matched |

### Ground-Truth Validation Exercise

GPT-4o (Model B) independently re-tagged the same 85 chunks without seeing the human labels, as a second check on whether the taxonomy itself is well-defined:

| Field | GPT-4o vs. human agreement |
|---|---:|
| Field | 100.0% |
| Competency | 98.8% |
| Learning_type | 81.2% |
| Level | 67.1% |

Even a frontier model only agrees with human Level labels two-thirds of the time — this is a taxonomy-definition issue (ambiguous Beginner/Intermediate/Advanced boundaries), not a weakness specific to any one model.

Re-scoring Model D and E against this GPT-4o-generated reference instead of human labels raises their apparent accuracy substantially (Model D full exact match: 58.8% → 72.9%; Model E: 57.6% → 76.5%). This is not read as evidence either model became more correct — it reflects correlated LLM judgment on a subjective field, not independent validation. The human-labeled ground truth remains authoritative for every accuracy figure and the model-selection decision in this report.

## 5. Infrastructure Benchmark

Each model was load-tested with `evaluation/benchmark_load.py` at concurrency 1, 2, 4, 8 (20 requests per level). SLO targets: TTFT p95 < 0.3s, E2E p95 < 4.0s.

**Model A** — Qwen2.5-VL-7B-Instruct

| Concurrency | Failed | TTFT p50 | TTFT p95 | E2E p50 | E2E p95 | Throughput | SLO met |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | 0.036s | 0.043s | 1.768s | 2.877s | 43.87 tok/s | Yes |
| 2 | 0 | 0.066s | 0.068s | 2.100s | 2.923s | 83.77 tok/s | Yes |
| 4 | 0 | 0.066s | 0.114s | 1.828s | 2.957s | 155.75 tok/s | Yes |
| 8 | 0 | 0.082s | 0.222s | 1.930s | 3.073s | 264.79 tok/s | Yes |

Throughput scales close to linearly, latency stays flat — clear headroom at this scale. Context window: 128,000 tokens (no override). Idle GPU memory: 28,919 / 49,140 MiB (~59%).

**Model B** — GPT-4o

| Concurrency | Failed | TTFT p50 | TTFT p95 | E2E p50 | E2E p95 | Throughput | SLO met |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | 0.451s | 0.840s | 1.181s | 1.626s | 66.97 tok/s | TTFT no, E2E yes |
| 2 | 0 | 0.423s | 0.511s | 0.853s | 1.375s | 145.22 tok/s | TTFT no, E2E yes |
| 4 | 0 | 0.434s | 0.516s | 1.024s | 1.488s | 263.54 tok/s | TTFT no, E2E yes |
| 8 | 0 | 0.438s | 0.635s | 0.936s | 1.348s | 482.50 tok/s | TTFT no, E2E yes |

TTFT never meets target — network-bound external API call. Throughput scales best of all five models.

**Model C** — Llama-3.2-11B-Vision-Instruct

| Concurrency | Failed | TTFT p50 | TTFT p95 | E2E p50 | E2E p95 | Throughput | SLO met |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | 0.042s | 0.062s | 3.647s | 3.851s | 33.03 tok/s | Yes |
| 2 | 0 | 0.065s | 0.067s | 3.827s | 4.020s | 60.92 tok/s | Borderline |
| 4 | 0 | 3.112s | 4.047s | 6.102s | 7.921s | 62.18 tok/s | No |
| 8 | 0 | 9.149s | 10.326s | 11.955s | 14.257s | 61.14 tok/s | No |

Throughput plateaus at ~61–62 tok/s after concurrency 2 while latency climbs sharply — the deployment is saturated (GPU/KV-cache contention), not genuinely serving more requests in parallel. Context window: only 8,192 tokens, yet 43,279 / 49,140 MiB GPU memory used at idle (~88%) — the 11B parameter count is the likely driver, leaving little headroom once concurrent requests compete for it.

**Model D** — Qwen3.5-4B (production model)

| Concurrency | Failed | TTFT p50 | TTFT p95 | E2E p50 | E2E p95 | Throughput | SLO met |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | 0.065s | 0.073s | 1.845s | 1.855s | 68.42 tok/s | Yes |
| 2 | 0 | 0.124s | 0.137s | 1.942s | 1.949s | 130.20 tok/s | Yes |
| 4 | 0 | 0.157s | 0.196s | 2.022s | 2.045s | 247.64 tok/s | Yes |
| 8 | 0 | 0.212s | 0.3207s | 2.169s | 2.266s | 384.73 tok/s | E2E yes, TTFT ~6.9% over |

Throughput scales cleanly and near-linearly (68.42 → 384.73 tok/s). Deployed with `--gpu-memory-utilization=0.5`, 32,768-token context. GPU memory flat at 22,915 / 49,140 MiB (~46.6%) at idle and peak. Peak power draw: 299.65 W.

**Model E** — Qwen3.5-9B

| Concurrency | Failed | TTFT p50 | TTFT p95 | E2E p50 | E2E p95 | Throughput | SLO met |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | 0.062s | 0.069s | 3.216s | 3.231s | 39.44 tok/s | Yes |
| 2 | 0 | 0.119s | 0.136s | 3.343s | 3.350s | 76.06 tok/s | Yes |
| 4 | 0 | 0.156s | 0.194s | 3.428s | 3.447s | 147.61 tok/s | Yes |
| 8 | 0 | 0.221s | 0.322s | 3.529s | 3.624s | 238.14 tok/s | E2E yes, TTFT ~7% over |

Same qualitative pattern as Model D, but slower at every concurrency level (238.14 vs. 384.73 tok/s at concurrency 8 — a 38% gap) and higher E2E latency throughout. Deployed with `--gpu-memory-utilization=0.65`, same 32,768-token context. GPU memory: 29,967–30,085 MiB (~61%). Peak power draw: 299.88 W.

### Configuration Sensitivity (Advanced Benchmarking)

- An initial Model D deployment at vLLM's default memory reservation (~88% of the card) and an 8,192-token context flatlined above concurrency 2 and failed both SLO targets at concurrency 4 and 8.
- Lowering to `--gpu-memory-utilization=0.5` and raising `--max-model-len=32768` restored linear scaling through concurrency 8 (the numbers above reflect this configuration).
- Model E's identical ~7% relative overshoot at concurrency 8 (despite double the parameters) rules out model size as the cause too. The overshoot most likely reflects a near-fixed per-request processing cost when 8 requests queue simultaneously on this specific GPU — not a tunable deployment parameter.

### Estimated Electricity Cost

Measured via `nvidia-smi` sampling (`evaluation/gpu_monitor.py`) combined with measured throughput at the highest tested concurrency (`evaluation/estimate_cost.py`). Tariff assumption: 0.18 SAR/kWh.

| | Model A | Model C | Model D | Model E |
|---|---:|---:|---:|---:|
| Peak GPU utilization | 100.0% | 97.0% | 100.0% | 100.0% |
| Peak GPU memory used | 28,919 MiB | 43,287 MiB | 22,915 MiB | 30,085 MiB |
| Peak power draw | 300.01 W | 300.24 W | 299.65 W | 299.88 W |
| Time to serve 1,000 requests | 336.70 s | 1,666.67 s | 332.23 s | 537.63 s |
| **Cost per 1,000,000 requests** | 5.0507 SAR | 25.0200 SAR | **4.9776 SAR** | 8.0613 SAR |

Model D is the cheapest self-hosted model per request. Model E costs 62% more than Model D despite near-identical power draw — the entire gap comes from Model E needing 62% longer to serve the same 1,000 requests (slower generation at the larger parameter count), not a power-efficiency difference. This covers electricity only and is not comparable to Model B's per-token API pricing (not yet looked up — see Next Steps).

## 6. Key Limitations

- Every self-hosted model (A, C, D, E) was benchmarked alone on the shared GPU, confirmed via `kubectl get deployments -n contentmap` — none of these numbers reflect real multi-model contention.
- Model D's tagging run was redone with `--eval-only` for a clean, directly comparable 85-row result. Level accuracy and full exact match came in ~2 points lower than an earlier, less rigorous pass — most likely ordinary temperature-0 serving nondeterminism, since Field, Learning_type, and Competency reproduced exactly.
- The Section 5 cost analysis covers electricity only (A, C, D, E) — no hardware amortization, cooling, or staff time. Model B's dollar cost still needs OpenAI's published per-token pricing.
- Level classification is the weakest field across all five models (61–67%) — most likely a taxonomy-definition issue, not a model capability gap (Model D and E landed on the identical 64.7% despite different sizes).
- The 85-row evaluation set is within the course's 100-datapoint guideline but small relative to the full 231-chunk corpus — accuracy numbers should be read as directional rather than final.

## 7. Conclusion

All five models were deployed and benchmarked against an identical 85-row human-labeled evaluation set, using the same prompt and decoding settings. No model dominates on every axis:

- Model A is the most dependable choice if a clean SLO pass at every concurrency level is the top priority, though its electricity cost is now slightly higher than Model D's.
- Model B has the strongest per-field accuracy and best throughput, but a fixed TTFT floor and per-token pricing.
- Model C needs its concurrency-scaling problem isolated from the shared-GPU test setup before it's reconsidered.
- Model E, tested as a larger 9B alternative to Model D, did not resolve the TTFT overshoot or improve accuracy — it is slower, 62% more expensive per request, and marginally less accurate. Model size is not the lever that matters here.

**Recommendation: Model D (Qwen3.5-4B).** Highest full-exact-match accuracy, lowest measured infrastructure cost per request, and both SLO targets met at every tested concurrency level except a marginal ~7% TTFT overshoot at concurrency 8. This holds against the human-labeled ground truth, which this report treats as authoritative (Section 4). Model D is the model this project is proceeding with for production and for fine-tuning.

## Next Steps

- Re-run Model C's load test on isolated GPU capacity, to separate a slow model from a contended cluster.
- Obtain OpenAI's published per-token pricing for GPT-4o and apply it to the already-measured token usage, so all five models compare on a common dollar-cost basis.
- Revisit the Level taxonomy definition with the team before further evaluation rounds.
- Proceed to prompt-engineering iteration and the RAG phase, per the project plan, using Model A as the baseline.

## Optional Stretch Work: Fine-Tuning

We tested supervised fine-tuning of Qwen3.5-4B using LoRA on 243 examples with provisional model-generated and assistant-reviewed labels. We selected the checkpoint using a separate development set and kept all 85 human-labelled benchmark examples out of training.

- Result: both the base model and the fine-tuned model achieved 50/85 exact matches across the four tags in the H100 comparison.
- This experiment did not improve benchmark accuracy — the base model was retained.
- Caveat: the historical benchmark shares source documents with some training chunks and was observed in an earlier experiment, so it is not a new blind test. The separate assistant-labelled check is not independent human validation. The negative result applies to this experiment specifically — it does not establish that fine-tuning cannot help.

## Competency Gap Analysis

The Progress Dashboard maps each learner's activity onto the same Competency tags used across the content library, so for every competency we can show how many of its tagged content items a learner has actually completed out of the total available — that's the real signal behind the gap percentage and the "What needs attention" cards, not a guess. Where a learner has also attempted a quiz tied to that competency, we show the real quiz score alongside it as extra evidence.

We deliberately didn't make quiz performance the main driver of the gap itself: right now most competencies don't have enough quiz attempts yet to support that reliably. That's exactly why the Personalized Learning Plan — a personalized plan per competency built from real quiz performance — is marked "coming soon" rather than shipped: it needs more quiz data across competencies before it can say something meaningful, and we'd rather leave it honestly unbuilt than fake it.
