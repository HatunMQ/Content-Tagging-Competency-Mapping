#!/usr/bin/env python3
"""Export the frozen selected adapter as a standalone BF16 model, without deployment."""
import argparse
import json
from pathlib import Path
import shutil
import torch
from huggingface_hub import hf_hub_download
from peft import PeftModel
from transformers import Qwen3_5ForConditionalGeneration
import finetune as ft

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adapter', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    p.add_argument('--repo', type=Path, default=ft.DEFAULT_REPO)
    a = p.parse_args()
    selection = json.loads(a.selection.read_text())
    run = json.loads((a.adapter / 'run.json').read_text())
    assert ft.sha(a.adapter / 'adapter_model.safetensors') == selection['adapter_sha256']
    assert run['base_model'] == ft.MODEL and run['revision'] == ft.REVISION
    if a.device == 'cuda':
        ft.gpu_guard(20)
    out = ft.new_output(a.out, a.repo)
    if shutil.disk_usage(out).free < 12 * 1024**3:
        raise ValueError('At least 12 GiB of output-disk space is required')
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        ft.MODEL, revision=run['revision'], dtype=torch.bfloat16,
        device_map={'': a.device}, attn_implementation='sdpa')
    model = PeftModel.from_pretrained(model, a.adapter, is_trainable=False)
    model = model.merge_and_unload(safe_merge=True)
    model.save_pretrained(out, safe_serialization=True, max_shard_size='4GB')
    ft.get_tokenizer(run['revision']).save_pretrained(out)
    for name in ['preprocessor_config.json','video_preprocessor_config.json']:
        shutil.copy2(hf_hub_download(ft.MODEL, name, revision=run['revision']), out / name)
    ft.write_json(out / 'finetune-provenance.json', {
        'run': run, 'selection': selection, 'selection_sha256': ft.sha(a.selection),
        'export_device': a.device, 'precision': 'BF16', 'deployment_performed': False})
    hashes = {p.name: ft.sha(p) for p in sorted(out.iterdir()) if p.is_file()}
    ft.write_json(out / 'SHA256SUMS.json', hashes)
    print('Standalone BF16 model exported to', out)

if __name__ == '__main__':
    main()
