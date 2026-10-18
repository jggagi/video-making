import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const specFile = 'src/madman/history-study-v3.json';
const spec = JSON.parse(fs.readFileSync(specFile, 'utf8'));
const original = JSON.parse(fs.readFileSync(spec.sourceTimeline, 'utf8')).shots.find(s => s.id === spec.sourceShotId);
const provider = JSON.parse(fs.readFileSync('public/madman/voice-v2/manifest.json', 'utf8'));
const rate = 48_000;
const total = spec.durationInFrames / spec.fps * rate;
const ffmpeg = '/opt/homebrew/bin/ffmpeg';
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const clamp = n => Math.min(1, Math.max(0, n));
const smooth = n => {const x = clamp(n); return x * x * (3 - 2 * x);};
assert.equal(spec.fps, 24);
assert.equal(spec.durationInFrames, 480);
assert.equal(total, 960_000);
assert.equal(spec.cues.map(c => c.text).join(''), original.cues.map(c => c.text).join(''), 'Selected source text changed.');
assert.equal(spec.captions.map(c => c.text).join(''), original.cues.map(c => c.text).join(''), 'Split captions changed source text.');
let end = 0;
for (const caption of spec.captions) {
  assert(caption.from >= end && caption.end > caption.from && caption.end <= spec.durationInFrames);
  end = caption.end;
}

const voice = new Float32Array(total * 2);
const bed = new Float32Array(total * 2);
const records = [];
let previousVoiceEnd = 0;
for (const cue of spec.cues) {
  const entry = provider.cues.find(c => c.id === cue.id);
  assert(entry && entry.text === cue.text && entry.path === cue.audioFile);
  assert.equal(hash(cue.audioFile), entry.sha256, `Cached source hash changed: ${cue.id}.`);
  const raw = execFileSync(ffmpeg, ['-v', 'error', '-i', cue.audioFile, '-ac', '1', '-ar', String(rate), '-f', 'f32le', 'pipe:1'], {maxBuffer: 8 * 1024 * 1024});
  assert.equal(raw.length % 4, 0);
  const samples = new Float32Array(raw.buffer, raw.byteOffset, raw.length / 4);
  let peak = 0;
  for (const value of samples) {assert(Number.isFinite(value)); peak = Math.max(peak, Math.abs(value));}
  assert(peak > 0);
  const gain = cue.peakTarget / peak;
  const start = cue.from / spec.fps * rate;
  assert(Number.isInteger(start) && start >= previousVoiceEnd);
  const insertAt = cue.pauseInsert ? Math.round(cue.pauseInsert.atSeconds * rate) : samples.length;
  const inserted = cue.pauseInsert ? Math.round(cue.pauseInsert.durationSeconds * rate) : 0;
  let pauseWindowRms = null;
  if (inserted) {
    assert(insertAt > 480 && insertAt < samples.length - 480);
    let sum = 0;
    let nearPeak = 0;
    for (let i = insertAt - 480; i < insertAt + 480; i++) {sum += samples[i] ** 2; nearPeak = Math.max(nearPeak, Math.abs(samples[i]));}
    pauseWindowRms = Math.sqrt(sum / 960);
    assert(pauseWindowRms < .01 && nearPeak < .04, 'Pause insertion must be inside the existing quiet interval.');
  }
  const voiceEnd = start + samples.length + inserted;
  assert(voiceEnd <= cue.captionEnd / spec.fps * rate && voiceEnd <= total);
  for (let i = 0; i < samples.length; i++) {
    const target = start + i + (i >= insertAt ? inserted : 0);
    const fade = smooth(i / (rate * .008)) * smooth((samples.length - 1 - i) / (rate * .008));
    const value = samples[i] * gain * fade;
    voice[target * 2] += value;
    voice[target * 2 + 1] += value;
  }
  records.push({id: cue.id, text: cue.text, file: cue.audioFile, sha256: entry.sha256, fromFrame: cue.from, sourceDurationSeconds: samples.length / rate, sourcePeak: peak, gain, peakTarget: cue.peakTarget, insertedSilenceSeconds: inserted / rate, insertAtSeconds: inserted ? insertAt / rate : null, insertionWindowRms: pauseWindowRms, mixedEndSeconds: voiceEnd / rate, model: entry.model, voice: entry.voice});
  previousVoiceEnd = voiceEnd;
}

