#!/usr/bin/env python3
"""Verify every narration sample against its cue and the authored silence."""
from pathlib import Path
import array, hashlib, json, wave

P=Path(__file__).resolve().parents[1];A=P/'public/audio';W=P.parent
def read(p):
    with wave.open(str(p),'rb') as w:
        shape=(w.getframerate(),w.getnchannels(),w.getsampwidth(),w.getnframes())
        data=array.array('h');data.frombytes(w.readframes(w.getnframes()))
    return shape,data
def digest(v):return hashlib.sha256(v.tobytes()).hexdigest()
timing=json.loads((P/'audio-timing.json').read_text())
shape,narration=read(A/'narration.wav')
assert shape==(48000,2,2,5760000),shape
mono=narration[0::2];assert mono==narration[1::2],'Narration channels differ'
results=[]
for segment in timing['segments']:
    sid=segment['id'];cue_shape,cue=read(A/'cues'/f'{sid}.wav');start=segment['voiceStartSample'];split=segment.get('split')
    assert cue_shape[:3]==(48000,1,2)
    if split:
        n=split['cueSplitSample'];resume=split['resumeAtSample'];actual=mono[start:start+n]+mono[resume:resume+len(cue)-n]
    else:actual=mono[start:start+len(cue)]
    assert actual==cue,sid+' narration differs from source cue'
    results.append({'id':sid,'samples_preserved':len(cue),'expected_pcm_sha256':digest(cue),'scheduled_pcm_sha256':digest(actual),'exact_match':True,'split':split})
silence={}
for name in ['narration','score','sfx','master']:
    q,v=read(A/f'{name}.wav');assert q==(48000,2,2,5760000),q
    peak=max(abs(x) for x in v[5740*800*2:5760*800*2]);assert peak==0,(name,peak)
    silence[name]={'samples_per_channel':q[3],'silence_peak_pcm16':peak}
report={'status':'PASS','method':'Independent PCM sample equality; narration left/right equal; reassembled S08 around inserted silence; no spoken samples removed','segments':results,'absolute_silence':{'startFrame':5740,'endFrameExclusive':5760,'stems':silence},'limitations':['This establishes exact scheduling and preservation, not pronunciation or perceived mix quality.']}
(W/'review/narration-alignment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('PASS: all ten narration cues preserved exactly; both channels and four silence windows verified')
