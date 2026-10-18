#!/usr/bin/env python3
"""Encode one shared AAC stream, verify it, then copy it into both native videos."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,subprocess
P=Path(__file__).resolve().parents[1];W=P.parent
MASTER=P/'public/audio/master.wav';AAC=P/'out/shared-delivery.m4a';REPORT=W/'review/shared-audio-encoding.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run(a):return subprocess.check_output(a,stderr=subprocess.PIPE,text=True)
def probe(p):return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def packet_hash(p,stream):return run(['ffmpeg','-v','error','-i',str(p),'-map',f'0:{stream}:0','-c','copy','-f','hash','-hash','sha256','-']).strip()
def save(d):REPORT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--apply',action='store_true');a=ap.parse_args()
s=importlib.util.spec_from_file_location('audio',P/'scripts/build_audio.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
if a.prepare:
 AAC.parent.mkdir(parents=True,exist_ok=True)
 run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-y','-i',str(MASTER),'-map','0:a:0','-c:a','aac','-b:a','320k','-ar','48000','-ac','2','-movflags','+faststart',str(AAC)])
 loud=m.parse_ebur128(AAC)
 if not (-18<=loud['integratedLUFS']<=-16 and loud['truePeakDBTP']<=-1):raise SystemExit(f'AAC outside target: {loud}')
 d={'master_sha256':sha(MASTER),'aac_sha256':sha(AAC),'aac_packet_sha256':packet_hash(AAC,'a'),'loudness':loud,'ffprobe':probe(AAC),'outputs':{},'status':'PREPARED_NOT_YET_MUXED'};save(d);print(json.dumps({'status':d['status'],'AAC_loudness':loud}))
else:
 d=json.loads(REPORT.read_text())
 if d['master_sha256']!=sha(MASTER) or d['aac_sha256']!=sha(AAC):raise SystemExit('Master/AAC changed after preparation')
 manifest=json.loads((W/'delivery.json').read_text())
 for layout,c in manifest['outputs'].items():
  p=W/c['path'];before=packet_hash(p,'v');temp=p.with_name(p.stem+'.audio-sync.tmp.mp4')
  run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-y','-i',str(p),'-i',str(AAC),'-map','0:v:0','-map','1:a:0','-map_metadata','0','-c','copy','-t','120','-movflags','+faststart',str(temp)])
  info=probe(temp);v=next(s for s in info['streams'] if s['codec_type']=='video')
  if (v['width'],v['height'],v['nb_frames'],v['avg_frame_rate'])!=(c['width'],c['height'],'7200','60/1'):raise SystemExit(f'Video changed in mux: {layout}')
  after=packet_hash(temp,'v');audio=packet_hash(temp,'a')
  if before!=after or audio!=d['aac_packet_sha256']:raise SystemExit('Stream integrity failure; original preserved')
  temp.replace(p);d['outputs'][layout]={'path':c['path'],'video_packet_sha256_before':before,'video_packet_sha256_after':after,'video_unchanged':True,'audio_packet_sha256':audio,'sha256':sha(p)};save(d);print(f'{layout}: shared AAC copied; video packet hash unchanged',flush=True)
 d['status']='BOTH_OUTPUTS_SAME_AAC_VERIFIED';save(d)
