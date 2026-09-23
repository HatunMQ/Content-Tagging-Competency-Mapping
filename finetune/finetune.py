#!/usr/bin/env python3
"""Qwen3.5-4B content tagging: prepare, check, train, evaluate, and merge.

Reads the team's content repository. Writes only to explicitly named NEW output
directories. Never manages services, Kubernetes, processes, or installed packages.
Data preparation uses only the Python standard library.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import difflib
from functools import lru_cache
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys

try:
    from rapidfuzz.fuzz import ratio as indel_ratio
except ImportError:
    indel_ratio = None

MODEL = "Qwen/Qwen3.5-4B"
REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "task_config.json").read_text(encoding="utf-8"))
FIELDS = list(CONFIG["taxonomy"])
DEFAULT_REPO = Path.home() / "aidc/Content-Tagging-Competency-Mapping"


def fail(message):
    raise ValueError(message)


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row):
    return (str(row["file_name"]).strip(), str(row["chunk_id"]).strip())


def fingerprint(chunk):
    # Match the actual content seen by the model, including its 2,000-char limit.
    text = (chunk.get("text") or "")[:CONFIG["input_character_limit"]]
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


@lru_cache(maxsize=4096)
def content_shingles(text):
    words = re.findall(r"\w+", text)
    return frozenset(tuple(words[i:i+5]) for i in range(max(0, len(words) - 4)))


def similar_content(a, b):
    a = " ".join(a["text"][:CONFIG["input_character_limit"]].casefold().split())
    b = " ".join(b["text"][:CONFIG["input_character_limit"]].casefold().split())
    if a == b:
        return True
    ratio = min(len(a), len(b)) / max(len(a), len(b))
    # Normalized Indel similarity uses the optimal common subsequence, so it is
    # an upper bound on SequenceMatcher's greedy matched subsequence. This cheap
    # C++ prefilter preserves the original duplicate predicate, including its
    # fallback when RapidFuzz is unavailable. The tolerance avoids boundary loss.
    could_match = indel_ratio is None or indel_ratio(a, b, score_cutoff=89.999999) >= 89.999999
    if ratio > .7 and could_match and difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= .9:
        return True
    sa, sb = content_shingles(a), content_shingles(b)
    return min(len(sa), len(sb)) >= 20 and ratio >= .6 and len(sa & sb) / min(len(sa), len(sb)) >= .85


def new_output(path, repo=None):
    path = Path(path).expanduser().resolve()
    if repo and path.is_relative_to(Path(repo).expanduser().resolve()):
        fail("Choose an output directory outside the original content repository.")
    path.mkdir(parents=True, exist_ok=False)
    return path


def load_chunks(repo):
    path = Path(repo) / "data/extracted/extracted_chunks.jsonl"
    rows = read_jsonl(path)
    result = {}
    for row in rows:
        k = key(row)
        if k in result:
            fail(f"Duplicate extracted chunk key: {k}")
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            fail(f"Empty or invalid extracted text: {k}")
        result[k] = row
    if not result:
        fail("No extracted chunks found.")
    return result


def read_labels(path, chunks):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"file_name", "chunk_id", *FIELDS}
        if not required.issubset(reader.fieldnames or []):
            fail(f"{path}: required CSV columns are {sorted(required)}")
        rows = []
        seen = set()
        for line, row in enumerate(reader, 2):
            k = key(row)
            if k in seen:
                fail(f"{path}:{line}: duplicate label key {k}")
            seen.add(k)
            if k not in chunks:
                fail(f"{path}:{line}: no matching extracted chunk for {k}")
            tags = {field: (row.get(field) or "").strip() for field in FIELDS}
            for field, value in tags.items():
                if value not in CONFIG["taxonomy"][field]:
                    fail(f"{path}:{line}: invalid or empty {field}={value!r}. Review every label before training.")
            rows.append({"chunk": chunks[k], "tags": tags})
    if not rows:
        fail(f"No labeled rows in {path}")
    # Do not silently train conflicting labels for identical visible content.
    by_text = {}
    for row in rows:
        fp = fingerprint(row["chunk"])
        if fp in by_text and row["tags"] != by_text[fp]:
            fail(f"Conflicting labels for identical content at {key(row['chunk'])}; review the labels.")
        by_text[fp] = row["tags"]
    return rows


def messages(chunk):
    meta = chunk.get("metadata", {})
    user = (f"File: {chunk.get('file_name')}\n"
            f"Section: {meta.get('section_title', '')}\n"
            f"Content type: {chunk.get('content_type')}\n---\n"
            f"{(chunk.get('text') or '')[:CONFIG['input_character_limit']]}")
    return [{"role": "system", "content": CONFIG["system_prompt"]},
            {"role": "user", "content": user}]


def label_sheet(args):
    chunks = load_chunks(args.repo)
    benchmark = read_labels(args.benchmark, chunks)
    held_keys = {key(r["chunk"]) for r in benchmark}
    held_text = {fingerprint(r["chunk"]) for r in benchmark}
    candidates = [c for k, c in chunks.items() if k not in held_keys and fingerprint(c) not in held_text
                  and not any(similar_content(c, r["chunk"]) for r in benchmark)]
    out = new_output(args.out, args.repo)
    columns = ["file_name", "chunk_id", "content_type", "section_title", "text_for_model", *FIELDS]
    with (out / "labels.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for c in candidates:
            writer.writerow({"file_name": c["file_name"], "chunk_id": c["chunk_id"],
                             "content_type": c.get("content_type", ""),
                             "section_title": c.get("metadata", {}).get("section_title", ""),
                             "text_for_model": c["text"][:CONFIG["input_character_limit"]]})
    write_json(out / "taxonomy.json", CONFIG["taxonomy"])
    print(f"Wrote {len(candidates)} unlabeled rows to {out / 'labels.csv'}. Fill all four label columns.")
    print(f"Reserved all {len(benchmark)} benchmark rows, plus any identical content, from training.")


def group_split(rows, fraction, seed):
    # Union documents that share an identical visible chunk. No document or exact
    # duplicate can cross the train/validation boundary.
    rows = sorted(rows, key=lambda r: key(r["chunk"]))
    parent = {r["chunk"]["file_name"]: r["chunk"]["file_name"] for r in rows}
    def root(x):
        while parent[x] != x:
            x = parent[x]
        return x
    owners = {}
    for r in rows:
        name, fp = r["chunk"]["file_name"], fingerprint(r["chunk"])
        if fp in owners:
            parent[root(name)] = root(owners[fp])
        owners[fp] = name
    groups = {}
    for r in rows:
        groups.setdefault(root(r["chunk"]["file_name"]), []).append(r)
    names = sorted(groups)
    if len(names) < 2:
        fail("Need at least two independent source-document groups for a held-out split.")
    random.Random(seed).shuffle(names)
    target = max(1, round(len(rows) * fraction))
    # This course has a dozen documents. Search those grouped splits directly to
    # avoid putting an entire rare competency or level only in validation.
    if len(names) <= 16:
        total_labels = Counter((f, r["tags"][f]) for r in rows for f in FIELDS)
        group_labels = {name: Counter((f, r["tags"][f]) for r in groups[name] for f in FIELDS)
                        for name in names}
        best = None
        for mask in range(1, 2**len(names) - 1):
            chosen = {name for i, name in enumerate(names) if mask & (1 << i)}
            n = sum(len(groups[name]) for name in chosen)
            if n < 2 or len(rows) - n < 8:
                continue
            held_labels = sum((group_labels[name] for name in chosen), Counter())
            missing_train = sum(held_labels[k] == total_labels[k] for k in total_labels)
            imbalance = sum(abs(held_labels[k] / n - total_labels[k] / len(rows)) for k in total_labels)
            score = (missing_train, abs(n - target), imbalance, mask)
            if best is None or score < best[0]:
                best = (score, chosen)
        if best is not None:
            selected = best[1]
            return ([r for name in names if name not in selected for r in groups[name]],
                    [r for name in names if name in selected for r in groups[name]])
    held = []
    selected = set()
    for name in names[:-1]:
        if len(held) >= target:
            break
        held.extend(groups[name])
        selected.add(name)
    rest = [r for name in names if name not in selected for r in groups[name]]
    return rest, held


def prepare(args):
    chunks = load_chunks(args.repo)
    benchmark = read_labels(args.benchmark, chunks)
    if not args.labels:
        fail("Provide --labels with separately annotated non-benchmark examples. Benchmark reuse is prohibited.")
    pool = read_labels(args.labels, chunks)
    test = benchmark
    test_keys = {key(r["chunk"]) for r in test}
    test_text = {fingerprint(r["chunk"]) for r in test}
    overlap = [key(r["chunk"]) for r in pool
               if key(r["chunk"]) in test_keys or fingerprint(r["chunk"]) in test_text
               or any(similar_content(r["chunk"], b["chunk"]) for b in test)]
    if overlap:
        fail(f"Training labels overlap the protected benchmark by key or similar text: {overlap[:5]}")
    mode = "benchmark-preserved: test measures held-out chunks from the same course corpus"
    label_source = args.labels
    train, validation = group_split(pool, .2, args.seed + 1)
    if len(train) < 8 or len(validation) < 2 or len(test) < 2:
        fail("Too few examples after grouping: need train >=8, validation >=2, test >=2.")
    splits = {"train": train, "validation": validation, "test": test}
    summary = {"model": MODEL, "mode": mode, "seed": args.seed,
               "repo": str(Path(args.repo).resolve()), "label_provenance": args.label_provenance,
               "task_config_sha256": sha(HERE / "task_config.json"),
               "inputs": {str(p): sha(p) for p in [Path(args.repo) / "data/extracted/extracted_chunks.jsonl",
                                                    Path(args.benchmark), Path(label_source)]}, "splits": {}}
    for split, rows in splits.items():
        summary["splits"][split] = {
            "rows": len(rows), "files": sorted({r["chunk"]["file_name"] for r in rows}),
            "labels": {field: dict(Counter(r["tags"][field] for r in rows)) for field in FIELDS}}
    train_labels = {f: {r["tags"][f] for r in train} for f in FIELDS}
    summary["labels_absent_from_training"] = {f: sorted(set(CONFIG["taxonomy"][f]) - train_labels[f]) for f in FIELDS}
    out = new_output(args.out, args.repo)
    for split, rows in splits.items():
        write_jsonl(out / f"{split}.jsonl", rows)
    summary["split_sha256"] = {s: sha(out / f"{s}.jsonl") for s in splits}
    write_json(out / "manifest.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def load_prepared(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest["task_config_sha256"] != sha(HERE / "task_config.json"):
        fail("Task prompt/taxonomy changed after preparation. Prepare a new dataset.")
    for split, expected in manifest["split_sha256"].items():
        if sha(path / f"{split}.jsonl") != expected:
            fail(f"{split}.jsonl changed after preparation. Prepare a new dataset.")
    return manifest


def data_identity(manifest):
    # Absolute source paths differ when a reviewed dataset moves between machines.
    # Bind the adapter to the actual prompt and split bytes, not those paths.
    return {"version": 1, "task_config_sha256": manifest["task_config_sha256"],
            "split_sha256": manifest["split_sha256"]}


def get_tokenizer(revision=REVISION):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=revision)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def encode(row, tokenizer, max_length):
    prompt = messages(row["chunk"])
    answer = json.dumps(row["tags"], ensure_ascii=False)
    prefix = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    full = tokenizer.apply_chat_template(prompt + [{"role": "assistant", "content": answer}],
                                         tokenize=False, add_generation_prompt=False, enable_thinking=False)
    if not full.startswith(prefix):
        fail("Qwen chat-template prefix changed. Refusing to guess the loss mask.")
    prefix_ids = tokenizer(prefix, add_special_tokens=False)["input_ids"]
    ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    if ids[:len(prefix_ids)] != prefix_ids:
        fail("Chat-template token boundary differs. Refusing an incorrect loss mask.")
    if len(ids) > max_length:
        fail(f"{key(row['chunk'])}: {len(ids)} tokens exceeds --max-length {max_length}; increase it. No labels were truncated.")
    labels = [-100] * len(prefix_ids) + ids[len(prefix_ids):]
    if all(x == -100 for x in labels):
        fail("No supervised answer tokens.")
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}


def collator(tokenizer):
    from transformers import DataCollatorForSeq2Seq
    return DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100, return_tensors="pt")


def check(args):
    load_prepared(args.data)
    tokenizer = get_tokenizer(args.revision)
    for split in ["train", "validation", "test"]:
        rows = read_jsonl(Path(args.data) / f"{split}.jsonl")
        encoded = [encode(r, tokenizer, args.max_length) for r in rows]
        print(f"{split}: {len(rows)} rows, longest {max(len(e['input_ids']) for e in encoded)} tokens; masks valid.")
    print("CPU/tokenizer check passed. No model weights or GPU were loaded.")


def gpu_guard(min_free_gib=12):
    # An idle allocation is still owned. Do not train alongside the serving engine.
    try:
        r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"],
                           capture_output=True, text=True, check=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        fail(f"Could not verify GPU availability: {exc}")
    if r.stdout.strip():
        fail("GPU already has a compute process. Arrange an idle training window with your team first. "
             "This script will not stop it.\n" + r.stdout.strip())
    import torch
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        fail("A CUDA GPU with BF16 support is required (the team's RTX A6000 supports this).")
    if torch.cuda.device_count() != 1:
        fail("Select exactly one GPU with CUDA_VISIBLE_DEVICES.")
    free, _ = torch.cuda.mem_get_info()
    if free < min_free_gib * 1024**3:
        fail(f"Need at least {min_free_gib} GiB free VRAM; found {free / 1024**3:.1f} GiB.")


def load_model(revision, quantized=True):
    import torch
    from transformers import BitsAndBytesConfig, Qwen3_5ForConditionalGeneration
    kwargs = dict(revision=revision, dtype=torch.bfloat16, device_map={"": 0}, attn_implementation="sdpa")
    if quantized:
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16)
    # Keep the native checkpoint structure so a later merged export retains its
    # vision encoder. Training examples are text; the vision encoder stays frozen.
    return Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, **kwargs)


def add_lora(model, rank=8):
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    if getattr(model, "is_loaded_in_4bit", False):
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                              gradient_checkpointing_kwargs={"use_reentrant": False})
    targets = [name for name, layer in model.named_modules()
               if name.startswith("model.language_model.layers.") and isinstance(layer, torch.nn.Linear)]
    if not targets or not any("linear_attn" in n for n in targets) or not any("self_attn" in n for n in targets):
        fail("Expected both Qwen3.5 linear-attention and full-attention layers. Check the pinned environment.")
    model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=.05,
                                           target_modules=targets, bias="none", task_type="CAUSAL_LM"))
    model.config.use_cache = False
    model.config.text_config.use_cache = False
    return model


def answer_only_inputs(inputs):
    # The Qwen vocabulary has 248k entries. Compute its output projection only for
    # positions that can contribute to answer loss, including the preceding token.
    # Input tokens and attention still cover the entire prompt. Labels are cropped
    # to the same suffix, so the model's usual causal shift remains unchanged.
    labels = inputs["labels"]
    positions = (labels != -100).any(dim=0).nonzero()
    if not len(positions):
        fail("No supervised answer tokens in this batch")
    start = max(0, int(positions[0]) - 1)
    result = dict(inputs)
    result["labels"] = labels[:, start:]
    result["logits_to_keep"] = labels.shape[1] - start
    return result


def train(args):
    manifest = load_prepared(args.data)
    gpu_guard(args.min_free_gib)
    from transformers import Trainer, TrainingArguments, set_seed
    import torch
    set_seed(args.seed)
    tokenizer = get_tokenizer(args.revision)
    train_rows = [encode(r, tokenizer, args.max_length) for r in read_jsonl(Path(args.data) / "train.jsonl")]
    val_rows = [encode(r, tokenizer, args.max_length) for r in read_jsonl(Path(args.data) / "validation.jsonl")]
    out = new_output(args.out, manifest["repo"])
    if shutil.disk_usage(out).free < 20 * 1024**3:
        fail("Need at least 20 GiB free disk for the model download and training artifacts.")
    model = add_lora(load_model(args.revision), args.rank)
    model.print_trainable_parameters()
    resolved_revision = getattr(model.config, "_commit_hash", None) or args.revision
    settings = TrainingArguments(
        output_dir=str(out / "checkpoints"), num_train_epochs=args.epochs,
        max_steps=args.max_steps, per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=4, learning_rate=args.learning_rate,
        lr_scheduler_type="cosine", warmup_ratio=.1, weight_decay=.01, max_grad_norm=1.,
        bf16=True, tf32=True, gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False}, optim="adamw_torch",
        eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
        metric_for_best_model="eval_loss", greater_is_better=False, save_total_limit=2,
        logging_steps=1, report_to="none", push_to_hub=False, seed=args.seed, data_seed=args.seed,
        dataloader_num_workers=0, remove_unused_columns=False, label_names=["labels"],
    )
    class AnswerOnlyTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            outputs = model(**answer_only_inputs(inputs))
            return (outputs.loss, outputs) if return_outputs else outputs.loss

    trainer = AnswerOnlyTrainer(model=model, args=settings, train_dataset=train_rows,
                      eval_dataset=val_rows, processing_class=tokenizer, data_collator=collator(tokenizer))
    # PEFT forwards **kwargs; do not let Trainer assume this model computes
    # loss normalization using num_items_in_batch through every wrapper.
    trainer.model_accepts_loss_kwargs = False
    provenance = {"base_model": MODEL, "revision": resolved_revision,
                  "data_manifest_sha256": sha(Path(args.data) / "manifest.json"),
                  "data_identity": data_identity(manifest),
                  "mode": manifest["mode"], "hyperparameters": vars(args),
                  "packages": {p: importlib.metadata.version(p) for p in
                               ["torch", "transformers", "peft", "accelerate", "bitsandbytes"]},
                  "gpu": torch.cuda.get_device_name(0)}
    # argparse's handler is not JSON data.
    provenance["hyperparameters"] = {k: str(v) if isinstance(v, Path) else v
                                    for k, v in vars(args).items() if k != "func"}
    write_json(out / "run.json", provenance)
    result = trainer.train()
    if not math.isfinite(result.training_loss):
        fail("Non-finite training loss. Do not use this adapter.")
    trainer.save_model(str(out / "adapter"))
    tokenizer.save_pretrained(out / "adapter")
    trainer.save_state()
    write_json(out / "train_metrics.json", result.metrics)
    write_json(out / "validation_metrics.json", trainer.evaluate())
    write_json(out / "gpu_memory.json", {"peak_allocated_gib": torch.cuda.max_memory_allocated() / 1024**3,
                                         "peak_reserved_gib": torch.cuda.max_memory_reserved() / 1024**3})
    shutil.copy2(out / "run.json", out / "adapter/run.json")
    print(f"Saved best validation-loss adapter to {out / 'adapter'}. Evaluate before claiming improvement.")


def adapter_revision(args, manifest=None):
    if not args.adapter:
        return args.revision
    run = json.loads((Path(args.adapter) / "run.json").read_text())
    if manifest is not None:
        same_data = (run["data_identity"] == data_identity(manifest) if "data_identity" in run else
                     run["data_manifest_sha256"] == sha(Path(args.data) / "manifest.json"))
        if not same_data:
            fail("Adapter belongs to a different data split. Use its original prepared data.")
    return run["revision"]


def evaluate(args):
    manifest = load_prepared(args.data)
    revision = adapter_revision(args, manifest)
    rows = read_jsonl(Path(args.data) / "test.jsonl")
    tokenizer = get_tokenizer(revision)
    for row in rows:
        encode(row, tokenizer, args.max_length)
    gpu_guard(args.min_free_gib)
    import torch
    from peft import PeftModel
    from transformers import set_seed
    set_seed(42)
    out = new_output(args.out, manifest["repo"])
    # BF16 evaluates the deployment/export precision, for both baseline and adapter.
    model = load_model(revision, quantized=False)
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter, is_trainable=False)
    model.eval()
    model.config.use_cache = True
    model.config.text_config.use_cache = True
    predictions = []
    team_predictions = []
    correct = Counter()
    exact = valid = 0
    for i, row in enumerate(rows, 1):
        prompt = tokenizer.apply_chat_template(messages(row["chunk"]), tokenize=False,
                                               add_generation_prompt=True, enable_thinking=False)
        inputs = tokenizer(prompt, add_special_tokens=False, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            generated = model.generate(**inputs, do_sample=False, max_new_tokens=200,
                                       pad_token_id=tokenizer.pad_token_id, use_cache=True)
        text = tokenizer.decode(generated[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        team_record = {"file_name": row["chunk"]["file_name"], "chunk_id": row["chunk"]["chunk_id"]}
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match is None:
                raise ValueError("No JSON object found")
            parsed = json.loads(match.group(0))
            if not isinstance(parsed, dict):
                raise ValueError("Expected JSON object")
            team_record.update({f: parsed.get(f, "") for f in FIELDS})
            team_record["error"] = None
        except (ValueError, TypeError) as exc:
            team_record["error"] = str(exc)
        team_predictions.append(team_record)
        error, tags = None, None
        try:
            tags = json.loads(text)
            if not isinstance(tags, dict) or set(tags) != set(FIELDS) or any(
                    tags[f] not in CONFIG["taxonomy"][f] for f in FIELDS):
                raise ValueError("Wrong JSON keys or out-of-taxonomy label")
            valid += 1
        except (ValueError, TypeError) as exc:
            error, tags = str(exc), None
        matches = {f: bool(tags is not None and tags[f] == row["tags"][f]) for f in FIELDS}
        correct.update({f: int(v) for f, v in matches.items()})
        exact += int(all(matches.values()))
        predictions.append({"file_name": row["chunk"]["file_name"], "chunk_id": row["chunk"]["chunk_id"],
                            "expected": row["tags"], "tags": tags, "raw_response": text,
                            "error": error, "matches": matches})
        print(f"{i}/{len(rows)}: exact matches {exact}, valid JSON {valid}", flush=True)
    write_jsonl(out / "predictions.jsonl", predictions)
    write_jsonl(out / "team_predictions.jsonl", team_predictions)
    write_json(out / "metrics.json", {
        "base_model": MODEL, "revision": revision, "adapter": args.adapter, "precision": "BF16",
        "data_manifest_sha256": sha(Path(args.data) / "manifest.json"), "mode": manifest["mode"],
        "rows": len(rows), "valid_json": valid, "exact_match": exact,
        "exact_match_pct": 100 * exact / len(rows),
        "per_field_accuracy_pct": {f: 100 * correct[f] / len(rows) for f in FIELDS},
        "scoring": "strict JSON and exact taxonomy strings; invalid output counts as wrong for all fields",
    })
    print((out / "metrics.json").read_text())


def merge(args):
    revision = adapter_revision(args)
    gpu_guard(args.min_free_gib)
    out = new_output(args.out, args.repo)
    if shutil.disk_usage(out).free < 12 * 1024**3:
        fail("Need at least 12 GiB free disk for a merged BF16 checkpoint.")
    from peft import PeftModel
    model = PeftModel.from_pretrained(load_model(revision, quantized=False), args.adapter)
    merged = model.merge_and_unload(safe_merge=True)
    merged.save_pretrained(out, safe_serialization=True, max_shard_size="4GB")
    get_tokenizer(revision).save_pretrained(out)
    # Multimodal serving engines may initialize these processors even for text
    # requests. Preserve them from the same base revision as the frozen encoder.
    from huggingface_hub import hf_hub_download
    for name in ("preprocessor_config.json", "video_preprocessor_config.json"):
        shutil.copy2(hf_hub_download(MODEL, name, revision=revision), out / name)
    shutil.copy2(Path(args.adapter) / "run.json", out / "finetune_run.json")
    print(f"Merged BF16 checkpoint: {out}. This command does not deploy it.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name, fn in [("label-sheet", label_sheet), ("prepare", prepare), ("check", check),
                     ("train", train), ("evaluate", evaluate), ("merge", merge)]:
        s = sub.add_parser(name, help=fn.__name__)
        s.set_defaults(func=fn)
        if name in {"label-sheet", "prepare", "merge"}:
            s.add_argument("--repo", type=Path, default=DEFAULT_REPO)
        if name in {"label-sheet", "prepare"}:
            s.add_argument("--benchmark", type=Path, help="Defaults to REPO/evaluation/eval_sample.csv")
        if name != "check":
            s.add_argument("--out", required=True, help="New output directory; existing paths are refused")
        if name in {"check", "train", "evaluate"}:
            s.add_argument("--data", required=True)
            s.add_argument("--max-length", type=int, default=2048)
        if name in {"check", "train", "evaluate", "merge"}:
            s.add_argument("--revision", default=REVISION, help="Pinned HF revision; adapters reuse their recorded base revision")
        if name in {"train", "evaluate", "merge"}:
            s.add_argument("--min-free-gib", type=float, default=12,
                           help="Startup VRAM guard; memory fit still requires a smoke test")
        if name in {"evaluate", "merge"}:
            s.add_argument("--adapter", required=(name == "merge"), help="Omit for base-model evaluation")
        if name in {"prepare", "train"}:
            s.add_argument("--seed", type=int, default=42)
        if name == "prepare":
            s.add_argument("--labels", type=Path)
            s.add_argument("--label-provenance", default="provided labels; source not specified")
        if name == "train":
            s.add_argument("--epochs", type=float, default=3.)
            s.add_argument("--max-steps", type=int, default=-1, help="2 gives a disposable training smoke test")
            s.add_argument("--learning-rate", type=float, default=5e-5)
            s.add_argument("--rank", type=int, default=8)
    args = p.parse_args()
    if hasattr(args, "benchmark") and args.benchmark is None:
        args.benchmark = args.repo / "evaluation/eval_sample.csv"
    if hasattr(args, "max_length") and args.max_length < 256:
        p.error("--max-length must be at least 256")
    if args.command == "train" and (args.epochs <= 0 or args.learning_rate <= 0 or args.rank <= 0):
        p.error("Epochs, learning rate, and rank must be positive")
    try:
        args.func(args)
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        p.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