// All sound effects are locally synthesized, with a fixed seed and no borrowed recordings.
let state = spec.sound.seed >>> 0;
const noise = () => {state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296 * 2 - 1;};
let lowLeft = 0;
let lowRight = 0;
let fibre = 0;
const paperEvents = [{start: .08, duration: .82, pan: -.28}, {start: 5.65, duration: .48, pan: .25}, {start: 11.65, duration: .62, pan: -.1}, {start: 14.65, duration: .88, pan: .08}];
for (let i = 0; i < total; i++) {
  const time = i / rate;
  const nL = noise();
  const nR = noise();
  lowLeft = .985 * lowLeft + .015 * nL;
  lowRight = .985 * lowRight + .015 * nR;
  fibre = .74 * fibre + .26 * nL;
  const out = smooth((20 - time) / .55);
  const beforeSilence = 1 - smooth((time - spec.sound.backgroundFadeStartSeconds) / .4);
  const afterWord = smooth((time - spec.sound.backgroundReturnSeconds) / .65);
  const windEnvelope = smooth(time / .5) * Math.max(beforeSilence, afterWord * .4) * out;
  const voiceActive = records.some(r => time >= r.fromFrame / spec.fps - .10 && time <= r.mixedEndSeconds + .2);
  const duck = voiceActive ? .5 : 1;
  let left = lowLeft * .1 * windEnvelope * duck;
  let right = lowRight * .1 * windEnvelope * duck;
  for (const event of paperEvents) {
    const t = time - event.start;
    if (t < 0 || t >= event.duration) continue;
    const envelope = Math.sin(Math.PI * t / event.duration) ** 1.5;
    const strokes = .55 + .45 * Math.sin(2 * Math.PI * 15 * t + .7) ** 2;
    const value = ((nL - fibre) * .007 + fibre * .033) * envelope * strokes;
    left += value * Math.sqrt(1 - event.pan);
    right += value * Math.sqrt(1 + event.pan);
  }
  if (time >= spec.sound.silenceStartSeconds && time < spec.sound.silenceEndSeconds) {left = 0; right = 0;}
  bed[i * 2] = left * out;
  bed[i * 2 + 1] = right * out;
}

const mix = new Float32Array(total * 2);
let peak = 0;
let silentPeak = 0;
for (let i = 0; i < mix.length; i++) {
  mix[i] = voice[i] + bed[i];
  assert(Number.isFinite(mix[i]) && Math.abs(mix[i]) < 1);
  peak = Math.max(peak, Math.abs(mix[i]));
  const time = Math.floor(i / 2) / rate;
  if (time >= spec.sound.silenceStartSeconds && time < spec.sound.silenceEndSeconds) silentPeak = Math.max(silentPeak, Math.abs(mix[i]));
}
assert.equal(silentPeak, 0, 'The designed pause must be actual silence.');

function wav(samples) {
  const dataBytes = samples.length * 2;
  const file = Buffer.alloc(44 + dataBytes);
  file.write('RIFF', 0); file.writeUInt32LE(file.length - 8, 4); file.write('WAVEfmt ', 8); file.writeUInt32LE(16, 16); file.writeUInt16LE(1, 20); file.writeUInt16LE(2, 22); file.writeUInt32LE(rate, 24); file.writeUInt32LE(rate * 4, 28); file.writeUInt16LE(4, 32); file.writeUInt16LE(16, 34); file.write('data', 36); file.writeUInt32LE(dataBytes, 40);
  for (let i = 0; i < samples.length; i++) file.writeInt16LE(Math.round(Math.max(-.9999, Math.min(.9999, samples[i])) * 32767), 44 + i * 2);
  return file;
}
const audioDir = 'public/madman/audio';
fs.mkdirSync(audioDir, {recursive: true});
const layers = {};
for (const [name, samples] of [['history-study-v3', mix], ['history-study-v3-voice', voice], ['history-study-v3-paper', bed]]) {
  const file = path.join(audioDir, `${name}.wav`);
  fs.writeFileSync(file, wav(samples));
  layers[name] = {file, sha256: hash(file)};
}
const stamp = (frame, separator) => {const ms = Math.round(frame / spec.fps * 1000); return `00:00:${String(Math.floor(ms / 1000)).padStart(2, '0')}${separator}${String(ms % 1000).padStart(3, '0')}`;};
const subtitleBase = 'out/madman/狂人日记-字缝加强样片-v3';
fs.mkdirSync(path.dirname(subtitleBase), {recursive: true});
fs.writeFileSync(`${subtitleBase}.srt`, spec.captions.map((c, i) => `${i + 1}\n${stamp(c.from, ',')} --> ${stamp(c.end, ',')}\n${c.text}\n`).join('\n'));
fs.writeFileSync(`${subtitleBase}.vtt`, `WEBVTT\n\n${spec.captions.map(c => `${stamp(c.from, '.')} --> ${stamp(c.end, '.')}\n${c.text}\n`).join('\n')}`);
const manifest = {edition: spec.edition, specFile, specSha256: hash(specFile), sourceTimelineSha256: hash(spec.sourceTimeline), providerManifestSha256: hash('public/madman/voice-v2/manifest.json'), durationSeconds: 20, durationFrames: 480, sampleRateHz: rate, channels: 2, bitDepth: 16, peakLinear: peak, peakDbfs: 20 * Math.log10(peak), silentInterval: {startSeconds: spec.sound.silenceStartSeconds, endSeconds: spec.sound.silenceEndSeconds, peakLinear: silentPeak}, synthesis: 'Reused Bailian voice clips; only an existing quiet interval was extended. Fixed-seed local paper/room sound.', cloudCalls: 0, narration: records, layers, humanListeningReview: false};
fs.writeFileSync(path.join(audioDir, 'history-study-v3-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Prepared 20s history study: ${records.length} cached voice cues, peak ${manifest.peakDbfs.toFixed(2)} dBFS, ${((spec.sound.silenceEndSeconds - spec.sound.silenceStartSeconds)).toFixed(2)}s silence.`);
