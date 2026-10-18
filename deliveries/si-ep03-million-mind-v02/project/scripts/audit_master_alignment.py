#!/usr/bin/env python3
"""Measure whether loudness processing shifted the authored PCM event timeline."""
from pathlib import Path
import importlib.util,json,subprocess
import numpy as np
P=Path(__file__).resolve().parents[1];A=P/'public/audio';D=P/'out/dry-mix-alignment.wav';D.parent.mkdir(parents=True,exist_ok=True)
flt='[1:a][0:a]sidechaincompress=threshold=0.035:ratio=5:attack=20:release=250:makeup=1[d];[0:a][d][2:a]amix=inputs=3:duration=longest:normalize=0,aresample=48000,atrim=end_sample=5760000,asetpts=PTS-STARTPTS[o]'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-y','-i',str(A/'narration.wav'),'-i',str(A/'score.wav'),'-i',str(A/'sfx.wav'),'-filter_complex',flt,'-map','[o]','-ar','48000','-ac','2','-c:a','pcm_s16le',str(D)],check=True)
s=importlib.util.spec_from_file_location('qa',P/'scripts/collect_qa.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
dry=m.decode_stereo_48k('ffmpeg',D,phase='Dry authored PCM timeline',numpy=np);master=m.decode_stereo_48k('ffmpeg',A/'master.wav',phase='Processed shared PCM master',numpy=np)
windows=[m.normalized_window_correlation(dry,master,center_seconds=t,numpy=np) for t in [2.1,17.2,50.2,76.2,100.4,117.2]]
ok=all(x['correlation'] is not None and x['correlation']>.95 and abs(x['best_lag_ms'])<=.05 for x in windows)
d={'status':'PASS' if ok else 'REVIEW_REQUIRED','method':'Dry pre-loudnorm authored mix compared to processed PCM master, six 0.5s windows with bounded FFT lag search','windows':windows,'source_sample_rate':48000,'limitation':'Waveform alignment and static SFX sample mapping evidence; not pronunciation or human listening acceptance'}
(P.parent/'review/master-event-alignment.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps(d,ensure_ascii=False,indent=2));raise SystemExit(not ok)
