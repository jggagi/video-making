"""Mux native visual track and exact120s PCM; never overwrite formal output."""
from pathlib import Path
import hashlib,json,subprocess,wave,os
P=Path(__file__).resolve().parents[1];W=P.parent
sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
m=json.loads((W/'delivery.json').read_text());pointer=W/'review/render-staging.json'
s=json.loads(pointer.read_text());v=Path(s['file']).resolve(strict=True)
assert s['status']=='READY' and str(v).startswith('/Volumes/AgentDev/') and v.name=='video-only.mp4'
assert sha(v)==s['sha256'] and v.stat().st_size==s['bytes']
a=P/'public/audio/master.wav'
with wave.open(str(a),'rb') as w:assert (w.getframerate(),w.getnchannels(),w.getnframes(),w.getsampwidth())==(48000,2,5760000,2)
o=W/m['outputs']['xiaohongshu']['path'];tmp=o.with_name(o.stem+'.mux-partial.mp4')
assert not o.exists() and not tmp.exists()
subprocess.run(['ffmpeg','-v','error','-n','-i',str(v),'-i',str(a),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','320k','-ar','48000','-ac','2','-movflags','+faststart',str(tmp)],check=True)
p=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(tmp)]));vs=next(x for x in p['streams'] if x['codec_type']=='video');aus=next(x for x in p['streams'] if x['codec_type']=='audio')
assert (int(vs['nb_frames']),float(vs['duration']),vs['r_frame_rate'],vs['width'],vs['height'])==(7200,120.,'60/1',2160,3840)
assert abs(float(aus['duration'])-120)<.05 and abs(float(p['format']['duration'])-120)<.05
os.link(tmp,o);tmp.unlink();s.update(status='MUXED',final_movie_sha256=sha(o));pointer.write_text(json.dumps(s,indent=2)+'\n')
r={'status':'PASS','video_only_sha256':s['sha256'],'movie_sha256':sha(o),'master_sha256':sha(a),'native_dimensions':[2160,3840],'video_frames':7200,'video_duration':120,'audio_duration':float(aus['duration']),'container_duration':float(p['format']['duration']),'master_samples_per_channel':5760000,'capture':s['capture']}
(W/'review/mux-provenance.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
