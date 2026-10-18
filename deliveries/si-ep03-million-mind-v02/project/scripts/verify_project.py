#!/usr/bin/env python3
"""Verify the EP03 production invariants; media checks remain separate."""
from pathlib import Path
import argparse,hashlib,json,re,wave
P=Path(__file__).resolve().parents[1]; W=P.parent
ap=argparse.ArgumentParser();ap.add_argument('--require-audio',action='store_true');args=ap.parse_args()
d=json.loads((W/'delivery.json').read_text());s=json.loads((P/'segments.json').read_text());t=json.loads((P/'timeline.json').read_text());f=(P/'src/Film.tsx').read_text();canvas=(P/'src/CanvasWorld.tsx').read_text();r=(P/'src/Root.tsx').read_text();issues=[]
def check(ok,msg):
 if not ok:issues.append(msg)
check((d['duration_seconds'],d['fps'],d['total_frames'])==(120,60,7200),'delivery timing')
check(hashlib.sha256((W/d['script']['path']).read_bytes()).hexdigest()==d['script']['sha256'],'original script SHA256')
check([x['id'] for x in s['segments']]==[f'S{i:02d}' for i in range(1,11)],'ten ordered segments')
clean=lambda x:re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]','',x)
for x in s['segments']:
 check(clean(x['original_script'])==clean(x['display_subtitle'])==clean(''.join(x['chunks'])),x['id']+' display/script preservation')
 check(0<=x['startFrame']<x['endFrame']<=7200,x['id']+' bounds')
 for chunk in x['chunks']: check(len(re.findall(r'[\u4e00-\u9fff]',chunk))<=14,x['id']+' <=14Chinese per subtitle')
shots=t['shots'];check(shots[0]['startFrame']==0 and shots[-1]['endFrame']==7200,'full shot coverage')
for a,b in zip(shots,shots[1:]):check(a['endFrame']==b['startFrame'],'no shot gap/overlap')
for p in (P/'src').glob('*.tsx'):check(not re.search(r'Math\.random\s*\(|Date\.now\s*\(',p.read_text()),'frame determinism '+p.name)
for text in ['HUMAN INTER-BRAIN BANDWIDTH: 39.0 BITS/S','KNOWLEDGE SYNC LOSS: 99.99% (ISOLATED SKULLS)','SI OPTICAL FABRIC: 1,024.0 TB/S (ZERO-COPY)','ACTIVE EXPERT INSTANCES: ']:check(text in f,'exact HUD '+text)
check('Landscape4K' in r and 'PortraitVertical' in r and r.count('durationInFrames={7200}')==2,'dual composition timing')
check('const count = 900' in canvas and 'const count = 1800' in canvas,'swarm/vortex counts')
e=json.loads((P/'sfx_events.json').read_text())['events']
for x in e:
 check(x['sample']==x['frame']*800,'SFX sample '+x['id'])
 if 'endFrame'in x:check(x['endSample']==x['endFrame']*800,'SFX silence end')
if args.require_audio:
 a=json.loads((P/'audio-timing.json').read_text());check(len(a['segments'])==10,'all PCM aligned segments');check(a.get('status')!='PLANNED_PREVIEW_ONLY_NOT_PCM_ALIGNED','real PCM timing required')
 for c in a['captions']:
  check(0<=c['startFrame']<c['endFrame']<=7200,'caption bounds')
  lines=c['text'].split('\n');check(len(lines)<=2,'caption max two lines')
  for line in lines:check(len(re.findall(r'[\u4e00-\u9fff]',line))<=14,'actual subtitle <=14 Chinese per line')
 for first,second in zip(a['captions'],a['captions'][1:]):check(first['endFrame']<=second['startFrame'],'no subtitle overlap')
 with wave.open(str(P/'public/audio/master.wav'),'rb') as v:
  check((v.getframerate(),v.getnchannels(),v.getnframes())==(48000,2,5760000),'exact stereo PCM master')
  v.setpos(4800000);check(set(v.readframes(16000))<={0},'20-frame absolute silence in PCM master')
report={'status':'FAIL' if issues else 'PASS','audio_checked':args.require_audio,'issues':issues,'limitations':['No final MP4 media validation','No continuous motion or listening claim','Safe zones require rendered-frame inspection']}
(W/'review/project-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(bool(issues))
