#!/usr/bin/env python3
"""同じ入力のCPU/GPU結果と、実際のGPU実行記録を確認する。"""
import json
from pathlib import Path
import sys
root = Path(sys.argv[1] if len(sys.argv) > 1 else 'evidence/ocr-check')
cpu = json.loads((root / 'diagnose-cpu.json').read_text())
gpu = json.loads((root / 'diagnose-gpu.json').read_text())
assert len(cpu['samples']) == len(gpu['samples']) == 2
for a, b in zip(cpu['samples'], gpu['samples']):
    for key in ['filename', 'acceptedLines', 'acceptedCharacters', 'keywords']:
        assert a[key] == b[key], (key, a[key], b[key])
    for trace in b['traces']:
        assert all(x['nonfinite'] == 0 for x in list(trace['inputs'].values()) + trace['outputs'])
assert gpu['samples'][0]['keywords']['運転免許証']
assert gpu['samples'][1]['acceptedLines'] == 0
for stage in ['detection', 'recognition']:
    counts = gpu['profiles'][stage]['providerEvents']
    assert counts.get('MIGraphXExecutionProvider', 0) > 0, (stage, counts)
    assert counts.get('CPUExecutionProvider', 0) == 0, (stage, counts)
print('CPU/GPUの一致、見本文字、白紙、検出・認識のGPU実行を確認しました')
