"""Collect final encoded media measurements and representative frames."""
from pathlib import Path
import hashlib,json,subprocess,os,re,tempfile,wave
from PIL import Image,ImageDraw
import numpy as np
P=Path(__file__).resolve().parents[1];W=P.parent;R=W/'review'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd):return subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
m=json.loads((W/'delivery.json').read_text());movie=W/m['outputs']['xiaohongshu']['path'];master=P/'public/audio/master.wav'
initial=sha(movie);probe=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]).stdout)
v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next(s for s in probe['streams'] if s['codec_type']=='audio')
assert (v['codec_name'],v['pix_fmt'],v['width'],v['height'],v['r_frame_rate'],int(v['nb_frames']))==('h264','yuv420p',2160,3840,'60/1',7200)
assert a['codec_name']=='aac' and int(a['sample_rate'])==48000 and a['channels']==2
assert abs(float(probe['format']['duration'])-120)<.05
run(['ffmpeg','-v','error','-xerror','-i',str(movie),'-f','null','-'])
loud=run(['ffmpeg','-hide_banner','-nostats','-i',str(movie),'-vn','-af','loudnorm=I=-16:TP=-1:LRA=11:print_format=json','-f','null','-']).stderr.decode()
measure=json.loads(re.findall(r'\{\s*"input_i"[\s\S]*?\}',loud)[-1]);assert float(measure['input_tp'])<=-1 and abs(float(measure['input_i'])+16)<1
frames=[0,180,300,1050,1680,2460,3120,3900,4439,4455,4470,5400,6030,6300,6780,7199]
folder=R/('encoded-qa-'+initial[:12]);folder.mkdir(exist_ok=False)
thumbs=[];native=[]
selector='+'.join('eq(n'+chr(92)+','+str(f)+')' for f in frames)
run(['ffmpeg','-v','error','-xerror','-n','-i',str(movie),'-vf','select='+selector,'-fps_mode','passthrough','-start_number','0','-threads','2',str(folder/'sample-%02d.png')])
for i,f in enumerate(frames):
    dest=folder/f'frame-{f}.png'
    (folder/f'sample-{i:02}.png').rename(dest)
    im=Image.open(dest).convert('RGB');assert im.size==(2160,3840)
    if f in [300,4470,6030,7199]:native.append({'frame':f,'path':dest.relative_to(W).as_posix(),'sha256':sha(dest)})
    im.thumbnail((360,640));thumbs.append(im.copy())
contact=Image.new('RGB',(1440,668*4),'#cec8bf');d=ImageDraw.Draw(contact)
for i,(f,im) in enumerate(zip(frames,thumbs)):
    x=i%4*360;y=i//4*668;contact.paste(im,(x,y));d.text((x+5,y+644),str(f),fill='#1D3557')
contact.save(folder/'contact.jpg',quality=92)
with tempfile.TemporaryDirectory(prefix='babel-encoded-audio-') as td:
    pcm=Path(td)/'encoded.wav';run(['ffmpeg','-v','error','-n','-i',str(movie),'-vn','-ar','48000','-ac','2','-c:a','pcm_s16le',str(pcm)])
    with wave.open(str(pcm),'rb') as d:encoded=np.frombuffer(d.readframes(d.getnframes()),dtype='<i2');decoded_samples=d.getnframes()
    with wave.open(str(master),'rb') as d:source=np.frombuffer(d.readframes(d.getnframes()),dtype='<i2')
    n=min(len(source),len(encoded));correlation=float(np.corrcoef(source[:n:16],encoded[:n:16])[0,1]);assert correlation>.98
    assert abs(decoded_samples-5760000)<=2400
assert sha(movie)==initial
report={'status':'PASS','movie_sha256':initial,'bytes':movie.stat().st_size,'master_sha256':sha(master),'native_dimensions':[2160,3840],'fps':60,'video_frames':7200,'video_duration':float(v['duration']),'audio_duration':float(a['duration']),'container_duration':float(probe['format']['duration']),'strict_full_decode':'PASS','encoded_loudness':{'integrated_lufs':float(measure['input_i']),'true_peak_dbtp':float(measure['input_tp'])},'master_to_AAC_correlation_stride16':correlation,'decoded_audio_samples_per_channel':decoded_samples,'representative_frames':frames,'native_evidence':native,'contact_sheet':{'path':(folder/'contact.jpg').relative_to(W).as_posix(),'sha256':sha(folder/'contact.jpg')},'human_continuous_review':'NOT_RUN','human_listening':'NOT_RUN','real_phone_playback':'NOT_RUN','screening_limit':'Representative encoded stills do not replace full-frame screening or human perception.'}
(R/'encoded-media-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
