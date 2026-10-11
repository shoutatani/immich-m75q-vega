#!/usr/bin/env python3
"""3.3.1の公式推論をCPU/GPUで実行し、実際の実行プロファイルを確認する。"""
import argparse
from collections import Counter
import json
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image
from immich_ml.models.facial_recognition.detection import FaceDetector
from immich_ml.models.facial_recognition.recognition import FaceRecognizer
from immich_ml.models.clip.visual import OpenClipVisualEncoder
from immich_ml.models.clip.textual import OpenClipTextualEncoder
from immich_ml.models.ocr.detection import TextDetector
from immich_ml.models.ocr.recognition import TextRecognizer
from immich_ml.schemas import FaceDetectionOptions, FaceRecognitionOptions, VisualOptions, TextualOptions, TextDetectionOptions, TextRecognitionOptions
from immich_ml.sessions.ort import OrtSession, GraphSpec

parser=argparse.ArgumentParser()
parser.add_argument('--backend',choices=['cpu','gpu'],required=True)
parser.add_argument('--output',type=Path,default=Path('/tmp/immich-gpu-check'))
parser.add_argument('--warmup',action='store_true',help='見本のプレビュー相当サイズも事前準備する')
a=parser.parse_args()
samples=Path('/opt/immich-m75q/samples')
out=a.output;out.mkdir(parents=True,exist_ok=True)
providers=['CPUExecutionProvider'] if a.backend=='cpu' else ['MIGraphXExecutionProvider','CPUExecutionProvider']
original_session=GraphSpec.session
sequence=0

def profiled(self,graph,sess_options=None):
    global sequence
    sequence+=1
    opts=sess_options or self.sess_options()
    opts.enable_profiling=True
    opts.profile_file_prefix=str(out/f'{a.backend}-{sequence}')
    return original_session(self,graph,opts)
GraphSpec.session=profiled
results={'backend':a.backend,'profiles':{},'ocr':[]}

def prepare(model):
    model._make_session=lambda: OrtSession(model.model_path,model.shape_policy,providers=providers,threads=model.threads)
    model.load()
    return model

def finish(model,label):
    counts=Counter()
    for graph in model.session.graphs.values():
        path=graph._session.end_profiling()
        counts.update(e['args']['provider'] for e in json.loads(Path(path).read_text()) if e.get('args',{}).get('provider'))
    expected=providers[0]
    assert counts[expected]>0,(label,counts)
    if a.backend=='gpu': assert counts['CPUExecutionProvider']==0,(label,counts)
    results['profiles'][label]=dict(counts)
    print(json.dumps({'stage':label,'events':dict(counts)}),flush=True)

def vector(value):
    v=np.array(json.loads(value));assert v.shape==(512,) and np.isfinite(v).all();return v.tolist()

image=(samples/'astronaut.png').read_bytes()
detector=prepare(FaceDetector('buffalo_l'))
faces=detector.predict(image,options=FaceDetectionOptions())
assert len(faces['boxes'])>=1
finish(detector,'face-detection')
recognizer=prepare(FaceRecognizer('buffalo_l'))
features=recognizer.predict(image,faces,options=FaceRecognitionOptions())
results['faceVectors']=[vector(face['embedding']) for face in features]
results['faces']=len(features)
finish(recognizer,'face-recognition')
for cls,label,data,options in [(OpenClipVisualEncoder,'clip-visual',image,VisualOptions()),(OpenClipTextualEncoder,'clip-textual','an astronaut in a spacesuit',TextualOptions())]:
    model=prepare(cls('ViT-B-32__openai'))
    results[label]=vector(model.predict(data,options=options))
    finish(model,label)
textdetector=prepare(TextDetector('PP-OCRv5_mobile'))
textrecognizer=prepare(TextRecognizer('PP-OCRv5_mobile'))
for filename in ['license-sample.png','blank.png']:
    im=Image.open(samples/filename).convert('RGB')
    boxes=textdetector.predict(im,options=TextDetectionOptions())
    recognized=textrecognizer.predict(im,boxes,options=TextRecognitionOptions(min_score=0.8))
    texts=recognized['text']
    assert all(np.isfinite(recognized[key]).all() for key in ['box','boxScore','textScore'])
    if filename.startswith('license'): assert any('運転免許証' in t for t in texts),texts
    else: assert len(texts)==0,texts
    results['ocr'].append({'filename':filename,'texts':texts,'lines':len(texts),'characters':sum(map(len,texts))})
if a.warmup:
    # アプリが使うプレビューと正方形画像も、公式のサイズ選択で準備する。
    for filename in ['license-sample.png','license-sample-after-restart.png','astronaut.png']:
        im=Image.open(samples/filename).convert('RGB')
        # v3.3.1の標準プレビューは長辺1440・JPEG品質80。原寸のJPEGも準備する。
        scale=1440/max(im.size)
        previews=[]
        for sized in [im,im.resize(tuple(round(size*scale) for size in im.size),Image.Resampling.LANCZOS)]:
            encoded=BytesIO()
            sized.save(encoded,format='JPEG',quality=80)
            encoded.seek(0)
            previews.append(Image.open(encoded).convert('RGB'))
        for preview in previews:
            boxes=textdetector.predict(preview,options=TextDetectionOptions())
            recognized=textrecognizer.predict(preview,boxes,options=TextRecognitionOptions(min_score=0.8))
            assert all(np.isfinite(recognized[key]).all() for key in ['box','boxScore','textScore'])
        print('プレビュー相当のGPU準備完了: '+filename,flush=True)
finish(textdetector,'ocr-detection');finish(textrecognizer,'ocr-recognition')
(out/f'{a.backend}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'passed','backend':a.backend,'faces':results['faces'],'ocr':results['ocr']},ensure_ascii=False),flush=True)
