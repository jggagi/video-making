from pathlib import Path
import hashlib,json,subprocess,wave,os
P=Path(__file__).resolve().parents[1];W=P.parent
sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
m=json.loads((W/'delivery.json').read_text());pointer=W/'review/render-staging.json';s=json.loads(pointer.read_text());v=Path(s['file']).resolve(strict=True)
assert s['status']=='READY' and str(v).startswith('/Volumes/AgentDev/') and sha(v)==s['sha256']
a=P/'public/audio/master.wav'
with wave.open(str(a),'rb') as w: assert(w.getframerate(),w.getnchannels(),w.getnframes(),w.getsampwidth())==(48000,2,5760000,2)
out=W/m['outputs']['xiaohongshu']['path'];partial=out.with_name(out.stem+'.mux-partial.mp4');assert not out.exists() and not partial.exists()
subprocess.run(['ffmpeg','-v','error','-n','-i',str(v),'-i',str(a),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','320k','-ar','48000','-ac','2','-movflags','+faststart',str(partial)],check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(partial)]));vs=next(x for x in probe['streams'] if x['codec_type']=='video');aas=next(x for x in probe['streams'] if x['codec_type']=='audio')
assert (int(vs['nb_frames']),float(vs['duration']),vs['width'],vs['height'],vs['r_frame_rate'])==(7200,120.,2160,3840,'60/1')
assert abs(float(aas['duration'])-120)<.05 and abs(float(probe['format']['duration'])-120)<.05
os.link(partial,out);partial.unlink();s.update(status='MUXED',final_movie_sha256=sha(out));pointer.write_text(json.dumps(s,indent=2)+'\n')
r={'status':'PASS','movie_sha256':sha(out),'master_sha256':sha(a),'video_only_sha256':sha(v),'native_dimensions':[2160,3840],'frames':7200,'video_duration':120,'audio_duration':aas['duration'],'container_duration':probe['format']['duration'],'PCM_samples_per_channel':5760000};(W/'review/mux-provenance.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
