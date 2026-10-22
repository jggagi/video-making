"""Build one evidence tile for every authored post-snap HUD-dimming flag."""
from pathlib import Path
import json,subprocess,hashlib,csv
import numpy as np
from PIL import Image,ImageDraw
W=Path(__file__).resolve().parents[2];Q=W/'review/visual-qc-xiaohongshu';d=json.loads((Q/'report.json').read_text());flags=d['flagged_frames'];ids=[x['frame'] for x in flags]
assert ids==list(range(4860,5400))
assert all(set(x['reasons'])<= {'stable_roi_template_outlier','stable_roi_consecutive_outlier'} for x in flags)
media=W/json.loads((W/'delivery.json').read_text())['outputs']['xiaohongshu']['path'];out=W/'review/hud-flag-evidence';out.mkdir(exist_ok=False)
cmd=['ffmpeg','-v','error','-ss','81','-i',str(media),'-an','-vf','crop=1728:200:130:346,scale=432:50:flags=bilinear','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
r=subprocess.run(cmd,check=True,stdout=subprocess.PIPE);frames=np.frombuffer(r.stdout,dtype=np.uint8).reshape((-1,50,432,3));assert len(frames)==540
reference=frames[0].astype(np.int16);measure=[]
for j in range(18):
 sheet=Image.new('RGB',(2160,420),'#120d0a');draw=ImageDraw.Draw(sheet)
 for k in range(30):
  i=j*30+k;x=k%5*432;y=k//5*70
  tile=Image.fromarray(frames[i]);sheet.paste(tile,(x,y+20));draw.text((x+6,y+3),str(ids[i]),fill='#ff9e00')
  mae=float(np.abs(frames[i].astype(np.int16)-reference).mean());measure.append({'frame':ids[i],'mae_to_post_snap_header':mae,'evidence':f'review/hud-flag-evidence/sheet-{j:02d}.jpg'})
 sheet.save(out/f'sheet-{j:02d}.jpg',quality=94)
max_mae=max(v['mae_to_post_snap_header'] for v in measure)
summary={'status':'EVIDENCE_COLLECTED_REVIEW_PENDING','movie_sha256':d['media_sha256'],'flags_preserved':540,'frames':measure,'max_header_mae_to_4860':max_mae,'source_cause':'Film.tsx sets HUD opacity from1 to0.46 for every frame>=4860; the resulting dim header persists for the entire nine-second ending.','no_full_frame_jump_or_dark_roi_flags':True,'scope':'Actual encoded HUD crops for every flagged frame; representative full frames and the4860cut are reviewed separately.'}
(out/'metadata.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='frames'},indent=2))
