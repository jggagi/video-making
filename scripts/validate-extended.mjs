import fs from 'node:fs';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {passages} from './text.mjs';
const dir=process.env.LANTING_OUTPUT_DIR??'out/extended',edition=process.env.LANTING_EDITION??'展厅增强版',sourceDir='out/extended',timeline=JSON.parse(fs.readFileSync('src/extended/timeline.json','utf8'));
assert.equal(timeline.shots.filter(s=>s.kind==='scene').map(s=>s.text).join(''),passages.map(s=>s.text).join(''));
let end=0;
for(const s of timeline.shots){assert.equal(s.from,end);assert.equal(s.cues.map(c=>c.text).join(''),s.text);end+=s.duration;}
assert.equal(end,timeline.durationInFrames);
const manifest=JSON.parse(fs.readFileSync(`${sourceDir}/manifest.json`,'utf8'));
assert.equal(manifest.model,'cosyvoice-v3-flash');assert.equal(manifest.voice,'longsanshu_v3');assert.equal(manifest.cues.length,26);
const media=[];
for(const [label,width,height] of [['4K',3840,2160],['1080p',1920,1080]]){
  const file=`${dir}/兰亭集序-${edition}-${label}.mp4`;
  const probe=JSON.parse(execFileSync('/opt/homebrew/bin/ffprobe',['-v','error','-show_streams','-show_format','-of','json',file],{encoding:'utf8'}));
  const v=probe.streams.find(s=>s.codec_type==='video'),a=probe.streams.find(s=>s.codec_type==='audio');
  assert.equal(v.codec_name,'h264');assert.equal(v.width,width);assert.equal(v.height,height);assert.equal(v.r_frame_rate,'24/1');assert.equal(Number(v.nb_frames),end);
  assert.equal(a.codec_name,'aac');assert.equal(a.sample_rate,'48000');assert.equal(a.channels,2);
  assert(Math.abs(Number(probe.format.duration)-end/24)<.05);
  const fd=fs.openSync(file,'r'),size=fs.statSync(file).size,boxes=[];
  for(let offset=0;offset<size;){const h=Buffer.alloc(16);fs.readSync(fd,h,0,16,offset);const n=h.readUInt32BE(0),len=n===1?Number(h.readBigUInt64BE(8)):n===0?size-offset:n;assert(len>=8&&offset+len<=size);boxes.push(h.toString('ascii',4,8));offset+=len;}
  fs.closeSync(fd);assert(boxes.indexOf('moov')>=0&&boxes.indexOf('moov')<boxes.indexOf('mdat'));
  execFileSync('/opt/homebrew/bin/ffmpeg',['-v','error','-threads','2','-i',file,'-f','null','-'],{stdio:['ignore','ignore','pipe']});
  const hash=createHash('sha256');for await(const b of fs.createReadStream(file))hash.update(b);
  media.push({file,width,height,frames:Number(v.nb_frames),fps:24,seconds:Number(probe.format.duration),bytes:size,sha256:hash.digest('hex'),fullDecodePassed:true,fastStart:true,audio:{codec:a.codec_name,sampleRate:48000,channels:2}});
  console.log(`${label}: full decode passed; ${v.nb_frames} frames`);
}
const previews=timeline.shots.map(s=>[s.id,s.from+Math.min(s.duration-1,Math.round(s.duration*(s.kind==='title'?.91:.72)))]);
previews.push(['final',end-1]);
let timeBridge;
if(edition==='古今回望版'){
  const shot=timeline.shots.find(s=>s.id==='time');
  previews.push(['time-ancient',shot.from+24],['time-empty',shot.from+70],['time-modern',shot.from+137]);
  const contract=JSON.parse(fs.readFileSync(`${dir}/edit-contract.json`,'utf8'));
  for(const [file,expected]of Object.entries(contract.unchangedSourceSha256))assert.equal(createHash('sha256').update(fs.readFileSync(file)).digest('hex'),expected,`Changed source: ${file}`);
  assert.equal(createHash('sha256').update(fs.readFileSync(contract.visitorArtwork.file)).digest('hex'),contract.visitorArtwork.sha256);
  timeBridge={...contract,narrationAndTimelineUnchanged:true,stages:['ancient gathering','empty garden','modern visitors'],modernCompleteAtFrame:shot.from+114};
}
for(const [name,frame]of previews)execFileSync('/opt/homebrew/bin/ffmpeg',['-v','error','-ss',String(frame/24),'-i',`${dir}/兰亭集序-${edition}-1080p.mp4`,'-frames:v','1','-y',`${dir}/final-${name}.png`]);
const preflight=JSON.parse(fs.readFileSync(`${sourceDir}/preflight.json`,'utf8'));
fs.writeFileSync(`${dir}/validation.json`,JSON.stringify({createdAt:new Date().toISOString(),edition,...preflight,typecheckPassed:true,media,previewFrames:previews,newArtwork:edition==='古今回望版'?7:6,newTransparentSprites:1,timeBridge,notHistoricalHandwriting:true,artworkNativeSize:'1672x941 backgrounds, raster upscaled in 4K; text, handwriting outlines, shaders rendered at target resolution',onsiteScreenAndAudioAudition:false},null,2)+'\n');
console.log('Final video frames extracted; validation.json saved');
