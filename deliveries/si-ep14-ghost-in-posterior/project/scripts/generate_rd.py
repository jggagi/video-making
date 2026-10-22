#!/usr/bin/env python3
"""Deterministically bake a 2D Gray–Scott concentration cache, never a 3D scene.

The cache is creative source data. Remotion selects two absolute-frame snapshots;
render order cannot affect the result. NumPy/Pillow come from the existing bundled
runtime. No unseeded RNG, network, wall-clock state, or frame-history dependence.
"""
from pathlib import Path
import base64,hashlib,io,json,os
import numpy as np
from PIL import Image
P=Path(__file__).resolve().parents[1]; OUT=P/'public/rd/gray-scott.json'
WIDTH,HEIGHT=256,192
START,END,STRIDE=2820,4380,24
SEED=14014
DU,DV,F,K,DT=0.16,0.08,0.033,0.0585,1.0
STEPS=2

def sha(b):return hashlib.sha256(b).hexdigest()
def lap(a):
 b=np.pad(a,1,mode='edge')
 return -a+.2*(b[:-2,1:-1]+b[2:,1:-1]+b[1:-1,:-2]+b[1:-1,2:])+.05*(b[:-2,:-2]+b[:-2,2:]+b[2:,:-2]+b[2:,2:])
def main():
 if OUT.exists():
  cache=json.loads(OUT.read_text())
  if cache.get('metadata',{}).get('generatorSha256')==sha(Path(__file__).read_bytes()):
   print('Matching deterministic cache already exists; reused');return
  raise SystemExit('Divergent reaction-diffusion cache preserved; version output before rebuilding')
 u=np.ones((HEIGHT,WIDTH),dtype=np.float64);v=np.zeros_like(u)
 yy,xx=np.mgrid[0:HEIGHT,0:WIDTH]
 noise=np.mod(np.sin(xx*12.9898+yy*78.233+SEED)*43758.5453,1)
 # Explicit modular sequence provides fixed seed positions; no random APIs.
 for i in range(47):
  x=12+((i*73+SEED*17)%(WIDTH-24));y=12+((i*47+SEED*13)%(HEIGHT-24))
  radius=3+(i%4)
  angle=np.arctan2(yy-y,xx-x)
  distorted=radius*(1+.27*np.sin(angle*3+i)+.16*np.sin(angle*5+i*.71))
  mask=(xx-x)**2+(yy-y)**2<=distorted**2
  u[mask]=.4+.2*noise[mask];v[mask]=.16+.26*noise[mask]
 # Small concentration perturbations are spatially fixed and deterministic.
 v+=.003*(np.sin(xx*.57+yy*.23)**2)
 def snapshot(frame):
  a=np.clip((v-.025)*760,0,225).astype(np.uint8)
  rgba=np.empty((HEIGHT,WIDTH,4),dtype=np.uint8)
  rgba[:,:,0]=16;rgba[:,:,1]=185;rgba[:,:,2]=129;rgba[:,:,3]=a
  b=io.BytesIO();Image.fromarray(rgba).save(b,format='PNG',compress_level=8)
  return {'frame':frame,'pngDataUri':'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()}
 frames=list(range(START,END,STRIDE))+[END]
 snapshots=[];previous=START
 for frame in frames:
  for _ in range((frame-previous)*STEPS):
   reaction=u*v*v
   un=u+DT*(DU*lap(u)-reaction+F*(1-u))
   vn=v+DT*(DV*lap(v)+reaction-(F+K)*v)
   np.clip(un,0,1,out=u);np.clip(vn,0,1,out=v)
  snapshots.append(snapshot(frame));previous=frame
 metadata={'algorithm':'Gray–Scott reaction-diffusion','algorithmVersion':2,'generatorSha256':sha(Path(__file__).read_bytes()),'seed':SEED,'grid':{'width':WIDTH,'height':HEIGHT},'startFrame':START,'endFrame':END,'sampleStrideFrames':STRIDE,'snapshotFrames':frames,'solverStepsPerFilmFrame':STEPS,'integrationStep':DT,'parameters':{'Du':DU,'Dv':DV,'F':F,'k':K},'laplacian':'no-flux edges; axial0.20/diagonal0.05/center-1','initialCondition':'47 fixed modular irregular spots with deterministic spatial concentration heterogeneity','interpolation':'absolute frame selects adjacent RGBA2D snapshots; linear alpha crossfade; no runtime history','rasterScope':'2D simulated concentration texture256x192; overlaid vector membrane and filaments are rasterized natively at2160x3840','stateSha256':sha(u.tobytes()+v.tobytes())}
 OUT.parent.mkdir(parents=True,exist_ok=True);encoded=json.dumps({'metadata':metadata,'snapshots':snapshots},separators=(',',':')).encode()+b'\n'
 with OUT.open('xb') as stream:stream.write(encoded)
 print(json.dumps({'snapshots':len(snapshots),'bytes':len(encoded),'sha256':sha(encoded),'grid':[WIDTH,HEIGHT]}))
if __name__=='__main__':main()
