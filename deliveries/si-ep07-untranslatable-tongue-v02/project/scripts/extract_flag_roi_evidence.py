#!/usr/bin/env python3
"""Extract every flagged ROI for model review; never changes scanner flags or thresholds."""
from pathlib import Path
import json,subprocess,hashlib,math
import numpy as np
from PIL import Image,ImageDraw
W=Path(__file__).resolve().parents[2];R=W/'review/visual-qc-xiaohongshu';report=json.loads((R/'report.json').read_text());media=Path(report['media_path']);ids=[x['frame'] for x in report['flagged_frames']];out=R/'roi-review';out.mkdir(exist_ok=True)
x,y,ww,hh=report['scan']['config']['stable_roi_normalized_xywh'];sw=report['scan']['scaled_width'];sh=report['scan']['scaled_height'];x0=math.floor(x*sw);y0=math.floor(y*sh);x1=math.ceil((x+ww)*sw);y1=math.ceil((y+hh)*sh);cw=x1-x0;ch=y1-y0
a,b=min(ids)-1,max(ids)+1
cmd=['ffmpeg','-v','error','-threads','2','-filter_threads','2','-i',str(media),'-an','-vf',f'select=between(n\\,{a}\\,{b}),scale={sw}:{sh}:flags=bilinear,format=rgb24,crop={cw}:{ch}:{x0}:{y0}','-frames:v',str(b-a+1),'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
data=subprocess.check_output(cmd);arr=np.frombuffer(data,np.uint8).reshape((-1,ch,cw,3));assert len(arr)==b-a+1
items=[];per=128;cols=4;cardw=cw+64;cardh=ch+8
for start in range(0,len(ids),per):
 batch=ids[start:start+per];sheet=Image.new('RGB',(cardw*cols,math.ceil(len(batch)/cols)*cardh),'#121923');draw=ImageDraw.Draw(sheet)
 for j,f in enumerate(batch):
  xx=(j%cols)*cardw;yy=(j//cols)*cardh;sheet.paste(Image.fromarray(arr[f-a]),(xx+64,yy+4));draw.text((xx+3,yy+6),f'f{f}',fill='white');items.append({'frame':f,'sheet':f'roi-review/all-flagged-rois-{start//per+1:02}.png','column':j%cols,'row':j//cols})
 sheet.save(out/f'all-flagged-rois-{start//per+1:02}.png')
ref=arr[0].astype(float);metrics=[]
for f in ids:
 im=arr[f-a];mask=(im[:,:,0]>140)&(im[:,:,1]>50)&(im[:,:,2]<100)
 refmask=(ref[:,:,0]>140)&(ref[:,:,1]>50)&(ref[:,:,2]<100)
 metrics.append({'frame':f,'roi_mae_from_previous':float(np.mean(np.abs(im.astype(float)-arr[f-a-1].astype(float)))),'amber_mask_xor_pixels_from_reference':int(np.sum(mask!=refmask)),'amber_mask_reference_pixels':int(refmask.sum())})
(out/'index.json').write_text(json.dumps({'media_sha256':hashlib.sha256(media.read_bytes()).hexdigest(),'scope':'Every originally flagged ROI extracted for review; no flags removed or thresholds changed','roi_pixels':[x0,y0,cw,ch],'reference_frame':a,'frames':items,'measurements':metrics},ensure_ascii=False,indent=2)+'\n')
select='+'.join(f'eq(n\\,{f})' for f in [356,357,600,900,1258,1259,1260,1261]);subprocess.run(['ffmpeg','-v','error','-threads','2','-i',str(media),'-vf',f'select={select},scale=360:640,tile=4x2','-frames:v','1','-y',str(out/'full-frame-boundary-contact.jpg')],check=True)
print(json.dumps({'flagged_rois_extracted':len(items),'sheets':math.ceil(len(items)/per),'roi_pixels':[x0,y0,cw,ch],'output':str(out)}))
