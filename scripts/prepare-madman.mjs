import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const timelinePath = path.resolve('src/madman/timeline.json');
const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
const sampleRate = 48_000;
const channels = 2;
const bitDepth = 16;
const expectedFps = 24;
const expectedFrames = 2_160;
const expectedSeconds = 90;
const seed = 0x4d41444d;
const maxPeak = 0.6;
const audioPath = path.resolve('public/madman/audio/atmosphere.wav');
const manifestPath = path.resolve('public/madman/audio/manifest.json');
const subtitleBase = path.resolve('out/madman/狂人日记-木刻意象版-v1');

assert.equal(timeline.fps, expectedFps, `Madman timeline must remain ${expectedFps} fps.`);
assert.equal(timeline.durationInFrames, expectedFrames, `Madman timeline must remain ${expectedFrames} frames.`);
assert.equal(timeline.durationInFrames / timeline.fps, expectedSeconds, 'Madman timeline must remain exactly 90 seconds.');

let cursor = 0;
const cues = [];
for (const shot of timeline.shots) {
  assert.equal(shot.from, cursor, `Timeline gap or overlap before ${shot.id}.`);
  assert(Number.isInteger(shot.duration) && shot.duration > 0, `Invalid duration in ${shot.id}.`);
  cursor += shot.duration;
  for (const cue of shot.cues ?? []) {
    assert(Number.isInteger(cue.from) && Number.isInteger(cue.duration), `Invalid cue frame in ${shot.id}.`);
    assert(cue.from >= 0 && cue.duration > 0 && cue.from + cue.duration <= shot.duration,
      `Cue exceeds the ${shot.id} shot bounds.`);
    assert.equal(typeof cue.text, 'string');
    const absoluteFrom = shot.from + cue.from;
    const absoluteEnd = absoluteFrom + cue.duration;
    assert(absoluteFrom >= 0 && absoluteEnd <= timeline.durationInFrames, `Cue exceeds the timeline bounds in ${shot.id}.`);
    cues.push({from: absoluteFrom, end: absoluteEnd, text: cue.text});
  }
}
assert.equal(cursor, timeline.durationInFrames, 'Shot durations do not match the timeline duration.');
for (let index = 1; index < cues.length; index++) {
  assert(cues[index].from >= cues[index - 1].from, 'Caption cues are not chronological.');
}

