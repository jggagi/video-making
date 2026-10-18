import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {passages} from './text.mjs';
import {buildPlan, MODEL, VOICE, FORMAT, SAMPLE_RATE} from './synthesize-extended.mjs';

const fps = 24;
const sourceFile = path.resolve('src/museum/timeline.json');
const manifestFile = path.resolve('out/extended/manifest.json');
const outputRoot = path.resolve('out/extended');
const speechRoot = path.resolve('out/extended/speech');
const timelineOutput = path.resolve('src/extended/timeline.json');
const soundtrackOutput = path.resolve('public/extended/audio/soundtrack.wav');
const voiceOutput = path.resolve('out/extended/兰亭集序-男声旁白.wav');
const subtitleBase = path.resolve('out/extended/兰亭集序-展厅增强版');
const expectedCueCount = 26;
const expectedSceneCount = 17;

function sourceContext() {
  const source = JSON.parse(fs.readFileSync(sourceFile, 'utf8'));
  const scenes = source.shots.filter((shot) => shot.kind === 'scene');
  assert.equal(scenes.length, expectedSceneCount, `Expected ${expectedSceneCount} scenes.`);
  assert.equal(passages.length, expectedSceneCount, `Expected ${expectedSceneCount} original passages.`);
  assert.equal(source.fps, fps, `Source timeline must use ${fps} fps.`);
  for (const [index, scene] of scenes.entries()) {
    assert.equal(scene.id, passages[index].id, `Passage order changed at ${scene.id}.`);
    assert.equal(scene.text, passages[index].text, `Original passage text changed at ${scene.id}.`);
    assert.equal(scene.cues.map((cue) => cue.text).join(''), scene.text, `Original cue text does not match ${scene.id}.`);
  }
  assert.equal(scenes.flatMap((scene) => scene.cues).length, expectedCueCount, `Expected ${expectedCueCount} cues.`);
  return {source, scenes, plan: buildPlan(source)};
}

function sourceOnlyPlan() {
  const {scenes, plan} = sourceContext();
  console.log(`${scenes.length} original passages and ${plan.length} exact-text cues; title 312 frames; closing 216 frames; no provider calls.`);
}

