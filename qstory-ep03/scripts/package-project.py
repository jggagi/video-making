#!/usr/bin/env python3
"""Package only this film's editable sources/assets; MP4 remains a separate download."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'review/validation.json').read_text())
if report['mode']!='full' or report['summary']['failed'] or report['summary']['pending']:
    raise SystemExit('Final delivery validation must finish first.')
folders=['src','scripts','source','public/audio-bailian','review']
files=[ROOT/n for n in ['README.md','package.json','package-lock.json','tsconfig.json','watch.html']]
for d in folders:
    files.extend(p for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.tmp'])
files.extend(ROOT/'public/audio'/n for n in ['voice_zh.wav','music.wav','sfx.wav'])
files.append(ROOT/'out/QStory-EP03-zh.srt')
files=[p for p in files if p.name!='mix_pre_loudnorm.wav']
target=ROOT/'out/QStory-EP03-editable-project.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
    for p in sorted(set(files)):
        z.write(p,Path('qstory-ep03')/p.relative_to(ROOT))
    if z.testzip() is not None: raise SystemExit('ZIP integrity failed')
outputs=[ROOT/'out/QStory-EP03-十万亿个分身-4K.mp4',ROOT/'out/QStory-EP03-zh.srt',target]
lines=[]
for p in outputs:
    h=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
    lines.append(f'{h}  {p.name}')
(ROOT/'out/SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps({'zip':str(target),'bytes':target.stat().st_size,'files':len(set(files)),'zipIntegrity':'passed'},ensure_ascii=False))
