#!/usr/bin/env python3
"""Cache one AAC encode and copy its packets into both final movies, preserving video."""
from pathlib import Path
import argparse, hashlib, json, subprocess

P=Path(__file__).resolve().parents[1]; W=P.parent; A=P/'public/audio'; R=W/'review'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def run(args): return subprocess.check_output(args,text=True)
def payload(p,stream):
    return run(['ffmpeg','-v','error','-i',str(p),'-map',stream,'-c','copy','-f','hash','-hash','sha256','-']).strip()
def probe(p): return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
parser=argparse.ArgumentParser();parser.add_argument('--layout',choices=['portrait','landscape'],required=True);args=parser.parse_args()
d=json.loads((W/'delivery.json').read_text());master=A/'master.wav';sha=digest(master)
assert sha==d['audio']['sha256']==d['audio']['master_sha256'],'Master manifest must be current'
assert (A/'mix-refinement.json').exists(),'Refined mix required'
cache=A/'master-shared-aac.m4a';cache_report=A/'master-shared-aac.json'
if cache.exists():
    c=json.loads(cache_report.read_text());assert c['masterSHA256']==sha and c['aacSHA256']==digest(cache)
else:
    assert not cache_report.exists()
    subprocess.run(['ffmpeg','-v','error','-n','-i',str(master),'-c:a','aac','-b:a','320k','-ar','48000','-ac','2','-movflags','+faststart',str(cache)],check=True)
    save(cache_report,{'masterSHA256':sha,'aacSHA256':digest(cache),'encoder':'local FFmpeg native AAC, 320k, 48kHz stereo','audioPayloadSHA256':payload(cache,'0:a:0')})
key='xiaohongshu' if args.layout=='portrait' else 'bilibili';media=W/d['outputs'][key]['path'];report=R/f'final-audio-remux-{args.layout}.json'
assert media.exists() and not report.exists(),'Refusing to replace a finalized movie or report'
candidate=media.with_name(media.stem+'.audio-finalizing.mp4');assert not candidate.exists()
oldsha=digest(media);vp=payload(media,'0:v:0');before=probe(media)
subprocess.run(['ffmpeg','-v','error','-n','-i',str(media),'-i',str(cache),'-map','0:v:0','-map','1:a:0','-c','copy','-map_metadata','0','-movflags','+faststart',str(candidate)],check=True)
after=probe(candidate);v=next(s for s in after['streams'] if s['codec_type']=='video');a=next(s for s in after['streams'] if s['codec_type']=='audio')
assert v['nb_frames']=='7200' and v['r_frame_rate']=='60/1' and float(v['duration'])==120
assert (v['width'],v['height'])==(d['outputs'][key]['width'],d['outputs'][key]['height'])
assert a['sample_rate']=='48000' and a['channels']==2 and abs(float(a['duration'])-120)<.05
assert payload(candidate,'0:v:0')==vp,'Video payload changed'
ap=payload(cache,'0:a:0');assert payload(candidate,'0:a:0')==ap,'AAC payload differs from shared cache'
preserved=R/'local-failed'/f'{args.layout}-before-final-audio.mp4.superseded';preserved.parent.mkdir(exist_ok=True);assert not preserved.exists()
media.rename(preserved);candidate.rename(media)
save(report,{'status':'PASS','inputSHA256':oldsha,'outputSHA256':digest(media),'output':str(media.relative_to(W)),'preservedInput':str(preserved.relative_to(W)),'masterSHA256':sha,'aacCacheSHA256':digest(cache),'videoPayloadSHA256':vp,'videoPayloadIdentical':True,'audioPayloadSHA256':ap,'audioMatchesSharedCache':True,'video':v,'audio':a})
print(json.dumps({'layout':args.layout,'status':'PASS','mediaSHA256':digest(media),'videoPayloadIdentical':True,'audioMatchesSharedCache':True}))
