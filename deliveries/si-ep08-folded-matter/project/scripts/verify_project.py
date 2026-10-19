#!/usr/bin/env python3
"""Source/timeline guards; no media quality or human acceptance inference."""
from pathlib import Path
import json,re
P=Path(__file__).resolve().parents[1]
t=json.loads((P/'timeline.json').read_text()); assert t['totalFrames']==7200 and t['fps']==60
assert t['shots'][0]['startFrame']==0 and t['shots'][-1]['endFrame']==7200
assert all(a['endFrame']==b['startFrame'] for a,b in zip(t['shots'],t['shots'][1:]))
for p in (P/'src').glob('*.ts*'):
 s=p.read_text(); assert not re.search(r'Math\.random\s*\(|Date\.now\s*\(|setInterval\s*\(',s),p
s=(P/'src/Film.tsx').read_text()
for term in ['EUCLIDEAN','TOPOLOGICAL','OPTIMIZATION','BIOMIMETIC','GEOMETRY']: assert term in s,term
assert all(term not in s for term in ['TOPOLOGCAL','OPTIMIZATON','BIOMIMTIC','EUCLIDIAN','GEOMTRY'])
timing=json.loads((P/'audio-timing.json').read_text())
if timing['segments']:
 assert len(timing['segments'])==10
 for c in timing['captions']:
  assert 0<=c['startFrame']<c['endFrame']<=7200
  lines=c['text'].split('\n'); assert len(lines)<=2
  assert all(len(x)<=14 for x in lines),(c['text'],len(c['text']))
 assert all(a['endFrame']<=b['startFrame'] for a,b in zip(timing['captions'],timing['captions'][1:]))
else: print('Audio captions pending; source-only evidence')
print('PASS source timeline, deterministic source, telemetry lexicon, caption bounds when available')
