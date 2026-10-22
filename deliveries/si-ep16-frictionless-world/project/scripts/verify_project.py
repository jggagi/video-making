from pathlib import Path
import json,hashlib,re,wave
P=Path(__file__).resolve().parents[1];W=P.parent
read=lambda p:json.loads(p.read_text());m=read(W/'delivery.json');s=read(P/'segments.json');t=read(P/'audio-timing.json')
assert m['duration_seconds']==120 and m['fps']==60 and m['total_frames']==7200 and m['platforms']==['xiaohongshu']
assert m['outputs']['xiaohongshu']['width']==2160 and m['outputs']['xiaohongshu']['height']==3840
assert hashlib.sha256((W/m['script']['path']).read_bytes()).hexdigest()==m['script']['sha256']
assert len(s)==9 and [v['id'] for v in s]==[f'S{i:02}' for i in range(1,10)]
for i,v in enumerate(s):
 assert 0<=v['startFrame']<v['endFrame']<=7200
 if i:assert s[i-1]['endFrame']<=v['startFrame']
assert t['status']!='PREVIEW_ONLY' and len(t['segments'])==9
for a,b in zip(t['captions'],t['captions'][1:]):assert a['endFrame']<=b['startFrame']
for v in t['captions']:
 assert 0<=v['startFrame']<v['endFrame']<=7200
 assert len(v['text'].splitlines())<=2 and max(map(len,v['text'].splitlines()))<=13
norm=lambda x:re.sub(r'[\s，。！？：；、“”‘’,.!?;:]+','',x)
assert norm(''.join(v['text'] for v in t['captions']))==norm(''.join(v['display_subtitle'] for v in s))
for name in ['narration.wav','sfx.wav','score.wav','master.wav']:
 with wave.open(str(P/'public/audio'/name)) as a:assert(a.getframerate(),a.getnchannels(),a.getsampwidth(),a.getnframes())==(48000,2,2,5760000)
print('PASS: original hash, platform, clock, nine segments, complete caption text and safe line lengths, exact four PCM stems')
