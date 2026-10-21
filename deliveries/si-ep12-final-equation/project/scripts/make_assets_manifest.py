"""Record local, inspectable EP12 creative resources without copying licensed system fonts."""
from pathlib import Path
import hashlib,json,wave
P=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
resources=[]
provider=json.loads((P/'public/audio/provider-manifest.json').read_text())
raw_counts={v['raw_path']:v['actual_samples_24k'] for v in provider['segments'].values()}
for f in sorted((P/'public/audio').rglob('*.wav')):
 with wave.open(str(f),'rb') as w:
  info={'sample_rate':w.getframerate(),'channels':w.getnchannels(),'samples_per_channel':w.getnframes(),'sample_width_bytes':w.getsampwidth()}
  if f.relative_to(P).as_posix() in raw_counts:
   info['declared_header_samples']=info['samples_per_channel'];info['samples_per_channel']=raw_counts[f.relative_to(P).as_posix()];info['count_basis']='Actual verified PCM payload in provider manifest, not streaming WAV header'
 resources.append({'id':f'audio/{f.relative_to(P/"public/audio").as_posix()}','path':f.relative_to(P).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size,**info})
fonts=[('PingFang SC',Path('/System/Library/AssetsV2/com_apple_MobileAsset_Font8/86ba2c91f017a3749571a82f2c6d890ac7ffb2fb.asset/AssetData/PingFang.ttc')),('Songti SC',Path('/System/Library/Fonts/Supplemental/Songti.ttc')),('Menlo',Path('/System/Library/Fonts/Menlo.ttc'))]
fontrecords=[{'family':name,'local_dependency':str(path),'sha256':sha(path),'redistributed':False,'reason':'Installed macOS font; rendered locally, no network font request or font redistribution.'} for name,path in fonts]
manifest={'schema_version':1,'resources':resources,'visuals':{'type':'deterministic frame-driven pure 2D SVG','path':'src/Geometry.tsx','sha256':sha(P/'src/Geometry.tsx'),'raster_assets':[]},'fonts':fontrecords,'narration_provenance':'public/audio/provider-manifest.json','sound_provenance':'public/audio/mix-manifest.json','reuse':'One narration cache and one 48kHz PCM master. No image/video cloud generation or ASR performed.'}
(P/'assets-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(f'Recorded {len(resources)} audio resources and {len(fontrecords)} local font dependencies')
