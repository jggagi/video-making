import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';

const RATE=48000, FPS=24, SPF=RATE/FPS;
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const hash=b=>createHash('sha256').update(b).digest('hex');
const fileHash=p=>hash(fs.readFileSync(p));
const planPath='public/madman/voice-v5/plan.json';
const providerPath='public/madman/voice-v5/manifest.json';
const editPath='src/madman/suspense-v5-edit.json';
const plan=read(planPath), provider=read(providerPath), edit=read(editPath);
assert(provider.complete&&provider.cues.length===23);
assert.equal(provider.planSha256,fileHash(planPath));
assert.equal(provider.model,'cosyvoice-v3-flash');assert.equal(provider.voice,'longsanshu_v3');
assert.equal(provider.rate,.92);
assert.equal(provider.cues.map(c=>c.text).join(''),plan.cues.map(c=>c.text).join(''));
const clips=new Map();
for(const cue of plan.cues){
  const entry=provider.cues.find(c=>c.id===cue.id);
  assert(entry&&entry.text===cue.text&&entry.modelReportedByCli&&entry.voiceReportedByCli);
  assert.equal(entry.model,provider.model);assert.equal(entry.voice,provider.voice);
  assert.equal(entry.sha256,fileHash(cue.audioFile));
  const bytes=execFileSync('/opt/homebrew/bin/ffmpeg',['-v','error','-i',cue.audioFile,'-ar',String(RATE),'-ac','1','-f','f32le','pipe:1'],{maxBuffer:12*1024*1024});
  assert(bytes.length>0&&bytes.length%4===0);
  const samples=new Float32Array(bytes.buffer,bytes.byteOffset,bytes.length/4);
  let peak=0;for(const value of samples){assert(Number.isFinite(value));peak=Math.max(peak,Math.abs(value));}
  assert(peak>0);assert(Math.abs(samples.length/RATE-entry.durationSeconds)<.0001);
  clips.set(cue.id,{cue,entry,samples,peak,audioFrames:Math.ceil(samples.length/SPF)});
}
const timeline={fps:FPS,width:1920,height:1080,audioFile:edit.audioFile,durationInFrames:0,shots:[],captions:[],source:plan.source};
let cursor=0;
function splitCaption(text){
  const tokens=text.match(/[^，。；：！？、,;:!?]+[，。；：！？、,;:!?]?/gu)??[text];
  const chunks=[];let current='';
  for(const token of tokens){
    if(current&&current.length+token.length>22){chunks.push(current);current='';}
    let rest=token;
    while(rest.length>22){if(current){chunks.push(current);current='';}chunks.push(rest.slice(0,22));rest=rest.slice(22);}
    current+=rest;
  }
  if(current)chunks.push(current);
  assert.equal(chunks.join(''),text);assert(chunks.every(c=>c.length<=22));return chunks;
}
for(const item of edit.shots){
  const shot={id:item.id,section:item.section,from:cursor,duration:0,cues:[]};
  let pos=Math.round(item.lead*FPS);
  for(let i=0;i<item.cueIds.length;i++){
    const id=item.cueIds[i], clip=clips.get(id);assert(clip&&clip.cue.shotId===item.id);
    const cue={id,text:clip.cue.text,from:pos,audioFrames:clip.audioFrames,duration:clip.audioFrames+8};
    shot.cues.push(cue);
    const chunks=splitCaption(cue.text), weights=chunks.map(c=>c.replace(/[\p{P}\p{Z}]/gu,'').length+1), sum=weights.reduce((a,b)=>a+b,0);
    let start=0,weight=0;
    for(let j=0;j<chunks.length;j++){
      weight+=weights[j];const end=j===chunks.length-1?cue.duration:Math.round(cue.audioFrames*weight/sum);
      assert(end>start);timeline.captions.push({from:shot.from+pos+start,duration:end-start,text:chunks[j],cueId:id});start=end;
    }
    pos+=cue.duration;if(i<item.cueIds.length-1)pos+=Math.round(item.gap*FPS);
  }
  shot.duration=Math.ceil((pos+Math.round(item.tail*FPS))/6)*6;assert(shot.duration>0);
  timeline.shots.push(shot);cursor+=shot.duration;
}
timeline.durationInFrames=cursor;
assert.equal(timeline.shots.flatMap(s=>s.cues.map(c=>c.text)).join(''),plan.cues.map(c=>c.text).join(''));
assert.equal(timeline.captions.map(c=>c.text).join(''),plan.cues.map(c=>c.text).join(''));
for(let i=1;i<timeline.captions.length;i++)assert(timeline.captions[i].from>=timeline.captions[i-1].from+timeline.captions[i-1].duration);
const count=cursor*SPF, voice=new Float32Array(count), bed=new Float32Array(count);
const narration=[];
for(const shot of timeline.shots)for(const cue of shot.cues){
  const clip=clips.get(cue.id), start=(shot.from+cue.from)*SPF;
  const target=['aside','cured'].includes(cue.id)?.46:.50, gain=target/clip.peak;
  assert(start+clip.samples.length<=(shot.from+cue.from+cue.duration)*SPF);
  for(let i=0;i<clip.samples.length;i++){
    const edge=Math.min(1,i/(RATE*.008),(clip.samples.length-1-i)/(RATE*.008));voice[start+i]+=clip.samples[i]*gain*edge;
  }
  narration.push({id:cue.id,text:cue.text,sourcePath:clip.cue.audioFile,sourceSha256:clip.entry.sha256,startFrame:shot.from+cue.from,startSample:start,endSample:start+clip.samples.length,sourceSamples:clip.samples.length,gain,peakTarget:target,captionMarginFrames:cue.duration-clip.samples.length/SPF,model:clip.entry.model,voice:clip.entry.voice});
}
const shotBy=id=>timeline.shots.find(s=>s.id===id);
const absoluteCue=id=>{for(const s of timeline.shots){const c=s.cues.find(c=>c.id===id);if(c)return(s.from+c.from)/FPS;}throw Error(id);};
const voiceEnd=id=>{const r=narration.find(c=>c.id===id);return r.endSample/RATE;};
const events=[
  {kind:'wood',time:absoluteCue('lock')+(voiceEnd('lock')-absoluteCue('lock'))*.7,gain:.035},
  {kind:'paper',time:absoluteCue('history-b')-.2,gain:.018},
  {kind:'paper',time:absoluteCue('history-c')-.15,gain:.017},
  {kind:'cup',time:absoluteCue('fish')-.3,gain:.012},
  {kind:'wood',time:shotBy('ending').from/FPS+1,gain:.03},
];
let seed=19180402,low=0;const noise=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2147483648-1;};
let si=0,envelope=0;
const resetTime=absoluteCue('false-weight'), duration=count/RATE;
for(let i=0;i<count;i++){
  const frame=Math.floor(i/SPF);while(si<timeline.shots.length-1&&frame>=timeline.shots[si].from+timeline.shots[si].duration)si++;
  const shot=timeline.shots[si],t=i/RATE,n=noise();low=low*.9993+n*.0007;
  let intensity=1;
  if(['title','moon','children','ending'].includes(shot.id))intensity=.6;
  if(shot.id==='question')intensity=.25;
  if(shot.id==='street'||shot.id==='aside')intensity=1.35;
  if(shot.id==='beams')intensity=t<resetTime?2.5: .3;
  if(t>=resetTime&&t<resetTime+.4)intensity=0;
  let value=(low*.16+Math.sin(t*2*Math.PI*47)*.0037+Math.sin(t*2*Math.PI*51.3)*.0023)*intensity;
  if(['consult','aside'].includes(shot.id))value+=Math.sin(t*2*Math.PI*54)*.006*Math.exp(-((t*1.08)%1)*15);
  for(const event of events){const dt=t-event.time;if(dt<0||dt>.9)continue;
    if(event.kind==='wood')value+=(n*.65+Math.sin(dt*2*Math.PI*148)*.35)*event.gain*Math.exp(-dt*27);
    if(event.kind==='paper')value+=n*event.gain*Math.sin(Math.min(1,dt/.6)*Math.PI)*Math.exp(-dt*3);
    if(event.kind==='cup')value+=Math.sin(dt*2*Math.PI*1640)*event.gain*Math.exp(-dt*23);
  }
  envelope=envelope*.995+voice[i]*voice[i]*.005;
  const duck=1-.65*Math.min(1,Math.sqrt(envelope)/.025);
  const fade=Math.min(1,t/.8,Math.max(0,(duration-2-t)/.8));
  bed[i]=value*duck*fade;
  if(t>=duration-2){voice[i]=0;bed[i]=0;}
}
let bedPeak=0;for(const value of bed)bedPeak=Math.max(bedPeak,Math.abs(value));
const bedScale=bedPeak>.055?.055/bedPeak:1;let mixPeak=0;
const outputDir='public/madman/audio';fs.mkdirSync(outputDir,{recursive:true});
function writeWav(file,layer){
  const wav=Buffer.alloc(44+count*4);wav.write('RIFF',0);wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(2,22);wav.writeUInt32LE(RATE,24);wav.writeUInt32LE(RATE*4,28);wav.writeUInt16LE(4,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(count*4,40);
  let peak=0;
  for(let i=0;i<count;i++){const v=layer==='voice'?voice[i]:layer==='atmosphere'?bed[i]*bedScale:voice[i]+bed[i]*bedScale;assert(Number.isFinite(v)&&Math.abs(v)<1);peak=Math.max(peak,Math.abs(v));const pcm=Math.round(v*32767);wav.writeInt16LE(pcm,44+i*4);wav.writeInt16LE(pcm,46+i*4);}
  assert(wav.subarray(wav.length-2*RATE*4).every(v=>v===0));fs.writeFileSync(file,wav);
  execFileSync('/opt/homebrew/bin/ffmpeg',['-v','error','-i',file,'-f','null','-']);return{file,sha256:hash(wav),sampleRate:RATE,channels:2,durationSeconds:duration,peak,finalSilenceSeconds:2};
}
const voiceOutput=writeWav(`${outputDir}/suspense-v5-voice.wav`,'voice');
const atmosphereOutput=writeWav(`${outputDir}/suspense-v5-atmosphere.wav`,'atmosphere');
const output=writeWav(`${outputDir}/suspense-v5.wav`,'mix');mixPeak=output.peak;
fs.writeFileSync('src/madman/suspense-v5-timeline.json',JSON.stringify(timeline,null,2)+'\n');
const stamp=(frame,vtt)=>{const ms=Math.round(frame/FPS*1000);return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}${vtt?'.':','}${String(ms%1000).padStart(3,'0')}`;};
const rows=timeline.captions.map((c,i)=>`${i+1}\n${stamp(c.from,false)} --> ${stamp(c.from+c.duration,false)}\n${c.text}\n`).join('\n');
fs.writeFileSync('public/madman/suspense-v5.srt',rows);
fs.writeFileSync('public/madman/suspense-v5.vtt','WEBVTT\n\n'+timeline.captions.map((c,i)=>`${i+1}\n${stamp(c.from,true)} --> ${stamp(c.from+c.duration,true)}\n${c.text}\n`).join('\n'));
const manifest={source:{planPath,planSha256:fileHash(planPath),providerPath,providerSha256:fileHash(providerPath),editPath,editSha256:fileHash(editPath)},timeline:{file:'src/madman/suspense-v5-timeline.json',sha256:fileHash('src/madman/suspense-v5-timeline.json'),durationInFrames:cursor,fps:FPS},output,stems:{voice:voiceOutput,atmosphere:atmosphereOutput},narration,atmosphere:{seed:19180402,events,peakLimit:.055,actualPeak:atmosphereOutput.peak,ducking:'65 percent at active narration',beamsResetSeconds:resetTime,finalSilenceSeconds:2},subtitles:{srt:'public/madman/suspense-v5.srt',vtt:'public/madman/suspense-v5.vtt',rows:timeline.captions.length,characters:553},cloudCalls:0,humanListeningReview:false};
fs.writeFileSync(`${outputDir}/suspense-v5-manifest.json`,JSON.stringify(manifest,null,2)+'\n');
fs.mkdirSync('out/madman',{recursive:true});
fs.writeFileSync('out/madman/prepare-v5-check.json',JSON.stringify({passed:true,durationSeconds:duration,frames:cursor,cues:narration.length,characters:553,captionRows:timeline.captions.length,mixPeak,bedPeak:atmosphereOutput.peak,finalTwoSecondsDigitalZero:true},null,2)+'\n');
console.log(JSON.stringify({durationSeconds:duration,frames:cursor,cues:narration.length,captionRows:timeline.captions.length,mixPeak,finalSilenceSeconds:2}));
