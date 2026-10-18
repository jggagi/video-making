#!/usr/bin/env python3
"""Copy the verified closed-GOP v2 prefix and concatenate the native v3 tail.

No audio is cut at a video packet boundary: sync_audio.py subsequently muxes
one intact 120-second AAC stream. The editable project can also render all
7200 frames with render.mjs video if the v2 export is unavailable.
"""
from pathlib import Path
import hashlib,json,subprocess
P=Path(__file__).resolve().parents[1]; W=P.parent
OLD=W.parent/'si-ep04-verifier-paradox-v02'; CUT=6300

def run(args):return subprocess.check_output(args,stderr=subprocess.PIPE)
def probe(p):return json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_packets','-show_data_hash','sha256','-of','json',str(p)]))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def call(args):run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-y']+args)
m=json.loads((W/'delivery.json').read_text());old=json.loads((OLD/'delivery.json').read_text());report={'cut_frame':CUT,'cut_seconds':105,'audio':'separately muxed intact; never concatenated','outputs':{}}
for layout,key in [('landscape','bilibili'),('portrait','xiaohongshu')]:
 source=OLD/old['outputs'][key]['path'];tail=P/'out'/f'tail-{layout}.mp4';prefix=P/'out'/f'prefix-{layout}.mp4';dest=W/m['outputs'][key]['path']
 a=probe(source);b=probe(tail);s=a['streams'][0];t=b['streams'][0]
 if len(a['packets'])!=7200 or len(b['packets'])!=900:raise SystemExit('Unexpected source/tail packet count')
 if 'K' not in a['packets'][CUT]['flags'] or float(a['packets'][CUT]['pts_time'])!=105:raise SystemExit('Cut is not the verified keyframe')
 if 'K' not in b['packets'][0]['flags'] or int(b['packets'][0]['pts'])!=0:raise SystemExit('Tail must begin with a keyframe at PTS zero')
 for k in ['codec_name','profile','level','width','height','pix_fmt','time_base','avg_frame_rate','color_space','extradata_hash']:
  if s.get(k)!=t.get(k):raise SystemExit(f'Incompatible stream {k}: {s.get(k)} vs {t.get(k)}')
 call(['-i',str(source),'-map','0:v:0','-an','-c:v','copy','-frames:v',str(CUT),'-video_track_timescale','90000',str(prefix)])
 pp=probe(prefix)
 if len(pp['packets'])!=CUT:raise SystemExit('Prefix count mismatch')
 listing=P/'out'/f'concat-{layout}.txt';listing.write_text(f"file '{prefix.as_posix()}'\nduration 105\nfile '{tail.as_posix()}'\nduration 15\n")
 call(['-f','concat','-safe','0','-auto_convert','0','-i',str(listing),'-map','0:v:0','-an','-c:v','copy','-video_track_timescale','90000','-movflags','+faststart','-metadata','title=神也会自我欺骗 · v3 直观结尾版',str(dest)])
 result=probe(dest)
 if len(result['packets'])!=7200 or result['streams'][0]['nb_frames']!='7200' or float(result['streams'][0]['duration'])!=120:raise SystemExit('Output timeline mismatch')
 if s['time_base']!='1/90000' or sorted(int(x['pts']) for x in result['packets'])!=list(range(0,7200*1500,1500)):raise SystemExit('Output PTS contains a gap or duplicate')
 dts=[int(x['dts']) for x in result['packets']]
 if any(y-x!=1500 for x,y in zip(dts,dts[1:])):raise SystemExit('Output DTS is not contiguous')
 source_prefix=[(x['pts'],x['dts'],x['data_hash']) for x in a['packets'][:CUT]]
 output_prefix=[(x['pts'],x['dts'],x['data_hash']) for x in result['packets'][:CUT]]
 if source_prefix!=output_prefix:raise SystemExit('Unchanged prefix packet bytes or timestamps diverged')
 tail_expected=[(int(x['pts'])+CUT*1500,int(x['dts'])+CUT*1500,x['data_hash']) for x in b['packets']]
 tail_actual=[(int(x['pts']),int(x['dts']),x['data_hash']) for x in result['packets'][CUT:]]
 if tail_expected!=tail_actual:raise SystemExit('Native tail packet/timestamp mapping diverged')
 report['outputs'][key]={'source_path':str(source.relative_to(W.parent)),'source_sha256':sha(source),'native_tail_sha256':sha(tail),'packet_count':7200,'prefix_packets_identical':True,'tail_packets_identical_at_105s_offset':True,'all_7200_pts_contiguous_and_unique':True,'all_dts_contiguous':True,'tail_starts_with_keyframe':True,'prefix_packet_sequence_sha256':hashlib.sha256(json.dumps(source_prefix).encode()).hexdigest(),'compatible_extradata_sha256':s['extradata_hash'],'duration_seconds':120,'status':'PASS'}
 print(layout+': 6300 prefix packets identical; 900 new native frames; total 7200',flush=True)
report['status']='PASS';(W/'review/prefix-reuse.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
