#!/usr/bin/env python3
"""BF16 LoRA experiment with development-only selection and a later test gate."""
import argparse
from collections import Counter
import importlib.metadata
import json
from pathlib import Path
import shutil
import time
import torch
from peft import PeftModel
from transformers import Trainer, TrainingArguments, set_seed
import finetune as ft

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'experiment-plan.json').read_text())

def predict(model, tokenizer, rows, output):
    output.mkdir(exist_ok=False, parents=True)
    model.eval()
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    model.config.text_config.use_cache = True
    predictions = []
    correct = Counter()
    exact = valid = 0
    start = time.time()
    for i, row in enumerate(rows, 1):
        prompt = tokenizer.apply_chat_template(ft.messages(row['chunk']), tokenize=False,
                                              add_generation_prompt=True, enable_thinking=False)
        inputs = tokenizer(prompt, add_special_tokens=False, return_tensors='pt').to(model.device)
        with torch.inference_mode():
            generated = model.generate(**inputs, do_sample=False, max_new_tokens=200,
                                       pad_token_id=tokenizer.pad_token_id, use_cache=True)
        text = tokenizer.decode(generated[0, inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()
        tags, error = None, None
        try:
            tags = json.loads(text)
            if not isinstance(tags, dict) or set(tags) != set(ft.FIELDS):
                raise ValueError('Wrong JSON shape')
            if any(tags[f] not in ft.CONFIG['taxonomy'][f] for f in ft.FIELDS):
                raise ValueError('Out-of-taxonomy value')
            valid += 1
        except (ValueError, TypeError) as e:
            error, tags = str(e), None
        matches = {f: bool(tags and tags[f] == row['tags'][f]) for f in ft.FIELDS}
        correct.update({f: int(v) for f, v in matches.items()})
        exact += int(all(matches.values()))
        predictions.append({'file_name': row['chunk']['file_name'], 'chunk_id': row['chunk']['chunk_id'],
                            'expected': row['tags'], 'tags': tags, 'raw_response': text,
                            'error': error, 'matches': matches})
        ft.write_jsonl(output / 'predictions.jsonl', predictions)
        print(output.name, i, '/', len(rows), 'exact', exact, flush=True)
    metrics = {'rows': len(rows), 'exact_match': exact, 'valid_json': valid,
               'field_correct': dict(correct), 'total_field_correct': sum(correct.values()),
               'exact_match_pct': 100 * exact / len(rows),
               'elapsed_seconds': time.time()-start, 'precision': 'BF16', 'batch_size': 1,
               'do_sample': False, 'enable_thinking': False, 'max_new_tokens': 200}
    ft.write_json(output / 'metrics.json', metrics)
    return metrics

def train():
    data = ROOT / 'prepared'
    gate = json.loads((data / 'training-approved.json').read_text())
    for split in ['train', 'validation']:
        assert ft.sha(data / f'{split}.jsonl') == gate[f'{split}_sha256'], 'Data changed after approval'
    assert ft.sha(ROOT / 'task_config.json') == gate['task_config_sha256']
    assert not (ROOT / 'benchmark.jsonl').exists(), 'Benchmark must not be uploaded until selection is frozen'
    assert not (ROOT / 'fresh-check.jsonl').exists(), 'Fresh check must remain local until selection is frozen'
    ft.gpu_guard(30)
    set_seed(42)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    tok = ft.get_tokenizer(PLAN['revision'])
    train_rows = ft.read_jsonl(data / 'train.jsonl')
    dev_rows = ft.read_jsonl(data / 'validation.jsonl')
    encoded = [ft.encode(r, tok, 2048) for r in train_rows]
    for r in dev_rows:
        ft.encode(r, tok, 2048)
    model = ft.load_model(PLAN['revision'], quantized=False)
    baseline = predict(model, tok, dev_rows, ROOT / 'development-base')
    model = ft.add_lora(model, rank=8)
    model.enable_input_require_grads()
    model.print_trainable_parameters()
    model.train()
    model.config.use_cache = False
    model.config.text_config.use_cache = False
    settings = TrainingArguments(
        output_dir=str(ROOT / 'checkpoints'), num_train_epochs=3,
        per_device_train_batch_size=2, gradient_accumulation_steps=4,
        learning_rate=2e-5, lr_scheduler_type='cosine', warmup_ratio=.1,
        weight_decay=.01, max_grad_norm=1., bf16=True, tf32=True,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={'use_reentrant': False},
        optim='adamw_torch', eval_strategy='no', save_strategy='epoch',
        save_total_limit=3, save_only_model=True, logging_steps=1,
        report_to='none', push_to_hub=False, seed=42, data_seed=42,
        dataloader_num_workers=0, remove_unused_columns=False, label_names=['labels'],
    )
    class AnswerOnlyTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            outputs = model(**ft.answer_only_inputs(inputs))
            return (outputs.loss, outputs) if return_outputs else outputs.loss
    trainer = AnswerOnlyTrainer(model=model, args=settings, train_dataset=encoded,
                               processing_class=tok, data_collator=ft.collator(tok))
    trainer.model_accepts_loss_kwargs = False
    provenance = {
        'base_model': PLAN['model'], 'revision': PLAN['revision'],
        'experiment_plan_sha256': ft.sha(ROOT / 'experiment-plan.json'),
        'runner_sha256': ft.sha(ROOT / 'cloud_run.py'),
        'helper_sha256': ft.sha(ROOT / 'finetune.py'),
        'approval': gate, 'hyperparameters': PLAN['hyperparameters'],
        'gpu': torch.cuda.get_device_name(0),
        'packages': {p: importlib.metadata.version(p) for p in ['torch','transformers','peft','accelerate','bitsandbytes']}}
    ft.write_json(ROOT / 'run.json', provenance)
    result = trainer.train()
    ft.write_json(ROOT / 'training-metrics.json', result.metrics)
    ft.write_json(ROOT / 'gpu-memory.json', {'peak_allocated_gib': torch.cuda.max_memory_allocated()/1024**3,
                                          'peak_reserved_gib': torch.cuda.max_memory_reserved()/1024**3})
    trainer.save_state()
    candidates = [{'checkpoint': 'base', 'epoch': 0, 'metrics': baseline}]
    checkpoint_paths = sorted((ROOT / 'checkpoints').glob('checkpoint-*'), key=lambda p: int(p.name.split('-')[-1]))
    for i, path in enumerate(checkpoint_paths, 1):
        model.load_adapter(path, adapter_name=f'epoch{i}', is_trainable=False)
        model.set_adapter(f'epoch{i}')
        metrics = predict(model, tok, dev_rows, ROOT / f'development-epoch-{i}')
        candidates.append({'checkpoint': str(path.relative_to(ROOT)), 'epoch': i, 'metrics': metrics})
    selected = max(candidates[1:], key=lambda c: (c['metrics']['exact_match'], c['metrics']['total_field_correct'], -c['epoch']))
    development_gate = (selected['metrics']['exact_match'], selected['metrics']['total_field_correct']) >= (baseline['exact_match'], baseline['total_field_correct'])
    selection = {'rule': PLAN['selection'], 'candidates': candidates, 'selected': selected,
                 'benchmark_accessed': False, 'selected_at_utc_epoch': time.time(),
                 'development_gate_passed': development_gate,
                 'training_approval_sha256': ft.sha(data / 'training-approved.json')}
    if selected['checkpoint'] != 'base':
        shutil.copytree(ROOT / selected['checkpoint'], ROOT / 'selected-adapter')
        shutil.copy2(ROOT / 'run.json', ROOT / 'selected-adapter/run.json')
        tok.save_pretrained(ROOT / 'selected-adapter')
        selection['adapter_sha256'] = ft.sha(ROOT / 'selected-adapter/adapter_model.safetensors')
    ft.write_json(ROOT / 'selection.json', selection)
    print('Selection frozen:', selected, flush=True)
    (ROOT / 'TRAINING_COMPLETE').write_text('development selection frozen; benchmark remains unevaluated\n')

def benchmark():
    selection = json.loads((ROOT / 'selection.json').read_text())
    assert selection['benchmark_accessed'] is False
    gate = json.loads((ROOT / 'benchmark-approved.json').read_text())
    assert ft.sha(ROOT / 'selection.json') == gate['selection_sha256']
    assert ft.sha(ROOT / 'benchmark.jsonl') == gate['benchmark_sha256']
    assert ft.sha(ROOT / 'fresh-check.jsonl') == gate['fresh_check_sha256']
    if selection['selected']['checkpoint'] != 'base':
        assert ft.sha(ROOT / 'selected-adapter/adapter_model.safetensors') == selection['adapter_sha256']
    ft.gpu_guard(20)
    set_seed(42)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    rows = ft.read_jsonl(ROOT / 'benchmark.jsonl')
    fresh_rows = ft.read_jsonl(ROOT / 'fresh-check.jsonl')
    assert len(rows) == 85
    tok = ft.get_tokenizer(PLAN['revision'])
    model = ft.load_model(PLAN['revision'], quantized=False)
    base = predict(model, tok, rows, ROOT / 'benchmark-base')
    fresh_base = predict(model, tok, fresh_rows, ROOT / 'fresh-base')
    candidate = fresh_candidate = None
    if selection['selected']['checkpoint'] != 'base':
        model = PeftModel.from_pretrained(model, ROOT / 'selected-adapter', is_trainable=False)
        # Measure the standalone BF16 form the team would actually serve.
        model = model.merge_and_unload(safe_merge=True)
        candidate = predict(model, tok, rows, ROOT / 'benchmark-selected')
        fresh_candidate = predict(model, tok, fresh_rows, ROOT / 'fresh-selected')
    ft.write_json(ROOT / 'benchmark-result.json', {'baseline': base, 'selected': candidate,
                  'selection_sha256': gate['selection_sha256'], 'benchmark_sha256': gate['benchmark_sha256'],
                  'historical_benchmark_previously_observed': True,
                  'candidate_export_form': 'LoRA merged into native BF16 Qwen3.5-4B',
                  'fresh_baseline': fresh_base, 'fresh_selected': fresh_candidate,
                  'fresh_check_sha256': gate['fresh_check_sha256'],
                  'handoff_gate_passed': bool(selection['development_gate_passed'] and candidate
                                             and candidate['exact_match'] > base['exact_match']
                                             and fresh_candidate['exact_match'] >= fresh_base['exact_match'])})
    (ROOT / 'BENCHMARK_COMPLETE').write_text('final benchmark scored; do not retune against these results\n')

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['train', 'benchmark'])
    a = p.parse_args()
    if a.command == 'train': train()
    else: benchmark()
