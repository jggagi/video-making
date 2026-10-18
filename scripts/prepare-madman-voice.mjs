import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const fps = 24;
const sourceRate = 24_000;
const sampleRate = 48_000;
const samplesPerFrame = sampleRate / fps;
const outputBitDepth = 16;
const voiceDirectory = path.resolve(root, 'public/madman/voice-v2');
const planPath = path.join(voiceDirectory, 'plan.json');
const voiceManifestPath = path.join(voiceDirectory, 'manifest.json');
const sourceTimelinePath = path.resolve(root, 'src/madman/timeline.json');
const atmospherePath = path.resolve(root, 'public/madman/audio/atmosphere.wav');
const atmosphereManifestPath = path.resolve(root, 'public/madman/audio/manifest.json');
const ffmpegPath = '/opt/homebrew/bin/ffmpeg';
const ffprobePath = process.env.FFPROBE_PATH ?? '/opt/homebrew/bin/ffprobe';

const voicedTimelinePath = path.resolve(root, 'src/madman/voiced-timeline.json');
const outputWavPath = path.resolve(root, 'public/madman/audio/voiced-v2.wav');
const outputManifestPath = path.resolve(root, 'public/madman/audio/voiced-v2-manifest.json');
const subtitleBase = path.resolve(root, 'out/madman/狂人日记-男声配音版-v2');

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function sha256(file) {
  return createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function probeAudio(file) {
  const result = execFileSync(ffprobePath, [
    '-v', 'error',
    '-select_streams', 'a:0',
    '-show_entries', 'stream=codec_name,codec_type,sample_rate,channels,bits_per_sample,duration,duration_ts,time_base',
    '-show_entries', 'format=format_name,duration',
    '-of', 'json',
    file,
  ], {encoding: 'utf8', maxBuffer: 128 * 1024});
  const parsed = JSON.parse(result);
  const stream = parsed.streams?.[0];
  assert(stream, `No audio stream found in ${path.basename(file)}.`);
  assert(String(parsed.format?.format_name ?? '').split(',').includes('wav'), `${path.basename(file)} is not a WAV file.`);
  return {
    codecName: stream.codec_name,
    sampleRate: Number(stream.sample_rate),
    channels: Number(stream.channels),
    bitsPerSample: Number(stream.bits_per_sample),
    duration: Number(stream.duration ?? parsed.format?.duration),
  };
}

function decodeFloat(file, channels) {
  const pcm = execFileSync(ffmpegPath, [
    '-v', 'error', '-i', file,
    '-map', '0:a:0', '-vn', '-sn', '-dn',
    '-ac', String(channels), '-ar', String(sampleRate),
    '-acodec', 'pcm_f32le', '-f', 'f32le', 'pipe:1',
  ], {maxBuffer: 512 * 1024 * 1024});
  assert.equal(pcm.length % 4, 0, `Decoded float audio has a partial sample in ${path.basename(file)}.`);
  assert.equal(pcm.length % (channels * 4), 0, `Decoded audio has a partial channel frame in ${path.basename(file)}.`);
  assert.equal(pcm.byteOffset % 4, 0, `Decoded float audio is not sample aligned in ${path.basename(file)}.`);
  const samples = new Float32Array(pcm.buffer, pcm.byteOffset, pcm.length / 4);
  assert(samples.length > 0, `Decoded audio is empty in ${path.basename(file)}.`);
  for (const value of samples) assert(Number.isFinite(value), `Decoded audio has a non-finite sample in ${path.basename(file)}.`);
  return samples;
}

function formatTimestamp(frame, separator) {
  const milliseconds = Math.round(frame * 1_000 / fps);
  const hours = Math.floor(milliseconds / 3_600_000);
  const minutes = Math.floor(milliseconds / 60_000) % 60;
  const seconds = Math.floor(milliseconds / 1_000) % 60;
  const remainder = milliseconds % 1_000;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}${separator}${String(remainder).padStart(3, '0')}`;
}

function encodeWav(stereoSamples) {
  assert.equal(stereoSamples.length % 2, 0);
  const dataBytes = stereoSamples.length * outputBitDepth / 8;
  const wav = Buffer.alloc(44 + dataBytes);
  wav.write('RIFF', 0);
  wav.writeUInt32LE(wav.length - 8, 4);
  wav.write('WAVEfmt ', 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(2, 22);
  wav.writeUInt32LE(sampleRate, 24);
  wav.writeUInt32LE(sampleRate * 4, 28);
  wav.writeUInt16LE(4, 32);
  wav.writeUInt16LE(outputBitDepth, 34);
  wav.write('data', 36);
  wav.writeUInt32LE(dataBytes, 40);

  let pcmPeak = 0;
  for (let index = 0; index < stereoSamples.length; index++) {
    const value = stereoSamples[index];
    assert(Number.isFinite(value) && Math.abs(value) < 1, `Mixed audio would clip at sample ${index}.`);
    const pcm = Math.max(-32_768, Math.min(32_767, Math.round(value * 32_768)));
    pcmPeak = Math.max(pcmPeak, Math.abs(pcm / 32_768));
    wav.writeInt16LE(pcm, 44 + index * 2);
  }
  return {wav, pcmPeak};
}

assert.equal(fps, 24);
assert.equal(samplesPerFrame, 2_000, '48 kHz samples must map to an integer number of 24 fps frames.');
assert(fs.existsSync(ffmpegPath), `The configured ffmpeg executable is missing: ${ffmpegPath}`);
assert(fs.existsSync(ffprobePath), `The configured ffprobe executable is missing: ${ffprobePath}`);

const plan = readJson(planPath);
const sourceTimeline = readJson(sourceTimelinePath);
const atmosphereManifest = readJson(atmosphereManifestPath);
const voiceManifest = readJson(voiceManifestPath);
assert.equal(plan.format, 'wav', 'Voice plan must specify WAV files.');
assert.equal(Number(plan.sampleRate), sourceRate, `Voice plan must specify ${sourceRate} Hz audio.`);
assert.equal(sourceTimeline.fps, fps, `Source timeline must use ${fps} fps.`);
assert.equal(sourceTimeline.durationInFrames, 2_160, 'Source timeline must remain the original 90-second, 2160-frame version.');
assert.equal(sourceTimeline.durationInFrames / fps, 90);
assert.equal(plan.sourceTimeline, 'src/madman/timeline.json');
for (const field of ['provider', 'voice', 'model']) {
  assert.equal(typeof voiceManifest[field], 'string', `Voice manifest must include ${field}.`);
  assert(voiceManifest[field].trim(), `Voice manifest ${field} must not be empty.`);
}
assert.equal(voiceManifest.voice, plan.voice, 'Voice manifest differs from the selected voice.');
assert.equal(voiceManifest.model, plan.expectedModel, 'Voice manifest differs from the selected model.');
assert.equal(voiceManifest.cues.length, plan.cues.length, 'The full set of narration cues is not ready.');

const originalShots = sourceTimeline.shots;
let originalCursor = 0;
const originalCueRows = [];
for (const shot of originalShots) {
  assert.equal(shot.from, originalCursor, `Source timeline gap or overlap before ${shot.id}.`);
  assert(Number.isInteger(shot.duration) && shot.duration > 0, `Invalid source duration in ${shot.id}.`);
  originalCursor += shot.duration;
  for (const [cueIndex, cue] of (shot.cues ?? []).entries()) {
    assert(cue.from >= 0 && cue.duration > 0 && cue.from + cue.duration <= shot.duration,
      `Original caption cue exceeds ${shot.id}.`);
    originalCueRows.push({shot, cue, cueIndex});
  }
}
assert.equal(originalCursor, sourceTimeline.durationInFrames, 'Source shot durations do not match the timeline.');
assert.equal(originalShots.length, 8, 'Expected the packet timeline with the original eight shots.');
assert.equal(originalShots[0].id, 'title');
assert.equal(originalShots[0].duration, 144, 'The 144-frame title must remain unchanged.');
assert.equal(plan.cues.length, originalCueRows.length, 'Voice plan cue count does not match the source timeline.');

const clipRecords = [];
for (const [index, plannedCue] of plan.cues.entries()) {
  const original = originalCueRows[index];
  assert(original, `Unexpected extra voice cue ${plannedCue.id}.`);
  assert.equal(plannedCue.shotId, original.shot.id, `Voice plan shot order differs at ${plannedCue.id}.`);
  assert.equal(plannedCue.cueIndex, original.cueIndex, `Voice plan cue index differs at ${plannedCue.id}.`);
  assert.equal(plannedCue.text, original.cue.text, `Voice text differs from the source cue ${plannedCue.id}.`);
  assert.equal(typeof plannedCue.audioFile, 'string', `Missing audioFile for ${plannedCue.id}.`);
  const file = path.resolve(root, plannedCue.audioFile);
  assert(file.startsWith(`${voiceDirectory}${path.sep}`), `Voice plan path escapes ${path.relative(root, voiceDirectory)}.`);
  assert(fs.existsSync(file), `Voice clip is not available yet: ${plannedCue.audioFile}`);
  const verifiedEntry = voiceManifest.cues.find(cue => cue.id === plannedCue.id);
  assert(verifiedEntry, `Missing provider manifest entry for ${plannedCue.id}.`);
  assert.equal(verifiedEntry.text, plannedCue.text, `Provider manifest text differs for ${plannedCue.id}.`);
  assert.equal(verifiedEntry.voice, plan.voice, `Provider manifest voice differs for ${plannedCue.id}.`);
  assert.equal(verifiedEntry.model, plan.expectedModel, `Provider manifest model differs for ${plannedCue.id}.`);
  assert.equal(verifiedEntry.sha256, sha256(file), `Provider audio hash differs for ${plannedCue.id}.`);

  const probe = probeAudio(file);
  assert.equal(probe.sampleRate, sourceRate, `${plannedCue.audioFile} must be ${sourceRate} Hz.`);
  assert.equal(probe.channels, 1, `${plannedCue.audioFile} must be mono.`);
  const samples = decodeFloat(file, 1);
  let sourcePeak = 0;
  for (const value of samples) sourcePeak = Math.max(sourcePeak, Math.abs(value));
  assert(sourcePeak > 0, `Voice clip ${plannedCue.audioFile} is silent.`);
  const normalizationGain = 0.6 / sourcePeak;
  let normalizedPeak = 0;
  for (let sample = 0; sample < samples.length; sample++) {
    samples[sample] *= normalizationGain;
    normalizedPeak = Math.max(normalizedPeak, Math.abs(samples[sample]));
  }
  assert(normalizedPeak <= 0.60001, `Normalized clip ${plannedCue.audioFile} exceeds the 0.60 voice peak target.`);
  clipRecords.push({
    id: plannedCue.id,
    shotId: plannedCue.shotId,
    cueIndex: plannedCue.cueIndex,
    text: plannedCue.text,
    audioFile: plannedCue.audioFile,
    absolutePath: file,
    sha256: sha256(file),
    sourceSampleRateHz: probe.sampleRate,
    sourceChannels: probe.channels,
    sourceDurationSeconds: samples.length / sampleRate,
    sourcePeak,
    normalizationGain,
    normalizedPeak,
    samples,
    originalCue: original.cue,
  });
}

const clipByKey = new Map(clipRecords.map((clip) => [`${clip.shotId}:${clip.cueIndex}`, clip]));
const voicedShots = [];
const shotLayouts = [];
const outputCueRows = [];
let newCursor = 0;
for (const originalShot of originalShots) {
  const oldCueList = originalShot.cues ?? [];
  const newCues = [];
  let previousCueEnd = null;
  for (const [cueIndex, originalCue] of oldCueList.entries()) {
    const clip = clipByKey.get(`${originalShot.id}:${cueIndex}`);
    assert(clip, `No voice clip is mapped to ${originalShot.id} cue ${cueIndex}.`);
    const audioDurationFrames = Math.ceil(clip.samples.length / samplesPerFrame);
    const actualStart = previousCueEnd === null
      ? originalCue.from
      : Math.max(originalCue.from, previousCueEnd + 8);
    const duration = Math.max(originalCue.duration, audioDurationFrames + 8);
    const cue = {
      ...originalCue,
      from: actualStart,
      duration,
      audioFile: clip.audioFile,
      audioDurationSeconds: clip.sourceDurationSeconds,
      audioStartFrame: newCursor + actualStart,
      audioDurationFrames,
    };
    newCues.push(cue);
    outputCueRows.push({shot: originalShot, cue, clip});
    previousCueEnd = actualStart + duration;
  }

  const originalLastCueEnd = oldCueList.length
    ? oldCueList[oldCueList.length - 1].from + oldCueList[oldCueList.length - 1].duration
    : originalShot.duration;
  const preservedTail = originalShot.duration - originalLastCueEnd;
  assert(preservedTail >= 0, `Original final cue exceeds ${originalShot.id}.`);
  const finalCueEnd = newCues.length
    ? newCues[newCues.length - 1].from + newCues[newCues.length - 1].duration
    : originalShot.duration;
  const newDuration = Math.max(originalShot.duration, finalCueEnd + preservedTail);
  const voicedShot = {
    ...originalShot,
    from: newCursor,
    duration: newDuration,
    cues: newCues,
  };
  voicedShots.push(voicedShot);
  shotLayouts.push({
    id: originalShot.id,
    originalFrom: originalShot.from,
    originalDuration: originalShot.duration,
    newFrom: newCursor,
    newDuration,
    preservedTailFrames: preservedTail,
  });
  newCursor += newDuration;
}

const voicedTimeline = {
  ...sourceTimeline,
  edition: plan.edition ?? '原文节选 · 男声配音版 v2',
  durationInFrames: newCursor,
  shots: voicedShots,
  audioFile: 'public/madman/audio/voiced-v2.wav',
  audio: {sampleRateHz: sampleRate, channels: 2, bitDepth: outputBitDepth, codec: 'pcm_s16le'},
};
assert.equal(voicedShots.length, originalShots.length, 'Voiced timeline changed shot count.');
for (let index = 0; index < voicedShots.length; index++) {
  const oldShot = originalShots[index];
  const newShot = voicedShots[index];
  assert.equal(newShot.id, oldShot.id, `Shot order changed at ${oldShot.id}.`);
  assert.equal(newShot.asset, oldShot.asset, `Shot asset changed in ${oldShot.id}.`);
  assert.equal(newShot.section, oldShot.section, `Shot section changed in ${oldShot.id}.`);
  assert.equal(newShot.cues.map((cue) => cue.text).join(''), oldShot.cues.map((cue) => cue.text).join(''),
    `Caption source text changed in ${oldShot.id}.`);
}
assert.equal(voicedShots[0].duration, 144, 'The title duration must remain 144 frames.');
assert(newCursor / fps <= 120, `Retimed narration timeline is ${newCursor / fps} seconds; the supported maximum is 120 seconds.`);
assert(Number.isInteger(newCursor * samplesPerFrame), 'Retimed audio duration is not an exact sample count.');

const atmosphereProbe = probeAudio(atmospherePath);
assert.equal(atmosphereProbe.codecName, 'pcm_s16le', 'The source atmosphere must be 16-bit PCM.');
assert.equal(atmosphereProbe.sampleRate, sampleRate, `The source atmosphere must be ${sampleRate} Hz.`);
assert.equal(atmosphereProbe.channels, 2, 'The source atmosphere must be stereo.');
assert.equal(atmosphereProbe.bitsPerSample, outputBitDepth, 'The source atmosphere must be 16-bit.');
const oldAtmosphere = decodeFloat(atmospherePath, 2);
const originalSampleCount = sourceTimeline.durationInFrames * samplesPerFrame;
assert.equal(oldAtmosphere.length, originalSampleCount * 2, 'The original atmosphere must cover the complete 90-second source timeline.');
assert.equal(Number(atmosphereManifest.durationSeconds), 90, 'The original atmosphere manifest must describe the 90-second source version.');
assert.equal(Number(atmosphereManifest.durationFrames), sourceTimeline.durationInFrames);

const outputSampleCount = newCursor * samplesPerFrame;
const background = new Float32Array(outputSampleCount * 2);
const shotLayoutById = new Map(shotLayouts.map((layout) => [layout.id, layout]));
let sourceFrameCursor = 0;
for (const layout of shotLayouts) {
  assert.equal(layout.originalFrom, sourceFrameCursor, `Original atmosphere source segment is discontinuous before ${layout.id}.`);
  const sourceSamples = layout.originalDuration * samplesPerFrame;
  const targetSamples = layout.newDuration * samplesPerFrame;
  const sourceStart = layout.originalFrom * samplesPerFrame * 2;
  const targetStart = layout.newFrom * samplesPerFrame * 2;
  assert(Number.isInteger(sourceSamples) && Number.isInteger(targetSamples));
  if (targetSamples === sourceSamples) {
    background.set(oldAtmosphere.subarray(sourceStart, sourceStart + sourceSamples * 2), targetStart);
  } else {
    const preservedSamples = Math.floor(sourceSamples * 0.9);
    const sourceTailSamples = sourceSamples - preservedSamples;
    const targetTailSamples = targetSamples - preservedSamples;
    assert(targetTailSamples > sourceTailSamples && sourceTailSamples >= 2, `Invalid atmosphere tail stretch in ${layout.id}.`);
    background.set(oldAtmosphere.subarray(sourceStart, sourceStart + preservedSamples * 2), targetStart);
    for (let index = 0; index < targetTailSamples; index++) {
      const position = preservedSamples + (sourceTailSamples - 1) * index / (targetTailSamples - 1);
      const lower = Math.floor(position);
      const upper = Math.min(sourceSamples - 1, lower + 1);
      const weight = position - lower;
      for (let channel = 0; channel < 2; channel++) {
        const a = oldAtmosphere[(sourceStart / 2 + lower) * 2 + channel];
        const b = oldAtmosphere[(sourceStart / 2 + upper) * 2 + channel];
        background[targetStart + (preservedSamples + index) * 2 + channel] = a + (b - a) * weight;
      }
    }
  }
  sourceFrameCursor += layout.originalDuration;
}
assert.equal(sourceFrameCursor, sourceTimeline.durationInFrames, 'Atmosphere source segments did not consume the full original recording.');

const voiceMix = new Float32Array(outputSampleCount * 2);
const speaking = new Uint8Array(outputSampleCount);
let lastVoiceEndSample = 0;
const manifestCues = [];
for (const row of outputCueRows) {
  const {shot, cue, clip} = row;
  const startSample = cue.audioStartFrame * samplesPerFrame;
  const endSample = startSample + clip.samples.length;
  const shotLayout = shotLayoutById.get(shot.id);
  assert(shotLayout, `Missing retimed layout for ${shot.id}.`);
  const shotStartSample = shotLayout.newFrom * samplesPerFrame;
  const shotEndSample = (shotLayout.newFrom + shotLayout.newDuration) * samplesPerFrame;
  const fitsVisualBounds = startSample >= shotStartSample && endSample <= shotEndSample;
  assert(fitsVisualBounds, `Voice clip ${clip.id} exceeds its retimed visual shot bounds.`);
  assert(startSample >= 0 && endSample <= outputSampleCount, `Voice clip ${clip.id} exceeds the new soundtrack bounds.`);
  for (let index = 0; index < clip.samples.length; index++) {
    const fadeIn = Math.min(1, index / Math.max(1, Math.round(sampleRate * 0.008)));
    const fadeOut = Math.min(1, (clip.samples.length - 1 - index) / Math.max(1, Math.round(sampleRate * 0.008)));
    const value = clip.samples[index] * Math.max(0, Math.min(fadeIn, fadeOut));
    const target = (startSample + index) * 2;
    voiceMix[target] += value;
    voiceMix[target + 1] += value;
    speaking[startSample + index] = 1;
  }
  lastVoiceEndSample = Math.max(lastVoiceEndSample, endSample);
  manifestCues.push({
    id: clip.id,
    shotId: clip.shotId,
    cueIndex: clip.cueIndex,
    text: clip.text,
    audioFile: clip.audioFile,
    sha256: clip.sha256,
    sourceSampleRateHz: clip.sourceSampleRateHz,
    sourceChannels: clip.sourceChannels,
    sourceDurationSeconds: clip.sourceDurationSeconds,
    sourcePeak: clip.sourcePeak,
    normalizationGain: clip.normalizationGain,
    normalizedPeak: clip.normalizedPeak,
    audioStartFrame: cue.audioStartFrame,
    audioStartSample: startSample,
    audioEndSampleExclusive: endSample,
    captionStartFrame: shotLayout.newFrom + cue.from,
    captionEndFrame: shotLayout.newFrom + cue.from + cue.duration,
    fitsVisualBounds,
  });
}

const fadeSamples = Math.round(sampleRate * 0.3);
const fadeStartSample = outputSampleCount - fadeSamples;
assert(lastVoiceEndSample <= fadeStartSample, 'The final 300 ms fade would overlap narration instead of following it in the preserved tail.');
const rawMix = new Float32Array(outputSampleCount * 2);
let backgroundGain = 0.8;
const attackStep = (0.8 - 0.36) / Math.round(sampleRate * 0.1);
const releaseStep = (0.8 - 0.36) / Math.round(sampleRate * 0.3);
let rawCombinedPeak = 0;
let maxBackgroundGainApplied = 0;
let minBackgroundGainApplied = 0.8;
for (let sample = 0; sample < outputSampleCount; sample++) {
  if (speaking[sample]) backgroundGain = Math.max(0.36, backgroundGain - attackStep);
  else backgroundGain = Math.min(0.8, backgroundGain + releaseStep);
  maxBackgroundGainApplied = Math.max(maxBackgroundGainApplied, backgroundGain);
  minBackgroundGainApplied = Math.min(minBackgroundGainApplied, backgroundGain);
  const fadeGain = sample < fadeStartSample
    ? 1
    : Math.max(0, (outputSampleCount - 1 - sample) / Math.max(1, fadeSamples - 1));
  const offset = sample * 2;
  const left = (background[offset] * backgroundGain + voiceMix[offset]) * fadeGain;
  const right = (background[offset + 1] * backgroundGain + voiceMix[offset + 1]) * fadeGain;
  assert(Number.isFinite(left) && Number.isFinite(right), `Non-finite mixed audio sample at ${sample}.`);
  rawMix[offset] = left;
  rawMix[offset + 1] = right;
  rawCombinedPeak = Math.max(rawCombinedPeak, Math.abs(left), Math.abs(right));
}

const combinedScale = rawCombinedPeak >= 0.95 ? 0.9 / rawCombinedPeak : 1;
const scaledMix = new Float32Array(rawMix.length);
for (let index = 0; index < rawMix.length; index++) scaledMix[index] = rawMix[index] * combinedScale;
const {wav, pcmPeak} = encodeWav(scaledMix);
assert(pcmPeak < 0.95, `Final PCM peak ${pcmPeak.toFixed(5)} must remain below 0.95.`);

const captionCues = outputCueRows.map(({shot, cue}) => ({
  ...cue,
  from: shotLayoutById.get(shot.id).newFrom + cue.from,
}));
for (let index = 0; index < captionCues.length; index++) {
  const cue = captionCues[index];
  assert(cue.from >= 0 && cue.from + cue.duration <= newCursor, `Caption cue ${index + 1} exceeds the retimed timeline.`);
  if (index > 0) assert(cue.from >= captionCues[index - 1].from + captionCues[index - 1].duration, 'Retimed caption cues overlap.');
}
const srt = captionCues.map((cue, index) =>
  `${index + 1}\n${formatTimestamp(cue.from, ',')} --> ${formatTimestamp(cue.from + cue.duration, ',')}\n${cue.text}\n`).join('\n');
const vtt = `WEBVTT\n\n${captionCues.map((cue) =>
  `${formatTimestamp(cue.from, '.')} --> ${formatTimestamp(cue.from + cue.duration, '.')}\n${cue.text}\n`).join('\n')}`;

const encodedTimeline = `${JSON.stringify(voicedTimeline, null, 2)}\n`;
const sourceTimelineHash = sha256(sourceTimelinePath);
const planHash = sha256(planPath);
const voiceManifestHash = sha256(voiceManifestPath);
const atmosphereHash = sha256(atmospherePath);
const atmosphereManifestHash = sha256(atmosphereManifestPath);
fs.mkdirSync(path.dirname(voicedTimelinePath), {recursive: true});
fs.mkdirSync(path.dirname(outputWavPath), {recursive: true});
fs.mkdirSync(path.dirname(subtitleBase), {recursive: true});
fs.writeFileSync(voicedTimelinePath, encodedTimeline, 'utf8');
fs.writeFileSync(outputWavPath, wav);
fs.writeFileSync(`${subtitleBase}.srt`, srt, 'utf8');
fs.writeFileSync(`${subtitleBase}.vtt`, vtt, 'utf8');

const manifest = {
  edition: voicedTimeline.edition,
  provider: voiceManifest.provider,
  voice: voiceManifest.voice,
  model: voiceManifest.model,
  expectedModel: plan.expectedModel,
  rate: plan.rate,
  sourceTimeline: {
    path: path.relative(root, sourceTimelinePath),
    sha256: sourceTimelineHash,
    edition: sourceTimeline.edition,
    durationFrames: sourceTimeline.durationInFrames,
    durationSeconds: sourceTimeline.durationInFrames / fps,
    fps,
  },
  voicePlan: {path: path.relative(root, planPath), sha256: planHash},
  voiceManifest: {path: path.relative(root, voiceManifestPath), sha256: voiceManifestHash},
  original90SecondSource: {
    path: path.relative(root, atmospherePath),
    version: sourceTimeline.edition,
    sha256: atmosphereHash,
    manifestPath: path.relative(root, atmosphereManifestPath),
    manifestSha256: atmosphereManifestHash,
    manifest: atmosphereManifest,
    retiming: 'copy each original shot segment at its new shot start; if extended, copy the first 90% exactly and linearly interpolate the final 10% across the added tail',
  },
  output: {
    wavPath: path.relative(root, outputWavPath),
    timelinePath: path.relative(root, voicedTimelinePath),
    srtPath: path.relative(root, `${subtitleBase}.srt`),
    vttPath: path.relative(root, `${subtitleBase}.vtt`),
    sampleRateHz: sampleRate,
    channels: 2,
    bitDepth: outputBitDepth,
    codec: 'pcm_s16le',
    durationFrames: newCursor,
    durationSeconds: newCursor / fps,
    sampleCountPerChannel: outputSampleCount,
    wavSha256: createHash('sha256').update(wav).digest('hex'),
    timelineSha256: createHash('sha256').update(encodedTimeline).digest('hex'),
    srtSha256: createHash('sha256').update(srt).digest('hex'),
    vttSha256: createHash('sha256').update(vtt).digest('hex'),
  },
  mix: {
    voiceNormalizationTargetPeak: 0.6,
    voiceFadeMilliseconds: 8,
    backgroundIdleGain: 0.8,
    backgroundSpeechGain: 0.36,
    duckAttackMilliseconds: 100,
    duckReleaseMilliseconds: 300,
    duckAttackCurve: 'linear',
    duckReleaseCurve: 'linear',
    backgroundGainRangeApplied: {minimum: minBackgroundGainApplied, maximum: maxBackgroundGainApplied},
    finalFadeMilliseconds: 300,
    finalFadeStartsAfterLastVoice: true,
    rawCombinedPeak: rawCombinedPeak,
    combinedScale,
    pcmPeak: pcmPeak,
    pcmPeakDbfs: 20 * Math.log10(pcmPeak),
  },
  fitsVisualBounds: manifestCues.every((cue) => cue.fitsVisualBounds),
  shots: shotLayouts,
  cues: manifestCues,
};
fs.writeFileSync(outputManifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

console.log(`Prepared ${manifest.cues.length} narration cues: ${manifest.output.durationSeconds.toFixed(2)}s, peak ${manifest.mix.pcmPeak.toFixed(4)}, scale ${manifest.mix.combinedScale.toFixed(5)}.`);
