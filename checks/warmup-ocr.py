#!/usr/bin/env python3
"""画像をアップロードする前に、設定したOCR入力サイズをGPU用に準備する。"""
import os
import time
import numpy as np
from immich_ml.models.ocr.detection import TextDetector
from immich_ml.models.ocr.recognition import TextRecognizer
from immich_ml.sessions.ort import OrtSession

model_name = os.getenv('OCR_TEST_MODEL', 'PP-OCRv5_mobile')
canvas = int(os.environ['MACHINE_LEARNING_OCR_CANVAS_SIZE'])
step = int(os.environ['MACHINE_LEARNING_OCR_WIDTH_STEP'])
batch = int(os.environ['MACHINE_LEARNING_MAX_BATCH_SIZE__OCR'])
assert batch == 1, 'この準備スクリプトはOCRバッチ1を対象としています'
for model, shapes in [(TextDetector(model_name), [(1,3,canvas,canvas)]),
                      (TextRecognizer(model_name), [(1,3,48,step),(1,3,48,step*2)])]:
    # 新規キャッシュでは、推論前に公式モデルを取得する。
    if not model.model_path.exists():
        model.download()
    session = OrtSession(model.model_path)
    assert 'MIGraphXExecutionProvider' in session.providers
    name = session.get_inputs()[0].name
    for shape in shapes:
        started = time.monotonic()
        print('GPU準備開始: '+model.model_type+' '+str(shape), flush=True)
        outputs = session.run(None, {name: np.zeros(shape, dtype=np.float32)})
        assert all(np.isfinite(value).all() for value in outputs)
        print('GPU準備完了: '+str(round(time.monotonic()-started,3))+'秒', flush=True)
