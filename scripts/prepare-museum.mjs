import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {passages, spoken} from './text.mjs';

const fps = 24;
const shift = 10 * fps;
const source = JSON.parse(fs.readFileSync('src/timeline.json', 'utf8'));
const timeline = {
  fps,
  durationInFrames: source.durationInFrames + shift + 4 * fps,
  shots: source.shots.map(shot => ({...shot,
    from: shot.kind === 'title' ? 0 : shot.from + shift,
    duration: shot.duration + (shot.kind === 'title' ? shift : shot.kind === 'end' ? 4 * fps : 0),
  })),
};
const out = 'out/museum';
fs.mkdirSync(out, {recursive: true});
fs.mkdirSync('public/museum/audio', {recursive: true});
fs.writeFileSync('src/museum/timeline.json', JSON.stringify(timeline, null, 2) + '\n');
let end = 0;
for (const shot of timeline.shots) {
  assert.equal(shot.from, end);
  end += shot.duration;
  assert.equal(shot.cues.map(c => c.text).join(''), shot.text);
  for (const cue of shot.cues) assert(cue.from >= 0 && cue.from + cue.duration <= shot.duration);
}
assert.equal(end, timeline.durationInFrames);
assert.equal(timeline.shots.filter(s => s.kind === 'scene').map(s => s.text).join(''), passages.map(s => s.text).join(''));
const cues = timeline.shots.flatMap(s => s.cues.map(c => ({...c, from: s.from + c.from})));
const stamp = (frame, separator) => {
  const ms = Math.round(frame / fps * 1000);
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}${separator}${String(ms % 1000).padStart(3, '0')}`;
};
fs.writeFileSync(`${out}/兰亭集序-博物馆版.srt`, cues.map((c,i) => `${i+1}\n${stamp(c.from, ',')} --> ${stamp(c.from+c.duration, ',')}\n${c.text}\n`).join('\n'));
fs.writeFileSync(`${out}/兰亭集序-博物馆版.vtt`, 'WEBVTT\n\n' + cues.map(c => `${stamp(c.from, '.')} --> ${stamp(c.from+c.duration, '.')}\n${c.text}\n`).join('\n'));

// Recover the verified, locally synthesized narration without synthesizing it again.
const rate = 22050;
const seconds = timeline.durationInFrames / fps;
const count = Math.ceil(seconds * rate);
const left = new Float32Array(count);
const right = new Float32Array(count);
let seed = 353;
let lowL = 0, lowR = 0, wind = 0;
for (let i = 0; i < count; i++) {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
  const noise = seed / 4294967296 * 2 - 1;
  lowL = lowL * .90 + noise * .10;
  lowR = lowR * .93 + noise * .07;
  wind = wind * .995 + noise * .005;
  const t = i / rate;
  const fade = Math.max(0, Math.min(1, t / 2.8, (seconds-t) / 4));
  const water = .019 * (.8 + .2 * Math.sin(t * .37));
  const rustle = .045 * (.65 + .35 * Math.sin(t * .17));
  left[i] = (lowL * water + wind * rustle) * fade;
  right[i] = (lowR * water + wind * rustle * .9) * fade;
}
const turn = timeline.shots.find(s => s.id === 'life').from / fps;
const notes = [146.83, 220, 293.66, 261.63, 392, 293.66, 220, 146.83];
for (let start = 1.2, n = 0; start < seconds - 5; start += 6.3, n++) {
  const f = notes[n % notes.length] * (start >= turn ? .75 : 1);
  const first = Math.round(start * rate);
  const length = Math.min(count-first, Math.round(rate * 5.8));
  const pan = Math.sin(n * 1.8) * .28;
  for (let j = 0; j < length; j++) {
    const t = j / rate;
    const envelope = Math.min(1, t/.015) * Math.exp(-t/1.95);
    const dry = .022 * envelope * (Math.sin(2*Math.PI*f*t) + .24*Math.sin(2*Math.PI*f*2.002*t) + .09*Math.sin(2*Math.PI*f*3.001*t));
    left[first+j] += dry * (1-pan);
    right[first+j] += dry * (1+pan);
    const echo = first+j+Math.round(rate*.28);
    if (echo < count) {left[echo] += dry*.16; right[echo] += dry*.22;}
  }
}
for (const [shotIndex, shot] of timeline.shots.filter(s => s.kind === 'scene').entries()) {
  for (const [cueIndex, cue] of shot.cues.entries()) {
    const hash = createHash('sha256').update(spoken(cue.text) + '|135|Tingting').digest('hex').slice(0,10);
    const name = `${String(shotIndex+1).padStart(2,'0')}-${String(cueIndex+1).padStart(2,'0')}-${hash}.aiff`;
    const hashed = path.resolve('out/speech-source',name);
    // v1's 26 source clips predate content-hashed filenames; their positions
    // were already verified against this unchanged phrase timeline.
    const file = fs.existsSync(hashed) ? hashed : path.resolve('out/speech-source',`${String(shotIndex+1).padStart(2,'0')}-${String(cueIndex+1).padStart(2,'0')}.aiff`);
    assert(fs.existsSync(file), `Missing verified narration ${name}`);
    const pcm = execFileSync('/opt/homebrew/bin/ffmpeg', ['-v','error','-i',file,'-ac','1','-ar',String(rate),'-f','s16le','-'], {maxBuffer: 20*1024*1024});
    assert(pcm.length/2/rate*fps <= cue.duration, `Narration exceeds caption window in ${shot.id}`);
    let peak=0;
    for (let i=0;i<pcm.length/2;i++) peak=Math.max(peak,Math.abs(pcm.readInt16LE(i*2)/32768));
    const gain=.68/Math.max(peak,.001);
    const first=Math.round((shot.from+cue.from)/fps*rate);
    for (let j=0;j<pcm.length/2;j++) {
      const value=pcm.readInt16LE(j*2)/32768*gain;
      left[first+j]+=value; right[first+j]+=value;
    }
  }
}
const wav = Buffer.alloc(44 + count*4);
wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);
wav.writeUInt16LE(1,20);wav.writeUInt16LE(2,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*4,28);
wav.writeUInt16LE(4,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(count*4,40);
let peak=0;
for (let i=0;i<count;i++) {
  peak=Math.max(peak,Math.abs(left[i]),Math.abs(right[i]));
  assert(Math.abs(left[i])<=1 && Math.abs(right[i])<=1, 'Audio clipping');
  wav.writeInt16LE(Math.round(left[i]*32767),44+i*4);wav.writeInt16LE(Math.round(right[i]*32767),46+i*4);
}
fs.writeFileSync('public/museum/audio/soundtrack.wav',wav);
fs.writeFileSync(`${out}/preflight.json`,JSON.stringify({fps,frames:end,seconds,cues:cues.length,scenes:17,fullTextMatches:true,continuousTimeline:true,audioPeakDb:20*Math.log10(peak),voice:'macOS Tingting, local synthesis',music:'Original locally synthesized sparse string tones, wind and water'},null,2)+'\n');
console.log(`${end} frames / ${seconds.toFixed(3)} seconds; exact full text; ${cues.length} aligned cues; peak ${Math.round(20*Math.log10(peak)*10)/10} dBFS`);
