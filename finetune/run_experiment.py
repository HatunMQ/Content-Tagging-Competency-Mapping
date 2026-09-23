#!/usr/bin/env python3
"""Reproduce training and evaluation in a new directory, without touching services."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import finetune as ft

HERE = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True, help='New experiment directory outside the team repository')
    p.add_argument('--repo', type=Path, default=ft.DEFAULT_REPO, help='Protected original repository path')
    a = p.parse_args()
    gate = json.loads((HERE / 'prepared/training-approved.json').read_text())
    for split in ['train', 'validation']:
        if ft.sha(HERE / f'prepared/{split}.jsonl') != gate[f'{split}_sha256']:
            raise ValueError('Training data changed; rerun the overlap audit before training')
    test = HERE / 'evaluation/benchmark.jsonl'
    fresh = HERE / 'evaluation/fresh-check.jsonl'
    if ft.sha(test) != gate['protected_benchmark_sha256'] or ft.sha(fresh) != gate['protected_fresh_check_sha256']:
        raise ValueError('Reserved evaluation data differs from the audited split')
    out = ft.new_output(a.out, a.repo)
    for name in ['cloud_run.py','finetune.py','task_config.json','experiment-plan.json',
                 'summarize_results.py','team_compare_results.py','export_model.py']:
        shutil.copy2(HERE / name, out / name)
    shutil.copytree(HERE / 'prepared', out / 'prepared')
    subprocess.run([sys.executable, str(out / 'cloud_run.py'), 'train'], cwd=out, check=True)
    if not (out / 'TRAINING_COMPLETE').exists():
        raise RuntimeError('Training did not freeze a development-selected checkpoint')
    # Only now introduce test examples into the run directory.
    shutil.copy2(test, out / 'benchmark.jsonl')
    shutil.copy2(fresh, out / 'fresh-check.jsonl')
    ft.write_json(out / 'benchmark-approved.json', {
        'selection_sha256': ft.sha(out / 'selection.json'),
        'benchmark_sha256': ft.sha(out / 'benchmark.jsonl'),
        'fresh_check_sha256': ft.sha(out / 'fresh-check.jsonl')})
    subprocess.run([sys.executable, str(out / 'cloud_run.py'), 'benchmark'], cwd=out, check=True)
    subprocess.run([sys.executable, str(out / 'summarize_results.py')], cwd=out, check=True)
    result = json.loads((out / 'benchmark-result.json').read_text())
    print('Historical benchmark:', result['baseline']['exact_match'], '->', result['selected']['exact_match'], 'of 85')
    print('Fresh provisional check:', result['fresh_baseline']['exact_match'], '->', result['fresh_selected']['exact_match'], 'of 24')
    print('Handoff checks passed:', result['handoff_gate_passed'])
    print('Results:', out)
    if not result['handoff_gate_passed']:
        print('Retain the unchanged base model. This adapter did not pass the predeclared checks.')

if __name__ == '__main__':
    main()
