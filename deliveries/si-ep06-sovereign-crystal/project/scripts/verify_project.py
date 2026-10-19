#!/usr/bin/env python3
"""Validate authored shared timeline, safe text layout and scientific qualifiers."""
import hashlib,json,re,wave
from pathlib import Path
P=Path(__file__).resolve().parents[1];W=P.parent
fail=[]; checks=[]
def check(ok,name):
 checks.append({'name':name,'pass':bool(ok)})
 if not ok:fail.append(name)
d=json.loads((W/'delivery.json').read_text());s=json.loads((P/'segments.json').read_text());tl=json.loads((P/'timeline.json').read_text());layout=json.loads((P/'layout-contract.json').read_text())
check(d['fps']==60 and d['total_frames']==7200 and d['duration_seconds']==120,'120s / 7200 frames / 60fps')
check(hashlib.sha256((W/d['script']['path']).read_bytes()).hexdigest()==d['script']['sha256'],'original script preserved')
sc=tl['scenes'];check(sc[0]['startFrame']==0 and sc[-1]['endFrame']==7200 and all(a['endFrame']==b['startFrame'] for a,b in zip(sc,sc[1:])),'scene coverage without gaps')
check(all(x['motion'] for x in sc),'each long hold has spatial motion design')
check(len(s['segments'])==10 and all(0<=x['startFrame']<x['endFrame']<=7200 for x in s['segments']),'ten valid narration windows')
source='\n'.join(x.read_text() for x in (P/'src').glob('*') if x.suffix in ('.ts','.tsx'))
check(not re.search(r'Math\.random\s*\(|Date\.now\s*\(',source),'frame deterministic source')
check(all(x in source for x in ['思想实验','非人格重建','随机性不等于自由','诗意表达']),'visible scientific boundaries')
sub=layout['subtitle'];check(sub['fontSize']/3>=13 and layout['hud']['fontSize']/3>=10,'360px effective typography')
check(sub['y']>=.72*1920 and sub['y']+sub['height']<=.78*1920 and sub['x']+sub['width']<=.86*1080,'portrait complete subtitle safe bounds')
check(all(len(re.findall(r'[\u3400-\u9fff]',line))<=14 for x in s['segments'] for line in x['chunks']),'authored phrase length <=14 Chinese characters')
if (P/'public/audio/master.wav').exists():
 with wave.open(str(P/'public/audio/master.wav')) as a: check((a.getnframes(),a.getframerate(),a.getnchannels())==(5760000,48000,2),'exact stereo PCM master')
 timing=json.loads((P/'audio-timing.json').read_text());check(len(timing.get('segments',[]))==10,'ten measured PCM spans')
 captions=timing.get('captions',[]);check(bool(captions) and all(len(x['text'].splitlines())<=2 and all(len(re.findall(r'[\u3400-\u9fff]',line))<=14 for line in x['text'].splitlines()) for x in captions),'rendered captions max two lines /14 Chinese')
 check(all(a['endFrame']<=b['startFrame'] for a,b in zip(captions,captions[1:])),'no overlapping captions')
 check(s['segments'][7]['endFrame']<=5740 and timing['segments'][7]['voiceEndSampleExclusive']<=5740*800,'S08 ends before dramatic silence')
r={'status':'FAIL' if fail else 'PASS','checks':checks,'failures':fail,'scope':'source and authored/measured timing, not media or human acceptance'}
(W/'review/project-validation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(bool(fail))
