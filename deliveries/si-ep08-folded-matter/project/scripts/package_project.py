#!/usr/bin/env python3
"""Create an inspectable editable-source ZIP; movies and local failed captures stay separate."""
from pathlib import Path
import hashlib,json,zipfile

P=Path(__file__).resolve().parents[1];W=P.parent
output=W/'si-ep08-folded-matter-project.zip';report=W/'review/package-integrity.json'
assert not output.exists() and not report.exists(),'Refusing to replace a source archive'
files=[]
for f in sorted(W.rglob('*')):
    if not f.is_file():continue
    r=f.relative_to(W)
    if any(x in r.parts for x in ['node_modules','__pycache__','local-failed']):continue
    if f.suffix.lower() in ['.mp4','.mov','.webm','.zip','.pyc','.log','.failed','.superseded']:continue
    if r.parts[0]=='review' and f.name.startswith('source-') and f.suffix=='.png':continue
    if r.parts[0]=='review' and any(x.startswith('quote-patch-') for x in r.parts) and f.name.startswith('frame-') and f.suffix=='.png':continue
    if f==report or f.name.startswith('.'):continue
    files.append((f,r.as_posix()))
hashes={name:hashlib.sha256(f.read_bytes()).hexdigest() for f,name in files}
with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for f,name in files:z.write(f,name)
with zipfile.ZipFile(output) as z:
    assert z.testzip() is None
    assert z.namelist()==list(hashes)
    for name,sha in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==sha
record={'status':'PASS','archive':output.name,'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'fileCount':len(files),'filesSHA256':hashes,'validation':'ZIP CRC plus SHA-256 of every uncompressed member; exact relative paths.','exclusions':['final and preview movies','local failed/superseded captures','rebuildable dependencies/cache','full-size intermediate source stills'],'scope':'Editable project, source script, cached provider cues, PCM stems/master, subtitles and compact QA as captured at packaging. Later archive/backup receipts remain in Git.'}
report.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['status','archive','bytes','sha256','fileCount']}))
