import fs from 'node:fs';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {passages} from './text.mjs';

const dir='out/museum';
const timeline=JSON.parse(fs.readFileSync('src/museum/timeline.json','utf8'));
assert.equal(timeline.shots.filter(s=>s.kind==='scene').map(s=>s.text).join(''),passages.map(s=>s.text).join(''));
const reports=[];
for (const [label,width,height] of [['4K',3840,2160],['1080p',1920,1080]]) {
  const file=`${dir}/兰亭集序-博物馆版-${label}.mp4`;
  const probe=JSON.parse(execFileSync('/opt/homebrew/bin/ffprobe',['-v','error','-show_streams','-show_format','-of','json',file],{encoding:'utf8'}));
  const video=probe.streams.find(s=>s.codec_type==='video');
  const audio=probe.streams.find(s=>s.codec_type==='audio');
  assert.equal(video.codec_name,'h264');assert.equal(video.width,width);assert.equal(video.height,height);
  assert.equal(video.r_frame_rate,'24/1');assert.equal(Number(video.nb_frames),timeline.durationInFrames);
  assert.equal(audio.codec_name,'aac');assert.equal(audio.sample_rate,'48000');assert.equal(audio.channels,2);
  assert(Math.abs(Number(probe.format.duration)-timeline.durationInFrames/24)<.05);
  const fd=fs.openSync(file,'r');const size=fs.statSync(file).size;const boxes=[];
  for(let offset=0;offset<size;) {
    const header=Buffer.alloc(16);fs.readSync(fd,header,0,16,offset);
    const type=header.toString('ascii',4,8);const short=header.readUInt32BE(0);
    const length=short===1?Number(header.readBigUInt64BE(8)):short===0?size-offset:short;
    assert(length>=8 && offset+length<=size);boxes.push(type);offset+=length;
  }
  fs.closeSync(fd);assert(boxes.indexOf('moov')>=0 && boxes.indexOf('moov')<boxes.indexOf('mdat'),'Missing fast start');
  execFileSync('/opt/homebrew/bin/ffmpeg',['-v','error','-threads','2','-i',file,'-f','null','-'],{stdio:['ignore','ignore','pipe']});
  const hash=createHash('sha256');
  for await(const chunk of fs.createReadStream(file)) hash.update(chunk);
  reports.push({file,width,height,fps:24,frames:Number(video.nb_frames),duration:Number(probe.format.duration),size,codec:video.codec_name,audio:{codec:audio.codec_name,sampleRate:Number(audio.sample_rate),channels:audio.channels},fastStart:true,fullDecodePassed:true,sha256:hash.digest('hex')});
  console.log(`${label}: ${video.nb_frames} frames, full decode passed`);
}
const previews=[['title-writing',90],['title',300],['grove',773],['water-a',864],['water-b',919],['cups-a',974],['cups-b',1053],['poems',1239],['breeze',1362],['traces-before',2461],['traces-after',2598],['mortality',2736],['judgment',3193],['record',3590],['future',3706],['end',3859],['final',3988]];
for (const [name,frame] of previews) {
  execFileSync('/opt/homebrew/bin/ffmpeg',['-v','error','-ss',String(frame/24),'-i',`${dir}/兰亭集序-博物馆版-1080p.mp4`,'-frames:v','1','-y',`${dir}/still-${name}.png`]);
}
const voice=JSON.parse(fs.readFileSync(`${dir}/preflight.json`,'utf8'));
fs.writeFileSync(`${dir}/validation.json`,JSON.stringify({createdAt:new Date().toISOString(),...voice,typecheckPassed:true,media:reports,previewFrames:previews,visualReview:'Representative rendered frames and motion sample reviewed; installation viewing distance and audio listening not tested on site',notHistoricalHandwriting:true,artworkNativeSize:'Background paintings approximately 1672×941; upscaled in 4K composition'},null,2)+'\n');
console.log('Final MP4 frames extracted; validation.json saved');
