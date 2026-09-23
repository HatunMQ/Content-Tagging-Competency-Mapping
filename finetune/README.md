# Qwen3.5-4B fine-tuning script

This package reproduces the content-tagging fine-tuning experiment. It trains Qwen3.5-4B to predict `Field`, `Learning_type`, `Level` and `Competency`, then compares the unchanged base model with the fine-tuned model. The prepared data, original tagging prompt and evaluation code are included.

## Run

Use Linux, Python 3.12 and an idle NVIDIA GPU supporting BF16, with at least 30 GiB free GPU memory and 20 GiB free disk space. The reference run used an H100 80 GB. The team's RTX A6000 supports BF16 and has sufficient total memory when idle; this package has not been run on that card. Internet access is needed to install dependencies and download the pinned Qwen checkpoint.

Extract the ZIP and open a terminal in the `Qwen35-Content-Tagging` folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_experiment.py --out ~/t05-qwen-finetune-run
```

Choose a new output directory outside the content-tagging repository. The script refuses an existing output directory or a GPU occupied by another compute process. It does not stop services or change the deployed model. If the serving model is running, use a separate idle training GPU.

`run_experiment.py` is the entry point. It calls `cloud_run.py` for training and evaluation, using the model and data helpers in `finetune.py`. Run it from this complete folder so the configuration and data remain available.

## What it does

The model is trained with LoRA, which updates small trainable adapters while keeping the original model weights frozen. The settings reproduce the completed experiment: BF16, rank 8, alpha 16, dropout 0.05, learning rate 0.00002, three epochs, batch size 2 with four accumulation steps, and seed 42.

Training uses 243 examples: 70 course-content chunks and 173 generated excerpts. Their labels are provisional model/assistant annotations. The supplied data is already prepared; running the 27B teacher again is unnecessary.

Checkpoint selection uses 24 development examples from separate source documents. Only after selection is frozen does the runner copy the 85 team benchmark examples and the separate 24-example assistant-labelled check into the run directory. Those examples and detected exact or near text duplicates were excluded from training and development. File hashes prevent silently substituting different data. Keep the benchmark reserved for evaluation.

The output directory contains `selected-adapter/`, `selection.json`, `benchmark-result.json`, `comparison.json`, and raw predictions for both models. An adapter is an experimental output, not an automatic deployment. GPU kernels and hardware can produce small differences between reruns.

## Paragraph for the project write-up

> We tested supervised fine-tuning of Qwen3.5-4B using LoRA on 243 examples with provisional model-generated and assistant-reviewed labels. We selected the checkpoint using a separate development set and kept all 85 human-labelled benchmark examples out of training. In the H100 comparison, both the base model and the fine-tuned model achieved 50/85 exact matches across the four tags. This experiment therefore did not improve benchmark accuracy, and we retained the base model. The limited training data and provisional labels constrain what we can conclude about fine-tuning more generally.

The historical benchmark shares source documents with some training chunks and was observed in an earlier experiment, so it is not a new blind test. The separate assistant-labelled check is not independent human validation. The negative result applies to this experiment; it does not establish that fine-tuning cannot help.
