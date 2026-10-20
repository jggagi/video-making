#!/usr/bin/env python3
"""Extract contacts and measure the actual encoded movie; no audience inference."""
from pathlib import Path
import json,subprocess,hashlib,re,wave
import numpy as np
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parents[1];W=P.parent
M=W/'小红书/si-ep10-dopamine-greenhouse-xiaohongshu-90s-portrait.mp4';R=W/'review'
frames=[0,150,300,450,600,720,870,1000,1200,1320,1369,1500,1650,1800,2040,2300,2450,2550,2700,2820,2940,3150,3300,3480,3600,3720,3870,3900,4043,4050,4200,4380,4500,4650,4800,4859,4860,4861,4890,4891,4900,5050,5200,5399]
# Decode from frame0 with one exact integer-index selection, not approximate seeks.
extraction_frames=sorted(set(frames)|set(range(4861,4891)))
select='+'.join(f'eq(n\\,{f})' for f in extraction_frames)
cmd=['ffmpeg','-v','error','-xerror','-i',str(M),'-vf',f'select={select},scale=360:640','-vsync','0','-f','rawvideo','-pix_fmt','rgb24','-']
p=subprocess.run(cmd,stdout=subprocess.PIPE,check=True);size=360*640*3
assert len(p.stdout)==len(extraction_frames)*size,(len(p.stdout),len(extraction_frames)*size)
byframe={f:p.stdout[i*size:(i+1)*size] for i,f in enumerate(extraction_frames)}
encoded_black_peak=max(max(byframe[f]) for f in range(4861,4891))
assert encoded_black_peak==0,('Blackout contains nonzero RGB',encoded_black_peak)
cols=6;rows=(len(frames)+cols-1)//cols
out=Image.new('RGB',(cols*360,rows*666),'#10151b');d=ImageDraw.Draw(out)
for i,f in enumerate(frames):
 im=Image.frombytes('RGB',(360,640),byframe[f]);x=(i%cols)*360;y=(i//cols)*666;out.paste(im,(x,y+26));d.text((x+12,y+7),f'f{f} / {f/60:.3f}s',fill='#c8d6e0')
out.save(R/'encoded-contact.jpg',quality=92)
native_frames=[1000,1369,2300,3480,3720,4043,4860,4900,5399]
native_select='+'.join(f'eq(n\\,{f})' for f in native_frames)
subprocess.run(['ffmpeg','-v','error','-i',str(M),'-vf',f'select={native_select}','-vsync','0','-y',str(R/'encoded-native-%02d.png')],check=True)
for i,f in enumerate(native_frames,1):(R/f'encoded-native-{i:02d}.png').replace(R/f'encoded-{f}.png')
im=Image.open(R/'encoded-1000.png');im.crop((500,900,1700,2100)).save(R/'native-dark-and-flower-crop.png')
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(M)]))
e=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(M),'-vn','-af','ebur128=peak=true','-f','null','-'],stderr=subprocess.PIPE,text=True,check=True).stderr
integrated=re.findall(r'I:\s*(-?\d+(?:\.\d+)?)\s+LUFS',e)[-1]
peak=re.search(r'True peak:\s*\n\s*Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS',e)
assert peak,e[-1200:]
loud={'integratedLUFS':float(integrated),'truePeakDBTP':float(peak.group(1))}
assert abs(loud['integratedLUFS']+16)<=.2,loud
assert loud['truePeakDBTP']<=-1,loud
decoded=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(M),'-vn','-ar','48000','-ac','2','-f','s16le','-']),dtype='<i2').reshape(-1,2)
with wave.open(str(P/'public/audio/master.wav'),'rb') as w:reference=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)
count=min(len(decoded),len(reference));corr=float(np.corrcoef(decoded[:count].astype(float).ravel(),reference[:count].astype(float).ravel())[0,1]);assert corr>.98,corr
window=decoded[4861*800:4891*800].astype(float);central=decoded[4863*800:4889*800].astype(float)
def level(x):
 peak=float(np.max(np.abs(x)))
 return {'peak_pcm16':peak,'peak_dbfs':float(20*np.log10(peak/32768)) if peak else None,'exact_zero':peak==0}
aac_compare={'decoded_samples_per_channel':len(decoded),'master_samples_per_channel':len(reference),'waveform_correlation_to_master':corr,'authored_silence_window':level(window),'silence_center_excluding2frames_at_edges':level(central),'note':'Exact30frame zero is a PCMmaster property. AAC MDCT boundary ringing and encoder padding are measured separately; no claim that encoded boundaries preserve digitalzero.'}
r={'status':'PASS','movie_sha256':hashlib.sha256(M.read_bytes()).hexdigest(),'frames_extracted':extraction_frames,'encoded_black_window':{'frames':[4861,4891],'continuous_frames_checked':30,'max_rgb_at360':encoded_black_peak,'exact_black':encoded_black_peak==0},'frame_extraction':'exact integer select from final encoded stream; contact at360px; native selected frames retained locally','loudness':loud,'aac_compare':aac_compare,'streams':[{k:s.get(k) for k in ('codec_type','codec_name','width','height','r_frame_rate','avg_frame_rate','nb_frames','duration','sample_rate','channels','pix_fmt','color_space','color_transfer','color_primaries')} for s in probe['streams']],'limitation':'No human listening, continuous audience review or physical RED playback inferred'}
(R/'encoded-qa.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))
