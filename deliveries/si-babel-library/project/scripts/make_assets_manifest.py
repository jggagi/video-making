"""Hash local creative assets; retain provider provenance without raw responses."""
from pathlib import Path
import hashlib,json,plistlib
P=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
for p in sorted((P/'public').rglob('*')):
    if p.is_file():
        assert not p.is_symlink()
        records.append({'id':p.relative_to(P/'public').as_posix(),'path':p.relative_to(P).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size,'source':'Aliyun Bailian authorized narration/cache' if any(x in p.parts for x in ['raw','canonical','cues','tts-input']) else 'Local procedural audio or verified provenance metadata'})
source_files=[*sorted((P/'src').glob('*')),P/'scripts/build_audio.py',P/'scripts/render.mjs',P/'scripts/synthesize.py',P/'segments.json',P/'timeline.json',P/'audio-timing.json']
chrome=Path('/Applications/Google Chrome.app/Contents/Info.plist');version=plistlib.loads(chrome.read_bytes())['CFBundleShortVersionString'] if chrome.exists() else 'not available'
manifest={'schema_version':1,'work':'si-babel-library','platforms':['xiaohongshu'],'asset_generation':'All visuals are deterministic DOM/SVG vector code rasterized at2160x3840. No generated bitmap/video source.','assets':records,'code':[{ 'path':p.relative_to(P).as_posix(),'sha256':sha(p)} for p in source_files],'font_dependencies':{'families_requested':['PingFang SC','Noto Sans CJK SC','sans-serif','Songti SC','Noto Serif CJK SC','serif','Menlo'],'source':'Installed system fonts, not redistributed','resolved_face':'System-resolved family stack; representative renders observed; exact platform face not introspected'},'capture':{'remotion':json.loads((P.parents[2]/'node_modules/remotion/package.json').read_text())['version'],'chrome_version':version,'native_width':2160,'native_height':3840,'fps':60,'total_frames':7200,'intermediate':'PNG','concurrency':2,'font_ready':'document.fonts.ready via Remotion delayRender','randomness':'No nondeterministic random or wall-clock animation'},'narration_provenance':'public/audio/provider-manifest.json','sound_provenance':'public/audio/mix-manifest.json','input_authorization':'audio-authorization.json'}
(P/'assets-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(len(records),'assets hashed; Chrome',version)
