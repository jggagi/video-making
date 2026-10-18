#!/usr/bin/env python3
"""Explicit authorized Bailian generation; preserve originals and measured cue caches."""
from pathlib import Path
import argparse, hashlib, json, struct, subprocess, wave

P=Path(__file__).resolve().parents[1]
A=P/'public/audio'
BL='/Users/guoq/.local/n/bin/bl'
SETTINGS={'provider':'Aliyun Bailian','model_selection':'active profile default','effective_model':'cosyvoice-v3-flash','voice':'longtian_v3','rate':1.0,'format':'wav','sample_rate':24000,'cli_version':'2.3.2'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def effective(obj,key):
    values=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if k.lower() in key and isinstance(v,str):values.append(v)
            elif isinstance(v,(dict,list)):values+=effective(v,key)
    elif isinstance(obj,list):
        for v in obj:values+=effective(v,key)
    return sorted(set(values))
def canonicalize(src,dst):
    b=src.read_bytes()
    if b[:4]!=b'RIFF' or b[8:12]!=b'WAVE':raise ValueError('Provider did not return WAV')
    off=12;fmt=None;pcm=None
    while off+8<=len(b):
        cid=b[off:off+4];size=struct.unpack_from('<I',b,off+4)[0];start=off+8;end=min(start+size,len(b))
        if cid==b'fmt ':fmt=struct.unpack_from('<HHIIHH',b,start)
        if cid==b'data':pcm=b[start:end];break
        off=start+size+(size&1)
    if not fmt or fmt[0]!=1 or fmt[1]!=1 or fmt[2]!=24000 or fmt[5]!=16 or not pcm or len(pcm)%2:raise ValueError('Unexpected PCM format')
    with wave.open(str(dst),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm)
    return {'actual_samples_24k':len(pcm)//2,'pcm_sha256':hashlib.sha256(pcm).hexdigest(),'raw_header_matches_payload':struct.unpack_from('<I',b,4)[0]==len(b)-8}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('segment',help='S01..S10 or all');args=ap.parse_args()
    segs=json.loads((P/'segments.json').read_text())['segments'];selection=segs if args.segment=='all' else [s for s in segs if s['id']==args.segment]
    if not selection:raise SystemExit('Unknown segment')
    for d in ['raw','canonical','cues','tts-input']:(A/d).mkdir(parents=True,exist_ok=True)
    mp=A/'provider-manifest.json';manifest=json.loads(mp.read_text()) if mp.exists() else {'settings':SETTINGS,'segments':{},'authorization':'User explicitly authorized ten EP04 TTS texts and charges in this conversation; CLI upgrade2.3.2 authorized.'}
    if manifest['settings']!=SETTINGS:raise SystemExit('Existing provider settings differ; preserved')
    for s in selection:
        sid=s['id'];text=s['tts_phonetic_text'];key=hashlib.sha256(json.dumps({'text':text,'settings':SETTINGS},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        raw=A/'raw'/f'{sid}-{key[:12]}.wav';canonical=A/'canonical'/f'{sid}.wav';cue=A/'cues'/f'{sid}.wav';entry=manifest['segments'].get(sid)
        if entry and entry['cache_key']==key and cue.exists() and sha(cue)==entry.get('cue_sha256'):
            print(sid,'verified cache skipped',flush=True);continue
        if entry:raise SystemExit(sid+' divergent or incomplete existing cache; preserved for review')
        inp=A/'tts-input'/f'{sid}.txt';inp.write_text(text)
        proc=subprocess.run([BL,'speech','synthesize','--text-file',str(inp),'--voice',SETTINGS['voice'],'--rate',str(SETTINGS['rate']),'--format','wav','--sample-rate','24000','--out',str(raw),'--concurrent','1','--output','json'],capture_output=True,text=True)
        if proc.returncode:raise SystemExit(f'{sid}: Bailian failed exit={proc.returncode}; no credential-bearing output retained')
        response=json.loads(proc.stdout)
        models=effective(response,{'model','model_id','resolved_model'});voices=effective(response,{'voice','voice_id','resolved_voice'})
        if models!=[SETTINGS['effective_model']] or voices!=[SETTINGS['voice']]:raise SystemExit('NEEDS_SOL: effective model/voice changed; raw result preserved, no automatic provider switch')
        meta=canonicalize(raw,canonical)
        subprocess.run(['ffmpeg','-v','error','-xerror','-y','-i',str(canonical),'-ar','48000','-ac','1','-c:a','pcm_s16le',str(cue)],check=True)
        with wave.open(str(cue),'rb') as w:n=w.getnframes()
        meta.update({'cache_key':key,'raw_path':str(raw.relative_to(P)),'raw_sha256':sha(raw),'canonical_sha256':sha(canonical),'cue_path':str(cue.relative_to(P)),'cue_sha256':sha(cue),'samples_48k':n,'duration_seconds':n/48000,'effective_model':models or 'unknown','effective_voice':voices or 'unknown','identity_status':'reported by CLI response' if models and voices else 'partially unknown','tts_phonetic_text':text})
        manifest['segments'][sid]=meta;mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'segment':sid,'seconds':n/48000,'window_seconds':(s['endFrame']-s['startFrame'])/60,'effective_model':models,'effective_voice':voices,'raw_header_matches_payload':meta['raw_header_matches_payload']},ensure_ascii=False),flush=True)
        if n>(s['endFrame']-s['startFrame'])*800:raise SystemExit(f'NEEDS_SOL: {sid} does not fit; no acceleration or truncation applied')
if __name__=='__main__':main()
