#!/usr/bin/env python3
"""専用インスタンスのGPU推論とアプリ経由の保存・検索・再起動を検証する。"""
import argparse
import getpass
import importlib.util
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import struct
import zlib
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manager', ROOT / 'scripts/manage.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--initialize-test-admin', action='store_true')
args = parser.parse_args()
directory = args.directory.expanduser().resolve()
state = m.load_instance(directory)
m.check_project(directory, state['project'])
base = 'http://127.0.0.1:' + str(state['port']) + '/api'
token = None
evidence = directory / 'evidence'
evidence.mkdir(exist_ok=True)

def api(path, body=None, method=None, headers=None):
    headers = dict(headers or {})
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if isinstance(body, dict):
        body = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    with urllib.request.urlopen(urllib.request.Request(base + path, data=body, headers=headers, method=method), timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if raw else None

def sql(query):
    return m.capture(m.compose(directory, 'exec', '-T', 'database', 'psql', '-X', '-q', '-U', 'postgres', '-d', 'immich', '-At', '-v', 'ON_ERROR_STOP=1'), input='BEGIN READ ONLY;\n'+query+'\nCOMMIT;\n')

def upload(path):
    boundary = uuid.uuid4().hex
    parts = []
    for name in ['fileCreatedAt','fileModifiedAt']:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n2026-10-10T00:00:00.000Z\r\n'.encode())
    # ピクセルは変えずに毎回異なる識別子を付け、既存画像の重複判定を避ける。
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n' or data[-8:-4] != b'IEND':
        raise ValueError('検証用PNGの形式が不正です')
    text = b'Comment\x00' + uuid.uuid4().hex.encode()
    chunk = b'tEXt' + text
    data = data[:-12] + struct.pack('>I',len(text)) + chunk + struct.pack('>I',zlib.crc32(chunk)&0xffffffff) + data[-12:]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="assetData"; filename="{path.name}"\r\nContent-Type: image/png\r\n\r\n'.encode()+data+b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return str(uuid.UUID(api('/assets', b''.join(parts), headers={'Content-Type':'multipart/form-data; boundary='+boundary})['id']))

def wait_for(check, description, seconds=900):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        result = check()
        if result:
            return result
        time.sleep(5)
    raise TimeoutError(description + 'が時間内に完了しませんでした')

def exec_ml(*command):
    m.run(m.compose(directory, 'exec', '-T', 'immich-machine-learning', *command))

credential_file = directory / 'test-admin-credentials.json'
if args.initialize_test_admin:
    user_count = int(sql('SELECT count(*) FROM "user";'))
    if credential_file.exists():
        credentials = json.loads(credential_file.read_text())
    else:
        # 既存ユーザーがいる環境では管理者を作成しない。
        if user_count != 0:
            raise ValueError('ユーザーが登録済みです。テスト管理者の自動作成は新規環境専用です')
        credentials = {'email':'gpu-test@example.invalid', 'password':secrets.token_urlsafe(30), 'name':'GPU検証用管理者'}
        fd = os.open(credential_file, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(credentials,stream)
    if user_count == 0:
        api('/auth/admin-sign-up', credentials)
else:
    credentials = {'email':input('この環境の管理者メール: '), 'password':getpass.getpass('パスワード: ')}
token = api('/auth/login', {k:credentials[k] for k in ['email','password']})['accessToken']
config = api('/system-config')
assert config['machineLearning']['ocr']['modelName'] == 'PP-OCRv5_mobile'
assert config['machineLearning']['facialRecognition']['modelName'] == 'buffalo_l'
assert config['machineLearning']['clip']['modelName'] == 'ViT-B-32__openai'
for key in ['ocr','facialRecognition','clip']:
    assert config['machineLearning'][key]['enabled'], key

print('OCRのCPU/GPU比較と実行プロファイルを確認します', flush=True)
exec_ml('mkdir','-p','/tmp/immich-ocr-check')
exec_ml('cp','/opt/immich-m75q/samples/license-sample.png','/opt/immich-m75q/samples/blank.png','/tmp/immich-ocr-check/')
for backend in ['cpu','gpu']:
    command = ['python','/opt/immich-m75q/checks/diagnose-ocr.py','--backend',backend,'--label',backend,'--model','PP-OCRv5_mobile','--images','license-sample.png','blank.png']
    if backend == 'gpu':
        command.append('--profile')
    exec_ml(*command)
exec_ml('python','/opt/immich-m75q/checks/compare-ocr.py','/tmp/immich-ocr-check')
print('顔検出・顔特徴抽出・画像検索のCPU/GPU比較を確認します', flush=True)
for backend in ['cpu','gpu']:
    exec_ml('python','/opt/immich-m75q/checks/profile-face-clip.py','--backend',backend)
m.run(m.compose(directory, 'cp', 'immich-machine-learning:/tmp/immich-ocr-check/.', str(evidence / 'inference')))
cpu = json.loads((evidence/'inference/face-clip-cpu.json').read_text())
gpu = json.loads((evidence/'inference/face-clip-gpu.json').read_text())
assert cpu['faces'] == gpu['faces'] and cpu['faces'] >= 1
similarities = {}
for key, a, b in [('face',cpu['faceVectors'][0],gpu['faceVectors'][0]), *[(key,cpu[key],gpu[key]) for key in ['clip-visual','clip-textual']]]:
    cosine = sum(x*y for x,y in zip(a,b)) / math.sqrt(sum(x*x for x in a)*sum(y*y for y in b))
    assert cosine > 0.99, (key,cosine)
    similarities[key] = cosine

results = {'status':'running','image':state['image'],'ocrModel':'PP-OCRv5_mobile','cosineSimilarities':similarities,'rounds':[]}
for round_number in range(2):
    if round_number:
        print('推論コンテナを再起動し、別の画像でも再検証します', flush=True)
        m.run(m.compose(directory,'restart','immich-machine-learning'))
        m.run(m.compose(directory,'up','-d','--wait','--wait-timeout','600','immich-machine-learning'))
    suffix = '-after-restart' if round_number else ''
    license_id = upload(ROOT/'samples'/('license-sample'+suffix+'.png'))
    blank_id = upload(ROOT/'samples'/('blank'+suffix+'.png'))
    face_id = upload(ROOT/'samples/astronaut.png')
    for asset_id in [license_id,blank_id,face_id]:
        wait_for(lambda: sql(f'SELECT ("ocrAt" IS NOT NULL)::int FROM asset_job_status WHERE "assetId"=\'{asset_id}\';') == '1', 'OCR保存')
    lines = api('/assets/'+license_id+'/ocr')
    text = '\n'.join(row['text'] for row in lines)
    assert '運転免許証' in text
    assert api('/assets/'+blank_id+'/ocr') == []
    found = wait_for(lambda: any(x['id']==license_id for x in api('/search/metadata',{'ocr':'運転免許証','size':100})['assets']['items']), 'OCR検索')
    face_count = wait_for(lambda: int(sql(f'SELECT count(*) FROM asset_face WHERE "assetId"=\'{face_id}\';')), '顔情報の保存')
    wait_for(lambda: sql(f'SELECT ("facesRecognizedAt" IS NOT NULL)::int FROM asset_job_status WHERE "assetId"=\'{face_id}\';') == '1', '顔認識ジョブの完了')
    wait_for(lambda: int(sql(f'SELECT count(*) FROM smart_search WHERE "assetId"=\'{face_id}\';')) == 1, 'スマート検索の特徴保存')
    round_result = {'assetIds':[license_id,blank_id,face_id], 'smartSearchStored':True, 'afterRestart':bool(round_number),'ocrLines':len(lines),'ocrCharacters':sum(len(x['text']) for x in lines),'blankLines':0,'ocrSearch':bool(found),'facesStored':face_count}
    results['rounds'].append(round_result)
    (evidence/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(round_result,ensure_ascii=False), flush=True)
results['status']='passed'
(evidence/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print('検証合格: GPU推論、CPU比較、アプリ保存・OCR検索、再起動後を確認しました',flush=True)
