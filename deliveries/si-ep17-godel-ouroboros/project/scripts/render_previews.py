from pathlib import Path
import subprocess,json,hashlib
P=Path(__file__).resolve().parents[1];W=P.parent
for args in [('stills','60','840','2160','3000','3960','4890','5160','5399'),('covers',),('preview','0','239'),('preview','2820','2999'),('preview','3900','4079'),('preview','4800','5039')]:
 subprocess.run(['node','scripts/render.mjs',*args],cwd=P,check=True)
files=[W/'review'/f'motion-{a}-{b}.mp4' for a,b in [(0,239),(2820,2999),(3900,4079),(4800,5039)]]
report={'status':'RENDERED_NOT_HUMAN_ACCEPTED','nativeDimensions':[2160,3840],'fps':60,'masterSha256':hashlib.sha256((P/'public/audio/master.wav').read_bytes()).hexdigest(),'clips':[{'path':str(x.relative_to(W)),'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()}for x in files],'continuous_human_listening':'NOT_RUN','device_playback':'NOT_RUN'}
(W/'review/native-preview-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
