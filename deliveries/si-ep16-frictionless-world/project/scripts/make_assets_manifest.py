from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
entries=[]
for p in sorted(P.rglob('*')):
 if not p.is_file() or p.name=='assets-manifest.json' or any(x in p.parts for x in ['__pycache__','.remotion']):continue
 entries.append({'path':str(p.relative_to(P)),'bytes':p.stat().st_size,'sha256':sha(p),'origin':'Aliyun Bailian TTS' if '/public/audio/' in str(p) and any(x in p.parts for x in ['raw','canonical','cues']) else 'Code-generated original soundscape' if p.suffix=='.wav' else 'Original editable production source or metadata'})
(P/'assets-manifest.json').write_text(json.dumps({'version':1,'work':'si-ep16-frictionless-world','visualAssets':'All visuals are original deterministic SVG code; native vector resolution','voice':'Bailian cosyvoice-v3-flash / longtian_v3, per direct EP16 authorization','scoreAndSFX':'Deterministic original synthesized sound; no third-party music','entries':entries},ensure_ascii=False,indent=2)+'\n')
print(len(entries),'assets indexed')
