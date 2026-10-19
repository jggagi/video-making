#!/usr/bin/env python3
"""Measure final AAC loudness and describe codec silence boundaries, without ASR."""
from pathlib import Path
import subprocess,re,json,hashlib,argparse
import numpy as np
P=Path(__file__).resolve().parents[1];W=P.parent;R=W/'review';d=json.loads((W/'delivery.json').read_text());report={'scope':'Final AAC sound measurements only; no pronunciation or human listening acceptance','outputs':{}}
parser=argparse.ArgumentParser();parser.add_argument('--layout',choices=['bilibili','xiaohongshu','both'],default='both');args=parser.parse_args()
existing=R/'encoded-audio-audit.json'
if existing.exists():report=json.loads(existing.read_text())
for key,spec in d['outputs'].items():
 if args.layout!='both' and args.layout!=key:continue
 f=W/spec['path']
 decoded=subprocess.run(['ffmpeg','-v','error','-i',str(f),'-vn','-ar','48000','-ac','2','-f','s16le','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
 x=np.frombuffer(decoded,dtype='<i2').reshape(-1,2)
 proc=subprocess.run(['ffmpeg','-hide_banner','-nostdin','-i',str(f),'-vn','-af','ebur128=peak=true','-f','null','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,text=True)
 text=proc.stderr; lufs=float(re.findall(r'I:\s+(-?[\d.]+) LUFS',text)[-1]);tp=float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS',text)[-1])
 windows={}
 for name,a,b in [('authoredPause',4704000,4728000),('pauseInterior',4706880,4725120)]:
  z=x[a:b].astype(np.float64);windows[name]={'startSample':a,'endSampleExclusive':b,'peakPcm16':int(np.max(np.abs(z))),'rmsDbfs':float(20*np.log10(max(np.sqrt(np.mean(z*z))/32768,1e-15))),'nonzeroSamples':int(np.count_nonzero(z))}
 report['outputs'][key]={'mediaSHA256':hashlib.sha256(f.read_bytes()).hexdigest(),'decodedPCM_SHA256':hashlib.sha256(decoded).hexdigest(),'samplesPerChannel':len(x),'integratedLUFS':lufs,'truePeakDBTP':tp,'loudnessPass':-18<=lufs<=-16 and tp<=-1,'pause':windows,'note':'PCM master is exact digital silence for the full authored interval. Lossy AAC may smear event energy at transform-window edges; interior measured separately.'}
 print(key,lufs,tp,flush=True)
report['identicalDecodedAACBetweenLayouts']=(len({v['decodedPCM_SHA256'] for v in report['outputs'].values()})==1) if len(report['outputs'])==2 else None
(R/'encoded-audio-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
assert all(v['loudnessPass'] for v in report['outputs'].values())
