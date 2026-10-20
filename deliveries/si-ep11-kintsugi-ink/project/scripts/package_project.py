#!/usr/bin/env python3
"""Package editable sources, cached narration and compact QA without movies."""
from pathlib import Path
import hashlib,json,zipfile
P=Path(__file__).resolve().parents[1];W=P.parent
out=W/f'{W.name}-project.zip';report=W/'review/package-integrity.json'
assert not out.exists() and not report.exists(),'Refusing to replace an archive'
files=[]
for f in sorted(W.rglob('*')):
 if not f.is_file():continue
 r=f.relative_to(W)
 if any(x in r.parts for x in ['node_modules','__pycache__']):continue
 if r.as_posix()=='review/render-staging.json':continue
 if f.suffix.lower() in ['.mp4','.mov','.webm','.zip','.pyc','.log','.failed','.partial']:continue
 if r.parts[0]=='review' and f.suffix.lower()=='.png' and not f.name.startswith('encoded-native-') and (f.name.startswith(('source-','encoded-','native-')) or f.stat().st_size>1_000_000):continue
 if f==report or f.name.startswith('.'):continue
 files.append((f,r.as_posix()))
hashes={name:hashlib.sha256(f.read_bytes()).hexdigest() for f,name in files}
with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f,name in files:z.write(f,name)
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 assert set(z.namelist())==set(hashes)
 for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
r={'status':'PASS','archive':out.name,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'file_count':len(files),'member_sha256':hashes,'validation':'ZIP CRC and SHA256 of every uncompressed member, exact relative paths','exclusions':['encoded movies and previews','full native intermediate stills','host-specific review/render-staging.json pointer','dependencies/caches/transient logs'],'scope':'Sources, exact original narration, PCM stems/master, captions, cover, scripts and compact QA as packaged; cloud archive receipts maintained in Git'}
report.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:r[k] for k in ['status','archive','bytes','sha256','file_count']}))
