"""Extract review evidence and requested covers from the final encoded movie."""
from pathlib import Path
import hashlib,json,subprocess
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parents[1];W=P.parent
m=json.loads((W/'delivery.json').read_text());v=W/m['outputs']['xiaohongshu']['path'];O=W/'review/encoded-frames';O.mkdir(exist_ok=True)
frames=sorted(set([0,60,180,300,600,750,900,1050,1320,1470,1500,1650,1800,1950,2100,2220,2370,2520,2670,2819,2820,2940,3090,3240,3390,3540,3600,3750,3900,4050,4200,4350,4380,4500,4650,4800,4859,4860,4889,4890,5040,5160,5310,5399]))
for f in frames:
 out=O/f'frame-{f:04d}.jpg'
 subprocess.run(['ffmpeg','-v','error','-n','-ss',str(f/60),'-i',str(v),'-frames:v','1','-vf','scale=360:640','-q:v','2',str(out)],check=True)
for label,f in [('A',2100),('B',5040)]:
 out=W/'小红书'/f'cover-{label}.png'
 subprocess.run(['ffmpeg','-v','error','-n','-ss',str(f/60),'-i',str(v),'-frames:v','1',str(out)],check=True)
for f in [2100,3900,5399]:
 out=W/'review'/f'encoded-native-{f}.png'
 subprocess.run(['ffmpeg','-v','error','-n','-ss',str(f/60),'-i',str(v),'-frames:v','1',str(out)],check=True)
selected=[60,2100,2940,3900,4500,4860,5040,5399];sheet=Image.new('RGB',(1440,1360),'#202329');d=ImageDraw.Draw(sheet)
for i,f in enumerate(selected):
 im=Image.open(O/f'frame-{f:04d}.jpg');x=(i%4)*360;y=(i//4)*680;sheet.paste(im,(x,y+30));d.text((x+10,y+6),f'FRAME {f} / {f/60:.2f}s',fill='white')
sheet.save(W/'review/encoded-mobile-contact.jpg',quality=95)
report={'status':'EXTRACTED_FROM_FINAL_MP4','movie_sha256':hashlib.file_digest(v.open('rb'),'sha256').hexdigest(),'frameIndexConvention':'zero-based, PTS=frame/60; exact-seeking decode after nearest keyframe','frames':frames,'mobileWidth':360,'covers':{'A':2100,'B':5040},'nativeFrames':[2100,3900,5399],'humanViewing':'NOT_RUN'};(W/'review/frame-extraction.json').write_text(json.dumps(report,indent=2)+'\n');print('Extracted',len(frames),'mobile frames,2rawcovers,3nativeframes')
