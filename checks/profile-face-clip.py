#!/usr/bin/env python3
"""実際の顔画像で検出・特徴抽出・画像検索を実行し、GPU実行を記録する。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
import onnxruntime as ort
from immich_ml.models.facial_recognition.detection import FaceDetector
from immich_ml.models.facial_recognition.recognition import FaceRecognizer
from immich_ml.models.clip.visual import OpenClipVisualEncoder
from immich_ml.models.clip.textual import OpenClipTextualEncoder
from immich_ml.sessions.ort import OrtSession

parser = argparse.ArgumentParser()
parser.add_argument('--backend', choices=['cpu','gpu'], default='gpu')
args = parser.parse_args()
root = Path('/tmp/immich-ocr-check')
root.mkdir(exist_ok=True)
image = Path('/opt/immich-m75q/samples/astronaut.png').read_bytes()
providers = ['CPUExecutionProvider'] if args.backend == 'cpu' else ['MIGraphXExecutionProvider','CPUExecutionProvider']
results = {'backend': args.backend, 'profiles': {}}

def prepare(model, label):
    options = ort.SessionOptions()
    options.enable_profiling = True
    options.profile_file_prefix = str(root / (args.backend + '-' + label))
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    model._make_session = lambda path: OrtSession(path, providers=providers, sess_options=options)
    model.load()
    return model

def finish(model, label):
    path = model.session.session.end_profiling()
    counts = Counter(e['args']['provider'] for e in json.loads(Path(path).read_text()) if e.get('args',{}).get('provider'))
    expected = 'MIGraphXExecutionProvider' if args.backend == 'gpu' else 'CPUExecutionProvider'
    assert counts[expected] > 0, (label, counts)
    if args.backend == 'gpu':
        assert counts['CPUExecutionProvider'] == 0, (label, counts)
    results['profiles'][label] = dict(counts)

detector = prepare(FaceDetector('buffalo_l'), 'face-detection')
faces = detector.predict(image, minScore=0.7)
assert len(faces['boxes']) >= 1, '顔画像から顔が検出されませんでした'
finish(detector, 'face-detection')
recognizer = prepare(FaceRecognizer('buffalo_l'), 'face-recognition')
embeddings = recognizer.predict(image, faces)
for face in embeddings:
    vector = np.array(json.loads(face['embedding']))
    assert vector.shape == (512,) and np.isfinite(vector).all()
finish(recognizer, 'face-recognition')
results['faces'] = len(embeddings)
results['faceVectors'] = [json.loads(face['embedding']) for face in embeddings]
for cls, label, data in [(OpenClipVisualEncoder,'clip-visual',image), (OpenClipTextualEncoder,'clip-textual','an astronaut in a spacesuit')]:
    model = prepare(cls('ViT-B-32__openai'), label)
    vector = np.array(json.loads(model.predict(data)))
    assert vector.shape == (512,) and np.isfinite(vector).all()
    results[label] = vector.tolist()
    finish(model, label)
(root / ('face-clip-' + args.backend + '.json')).write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps({'backend': args.backend, 'faces': results['faces'], 'profiles':results['profiles']}), flush=True)
