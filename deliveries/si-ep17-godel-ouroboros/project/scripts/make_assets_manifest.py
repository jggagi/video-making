"""Index the exact local assets/settings used for this edition."""
from pathlib import Path
import hashlib,json,wave
P=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assets=[]
for p in sorted((P/'public').rglob('*')):
 if not p.is_file() or 'mix-candidate-' in str(p):continue
 item={'id':str(p.relative_to(P/'public')),'path':str(p.relative_to(P)),'sha256':sha(p),'bytes':p.stat().st_size}
 if p.suffix=='.wav':
  try:
   with wave.open(str(p),'rb') as w:item['measuredWav']={'sample_rate':w.getframerate(),'channels':w.getnchannels(),'sample_width':w.getsampwidth(),'declared_samples':w.getnframes(),'actual_decoded_bytes':len(w.readframes(w.getnframes()))}
  except wave.Error:item['rawHeader']='Provider original retained; use canonical and measured synthesis manifest for playback'
 assets.append(item)
source={str(p.relative_to(P)):sha(p) for p in sorted((P/'src').glob('*'))if p.is_file()}
report={'work':'si-ep17-godel-ouroboros','generation':'Native deterministic Canvas2D/SVG code; no generated raster image or 3D asset','visual_source':source,'typography':{'families':['Songti SC','PingFang SC','Menlo'],'source':'Local macOS fonts; not redistributed; alternate machines need layout verification'},'narration_provider':'Aliyun Bailian','actual_model':'cosyvoice-v3-flash','voice':'longtian_v3','synthesis_evidence':'../review/audio-synthesis.json','music_and_sfx':'Local original deterministic procedural score, no sampled commercial recording','assets':assets}
(P/'assets-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('Indexed',len(assets),'local assets')
