#!/usr/bin/env python3
"""Per-layout final-encoded motion pairs; permits serial QA between renders."""
from pathlib import Path
from PIL import Image,ImageDraw
import importlib.util,json,subprocess,argparse,hashlib
P=Path(__file__).resolve().parents[1];W=P.parent
parser=argparse.ArgumentParser();parser.add_argument('--layout',choices=['portrait','landscape'],required=True);args=parser.parse_args();key='xiaohongshu' if args.layout=='portrait' else 'bilibili'
spec=importlib.util.spec_from_file_location('motion',P/'scripts/capture_motion.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
d=json.loads((W/'delivery.json').read_text());media=W/d['outputs'][key]['path'];out=W/'review/motion-evidence'/args.layout
assert not out.exists(),'Refusing to replace motion evidence';out.mkdir(parents=True)
pairs=m.PAIR_MAP;frames=sorted({f for _,a,b in pairs for f in (a,b)});images=m.extract_compact_frames('ffmpeg',media,out/'frames',frames);H=640 if args.layout=='portrait' else 202;roi=(.10,.23,.84,.61) if args.layout=='portrait' else (.50,.24,.95,.78)
rows=[];page_h=660 if args.layout=='portrait' else 230;sheet=None
for i,(scene,a,b) in enumerate(pairs):
 if i%6==0:sheet=Image.new('RGB',(1440,page_h*3),'#141a22');draw=ImageDraw.Draw(sheet)
 x=(i%2)*720;y=((i%6)//2)*page_h
 for j,f in enumerate([a,b]):
  sheet.paste(Image.open(images[f]),(x+j*360,y+20));draw.text((x+j*360+4,y+3),f'{scene} {f} / {f/60:.2f}s',fill='white')
 v=m.edge_difference_yavg('ffmpeg',images[a],images[b],360,H,roi);rows.append({'scene':scene,'frames':[a,b],'deltaSeconds':2.5,'roiXYXY':roi,'edgeDifferenceYAVG':v,'warning':v<.5})
 if i%6==5 or i==len(pairs)-1:sheet.save(out/f'contact-{i//6+1}.jpg',quality=92)
report={'media':str(media.relative_to(W)),'mediaSHA256':hashlib.sha256(media.read_bytes()).hexdigest(),'pairs':rows,'method':'Exact decoded frame n from final MP4, 360px previews. Crop excludes HUD and captions. Difference is a review cue, not a perceptual pass.','humanContinuousPlayback':'NOT_RUN'}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(args.layout,'pairs',len(rows),'warnings',sum(x['warning'] for x in rows),flush=True)