function timestamp(frame, separator) {
  const milliseconds = Math.round(frame * 1_000 / timeline.fps);
  const hours = Math.floor(milliseconds / 3_600_000);
  const minutes = Math.floor(milliseconds / 60_000) % 60;
  const seconds = Math.floor(milliseconds / 1_000) % 60;
  const remainder = milliseconds % 1_000;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}${separator}${String(remainder).padStart(3, '0')}`;
}

const srt = cues.map((cue, index) => `${index + 1}\n${timestamp(cue.from, ',')} --> ${timestamp(cue.end, ',')}\n${cue.text}\n`).join('\n');
const vtt = `WEBVTT\n\n${cues.map((cue) => `${timestamp(cue.from, '.')} --> ${timestamp(cue.end, '.')}\n${cue.text}\n`).join('\n')}`;
fs.mkdirSync(path.dirname(audioPath), {recursive: true});
fs.mkdirSync(path.dirname(subtitleBase), {recursive: true});
fs.writeFileSync(`${subtitleBase}.srt`, srt, 'utf8');
fs.writeFileSync(`${subtitleBase}.vtt`, vtt, 'utf8');

const totalSamples = expectedSeconds * sampleRate;
const pcmBytes = totalSamples * channels * (bitDepth / 8);
const wav = Buffer.alloc(44 + pcmBytes);
wav.write('RIFF', 0);
wav.writeUInt32LE(wav.length - 8, 4);
wav.write('WAVEfmt ', 8);
wav.writeUInt32LE(16, 16);
wav.writeUInt16LE(1, 20);
wav.writeUInt16LE(channels, 22);
wav.writeUInt32LE(sampleRate, 24);
wav.writeUInt32LE(sampleRate * channels * (bitDepth / 8), 28);
wav.writeUInt16LE(channels * (bitDepth / 8), 32);
wav.writeUInt16LE(bitDepth, 34);
wav.write('data', 36);
wav.writeUInt32LE(pcmBytes, 40);

const framesById = new Map(timeline.shots.map((shot) => [shot.id, shot]));
const watch = framesById.get('watch');
const history = framesById.get('history');
const children = framesById.get('children');
const plea = framesById.get('plea');
assert(watch && history && children && plea, 'Expected watch, history, children, and plea shots in the Madman timeline.');

const leftPadStart = watch.from / timeline.fps;
const padHinge = history.from / timeline.fps;
const leftPadEnd = (history.from + history.duration) / timeline.fps;
const rightPadEnd = leftPadEnd;
const knockEvents = timeline.shots.slice(1).map((shot, index) => ({
  time: shot.from / timeline.fps + 0.035,
  pan: Math.sin(index * 1.7) * 0.35,
}));
const warmNotes = [
  {time: children.from / timeline.fps + 0.75, duration: 2.8, frequency: 392.0, pan: -0.18},
  {time: children.from / timeline.fps + 4.35, duration: 2.5, frequency: 523.25, pan: 0.16},
  {time: children.from / timeline.fps + 8.5, duration: 2.1, frequency: 659.25, pan: -0.1},
  {time: plea.from / timeline.fps + 1.0, duration: 2.5, frequency: 392.0, pan: 0.12},
];

function smoothstep(value) {
  const x = Math.max(0, Math.min(1, value));
  return x * x * (3 - 2 * x);
}

function writeEvent(firstSample, count, pan, sampleAt) {
  const leftGain = Math.sqrt((1 - pan) / 2) * Math.SQRT2;
  const rightGain = Math.sqrt((1 + pan) / 2) * Math.SQRT2;
  const end = Math.min(totalSamples, firstSample + count);
  for (let sample = Math.max(0, firstSample); sample < end; sample++) {
    const value = sampleAt((sample - firstSample) / sampleRate);
    const currentLeft = eventLeft[sample] + value * leftGain;
    const currentRight = eventRight[sample] + value * rightGain;
    eventLeft[sample] = currentLeft;
    eventRight[sample] = currentRight;
  }
}

const eventLeft = new Float32Array(totalSamples);
const eventRight = new Float32Array(totalSamples);
for (const event of knockEvents) {
  const start = Math.round(event.time * sampleRate);
  const duration = 0.42;
  writeEvent(start, Math.round(duration * sampleRate), event.pan, (time) => {
    const decay = Math.exp(-time / 0.115);
    const body = Math.sin(2 * Math.PI * 48 * time) + 0.28 * Math.sin(2 * Math.PI * 79 * time + 0.25);
    const softAttack = Math.min(1, time / 0.006);
    return 0.095 * softAttack * decay * body;
  });
}
for (const note of warmNotes) {
  const start = Math.round(note.time * sampleRate);
  const count = Math.round(note.duration * sampleRate);
  writeEvent(start, count, note.pan, (time) => {
    const fadeIn = smoothstep(time / 0.55);
    const fadeOut = smoothstep((note.duration - time) / 0.72);
    const envelope = fadeIn * fadeOut;
    const fundamental = Math.sin(2 * Math.PI * note.frequency * time);
    const softOvertone = 0.16 * Math.sin(2 * Math.PI * note.frequency * 2.003 * time + 0.12);
    return 0.038 * envelope * (fundamental + softOvertone);
  });
}

let randomState = seed >>> 0;
let windLeft = 0;
let windRight = 0;
let slowLeft = 0;
let slowRight = 0;
let peak = 0;
for (let sample = 0; sample < totalSamples; sample++) {
  randomState = (Math.imul(randomState, 1_664_525) + 1_013_904_223) >>> 0;
  const noiseLeft = randomState / 4_294_967_296 * 2 - 1;
  randomState = (Math.imul(randomState, 1_664_525) + 1_013_904_223) >>> 0;
  const noiseRight = randomState / 4_294_967_296 * 2 - 1;
  windLeft = windLeft * 0.91 + noiseLeft * 0.09;
  windRight = windRight * 0.91 + noiseRight * 0.09;
  slowLeft = slowLeft * 0.986 + noiseLeft * 0.014;
  slowRight = slowRight * 0.986 + noiseRight * 0.014;

  const time = sample / sampleRate;
  const fadeIn = smoothstep(time / 1.8);
  const fadeOut = Math.max(0, Math.min(1, expectedSeconds - time));
  const globalEnvelope = fadeIn * fadeOut;
  const swell = 0.83 + 0.17 * Math.sin(2 * Math.PI * time / 21.5 + 0.6);
  const windGain = globalEnvelope * swell;
  let left = (windLeft * 0.12 + slowLeft * 0.05 + noiseLeft * 0.006) * windGain;
  let right = (windRight * 0.12 + slowRight * 0.05 + noiseRight * 0.006) * windGain;

  const padIn = smoothstep((time - leftPadStart) / 1.4);
  const padOut = Math.max(0, Math.min(1, (leftPadEnd - time) / 1.6));
  const padEnvelope = padIn * padOut;
  const tension = smoothstep((time - padHinge) / Math.max(0.001, leftPadEnd - padHinge));
  const rootHz = 98 + tension * 5.5;
  const fifthHz = 146.83 + tension * 8.1;
  if (padEnvelope > 0) {
    const rootPhase = 2 * Math.PI * time * rootHz;
    const fifthPhase = 2 * Math.PI * time * fifthHz;
    const pad = padEnvelope * (
      0.034 * Math.sin(rootPhase) +
      0.025 * Math.sin(fifthPhase) +
      0.006 * Math.sin(rootPhase * 2.001 + 0.15)
    );
    const width = 0.09 * Math.sin(2 * Math.PI * time / 13.7);
    left += pad * (1 + width);
    right += pad * (1 - width);
  }

  left += eventLeft[sample] * globalEnvelope;
  right += eventRight[sample] * globalEnvelope;
  assert(Number.isFinite(left) && Number.isFinite(right), `Non-finite audio sample at ${sample}.`);
  peak = Math.max(peak, Math.abs(left), Math.abs(right));
  assert(peak <= maxPeak, `Audio peak ${peak.toFixed(4)} exceeds ${maxPeak}.`);
  wav.writeInt16LE(Math.round(left * 32_767), 44 + sample * 4);
  wav.writeInt16LE(Math.round(right * 32_767), 46 + sample * 4);
}

fs.writeFileSync(audioPath, wav);
const manifest = {
  source: 'procedural local synthesis',
  speech: 'none',
  sampleRateHz: sampleRate,
  channels,
  bitDepth,
  codec: 'pcm_s16le',
  durationSeconds: expectedSeconds,
  durationFrames: expectedFrames,
  peakLinear: peak,
  peakDbfs: 20 * Math.log10(peak),
  seed,
  cues: cues.length,
};
fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
console.log(`Generated ${expectedSeconds}s stereo PCM atmosphere (${cues.length} captions, peak ${peak.toFixed(4)}).`);
