"""Cache exact EP19 narration with the repository-selected Bailian voice."""
import json,hashlib,subprocess,os,wave,struct,sys,shutil
from pathlib import Path
P=Path(__file__).resolve().parents[1]; A=P/'public/audio'; A.mkdir(parents=True,exist_ok=True)
SET={'provider':'Aliyun Bailian','model':'qwen-audio-3.0-tts-plus','voice':'qwen-audio-3.0-tts-plus-longlangmoyue','rate':1.0,'sample_rate':24000,'format':'wav','instruction':'中文叙事旁白。声音沉稳、有分量，情绪克制，略带怅惘。自然清晰地连贯讲述，避免广告腔和过长停顿。完整朗读原文。'}
segments=json.loads((P/'segments.json').read_text()); manifest=A/'provider-manifest.json'
m=json.loads(manifest.read_text()) if manifest.exists() else {'settings':SET,'segments':{}}
assert m['settings']==SET
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def find(v,keys):
 out=[]
 if isinstance(v,dict):
  for k,x in v.items():
   if k.lower() in keys and isinstance(x,str):out.append(x)
   elif isinstance(x,(dict,list)):out+=find(x,keys)
 elif isinstance(v,list):
  for x in v:out+=find(x,keys)
 return sorted(set(out))
for s in segments:
 if sys.argv[1:] and s['id'] not in sys.argv[1:]:continue
 key=hashlib.sha256(json.dumps({'text':s['tts_phonetic_text'],'settings':SET},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 sid=s['id']; entry=m['segments'].get(sid)
 if entry:
  assert entry['cacheKey']==key
  for fld in ('raw','cue'):assert sha(P/entry[fld]['path'])==entry[fld]['sha256']
  print(sid,'verified cache',entry['durationSeconds'],flush=True);continue
 for sub in ['tts-input','raw','cues']:(A/sub).mkdir(exist_ok=True)
 text=A/'tts-input'/f'{sid}-{key[:12]}.txt';text.write_text(s['tts_phonetic_text'])
 raw=A/'raw'/f'{sid}-{key[:12]}.wav';cue=A/'cues'/f'{sid}.wav'
 assert not raw.exists() and not cue.exists(),'Preserve unmatched output; investigate before retry'
 env=os.environ.copy();env.update(BAILIAN_CALLER_TYPE='agent',BAILIAN_CALLER_NAME='codex',BAILIAN_SKILL_NAME='bailian-gen',BAILIAN_SKILL_VERSION='2.5.1')
 r=subprocess.run([(os.environ.get('BL_BIN') or shutil.which('bl',path=str(Path.home()/'.local/n/bin')+os.pathsep+os.environ.get('PATH','')) or 'bl'),'speech','synthesize','--text-file',str(text),'--model',SET['model'],'--voice',SET['voice'],'--rate','1.0','--format','wav','--sample-rate','24000','--instruction',SET['instruction'],'--concurrent','1','--out',str(raw),'--output','json'],env=env,capture_output=True,text=True)
 if r.returncode: print(sid,'provider failed',r.returncode,'no fallback; raw preserved',raw.exists());sys.exit(2)
 response=json.loads(r.stdout);models=find(response,{'model','model_id','resolved_model'});voices=find(response,{'voice','voice_id','resolved_voice'})
 if models!=[SET['model']] or voices!=[SET['voice']]:print('NEEDS_SOL identity mismatch',models,voices);sys.exit(2)
 b=raw.read_bytes();assert b[:4]==b'RIFF' and b[8:12]==b'WAVE';off=12;fmt=None;pcm=None;declared=None
 while off+8<=len(b):
  name=b[off:off+4];n=struct.unpack_from('<I',b,off+4)[0];start=off+8
  if name==b'fmt ':fmt=struct.unpack_from('<HHIIHH',b,start)
  if name==b'data':pcm=b[start:min(len(b),start+n)];declared=n;break
  off=start+n+(n&1)
 assert fmt and fmt[0:3]==(1,1,24000) and fmt[-1]==16 and pcm and len(pcm)%2==0
 with wave.open(str(cue),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm)
 entry={'cacheKey':key,'text':s['tts_phonetic_text'],'requestedSettings':SET,'reportedModels':models,'reportedVoices':voices,'raw':{'path':str(raw.relative_to(P)),'sha256':sha(raw)},'cue':{'path':str(cue.relative_to(P)),'sha256':sha(cue)},'actualSamples':len(pcm)//2,'durationSeconds':len(pcm)/48000,'rawDeclaredDataBytes':declared,'actualDataBytes':len(pcm),'canonicalRepair':declared!=len(pcm)}
 m['segments'][sid]=entry;manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(sid,'generated',entry['durationSeconds'],flush=True)
