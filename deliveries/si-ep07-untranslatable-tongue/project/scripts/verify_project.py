#!/usr/bin/env python3
"""Check deliverable invariants against original script and measured local files."""
from pathlib import Path
import json,re,wave,hashlib
P=Path(__file__).resolve().parents[1];W=P.parent
report={}; errors=[]
def check(name,condition):
 report[name]=bool(condition)
 if not condition: errors.append(name)
d=json.loads((W/'delivery.json').read_text());s=json.loads((P/'segments.json').read_text())['segments'];t=json.loads((P/'audio-timing.json').read_text())
check('original_script_hash',hashlib.sha256((W/d['script']['path']).read_bytes()).hexdigest()==d['script']['sha256'])
check('native_dual_4k',d['outputs']['xiaohongshu']['width']==2160 and d['outputs']['xiaohongshu']['height']==3840 and d['outputs']['bilibili']['width']==3840 and d['outputs']['bilibili']['height']==2160)
check('exact_timeline',(d['duration_seconds'],d['fps'],d['total_frames'])==(120,60,7200))
check('all_original_tts_segments',len(s)==11 and all(x['original_script']==x['display_subtitle'] for x in s))
check('all_measured_cues',len(t.get('segments',[]))==11)
caps=t.get('captions',[])
check('captions_present',bool(caps))
check('mobile_caption_line_lengths',all(len(line)<=14 for c in caps for line in c['text'].split('\n')))
check('mobile_caption_line_counts',all(len(c['text'].split('\n'))<=2 for c in caps))
check('caption_bounds',all(0<=c['startFrame']<c['endFrame']<=7200 for c in caps))
check('visual_gate_required',d.get('visual_qc',{}).get('required') is True)
source='\n'.join(x.read_text() for x in (P/'src').glob('*.tsx'))
check('no_real_time_random',not re.search(r'Math\.random\(|Date\.now\(',source))
check('fiction_mark_visible','科幻思想实验' in source)
master=P/'public/audio/master.wav'
if master.exists():
 with wave.open(str(master),'rb') as f:
  check('pcm_master_exact',(f.getframerate(),f.getnchannels(),f.getnframes())==(48000,2,5760000))
  f.setpos(5880*800);zero=f.readframes(30*800)
  check('exact_half_second_absolute_silence',len(zero)==96000 and not any(zero))
else: check('pcm_master_exists',False)
report['errors']=errors
(W/'review/project-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(bool(errors))
