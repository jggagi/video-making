#!/usr/bin/env python3
"""Collect encoded portrait evidence before publication, reusing the full QA collector."""
from pathlib import Path
from datetime import datetime,timezone
import json
import collect_qa as qa
W=qa.DELIVERY_DIR
manifest=qa.read_json(W/'delivery.json','delivery manifest')
media=W/manifest['outputs']['xiaohongshu']['path']
master=W/manifest['audio']['master']
if not media.is_file() or not master.is_file():raise SystemExit('Final portrait/master missing')
stage=W/'review/portrait-prepublication-evidence';rev=2
while stage.exists():
 stage=W/f'review/portrait-prepublication-evidence-r{rev:02}';rev+=1
stage.mkdir(parents=True)
mods=qa.image_modules();np=mods[0];ff=qa.require_tool('ffmpeg');fp=qa.require_tool('ffprobe')
before=qa.file_identity(media)
report,frames=qa.collect_layout(layout='portrait',media=media,ffmpeg=ff,ffprobe=fp,master=master,numpy=np,modules=mods,stage=stage)
comparisons=[qa.compare_audio_window(np,ff,master,media,t) for t in (2,44,98,116)]
if qa.file_identity(media)!=before:raise SystemExit('Portrait changed during collection')
result={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Encoded portrait measurements and representative/paired-frame evidence, not human listening or device acceptance','portrait':report,'audio_window_comparisons':comparisons}
(W/'review/portrait-prepublication-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'evidence_collected','sha256':before[1],'ebur128':report['media']['ebur128'],'correlations':[x['correlation'] for x in comparisons],'contact_sheet':report['contact_sheet']},ensure_ascii=False,indent=2))
