import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {passages, spoken} from './text.mjs';

const fps = 24;
const rate = 22050;
const audioDir = path.resolve('public/audio');
const tempDir = path.resolve('out/speech-source');
fs.mkdirSync(audioDir, {recursive: true});
fs.mkdirSync(tempDir, {recursive: true});

function wav(file, left, right = left) {
  const channels = right === left ? 1 : 2;
  const samples = left.length;
  const result = Buffer.alloc(44 + samples * channels * 2);
  result.write('RIFF', 0); result.writeUInt32LE(result.length - 8, 4);
  result.write('WAVEfmt ', 8); result.writeUInt32LE(16, 16);
  result.writeUInt16LE(1, 20); result.writeUInt16LE(channels, 22);
  result.writeUInt32LE(rate, 24); result.writeUInt32LE(rate * channels * 2, 28);
  result.writeUInt16LE(channels * 2, 32); result.writeUInt16LE(16, 34);
  result.write('data', 36); result.writeUInt32LE(result.length - 44, 40);
  for (let i = 0; i < samples; i++) {
    result.writeInt16LE(Math.round(Math.max(-1, Math.min(1, left[i])) * 32767), 44 + i * channels * 2);
    if (channels === 2) result.writeInt16LE(Math.round(Math.max(-1, Math.min(1, right[i])) * 32767), 46 + i * 4);
  }
  fs.writeFileSync(file, result);
}

function chunks(text) {
  const clauses = text.match(/[^，。；！？]+[，。；！？]?[”’]?/g) ?? [text];
  const result = [];
  let current = '';
  for (const clause of clauses) {
    if (current.length + clause.length > 22 && current) {result.push(current); current = '';}
    current += clause;
  }
  if (current) result.push(current);
  return result;
}

let cursor = 5 * fps;
const shots = [{id: 'title', kind: 'title', from: 0, duration: cursor, image: 'landscape', chapter: '', hero: [], mood: 'joy', text: '', cues: []}];
const voiceClips = [];
for (const [shotIndex, passage] of passages.entries()) {
  const cues = [];
  let relative = 18;
  for (const [cueIndex, text] of chunks(passage.text).entries()) {
    const hash = createHash('sha256').update(spoken(text) + '|135|Tingting').digest('hex').slice(0, 10);
    const base = `${String(shotIndex + 1).padStart(2, '0')}-${String(cueIndex + 1).padStart(2, '0')}-${hash}`;
    const aiff = path.join(tempDir, base + '.aiff');
    if (!fs.existsSync(aiff)) {
      execFileSync('/usr/bin/say', ['-v', 'Tingting (Chinese (China mainland))', '-r', '135', '-o', aiff, spoken(text)]);
    }
    const pcm = execFileSync('/opt/homebrew/bin/ffmpeg', ['-v', 'error', '-i', aiff, '-ac', '1', '-ar', String(rate), '-f', 's16le', '-'], {maxBuffer: 20 * 1024 * 1024});
    const values = new Float32Array(pcm.length / 2);
    let peak = 0;
    for (let i = 0; i < values.length; i++) {values[i] = pcm.readInt16LE(i * 2) / 32768; peak = Math.max(peak, Math.abs(values[i]));}
    const gain = peak > 0 ? 0.68 / peak : 1;
    for (let i = 0; i < values.length; i++) values[i] *= gain;
    const audioFrames = Math.ceil(values.length / rate * fps);
    const duration = audioFrames + 7;
    cues.push({text, from: relative, duration});
    voiceClips.push({frame: cursor + relative, values});
    relative += duration;
  }
  const duration = Math.max(5 * fps, relative + 24);
  // Keep the last subtitle visible through the short contemplative tail.
  cues[cues.length - 1].duration += duration - relative;
  shots.push({...passage, kind: 'scene', from: cursor, duration, cues});
  cursor += duration;
  console.log(`${passage.id}: ${(duration / fps).toFixed(2)}s, ${cues.length} aligned phrases`);
}
shots.push({id: 'end', kind: 'end', from: cursor, duration: 6 * fps, image: 'landscape', chapter: '', hero: [], mood: 'reflect', text: '', cues: []});
cursor += 6 * fps;
const timeline = {fps, durationInFrames: cursor, shots};
fs.writeFileSync('src/timeline.json', JSON.stringify(timeline, null, 2) + '\n');

const seconds = cursor / fps;
const length = Math.ceil(seconds * rate);
const left = new Float32Array(length);
const right = new Float32Array(length);
// Original sparse pentatonic string score, generated locally; not a recording.
const notes = [146.83, 220, 261.63, 293.66, 392, 329.63, 293.66, 220, 146.83, 261.63, 220, 196];
for (let start = 1.4, n = 0; start < seconds - 4; start += 5.7, n++) {
  const frequency = notes[n % notes.length];
  const first = Math.round(start * rate);
  const count = Math.min(length - first, rate * 5);
  const pan = Math.sin(n * 1.9) * 0.2;
  for (let j = 0; j < count; j++) {
    const t = j / rate;
    const attack = Math.min(1, t / 0.008);
    const decay = Math.exp(-t / 1.7);
    const value = 0.018 * attack * decay * (Math.sin(2 * Math.PI * frequency * t) + 0.3 * Math.sin(2 * Math.PI * frequency * 2.002 * t) + 0.11 * Math.sin(2 * Math.PI * frequency * 3.001 * t));
    left[first + j] += value * (1 - pan); right[first + j] += value * (1 + pan);
  }
}
let seed = 81735;
let waterL = 0, waterR = 0;
for (let i = 0; i < length; i++) {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
  const noise = seed / 4294967296 * 2 - 1;
  waterL = waterL * 0.88 + noise * 0.12;
  waterR = waterR * 0.91 + noise * 0.09;
  const t = i / rate;
  const fade = Math.min(1, t / 3, (seconds - t) / 4);
  const level = 0.012 * (0.7 + Math.sin(t * 0.32) * 0.3);
  left[i] = (left[i] + waterL * level) * fade;
  right[i] = (right[i] + waterR * level) * fade;
}
for (const clip of voiceClips) {
  const first = Math.round(clip.frame / fps * rate);
  for (let j = 0; j < clip.values.length && first + j < length; j++) {
    left[first + j] += clip.values[j]; right[first + j] += clip.values[j];
  }
}
wav(path.join(audioDir, 'soundtrack.wav'), left, right);
fs.writeFileSync('out/audio-manifest.json', JSON.stringify({voice: 'macOS Tingting (Chinese (China mainland))', speechRate: 135, rate, seconds, clips: voiceClips.length, captionCharacters: passages.map(p => p.text).join('').replace(/[，。；：“”！]/g, '').length, spokenHomophones: ['会稽→快稽', '修禊→修细', '少长咸集→绍掌咸集', '夫人→扶人', '悟言→晤言', '趣舍→取舍', '悲夫→悲福']}, null, 2));
console.log(`Soundtrack and exact phrase timeline: ${seconds.toFixed(2)}s (${cursor} frames)`);