function loadAndCheckManifest(plan) {
  const manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
  assert.equal(manifest.model, MODEL, 'Manifest model does not match the selected model.');
  assert.equal(manifest.voice, VOICE, 'Manifest voice does not match the selected voice.');
  assert.equal(manifest.format, FORMAT, 'Manifest format must be WAV.');
  assert.equal(Number(manifest.sampleRate), SAMPLE_RATE, `Manifest sample rate must be ${SAMPLE_RATE}.`);
  assert.equal(Number(manifest.channels), 1, 'Manifest audio must be mono.');
  assert.equal(manifest.cues?.length, expectedCueCount, `Manifest must contain ${expectedCueCount} generated cues.`);

  const checked = [];
  for (const expected of plan) {
    const entry = manifest.cues.find((item) => item.sceneId === expected.sceneId && item.cueIndex === expected.cueIndex);
    assert(entry, `Manifest is missing ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(entry.contentHash, expected.contentHash, `Content hash does not match ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(entry.model, MODEL, `Model changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(entry.voice, VOICE, `Voice changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(Number(entry.rate), expected.rate, `Speech rate changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(entry.format, FORMAT, `Audio format changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(Number(entry.sampleRate), SAMPLE_RATE, `Sample rate changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(entry.text, expected.originalText, `Original cue text changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(entry.path, expected.relativePath, `Audio path changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.match(entry.sha256, /^[0-9a-f]{64}$/, `Invalid audio digest for ${expected.sceneId} cue ${expected.cueIndex}.`);
    const file = path.resolve(entry.path);
    assert(file.startsWith(`${speechRoot}${path.sep}`), 'Manifest audio path escaped the extended speech directory.');
    assert(fs.existsSync(file), `Generated audio is missing for ${expected.sceneId} cue ${expected.cueIndex}.`);
    const digest = fileSha256(file);
    assert.equal(digest, entry.sha256, `Generated audio hash changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    const probe = probeAudio(file);
    assert.equal(probe.sampleRate, SAMPLE_RATE, `Generated audio sample rate changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(probe.channels, 1, `Generated audio must be mono for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert.equal(probe.codecName, 'pcm_s16le', `Generated audio must be 16-bit PCM for ${expected.sceneId} cue ${expected.cueIndex}.`);
    assert(Math.abs(Number(entry.durationSeconds) - probe.durationSeconds) <= 1 / SAMPLE_RATE, `Manifest duration changed for ${expected.sceneId} cue ${expected.cueIndex}.`);
    checked.push({...expected, entry, file, ...probe});
  }
  return checked;
}

function fileSha256(file) {
  return createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function probeAudio(file) {
  let result;
  try {
    result = execFileSync('ffprobe', [
      '-v', 'error',
      '-select_streams', 'a:0',
      '-show_entries', 'stream=codec_name,sample_rate,channels,duration_ts,time_base',
      '-of', 'json',
      file,
    ], {encoding: 'utf8', maxBuffer: 64 * 1024});
  } catch {
    throw new Error(`ffprobe could not inspect ${path.basename(file)}.`);
  }
  const stream = JSON.parse(result).streams?.[0];
  assert(stream, `No audio stream found in ${path.basename(file)}.`);
  const sampleRate = Number(stream.sample_rate);
  const channels = Number(stream.channels);
  const durationTicks = Number(stream.duration_ts);
  const [timeNumerator, timeDenominator] = String(stream.time_base).split('/').map(Number);
  assert(Number.isFinite(durationTicks) && Number.isFinite(timeNumerator) && Number.isFinite(timeDenominator) && timeDenominator > 0,
    `ffprobe did not return sample-accurate duration for ${path.basename(file)}.`);
  const exactSamples = durationTicks * timeNumerator / timeDenominator * sampleRate;
  const samples = Math.round(exactSamples);
  assert(Math.abs(samples - exactSamples) < 1e-6, `Audio sample count is not integral for ${path.basename(file)}.`);
  return {sampleRate, channels, codecName: stream.codec_name, samples, durationSeconds: samples / sampleRate};
}

function makeTimeline(source, checked) {
  const byCue = new Map(checked.map((item) => [`${item.sceneId}:${item.cueIndex}`, item]));
  const title = source.shots.find((shot) => shot.kind === 'title');
  const ending = source.shots.find((shot) => shot.kind === 'end');
  assert(title && ending, 'Source timeline must have title and end shots.');
  const shots = [{...title, from: 0, duration: 312, cues: []}];
  let nextFrame = 312;
  const cueChecks = [];
  for (const scene of source.shots.filter((shot) => shot.kind === 'scene')) {
    let localFrame = 18;
    const cues = scene.cues.map((cue, index) => {
      const audio = byCue.get(`${scene.id}:${index + 1}`);
      assert(audio, `No generated audio found for ${scene.id} cue ${index + 1}.`);
      const duration = Math.ceil(audio.samples / SAMPLE_RATE * fps) + 10;
      const aligned = {
        text: cue.text,
        from: localFrame,
        duration,
        sourceAudio: audio.relativePath,
      };
      assert(audio.samples <= duration / fps * SAMPLE_RATE, `Audio sample count exceeds its cue window in ${scene.id}.`);
      cueChecks.push({sceneId: scene.id, cueIndex: index + 1, samples: audio.samples, durationFrames: duration});
      localFrame += duration;
      return aligned;
    });
    const minimum = scene.id === 'record' ? 216 : scene.id === 'poems' ? 190 : 0;
    const duration = Math.max(localFrame + 18, minimum);
    shots.push({...scene, from: nextFrame, duration, cues});
    nextFrame += duration;
  }
  shots.push({...ending, from: nextFrame, duration: 216, cues: []});
  nextFrame += 216;
  const timeline = {fps, durationInFrames: nextFrame, shots};
  let cursor = 0;
  for (const shot of shots) {
    assert.equal(shot.from, cursor, `Timeline gap or overlap before ${shot.id}.`);
    cursor += shot.duration;
    if (shot.kind === 'scene') {
      assert.equal(shot.cues.map((cue) => cue.text).join(''), shot.text, `Caption text changed in ${shot.id}.`);
      for (const cue of shot.cues) assert(cue.from >= 0 && cue.from + cue.duration <= shot.duration, `Cue window escaped ${shot.id}.`);
    }
  }
  assert.equal(cursor, timeline.durationInFrames, 'Timeline total duration is inconsistent.');
  assert.equal(shots.find((shot) => shot.id === 'title').duration, 312, 'Title must last 13 seconds.');
  assert.equal(shots.find((shot) => shot.id === 'end').duration, 216, 'Closing must last 9 seconds.');
  assert.equal(shots.filter((shot) => shot.kind === 'scene').map((shot) => shot.text).join(''), passages.map((passage) => passage.text).join(''), 'Full passage text changed.');
  assert.equal(cueChecks.length, expectedCueCount, 'Not all cue audio was aligned.');
  return {timeline, cueChecks};
}

function stamp(frame, separator) {
  const ms = Math.round(frame / fps * 1000);
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}${separator}${String(ms % 1000).padStart(3, '0')}`;
}

function captions(timeline) {
  const cues = timeline.shots.flatMap((shot) => shot.kind === 'scene'
    ? shot.cues.map((cue) => ({...cue, from: shot.from + cue.from}))
    : []);
  const srt = cues.map((cue, index) => `${index + 1}\n${stamp(cue.from, ',')} --> ${stamp(cue.from + cue.duration, ',')}\n${cue.text}\n`).join('\n');
  const vtt = `WEBVTT\n\n${cues.map((cue) => `${stamp(cue.from, '.')} --> ${stamp(cue.from + cue.duration, '.')}\n${cue.text}\n`).join('\n')}`;
  return {srt, vtt, cues};
}

function encodeWav(samples, channels) {
  const dataBytes = samples.length * 2;
  const buffer = Buffer.alloc(44 + dataBytes);
  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(36 + dataBytes, 4);
  buffer.write('WAVEfmt ', 8);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(channels, 22);
  buffer.writeUInt32LE(SAMPLE_RATE, 24);
  buffer.writeUInt32LE(SAMPLE_RATE * channels * 2, 28);
  buffer.writeUInt16LE(channels * 2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write('data', 36);
  buffer.writeUInt32LE(dataBytes, 40);
  for (let index = 0; index < samples.length; index++) {
    const value = samples[index];
    assert(Number.isFinite(value) && Math.abs(value) < 1, 'Audio mix would clip.');
    buffer.writeInt16LE(Math.round(value * 32767), 44 + index * 2);
  }
  return buffer;
}

function decodePcm(file, expectedSamples) {
  let pcm;
  try {
    pcm = execFileSync('ffmpeg', [
      '-v', 'error', '-i', file,
      '-map', '0:a:0', '-ac', '1', '-ar', String(SAMPLE_RATE),
      '-acodec', 'pcm_s16le', '-f', 's16le', '-',
    ], {maxBuffer: 64 * 1024 * 1024});
  } catch {
    throw new Error(`ffmpeg could not decode ${path.basename(file)}.`);
  }
  assert.equal(pcm.length % 2, 0, `Decoded audio has an incomplete sample in ${path.basename(file)}.`);
  assert.equal(pcm.length / 2, expectedSamples, `Decoded sample count changed in ${path.basename(file)}.`);
  return pcm;
}

function renderAudio(timeline, checked) {
  const totalSamples = timeline.durationInFrames * SAMPLE_RATE / fps;
  assert(Number.isInteger(totalSamples), 'Timeline cannot be represented at the requested sample rate.');
  const voice = new Float32Array(totalSamples);
  const left = new Float32Array(totalSamples);
  const right = new Float32Array(totalSamples);
  let maxGain = 0;
  let maxVoicePeak = 0;
  const fadeSamples = Math.round(SAMPLE_RATE * 0.005);
  const cueLookup = new Map(checked.map((item) => [`${item.sceneId}:${item.cueIndex}`, item]));

  for (const scene of timeline.shots.filter((shot) => shot.kind === 'scene')) {
    for (const [index, cue] of scene.cues.entries()) {
      const audio = cueLookup.get(`${scene.id}:${index + 1}`);
      const pcm = decodePcm(audio.file, audio.samples);
      let peak = 0;
      for (let sample = 0; sample < audio.samples; sample++) peak = Math.max(peak, Math.abs(pcm.readInt16LE(sample * 2) / 32768));
      const gain = Math.min(3, 0.62 / Math.max(peak, 0.001));
      maxGain = Math.max(maxGain, gain);
      const cuePeak = Math.min(peak * gain, 0.62);
      maxVoicePeak = Math.max(maxVoicePeak, cuePeak);
      const start = (scene.from + cue.from) * SAMPLE_RATE / fps;
      assert(Number.isInteger(start), 'Cue start is not on an audio sample boundary.');
      assert(start + audio.samples <= totalSamples, `Audio sample escaped the timeline in ${scene.id}.`);
      for (let sample = 0; sample < audio.samples; sample++) {
        const fadeIn = Math.min(1, sample / fadeSamples);
        const fadeOut = Math.min(1, (audio.samples - 1 - sample) / fadeSamples);
        const value = pcm.readInt16LE(sample * 2) / 32768 * gain * Math.max(0, Math.min(fadeIn, fadeOut));
        voice[start + sample] += value;
        left[start + sample] += value;
        right[start + sample] += value;
      }
    }
  }

  const seconds = timeline.durationInFrames / fps;
  let seed = 353;
  let lowL = 0;
  let lowR = 0;
  let wind = 0;
  for (let sample = 0; sample < totalSamples; sample++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const noise = seed / 4294967296 * 2 - 1;
    lowL = lowL * 0.90 + noise * 0.10;
    lowR = lowR * 0.93 + noise * 0.07;
    wind = wind * 0.995 + noise * 0.005;
    const time = sample / SAMPLE_RATE;
    const fade = Math.max(0, Math.min(1, time / 2.8, (seconds - time) / 4));
    const water = 0.019 * (0.8 + 0.2 * Math.sin(time * 0.37));
    const rustle = 0.045 * (0.65 + 0.35 * Math.sin(time * 0.17));
    left[sample] += (lowL * water + wind * rustle) * fade;
    right[sample] += (lowR * water + wind * rustle * 0.9) * fade;
  }

  const turn = timeline.shots.find((shot) => shot.id === 'life').from / fps;
  const notes = [146.83, 220, 293.66, 261.63, 392, 293.66, 220, 146.83];
  for (let startSeconds = 1.2, noteIndex = 0; startSeconds < seconds - 5; startSeconds += 6.3, noteIndex++) {
    const frequency = notes[noteIndex % notes.length] * (startSeconds >= turn ? 0.75 : 1);
    const first = Math.round(startSeconds * SAMPLE_RATE);
    const length = Math.min(totalSamples - first, Math.round(SAMPLE_RATE * 5.8));
    const pan = Math.sin(noteIndex * 1.8) * 0.28;
    for (let sample = 0; sample < length; sample++) {
      const time = sample / SAMPLE_RATE;
      const envelope = Math.min(1, time / 0.015) * Math.exp(-time / 1.95);
      const dry = 0.022 * envelope * (Math.sin(2 * Math.PI * frequency * time)
        + 0.24 * Math.sin(2 * Math.PI * frequency * 2.002 * time)
        + 0.09 * Math.sin(2 * Math.PI * frequency * 3.001 * time));
      left[first + sample] += dry * (1 - pan);
      right[first + sample] += dry * (1 + pan);
      const echo = first + sample + Math.round(SAMPLE_RATE * 0.28);
      if (echo < totalSamples) {
        left[echo] += dry * 0.16;
        right[echo] += dry * 0.22;
      }
    }
  }

  let mixPeak = 0;
  const stereo = new Float32Array(totalSamples * 2);
  for (let sample = 0; sample < totalSamples; sample++) {
    assert(Math.abs(voice[sample]) < 1, 'Voice-only mix would clip.');
    assert(Math.abs(left[sample]) < 1 && Math.abs(right[sample]) < 1, 'Soundtrack mix would clip.');
    mixPeak = Math.max(mixPeak, Math.abs(left[sample]), Math.abs(right[sample]));
    stereo[sample * 2] = left[sample];
    stereo[sample * 2 + 1] = right[sample];
  }
  return {
    soundtrack: encodeWav(stereo, 2),
    voiceOnly: encodeWav(voice, 1),
    maxGain,
    maxVoicePeak,
    mixPeak,
    voicePeak: maxVoicePeak,
  };
}

function prepare() {
  const {source, scenes, plan} = sourceContext();
  assert(fs.existsSync(manifestFile), `Generated manifest is missing: ${path.relative(process.cwd(), manifestFile)}.`);
  const checked = loadAndCheckManifest(plan);
  const {timeline, cueChecks} = makeTimeline(source, checked);
  const {srt, vtt, cues} = captions(timeline);
  const audio = renderAudio(timeline, checked);
  const preflight = {
    fps,
    frames: timeline.durationInFrames,
    seconds: timeline.durationInFrames / fps,
    scenes: scenes.length,
    cues: cues.length,
    fullTextMatches: true,
    continuousTimeline: true,
    allCueSamplesFit: cueChecks.length === expectedCueCount,
    cueSampleChecks: cueChecks,
    model: MODEL,
    voice: VOICE,
    sampleRate: SAMPLE_RATE,
    soundtrackChannels: 2,
    voicePeakTarget: 0.62,
    maxAppliedVoiceGain: audio.maxGain,
    measuredVoicePeak: audio.voicePeak,
    soundtrackPeakDbfs: 20 * Math.log10(Math.max(audio.mixPeak, 1e-9)),
    music: 'Original locally synthesized sparse string tones, wind and water',
  };

  fs.mkdirSync(path.dirname(timelineOutput), {recursive: true});
  fs.mkdirSync(path.dirname(soundtrackOutput), {recursive: true});
  fs.mkdirSync(outputRoot, {recursive: true});
  fs.writeFileSync(timelineOutput, `${JSON.stringify(timeline, null, 2)}\n`);
  fs.writeFileSync(soundtrackOutput, audio.soundtrack);
  fs.writeFileSync(voiceOutput, audio.voiceOnly);
  fs.writeFileSync(`${subtitleBase}.srt`, srt);
  fs.writeFileSync(`${subtitleBase}.vtt`, vtt);
  fs.writeFileSync(path.join(outputRoot, 'preflight.json'), `${JSON.stringify(preflight, null, 2)}\n`);
  console.log(`${timeline.durationInFrames} frames / ${(timeline.durationInFrames / fps).toFixed(3)} seconds; ${cues.length} exact-text cues; ${scenes.length} passages; mix peak ${Math.round(preflight.soundtrackPeakDbfs * 10) / 10} dBFS.`);
}

function run() {
  if (process.argv.includes('--plan') || process.argv.includes('--check')) return sourceOnlyPlan();
  prepare();
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    run();
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
