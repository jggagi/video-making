#!/usr/bin/env python3
"""Reflow display phrases using measured PCM spans; preserves every audio file."""
from pathlib import Path
import json,hashlib,importlib.util,re
P=Path(__file__).resolve().parents[1];W=P.parent
spec=importlib.util.spec_from_file_location('audio_builder',P/'scripts/build_audio.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
layout=json.loads((P/'caption-layout.json').read_text());segments=json.loads((P/'segments.json').read_text())['segments'];timing=json.loads((P/'audio-timing.json').read_text())
strip=lambda x:re.sub(r'[\W_]+','',x,flags=re.UNICODE)
for s in segments:
 old=strip(''.join(s['chunks']));new=strip(''.join(layout[s['id']]))
 assert old==new,(s['id'],old,new)
 assert all(len(x)<=14 for x in layout[s['id']])
 s['chunks']=layout[s['id']]
# All narration wording and measured start/end samples remain intact.
timing['captions']=m.build_captions(segments,timing['segments']);timing['captionLayout']={'path':'project/caption-layout.json','sha256':hashlib.sha256((P/'caption-layout.json').read_bytes()).hexdigest(),'reason':'Natural Chinese phrase boundaries; no word split by character-count slicing; audio unchanged.'}
(P/'audio-timing.json').write_text(json.dumps(timing,ensure_ascii=False,indent=2)+'\n')
for platform in ['B站','小红书']:m.write_srt(W/platform/'captions.srt',timing['captions'])
print('Reflowed',len(timing['captions']),'captions; unchanged PCM')
