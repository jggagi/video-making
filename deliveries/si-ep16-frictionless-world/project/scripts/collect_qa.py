from pathlib import Path
import json,hashlib,subprocess,re
import numpy as np
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parents[1];W=P.parent
m=json.loads((W/'delivery.json').read_text());media=W/m['outputs']['xiaohongshu']['path'];sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
h=sha(media);out=W/'review'/('encoded-qa-'+h[:12]);out.mkdir(exist_ok=True)
frames=[0,60,180,330,780,930,1140,1320,1590,1740,2340,2490,3180,3330,3990,4140,4860,5010,5578,5579,5580,5581,5700,5850,6120,6270,6358,6359,6360,6361,6400,6401,6420,6480,6630,6870,7020,7199]
repair=W/'review/tile-repair.json'
if repair.exists():
 targets=[v['frame'] for v in json.loads(repair.read_text())['overlays']]
 frames=sorted(set(frames)|{n+d for n in targets for d in [-1,0,1] if 0<=n+d<7200})
for f in frames:
 p=out/f'frame-{f:04}.jpg'
 if not p.exists():subprocess.run(['ffmpeg','-v','error','-ss',str(f/60),'-i',str(media),'-frames:v','1','-vf','scale=540:960','-q:v','2',str(p)],check=True)
contact=Image.new('RGB',(540*5,995*((len(frames)+4)//5)),'#E7EBEF');draw=ImageDraw.Draw(contact)
for i,f in enumerate(frames):
 im=Image.open(out/f'frame-{f:04}.jpg');x=i%5*540;y=i//5*995;contact.paste(im,(x,y+35));draw.text((x+15,y+10),f'frame {f} / {f/60:.2f}s',fill='black')
contact.save(out/'contact.jpg')
for page in range((len(frames)+8)//9):
 panel=Image.new('RGB',(1080,1980),'#E7EBEF');draw=ImageDraw.Draw(panel)
 for n,f in enumerate(frames[page*9:(page+1)*9]):
  im=Image.open(out/f'frame-{f:04}.jpg');im.thumbnail((360,640));x=n%3*360;y=n//3*660;panel.paste(im,(x,y+20));draw.text((x+6,y+4),f'{f} / {f/60:.2f}s',fill='black')
 panel.save(out/f'panel-{page+1}.jpg')
native=[]
for f in [1740,6270,7020]:
 p=out/f'native-{f}.png'
 if not p.exists():subprocess.run(['ffmpeg','-v','error','-ss',str(f/60),'-i',str(media),'-frames:v','1',str(p)],check=True)
 native.append({'frame':f,'path':str(p.relative_to(W)),'sha256':sha(p)})
pairs=[]
for a,b in [(180,330),(780,930),(1590,1740),(2340,2490),(3180,3330),(3990,4140),(4860,5010),(6120,6270),(6480,6630),(6870,7020)]:
 x=np.asarray(Image.open(out/f'frame-{a:04}.jpg').crop((35,250,460,640)),dtype=float);y=np.asarray(Image.open(out/f'frame-{b:04}.jpg').crop((35,250,460,640)),dtype=float);pairs.append({'frames':[a,b],'subjectCropMeanAbsDifference':float(abs(x-y).mean()),'excludesCaptionsAndTelemetry':True})
process=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(media),'-af','ebur128=peak=true','-vn','-f','null','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=True);summary=process.stderr.split('Summary:')[-1];(out/'encoded-loudness.txt').write_text('\n'.join(line.rstrip() for line in summary.splitlines())+'\n')
report={'media_sha256':h,'frames':frames,'native':native,'motion_pairs':pairs,'captionTiming':'estimated phrase weights within measured source PCM','encodedLoudness':summary,'model_visual_review':'PENDING','human_listening':'NOT_RUN','continuous_human_viewing':'NOT_RUN','phone_app_playback':'NOT_RUN'};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(out)
