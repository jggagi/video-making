"""Record portable EP14 sources, deterministic art and hash-verified local audio."""
from pathlib import Path
import hashlib,json,wave
P=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
provider=json.loads((P/'public/audio/provider-manifest.json').read_text());rawcounts={x['rawPath']:x['rawSamples24k'] for x in provider['segments'].values()}
resources=[]
for f in sorted((P/'public').rglob('*')):
 if not f.is_file() or f.suffix not in ('.wav','.json'):continue
 if 'history' in f.parts:continue
 rel=f.relative_to(P).as_posix();item={'id':rel.removeprefix('public/'),'path':rel,'sha256':sha(f),'bytes':f.stat().st_size}
 if f.suffix=='.wav':
  with wave.open(str(f),'rb') as w:item.update(sample_rate=w.getframerate(),channels=w.getnchannels(),sample_width_bytes=w.getsampwidth(),samples_per_channel=w.getnframes())
  if rel in rawcounts:item.update(declared_header_samples=item['samples_per_channel'],samples_per_channel=rawcounts[rel],count_basis='Verified actual PCM payload in provider manifest; provider streaming-header declarations can overflow')
 resources.append(item)
fonts=[]
for family,path in [('Heiti SC','/System/Library/Fonts/STHeiti Medium.ttc'),('Menlo','/System/Library/Fonts/Menlo.ttc')]:
 f=Path(path);fonts.append({'family':family,'installed_dependency':path,'sha256':sha(f),'redistributed':False,'source':'macOS installed font; no remote font request'})
rd=json.loads((P/'public/rd/gray-scott.json').read_text())
manifest={'schema_version':1,'resources':resources,'fonts':fonts,'visuals':{'type':'Frame-driven flat SVG + deterministic 2D Gray–Scott cache','geometry_sha256':sha(P/'src/Geometry.tsx'),'rd_metadata':rd['metadata'],'native_vector_rasterization':[2160,3840],'procedural_texture_resolution':[256,192],'voiceprint':'Locally computed mel spectrum of narrator S01 cue; fictional acoustic fossil, no real deceased-person voice'},'narration':{'provider':'Aliyun Bailian','effective_model':'cosyvoice-v3-flash','voice':'longtian_v3','rate':1,'cache':'public/audio/provider-manifest.json'},'audio':'One exact90s48kHz stereo master reused by portrait; deterministic local score/SFX; no ASR/image/video cloud calls','source_files':{f.relative_to(P).as_posix():sha(f) for f in sorted((P/'src').glob('*')) if f.is_file()}}
(P/'assets-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print('Recorded',len(resources),'resources and',len(fonts),'installed fonts')
