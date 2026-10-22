"""Create a deterministic local mel voiceprint from the authorized narrator cue.
This is a fictional acoustic fossil graphic, not a deceased person's recording.
"""
from pathlib import Path
import hashlib,json,wave
import numpy as np
P=Path(__file__).resolve().parents[1]
m=json.loads((P/'public/audio/provider-manifest.json').read_text())['segments']['S01'];f=P/m['cuePath']
assert hashlib.sha256(f.read_bytes()).hexdigest()==m['cueSha256']
with wave.open(str(f),'rb') as w:
 sr=w.getframerate();assert w.getnchannels()==1
 x=np.frombuffer(w.readframes(sr*4),dtype='<i2').astype(float)/32768
nfft=1024;hop=256
frames=np.lib.stride_tricks.sliding_window_view(np.pad(x,(0,nfft)),nfft)[::hop]
power=np.abs(np.fft.rfft(frames*np.hanning(nfft),axis=1))**2
mel=lambda hz:2595*np.log10(1+hz/700)
hz=lambda me:700*(10**(me/2595)-1)
edges=hz(np.linspace(mel(60),mel(8000),34));freq=np.fft.rfftfreq(nfft,1/sr)
filters=[]
for lo,mid,hi in zip(edges[:-2],edges[1:-1],edges[2:]):filters.append(np.maximum(0,np.minimum((freq-lo)/(mid-lo),(hi-freq)/(hi-mid))))
energy=power@np.array(filters).T
energy=10*np.log10(np.maximum(energy,1e-12));energy=np.clip((energy-(energy.max()-65))/65,0,1)
indices=np.linspace(0,len(energy)-1,88).astype(int)
data=np.rint(energy[indices]*255).astype(int).tolist()
record={'method':'1024sample Hann STFT /256sample hop /32 triangular mel bands60..8000Hz /65dB range','sourceCue':m['cuePath'],'sourceSha256':m['cueSha256'],'sourceDurationSeconds':4,'narrationVoice':'longtian_v3','meaning':'Narrator cue is used as fictional acoustic-fossil art. No real deceased-person recording or voice cloning.','timeBins':88,'melBands':32,'values':data}
(P/'public/voiceprint.json').write_text(json.dumps(record,separators=(',',':'))+'\n');print('Local mel voiceprint generated:88time bins x32mel bands')
