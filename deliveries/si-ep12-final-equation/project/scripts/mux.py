"""Mux the verified native visual track with the exact 90-second PCM master."""
from pathlib import Path
import hashlib,json,subprocess,wave,os
P=Path(__file__).resolve().parents[1];W=P.parent
sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
manifest=json.loads((W/'delivery.json').read_text());pointer=W/'review/render-staging.json'
s=json.loads(pointer.read_text());video=Path(s['file']).resolve(strict=True)
assert s['status']=='READY' and str(video).startswith('/Volumes/AgentDev/') and video.name=='video-only.mp4'
assert sha(video)==s['sha256'] and video.stat().st_size==s['bytes']
master=P/'public/audio/master.wav'
with wave.open(str(master),'rb') as a:
 assert (a.getframerate(),a.getnchannels(),a.getnframes(),a.getsampwidth())==(48000,2,4320000,2)
 a.setpos(4860*800);assert not any(a.readframes(30*800))
out=W/manifest['outputs']['xiaohongshu']['path'];partial=out.with_name(out.stem+'.mux-partial.mp4')
assert not out.exists() and not partial.exists()
subprocess.run(['ffmpeg','-v','error','-n','-i',str(video),'-i',str(master),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','320k','-ar','48000','-ac','2','-movflags','+faststart',str(partial)],check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(partial)]))
v=next(x for x in probe['streams'] if x['codec_type']=='video');a=next(x for x in probe['streams'] if x['codec_type']=='audio')
assert (int(v['nb_frames']),float(v['duration']),v['r_frame_rate'])==(5400,90.,'60/1')
assert abs(float(a['duration'])-90)<.05 and abs(float(probe['format']['duration'])-90)<.05
os.link(partial,out);partial.unlink()
s.update(status='MUXED',final_movie_sha256=sha(out));pointer.write_text(json.dumps(s,indent=2)+'\n')
report={'status':'PASS','video_only_sha256':s['sha256'],'movie_sha256':sha(out),'master_sha256':sha(master),'native_dimensions':[v['width'],v['height']],'video_frames':int(v['nb_frames']),'video_duration':float(v['duration']),'audio_duration':float(a['duration']),'container_duration':float(probe['format']['duration']),'master_samples_per_channel':4320000,'master_silence_frames':[4860,4890],'AAC_silence_note':'Exact digital zero is guaranteed in PCM; AAC transform coding can create boundary leakage, separately measured.'}
(W/'review/mux-provenance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
