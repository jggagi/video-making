#!/usr/bin/env python3
"""Export frame-aligned SRTs and the explicitly unspoken EP04 closing card."""
import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]; w=p.parent
f=p/'audio-timing.json';d=json.loads(f.read_text())
if len(d['segments'])!=10:raise SystemExit('Need all ten real PCM cues before subtitle export')
# Keep every spoken display character and append the user-requested, unspoken
# EP04 tag. Hold only this closing card to the final frame for readability.
closing=[c for c in d['captions'] if c['segmentId']=='S10']
if not closing:raise SystemExit('Missing S10 measured cue')
start=min(c['startFrame'] for c in closing)
d['captions']=[c for c in d['captions'] if c['segmentId']!='S10']+[{'id':'S10-closing-card','segmentId':'S10','startFrame':start,'endFrame':7200,'text':'下一次观测：验证器悖论。\n[EP.04 神也会自我欺骗]','unspoken_overlay':'[EP.04 神也会自我欺骗]','display_hold_after_pcm':True}]
d['closing_card_note']='S10 display includes the requested unspoken EP04 tag and holds after narration until frame7200; phrase timing elsewhere remains an estimate within actual measured segment PCM.'
f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def stamp(frame):
 ms=round(frame*1000/60);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000);return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
s='\n'.join(f"{i}\n{stamp(c['startFrame'])} --> {stamp(c['endFrame'])}\n{c['text']}\n" for i,c in enumerate(d['captions'],1))
for folder in ['B站','小红书']:(w/folder/'captions.srt').write_text(s,encoding='utf-8')
print(f'Exported {len(d["captions"])} shared subtitle windows; unspoken closing tag retained')
