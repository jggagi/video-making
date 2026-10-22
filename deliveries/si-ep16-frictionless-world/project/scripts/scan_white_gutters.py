from pathlib import Path
import subprocess,json,hashlib,csv,sys
import numpy as np
P=Path(__file__).resolve().parents[1];W=P.parent
m=json.loads((W/'delivery.json').read_text());media=Path(sys.argv[1]) if len(sys.argv)>1 else W/m['outputs']['xiaohongshu']['path'];out=Path(sys.argv[2]) if len(sys.argv)>2 else W/'review/white-gutter-scan-01';out.mkdir(exist_ok=True)
sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest();h=sha(media)
w,ht=540,960;size=w*ht*3
regions={'right_blank_gutter':(497,160,535,870),'top_blank_gap':(40,221,455,239),'bottom_blank_margin':(40,885,530,940)}
cmd=['ffmpeg','-v','error','-threads','2','-i',str(media),'-an','-vf','scale=540:960','-filter_threads','2','-pix_fmt','rgb24','-f','rawvideo','-'];p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
flags=[];metrics=[];i=0
while True:
 b=p.stdout.read(size)
 if not b:break
 assert len(b)==size
 a=np.frombuffer(b,dtype=np.uint8).reshape(ht,w,3);v={}
 for name,(x0,y0,x1,y1) in regions.items():
  crop=a[y0:y1,x0:x1];luma=crop.mean(axis=2);v[name]=int((luma<225).sum())
 if any(vv>5 for vv in v.values()):flags.append({'frame':i,'dark_pixel_counts':v})
 metrics.append({'frame':i,**v});i+=1
stderr=p.stderr.read().decode();rc=p.wait();assert rc==0 and i==7200 and sha(media)==h,(rc,i,stderr)
with (out/'metrics.csv').open('w') as f:
 wr=csv.DictWriter(f,fieldnames=['frame',*regions],lineterminator='\n');wr.writeheader();wr.writerows(metrics)
r={'media':str(media),'sha256':h,'every_frame':True,'frames':i,'decode_return_code':rc,'regions_540x960':regions,'basis':'Regions intentionally contain only uniform #F8FAFC background in every authored non-cover frame. Any >5 pixels mean RGB<225 requires review. Source-shape checks and report do not assert every kind of capture flaw is detectable.','flagged_frames':flags};(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'frames':i,'flagged_frames':len(flags),'frame_indices':[v['frame'] for v in flags]}))
