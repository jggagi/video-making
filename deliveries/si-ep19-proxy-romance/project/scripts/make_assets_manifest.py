from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parents[1]
files=[]
for f in sorted(P.rglob('*')):
 if f.is_file() and '__pycache__' not in f.parts and f.name!='assets-manifest.json' and 'node_modules' not in f.parts:
  files.append({'id':str(f.relative_to(P)),'path':str(f.relative_to(P)),'bytes':f.stat().st_size,'sha256':hashlib.file_digest(f.open('rb'),'sha256').hexdigest()})
m={'schemaVersion':1,'work':'si-ep19-proxy-romance','visuals':{'kind':'deterministic SVG paths and DOM typesetting','rasterAssets':[],'logicalCanvas':[1080,1920],'nativeRaster':[2160,3840],'timing':'absolute frame math at60fps','palette':{'canvas':'#07090C','hosts':['#3F3F46','#18181B'],'shadows':['#E2E8F0','#D97706']}},'fonts':{'source':'licensed locally installed macOS fonts, not redistributed','families':['PingFang SC','Songti SC','Menlo','SFMono-Regular']},'audio':{'narration':'Aliyun Bailian qwen-audio-3.0-tts-plus, qwen-audio-3.0-tts-plus-longlangmoyue','cacheManifest':'public/audio/provider-manifest.json','originalSourceSamples':'public/audio/history/original-full-text-rate1/','scoreSFX':'original local deterministic DSP; no external music'},'files':files}
(P/'assets-manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print('Hashed',len(files),'project assets')
