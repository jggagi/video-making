"""Replace only a proved bad capture with a fresh render of the same source frame."""
from pathlib import Path
import json,hashlib,os,subprocess,tempfile
P=Path(__file__).resolve().parents[1];W=P.parent;R=W/'review'
sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
assert os.environ.get('TMPDIR','').startswith('/Volumes/AgentDev/')
pointer=R/'render-staging.json';old=json.loads(pointer.read_text());bad=Path(old['file']);fix=R/'source-4698.png';assert old['status']=='MUXED' and sha(bad)==old['sha256']
assets=json.loads((P/'assets-manifest.json').read_text());assert all(sha(P/x['path'])==x['sha256'] for x in assets['code'])
# Independent miniature filter check establishes eq(n,2) targets zero-based frame2.
test=['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=16x16:r=60:d=0.1','-f','lavfi','-i','color=red:s=16x16:r=60:d=0.0166667','-filter_complex','[0:v][1:v]overlay=enable=eq(n\\,2):eof_action=repeat:shortest=0,format=rgb24[v]','-map','[v]','-frames:v','6','-f','rawvideo','pipe:1']
r=subprocess.run(test,capture_output=True,check=True).stdout;assert [i for i in range(6) if r[i*16*16*3]>100]==[2]
stage=Path(tempfile.mkdtemp(prefix='babel-native-repair-'));out=stage/'video-only.mp4'
filters='[1:v]scale=2160:3840:in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p,setsar=1[fix];[0:v][fix]overlay=enable=eq(n\\,4698):eof_action=repeat:shortest=0:format=yuv420[v]'
cmd=['ffmpeg','-v','error','-n','-i',str(bad),'-i',str(fix),'-filter_complex_threads','2','-filter_complex',filters,'-map','[v]','-an','-frames:v','7200','-r','60','-c:v','libx264','-preset','fast','-crf','18','-threads','4','-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart','-progress','pipe:1','-nostats',str(out)]
proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);last=-600
for line in proc.stdout:
 if line.startswith('frame='):
  f=int(line.strip().split('=')[1])
  if f>=last+600:last=f;print('repair encoded frames',f,flush=True)
err=proc.stderr.read();assert proc.wait()==0,err[-1000:]
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(out)]));v=probe['streams'][0];assert (int(v['nb_frames']),v['width'],v['height'],v['r_frame_rate'],float(v['duration']))==(7200,2160,3840,'60/1',120.)
report={'status':'REPAIRED_TRACK_READY_PENDING_FINAL_QC','bad_frame_zero_based':4698,'method':'Fresh Remotion PNG of exact absolute source frame4698; FFmpeg full-frame replacement at eq(n,4698), full H264 reencode. No adjacent-frame substitution, interpolation or frame deletion.','frame_index_filter_check':{'eq_n_2_affected_zero_based_frames':[2]},'failed_movie':'review/candidate-02-capture-rejected/capture-fault-4698.mp4','failed_movie_sha256':old['final_movie_sha256'],'original_video_track_sha256':old['sha256'],'native_redraw':{'path':'review/source-4698.png','sha256':sha(fix),'dimensions':[2160,3840]},'new_video_track_sha256':sha(out),'total_frames':7200,'duration_seconds':120,'frame_rate':60,'source_code_hashes':assets['code'],'final_rescan':'PENDING'}
(R/'capture-repair.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
new={'status':'READY','file':str(out),'sha256':sha(out),'bytes':out.stat().st_size,'capture':{**old['capture'],'repair_frame':4698,'repair_record':'review/capture-repair.json'},'scope':'Owned corrected scratch track; failed originals retained'};pointer.write_text(json.dumps(new,indent=2)+'\n');print('Corrected native track ready',flush=True)
