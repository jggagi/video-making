#!/usr/bin/env python3
"""Capture final-encoded native/mobile frames and covers without rendering again."""
from pathlib import Path
import subprocess,json,hashlib,argparse
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parents[1];W=P.parent;R=W/'review';d=json.loads((W/'delivery.json').read_text())
parser=argparse.ArgumentParser();parser.add_argument('--layout',choices=['bilibili','xiaohongshu','both'],default='both');args=parser.parse_args()
frames=[0,360,960,1500,2190,2700,3120,3900,4500,4800,5879,5880,5910,6500,7100,7199]
for key,spec in d['outputs'].items():
 if args.layout!='both' and args.layout!=key:continue
 media=W/spec['path'];o=R/'encoded-frames'/key
 o.mkdir(parents=True,exist_ok=True); rows=[]
 for f in frames:
  dst=o/f"frame-{f}.{'png' if f in (2700,4500) else 'jpg'}"
  subprocess.run(['ffmpeg','-v','error','-y','-ss',str(f/60),'-i',str(media),'-frames:v','1','-q:v','2',str(dst)],check=True)
  im=Image.open(dst).convert('RGB');im.thumbnail((360,640));im.save(o/f'mobile-{f}.jpg',quality=92)
  rows.append({'frame':f,'native':str(dst.relative_to(W)),'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
 cols=4;tw,th=(360,660) if key=='xiaohongshu' else (360,223)
 sheet=Image.new('RGB',(cols*tw,4*th),'#171d26');dr=ImageDraw.Draw(sheet)
 for i,f in enumerate(frames):
  im=Image.open(o/f'mobile-{f}.jpg');x=(i%cols)*tw;y=(i//cols)*th
  sheet.paste(im,(x,y+20));dr.text((x+5,y+3),f'{f}/60 = {f/60:.3f}s',fill='white')
 sheet.save(o/'contact.jpg',quality=92)
 # Cover from the final encoded 75s artifact shot.
 Image.open(o/'frame-4500.png').convert('RGB').save(W/Path(spec['path']).parent/'cover-75s.jpg',quality=95)
 (o/'index.json').write_text(json.dumps({'media':spec['path'],'mediaSHA256':hashlib.sha256(media.read_bytes()).hexdigest(),'frames':rows},indent=2)+'\n')
 print('Captured final encoded frames',key,flush=True)
