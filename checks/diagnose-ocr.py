#!/usr/bin/env python3
"""同じ画像をCPU/GPUで処理し、OCRの中間値を比較する。"""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import onnxruntime as ort
from PIL import Image
from immich_ml.models.ocr.detection import TextDetector
from immich_ml.models.ocr.recognition import TextRecognizer
from immich_ml.models.ocr.ctc import CtcDecoder
from immich_ml.sessions.ort import OrtSession

parser = argparse.ArgumentParser()
parser.add_argument('--backend', choices=['cpu', 'gpu'], required=True)
parser.add_argument('--images', nargs='+', default=['license-sample.png', 'app-preview-license-sample.jpeg'])
parser.add_argument('--label')
parser.add_argument('--model', default='PP-OCRv5_server')
parser.add_argument('--profile', action='store_true')
args = parser.parse_args()

def stats(a):
    finite = np.isfinite(a)
    values = a[finite]
    return {'shape': list(a.shape), 'dtype': str(a.dtype), 'nonfinite': int((~finite).sum()),
            'min': float(values.min()) if values.size else None,
            'max': float(values.max()) if values.size else None,
            'mean': float(values.mean()) if values.size else None}

class TraceSession:
    def __init__(self, inner, kind):
        self.inner, self.kind, self.calls = inner, kind, []
    def __getattr__(self, name):
        return getattr(self.inner, name)
    def run(self, names, inputs, *a):
        started = time.monotonic()
        outputs = self.inner.run(names, inputs, *a)
        row = {'stage': self.kind, 'inputs': {k: stats(v) for k, v in inputs.items()},
               'outputs': [stats(v) for v in outputs], 'seconds': round(time.monotonic()-started, 3)}
        self.calls.append(row)
        print(json.dumps(row), flush=True)
        return outputs

detector, recognizer = TextDetector(args.model), TextRecognizer(args.model)
providers = ['CPUExecutionProvider'] if args.backend == 'cpu' else ['MIGraphXExecutionProvider', 'CPUExecutionProvider']
def make_session(path, stage):
    options = None
    if args.profile:
        options = ort.SessionOptions()
        options.enable_profiling = True
        options.profile_file_prefix = '/tmp/immich-ocr-check/profile-' + (args.label or args.backend) + '-' + stage
        options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
    return TraceSession(OrtSession(path, providers=providers, sess_options=options), stage)

ds = make_session(detector.model_path, 'detection')
rs = make_session(recognizer.model_path, 'recognition')
detector = TextDetector(args.model, session=ds)
recognizer = TextRecognizer(args.model, session=rs)
recognizer.decoder = CtcDecoder(rs.get_metadata()['character'].splitlines())
result = {'model': args.model, 'backend': args.backend, 'samples': []}
for filename in args.images:
    print('IMAGE ' + filename, flush=True)
    img = Image.open(Path('/tmp/immich-ocr-check') / filename).convert('RGB')
    boxes = detector.predict(img, maxResolution=736, minScore=0.5)
    row = {'filename': filename, 'boxes': len(boxes['boxes']), 'detectionScores': boxes['scores'].tolist()}
    output = recognizer.predict(img, boxes, minScore=-1)
    accepted = [text for text, score in zip(output['text'], output['textScore']) if score > 0.8]
    row.update({'recognitionScores': output['textScore'].tolist(), 'textLengths': list(map(len, output['text'])),
                'hasLicenseTitle': any('運転免許証' in x for x in output['text']),
                'acceptedLines': len(accepted), 'acceptedCharacters': sum(map(len, accepted)),
                'keywords': {word: any(word in text for text in accepted) for word in ['運転免許証', '免許', 'お荷物', 'お届け']}})
    row['traces'] = ds.calls + rs.calls
    ds.calls, rs.calls = [], []
    result['samples'].append(row)
    Path('/tmp/immich-ocr-check/diagnose-' + (args.label or args.backend) + '.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('RESULT ' + json.dumps(row, ensure_ascii=False), flush=True)
if args.profile:
    result['profiles'] = {}
    for session in [ds, rs]:
        filename = session.inner.session.end_profiling()
        events = json.loads(Path(filename).read_text())
        counts = {}
        for event in events:
            provider = event.get('args', {}).get('provider')
            if provider:
                counts[provider] = counts.get(provider, 0) + 1
        result['profiles'][session.kind] = {'path': filename, 'providerEvents': counts}
    Path('/tmp/immich-ocr-check/diagnose-' + (args.label or args.backend) + '.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('PROFILES ' + json.dumps(result['profiles']), flush=True)
