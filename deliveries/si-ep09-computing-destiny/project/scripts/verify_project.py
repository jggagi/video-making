#!/usr/bin/env python3
"""Check the specific EP09 production invariants; not perceptual acceptance."""
from pathlib import Path
import json,hashlib,re,wave
P=Path(__file__).resolve().parents[1];W=P.parent
read=lambda p:json.loads(p.read_text())
m=read(W/'delivery.json');s=read(P/'segments.json');t=read(P/'audio-timing.json')
assert (m['duration_seconds'],m['fps'],m['total_frames'])==(90,60,5400)
assert m['platforms']==['xiaohongshu'] and set(m['outputs'])=={'xiaohongshu'}
assert m['outputs']['xiaohongshu']['width']==2160 and m['outputs']['xiaohongshu']['height']==3840
assert m['script']['sha256']==hashlib.sha256((W/m['script']['path']).read_bytes()).hexdigest()
assert [x['id'] for x in s]==[f'S{i:02}' for i in range(1,9)]
assert all(0<=x['startFrame']<x['endFrame']<=5400 for x in s)
assert all(a['endFrame']<=b['startFrame'] for a,b in zip(s,s[1:]))
assert not t.get('status','').startswith(('PREVIEW','preview'))
caps=t['captions'];assert caps
for c in caps:
 assert 0<=c['startFrame']<c['endFrame']<=5400
 assert 1<=len(c['text'].splitlines())<=2
 assert all(len(x)<=13 for x in c['text'].splitlines()),c
assert all(a['endFrame']<=b['startFrame'] for a,b in zip(caps,caps[1:]))
for src in (P/'src').glob('*'):
 if src.suffix in ('.ts','.tsx'):
  assert not re.search(r'Math\.random\s*\(|Date\.now\s*\(|setInterval\s*\(',src.read_text()),src
lex=read(P/'telemetry-lexicon.json')
for line in lex['persistent_hud']:assert line.replace('"','\\"') in (P/'src/Film.tsx').read_text() or line in (P/'src/Film.tsx').read_text()
measure={}
for name in ('narration','score','sfx','master'):
 p=P/'public/audio'/f'{name}.wav'
 with wave.open(str(p)) as w:
  assert (w.getframerate(),w.getnchannels(),w.getsampwidth(),w.getnframes())==(48000,2,2,4320000),(name,w.getparams())
  w.setpos(4860*800);assert not any(w.readframes(25*800)),name
 measure[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'samples_per_channel':4320000,'silence_window_exact_zero':True}
r={'status':'PASS','scope':'Project timing, subtitle layout, source determinism, output target, PCM counts and silence; no human listening or perceptual acceptance','caption_count':len(caps),'audio':measure,'safe_geometry':{'critical_x':[64,902],'hud_y':[173,288],'subtitle_y':[1374,1494],'preview_width':360,'subtitle_effective_px':49/3}}
(W/'review/project-invariants.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(r,ensure_ascii=False,indent=2))
