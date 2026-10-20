#!/usr/bin/env python3
"""Check authored clocks, text preservation, safe typography and determinism."""
from pathlib import Path
import hashlib,json,re

P=Path(__file__).resolve().parents[1];W=P.parent
def read(name):return json.loads((P/name).read_text())
def h(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(text):return ''.join(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]',text))
d=json.loads((W/'delivery.json').read_text());s=read('segments.json');t=read('timeline.json');e=read('sfx_events.json')
assert (d['duration_seconds'],d['fps'],d['total_frames'])==(90,60,5400)
assert d['platforms']==['xiaohongshu'] and set(d['outputs'])=={'xiaohongshu'}
assert (d['outputs']['xiaohongshu']['width'],d['outputs']['xiaohongshu']['height'])==(2160,3840)
assert [x['id'] for x in s]==[f'S{i:02}' for i in range(1,9)]
assert [(a['startFrame'],a['endFrame']) for a in t['acts']]==[(0,1320),(1320,2820),(2820,4380),(4380,5400)]
assert e['absoluteSilence']==[4861,4891] and e['absoluteBlack']==[4861,4891]
assert all(x['sample']==x['frame']*800 for x in e['events'])
assert next(x for x in e['events'] if x['id']=='screen_lock')['frame']==4860
for seg in s:
 assert norm(''.join(seg['chunks']))==norm(seg['display_subtitle']),seg['id']
 assert all(len(re.findall(r'[\u4e00-\u9fff]',x))<=13 for x in seg['chunks']),seg['id']
for f in (P/'src').glob('*.tsx'):
 assert not re.search(r'Math\.random\s*\(|Date\.now\s*\(|performance\.now\s*\(',f.read_text()),f
assert h(W/d['script']['path'])==d['script']['sha256']
timing=read('audio-timing.json');caps=timing['captions']
for c in caps:
 assert 0<=c['startFrame']<c['endFrame']<=5400
 assert len(c['text'].split('\n'))<=2
 assert all(len(re.findall(r'[\u4e00-\u9fff]',line))<=13 for line in c['text'].split('\n'))
 if timing.get('status')!='PREVIEW_ONLY_NO_AUDIO':
  assert c['endFrame']<=4861 or c['startFrame']>=4891
report={'status':'PASS','scope':'Source invariants only; no media/listening pass inferred','durationFrames':5400,'samplesPerChannel':4320000,'captionEffectivePxAt360':49/3,'safeLogicalBounds':{'left':64,'right':902,'topHud':173,'captionTop':1384,'captionBottom':1492,'bottomUiBegins':1497.6},'blackAndSilenceFrames':[4861,4891],'ttsAndDisplaySeparate':True,'captionTimingState':timing.get('status','MEASURED_PCM_WEIGHTED_CAPTION_ESTIMATE'),'fileSha256':{str(f.relative_to(W)):h(f) for f in sorted(P.rglob('*')) if f.is_file() and f.suffix in ['.tsx','.ts','.json','.py','.mjs'] and not any(x in f.parts for x in ['node_modules','__pycache__'])}}
(W/'review/project-invariants.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('PASS: portrait clocks, full text, frame determinism and caption typography; media separate')
