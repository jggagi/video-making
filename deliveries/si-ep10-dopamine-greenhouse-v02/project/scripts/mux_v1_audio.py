"""Publish new visual track with the exact original approved AAC stream."""
from pathlib import Path
import hashlib,json,os,subprocess,wave,sys

P=Path(__file__).resolve().parents[1];W=P.parent
V1=W.parent/'si-ep10-dopamine-greenhouse'
OLD=V1/'小红书/si-ep10-dopamine-greenhouse-xiaohongshu-90s-portrait.mp4'
POINTER=W/'review/render-staging.json'
stage=json.loads(POINTER.read_text())
VIDEO=Path(stage['file']).resolve(strict=True)
assert stage['status']=='READY' and VIDEO.name=='video-only.mp4'
if sys.platform=='darwin':assert str(VIDEO).startswith('/Volumes/AgentDev/')
D=json.loads((W/'delivery.json').read_text())
OUT=W/D['outputs']['xiaohongshu']['path']
PART=OUT.with_name(OUT.stem+'.mux-partial.mp4')
REPORT=W/'review/audio-preservation.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def aac(p):return hashlib.sha256(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:a:0','-c:a','copy','-f','adts','-'])).hexdigest()
assert not OUT.exists() and not PART.exists() and not REPORT.exists(),'Refusing overwrite'
assert sha(VIDEO)==stage['sha256'] and VIDEO.stat().st_size==stage['bytes']
assert sha(OLD)=='2241fd76ba65c08758a84813f0f13bbe125f1d5ca6f868a090e56e85e44323b0'
master=P/'public/audio/master.wav'
assert sha(master)==D['audio']['master_sha256']=='d787f5794a2f8cc76f159a58df02b66cd7721bb54e08d94149f1f0f251ecc968'
with wave.open(str(master),'rb') as w:
 assert (w.getframerate(),w.getnchannels(),w.getnframes())==(48000,2,4320000)
 w.setpos(4861*800);assert not any(w.readframes(30*800))
before=probe(VIDEO);vs=before['streams']
assert len(vs)==1 and vs[0]['codec_type']=='video'
assert (int(vs[0]['nb_frames']),vs[0]['r_frame_rate'],float(vs[0]['duration']))==(5400,'60/1',90.0)
subprocess.run(['ffmpeg','-v','error','-n','-i',str(VIDEO),'-i',str(OLD),'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(PART)],check=True)
after=probe(PART);v=next(s for s in after['streams'] if s['codec_type']=='video');a=next(s for s in after['streams'] if s['codec_type']=='audio')
assert (int(v['nb_frames']),v['r_frame_rate'],float(v['duration']))==(5400,'60/1',90.0)
old_aac=aac(OLD);new_aac=aac(PART);assert old_aac==new_aac
def audio_packets(p):
 r=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_packets','-select_streams','a:0','-show_entries','stream=nb_read_packets','-of','json',str(p)]))
 return int(r['streams'][0]['nb_read_packets'])
assert audio_packets(OLD)==audio_packets(PART)==4221
os.link(PART,OUT);PART.unlink()
report={'status':'PASS','v1_movie_sha256':sha(OLD),'v2_movie_sha256':sha(OUT),'master_sha256':sha(master),'aac_adts_sha256':new_aac,'v1_aac_adts_sha256':old_aac,'audio_packets':4221,'audio_stream_copied':True,'audio_reencoded':False,'pcm_samples_per_channel':4320000,'pcm_silence_frames':[4861,4891],'video_duration':float(v['duration']),'audio_duration':float(a['duration']),'container_duration':float(after['format']['duration']),'method':'New native video track only; uncapped stream-copy mux of original approved v1 AAC, no shortest/trim/frame cap at mux.'}
REPORT.write_text(json.dumps(report,indent=2)+'\n')
stage['status']='MUXED';stage['final_movie_sha256']=report['v2_movie_sha256'];POINTER.write_text(json.dumps(stage,indent=2)+'\n')
print(json.dumps(report,indent=2))
