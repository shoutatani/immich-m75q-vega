"""CPU/GPUの認識内容・特徴量と実行イベントを照合する。"""
import argparse
import json,math
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory',type=Path)
root=parser.parse_args().directory
a=json.loads((root/'cpu.json').read_text());b=json.loads((root/'gpu.json').read_text())
assert a['faces']==b['faces'] and a['faces']>0
cosines={}
for key,x,y in [('face',a['faceVectors'][0],b['faceVectors'][0]),*[(k,a[k],b[k]) for k in ['clip-visual','clip-textual']]]:
 value=sum(i*j for i,j in zip(x,y))/math.sqrt(sum(i*i for i in x)*sum(j*j for j in y))
 assert value>.99,(key,value)
 cosines[key]=value
for item in b['ocr']:
 cpu=next(x for x in a['ocr'] if x['filename']==item['filename'])
 assert item['texts']==cpu['texts'],(item['filename'],item['texts'],cpu['texts'])
for label,counts in b['profiles'].items():
 assert counts.get('MIGraphXExecutionProvider',0)>0 and counts.get('CPUExecutionProvider',0)==0,(label,counts)
result={'status':'passed','cosineSimilarities':cosines,'profiles':b['profiles'],'ocr':b['ocr']}
(root/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
