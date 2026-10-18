import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const timelinePath = path.resolve(root, 'src/madman/full-v4-timeline.json');
const providerPath = path.resolve(root, 'public/madman/voice-v2/manifest.json');
const historyManifestPath = path.resolve(root, 'public/madman/audio/history-study-v3-manifest.json');
const ffmpegPath = '/opt/homebrew/bin/ffmpeg';
const ffprobePath = '/opt/homebrew/bin/ffprobe';
const wavPath = path.resolve(root, 'public/madman/audio/full-v4.wav');
const outputManifestPath = path.resolve(root, 'public/madman/audio/full-v4-manifest.json');
const subtitleBase = path.resolve(root, 'out/madman/狂人日记-节奏意象加强版-v4');
const rate = 48_000;
const fps = 24;
const samplesPerFrame = rate / fps;
const channels = 2;
const totalFrames = 1_896;
const totalSamplesPerChannel = totalFrames * samplesPerFrame;
const finalSilenceFromFrame = 1_824;
const historyId = 'history';

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function sha256(data) {
  return createHash('sha256').update(data).digest('hex');
}

function hashFile(file) {
  return sha256(fs.readFileSync(file));
}

function smooth(value) {
  const x = Math.max(0, Math.min(1, value));
  return x * x * (3 - 2 * x);
}

function decodeMonoFloat(file) {
  const pcm = execFileSync(ffmpegPath, [
    '-v', 'error', '-i', file,
    '-map', '0:a:0', '-vn', '-sn', '-dn',
    '-ac', '1', '-ar', String(rate), '-acodec', 'pcm_f32le', '-f', 'f32le', 'pipe:1',
  ], {maxBuffer: 32 * 1024 * 1024});
  assert.equal(pcm.length % 4, 0, `Decoded audio has a partial float sample: ${file}`);
  assert.equal(pcm.byteOffset % 4, 0, `Decoded audio is not sample aligned: ${file}`);
  const samples = new Float32Array(pcm.buffer, pcm.byteOffset, pcm.length / 4);
  assert(samples.length > 0, `Decoded audio is empty: ${file}`);
  for (const sample of samples) assert(Number.isFinite(sample), `Decoded audio has a non-finite sample: ${file}`);
  return samples;
}

function probeWav(file) {
  const parsed = JSON.parse(execFileSync(ffprobePath, [
    '-v', 'error', '-select_streams', 'a:0',
    '-show_entries', 'stream=codec_name,sample_rate,channels,bits_per_sample,duration',
    '-show_entries', 'format=format_name,duration', '-of', 'json', file,
  ], {encoding: 'utf8', maxBuffer: 128 * 1024}));
  const stream = parsed.streams?.[0];
  assert(stream, `No audio stream in ${file}`);
  return {
    codec: stream.codec_name,
    sampleRateHz: Number(stream.sample_rate),
    channels: Number(stream.channels),
    bitDepth: Number(stream.bits_per_sample),
    durationSeconds: Number(stream.duration ?? parsed.format?.duration),
    format: parsed.format?.format_name,
  };
}

function readPcm16Wav(file) {
  const buffer = fs.readFileSync(file);
  assert.equal(buffer.toString('ascii', 0, 4), 'RIFF', `${file} must be RIFF.`);
  assert.equal(buffer.toString('ascii', 8, 12), 'WAVE', `${file} must be WAVE.`);
  assert.equal(buffer.readUInt32LE(4) + 8, buffer.length, `${file} has an invalid RIFF size.`);
  let offset = 12;
  let format = null;
  let data = null;
  while (offset + 8 <= buffer.length) {
    const id = buffer.toString('ascii', offset, offset + 4);
    const size = buffer.readUInt32LE(offset + 4);
    const body = offset + 8;
    assert(body + size <= buffer.length, `${file} has a truncated ${id} chunk.`);
    if (id === 'fmt ') {
      assert(size >= 16, `${file} has an incomplete fmt chunk.`);
      format = {
        encoding: buffer.readUInt16LE(body),
        channels: buffer.readUInt16LE(body + 2),
        sampleRateHz: buffer.readUInt32LE(body + 4),
        byteRate: buffer.readUInt32LE(body + 8),
        blockAlign: buffer.readUInt16LE(body + 12),
        bitDepth: buffer.readUInt16LE(body + 14),
      };
    } else if (id === 'data') {
      data = {offset: body, length: size, bytes: buffer.subarray(body, body + size)};
    }
    offset = body + size + (size % 2);
  }
  assert(format && data, `${file} is missing a fmt or data chunk.`);
  assert.equal(format.encoding, 1, `${file} must use integer PCM.`);
  assert.equal(format.channels, channels, `${file} must be stereo.`);
  assert.equal(format.sampleRateHz, rate, `${file} must be 48 kHz.`);
  assert.equal(format.bitDepth, 16, `${file} must use 16-bit PCM.`);
  assert.equal(format.blockAlign, channels * 2, `${file} has unexpected PCM block alignment.`);
  assert.equal(data.length % format.blockAlign, 0, `${file} ends in a partial PCM frame.`);
  return {buffer, format, data};
}

function makeWav(pcmBytes) {
  assert.equal(pcmBytes.length, totalSamplesPerChannel * channels * 2);
  const wav = Buffer.alloc(44 + pcmBytes.length);
  wav.write('RIFF', 0, 'ascii');
  wav.writeUInt32LE(wav.length - 8, 4);
  wav.write('WAVEfmt ', 8, 'ascii');
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(channels, 22);
  wav.writeUInt32LE(rate, 24);
  wav.writeUInt32LE(rate * channels * 2, 28);
  wav.writeUInt16LE(channels * 2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write('data', 36, 'ascii');
  wav.writeUInt32LE(pcmBytes.length, 40);
  pcmBytes.copy(wav, 44);
  return wav;
}

function timestamp(frame, separator) {
  const millis = Math.round(frame * 1_000 / fps);
  const hours = Math.floor(millis / 3_600_000);
  const minutes = Math.floor(millis / 60_000) % 60;
  const seconds = Math.floor(millis / 1_000) % 60;
  const remainder = millis % 1_000;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}${separator}${String(remainder).padStart(3, '0')}`;
}

assert(fs.existsSync(ffmpegPath), `Missing configured ffmpeg: ${ffmpegPath}`);
assert(fs.existsSync(ffprobePath), `Missing configured ffprobe: ${ffprobePath}`);

const spec = readJson(timelinePath);
const sourceTimelinePath = path.resolve(root, spec.sourceTimeline);
const sourceTimeline = readJson(sourceTimelinePath);
const provider = readJson(providerPath);
const historyManifest = readJson(historyManifestPath);
const historySpecPath = path.resolve(root, spec.historySpec);
const historySpec = readJson(historySpecPath);
assert.equal(spec.fps, fps);
assert.equal(spec.width, 1_920);
assert.equal(spec.height, 1_080);
assert.equal(spec.durationInFrames, totalFrames);
assert.equal(spec.durationInFrames / fps, 79);
assert.equal(spec.audioFile, 'madman/audio/full-v4.wav');
assert.equal(spec.shots.length, 8);
assert.equal(sourceTimeline.fps, fps);
assert.equal(sourceTimeline.shots.length, spec.shots.length);
assert.equal(provider.provider, 'Bailian');
assert.equal(provider.model, 'cosyvoice-v3-flash');
assert.equal(provider.voice, 'longsanshu_v3');
assert.equal(provider.sampleRate, 24_000);
assert.equal(provider.format, 'wav');
assert.equal(provider.cues.length, 11);
for (const entry of provider.cues) {
  assert.equal(entry.sampleRate, 24_000, `Unexpected source sample rate for ${entry.id}.`);
  assert.equal(entry.channels, 1, `Cached voice source must be mono: ${entry.id}.`);
}
assert.equal(historyManifest.durationSeconds, 20);
assert.equal(historyManifest.durationFrames, 480);
assert.equal(historyManifest.sampleRateHz, rate);
assert.equal(historyManifest.channels, channels);
assert.equal(historyManifest.bitDepth, 16);
assert.equal(historyManifest.cloudCalls, 0);
assert.equal(historySpec.fps, fps);
assert.equal(historySpec.durationInFrames, 480);

let sourceCursor = 0;
for (const sourceShot of sourceTimeline.shots) {
  assert.equal(sourceShot.from, sourceCursor, `Source timeline gap/overlap before ${sourceShot.id}.`);
  assert(Number.isInteger(sourceShot.duration) && sourceShot.duration > 0);
  sourceCursor += sourceShot.duration;
}
assert.equal(sourceCursor, sourceTimeline.durationInFrames, 'Source timeline shots do not cover its declared duration.');

let cursor = 0;
let cueCount = 0;
const voiceRows = [];
const sourceCuesInOrder = [];
const shotById = new Map();
for (const [shotIndex, shot] of spec.shots.entries()) {
  const sourceShot = sourceTimeline.shots[shotIndex];
  assert(sourceShot, `Missing source shot ${shot.id}.`);
  assert.equal(shot.id, sourceShot.id, `Source shot id changed at position ${shotIndex}.`);
  assert.equal(shot.section, sourceShot.section, `Source section changed in ${shot.id}.`);
  assert.equal(shot.asset, sourceShot.asset, `Source asset changed in ${shot.id}.`);
  assert.equal(shot.from, cursor, `V4 shot gap or overlap before ${shot.id}.`);
  assert(Number.isInteger(shot.duration) && shot.duration > 0, `Invalid duration in ${shot.id}.`);
  assert.equal(shot.cues.length, (sourceShot.cues ?? []).length, `Cue count changed in ${shot.id}.`);
  for (const [cueIndex, cue] of shot.cues.entries()) {
    const sourceCue = sourceShot.cues[cueIndex];
    assert.equal(cue.text, sourceCue.text, `Source cue text changed in ${shot.id} at ${cueIndex}.`);
    assert(Number.isInteger(cue.from) && Number.isInteger(cue.duration));
    assert(cue.from >= 0 && cue.duration > 0 && cue.from + cue.duration <= shot.duration,
      `Cue is outside the ${shot.id} shot.`);
    sourceCuesInOrder.push(cue.text);
    if (shot.id !== historyId) {
      cueCount++;
      voiceRows.push({shot, cue, cueIndex});
    }
  }
  shotById.set(shot.id, shot);
  cursor += shot.duration;
}
assert.equal(cursor, totalFrames, 'V4 shot durations do not cover 79 seconds.');
assert.equal(cueCount, 8, 'Expected eight separately decoded voice clips outside the reused history mix.');

const historyShot = shotById.get(historyId);
assert(historyShot, 'Missing history shot.');
assert.equal(historyShot.duration, 480, 'History shot must remain exactly 20 seconds.');
assert.equal(historyShot.reuseMixedAudio, historyManifest.layers['history-study-v3'].file);
assert.equal(historyManifest.narration.length, historyShot.cues.length);
assert.equal(historyShot.cues.length, 3);
const historySourceShot = historyTimelineShot(historySpec, sourceTimeline);
assert(historySourceShot, 'Could not map the history source shot.');
assert.equal(historySpec.cues.length, historyManifest.narration.length);
for (const [index, sourceCue] of historySpec.cues.entries()) {
  const timelineCue = historyShot.cues[index];
  const record = historyManifest.narration[index];
  const historySourceCue = historySourceShot.cues[index];
  assert.equal(record.text, sourceCue.text);
  assert.equal(record.text, timelineCue.text);
  assert.equal(historySourceCue.text, sourceCue.text);
  assert.equal(record.fromFrame, sourceCue.from);
  assert.equal(timelineCue.from, record.fromFrame, 'V4 history cue must follow the reused audio exactly.');
  assert.equal(timelineCue.peakTarget, record.peakTarget, 'Reused history levels must remain unchanged.');
  assert.equal(record.sha256, hashFile(path.resolve(root, record.file)));
  const providerCue = provider.cues.find((entry) => entry.id === record.id);
  assert(providerCue, `Missing provider manifest cue ${record.id}.`);
  assert.equal(providerCue.text, record.text);
  assert.equal(providerCue.sha256, record.sha256);
  assert.equal(record.insertedSilenceSeconds, sourceCue.pauseInsert?.durationSeconds ?? 0);
}

const historyFile = path.resolve(root, historyManifest.layers['history-study-v3'].file);
assert.equal(hashFile(historyFile), historyManifest.layers['history-study-v3'].sha256,
  'Approved history waveform SHA256 differs from its manifest.');
const historyProbe = probeWav(historyFile);
assert.equal(historyProbe.codec, 'pcm_s16le');
assert.equal(historyProbe.sampleRateHz, rate);
assert.equal(historyProbe.channels, channels);
assert.equal(historyProbe.bitDepth, 16);
assert.equal(historyProbe.durationSeconds, 20);
const historyWav = readPcm16Wav(historyFile);
assert.equal(historyWav.data.length, 20 * rate * channels * 2);
assert.equal(historyWav.data.length / (channels * 2), 960_000);

const seenProviderIds = new Set();
const voiceMix = new Float32Array(totalSamplesPerChannel * channels);
const speaking = new Uint8Array(totalFrames);
const voiceRecords = [];
for (const {shot, cue, cueIndex} of voiceRows) {
  const entry = provider.cues.find((candidate) => candidate.shotId === shot.id && candidate.cueIndex === cueIndex);
  assert(entry, `Missing provider cue for ${shot.id}:${cueIndex}.`);
  assert(!seenProviderIds.has(entry.id), `Duplicate provider cue mapping: ${entry.id}.`);
  seenProviderIds.add(entry.id);
  assert.equal(entry.text, cue.text, `Provider source text differs for ${entry.id}.`);
  assert.equal(entry.path, cue.audioFile, `Provider audio path differs for ${entry.id}.`);
  assert.equal(entry.model, 'cosyvoice-v3-flash');
  assert.equal(entry.voice, 'longsanshu_v3');
  assert.equal(entry.modelReportedByCli, true, `Model reporting flag missing for ${entry.id}.`);
  assert.equal(entry.voiceReportedByCli, true, `Voice reporting flag missing for ${entry.id}.`);
  const file = path.resolve(root, cue.audioFile);
  assert(file.startsWith(`${path.resolve(root, 'public/madman/voice-v2')}${path.sep}`), 'Voice clip path escaped its cache folder.');
  assert.equal(hashFile(file), entry.sha256, `Cached voice hash changed for ${entry.id}.`);
  const samples = decodeMonoFloat(file);
  let sourcePeak = 0;
  for (const sample of samples) sourcePeak = Math.max(sourcePeak, Math.abs(sample));
  assert(sourcePeak > 0, `Cached voice clip is silent: ${entry.id}.`);
  const gain = cue.peakTarget / sourcePeak;
  const startFrame = shot.from + cue.from;
  const startSample = startFrame * samplesPerFrame;
  const endSample = startSample + samples.length;
  const captionEndFrame = shot.from + cue.from + cue.duration;
  const captionEndSample = captionEndFrame * samplesPerFrame;
  const shotEndSample = (shot.from + shot.duration) * samplesPerFrame;
  assert(Number.isInteger(startSample) && endSample <= captionEndSample,
    `Whole source clip ${entry.id} does not fit its caption cue.`);
  assert(endSample <= shotEndSample && endSample <= totalSamplesPerChannel,
    `Whole source clip ${entry.id} crosses the scene end.`);
  const captionMarginFrames = (captionEndSample - endSample) / samplesPerFrame;
  const sixFrameMarginPossible = samples.length + 6 * samplesPerFrame <= cue.duration * samplesPerFrame;
  if (sixFrameMarginPossible) assert(captionMarginFrames >= 6 - 1e-9,
    `Voice clip ${entry.id} lost its available six-frame caption margin.`);
  const fadeSamples = Math.round(rate * 0.008);
  for (let index = 0; index < samples.length; index++) {
    const fadeIn = smooth(index / fadeSamples);
    const fadeOut = smooth((samples.length - 1 - index) / fadeSamples);
    const value = samples[index] * gain * Math.min(fadeIn, fadeOut);
    const target = (startSample + index) * channels;
    voiceMix[target] += value;
    voiceMix[target + 1] += value;
  }
  const firstFrame = Math.floor(startSample / samplesPerFrame);
  const lastFrameExclusive = Math.ceil(endSample / samplesPerFrame);
  speaking.fill(1, firstFrame, lastFrameExclusive);
  voiceRecords.push({
    id: entry.id,
    shotId: shot.id,
    cueIndex,
    text: cue.text,
    file: cue.audioFile,
    sha256: entry.sha256,
    sourceSampleRateHz: entry.sampleRate,
    sourceChannels: entry.channels,
    decodedSampleRateHz: rate,
    decodedSamples: samples.length,
    sourceDurationSeconds: samples.length / rate,
    sourcePeak,
    gain,
    peakTarget: cue.peakTarget,
    normalizedClipPeak: sourcePeak * gain,
    fromFrame: startFrame,
    startSample,
    endSampleExclusive: endSample,
    captionStartFrame: shot.from + cue.from,
    captionEndFrame,
    captionMarginFrames,
    sixFrameMarginPossible,
    sceneEndFrame: shot.from + shot.duration,
    fadeMilliseconds: 8,
    model: entry.model,
    modelReportedByCli: entry.modelReportedByCli,
    voice: entry.voice,
    voiceReportedByCli: entry.voiceReportedByCli,
  });
}
assert.equal(seenProviderIds.size + historyManifest.narration.length, provider.cues.length,
  'Every provider manifest clip must be accounted for exactly once.');
for (const historyRecord of historyManifest.narration) {
  const providerEntry = provider.cues.find((entry) => entry.id === historyRecord.id);
  assert(providerEntry, `Missing provider record for reused history voice ${historyRecord.id}.`);
  assert.equal(providerEntry.model, 'cosyvoice-v3-flash');
  assert.equal(providerEntry.voice, 'longsanshu_v3');
  assert.equal(providerEntry.modelReportedByCli, true);
  assert.equal(providerEntry.voiceReportedByCli, true);
  assert.equal(providerEntry.sha256, historyRecord.sha256);
  assert.equal(providerEntry.text, historyRecord.text);
}

const historyStartFrame = historyShot.from;
const historyEndFrame = historyShot.from + historyShot.duration;
const historyVoiceRecords = historyManifest.narration.map((record) => ({
  ...record,
  shotId: historyId,
  reusedFrom: historyFile === path.resolve(root, record.file) ? record.file : historyFile,
  reusedMix: historyManifest.layers['history-study-v3'].file,
  embeddedInReusedMix: true,
  sourceFromFrame: record.fromFrame,
  sourceMixedEndSeconds: record.mixedEndSeconds,
  fromFrame: historyStartFrame + record.fromFrame,
  startSample: (historyStartFrame + record.fromFrame) * samplesPerFrame,
  mixedEndSeconds: historyStartFrame / fps + record.mixedEndSeconds,
  mixedEndFrame: historyStartFrame + record.mixedEndSeconds * fps,
  silenceInsertApplied: record.insertedSilenceSeconds,
  modelReportedByCli: true,
  voiceReportedByCli: true,
}));
assert(historyVoiceRecords.some((record) => record.id === 'history-3' && record.silenceInsertApplied === 0.45),
  'The approved history-3 silence insertion was not represented.');

const sortedVoiceRecords = [...voiceRecords, ...historyVoiceRecords].sort((a, b) => a.startSample - b.startSample);
let previousVoiceEnd = 0;
for (const record of sortedVoiceRecords) {
  const endSample = record.endSampleExclusive ?? Math.round(record.mixedEndSeconds * rate);
  assert(record.startSample >= previousVoiceEnd, `Voice records overlap before ${record.id}.`);
  previousVoiceEnd = endSample;
}
assert.equal(sortedVoiceRecords.length, 11, 'Expected all eleven original cached speech clips.');

// Synthesize only the decided local wind/room texture and the single 48 Hz watch-entry knock.
const bed = new Float32Array(totalSamplesPerChannel * channels);
let randomState = spec.sound.seed >>> 0;
const noise = () => {
  randomState = (Math.imul(randomState, 1_664_525) + 1_013_904_223) >>> 0;
  return randomState / 4_294_967_296 * 2 - 1;
};
let lowLeft = 0;
let lowRight = 0;
const titleShot = shotById.get('title');
const moonShot = shotById.get('moon');
const watchShot = shotById.get('watch');
const questionShot = shotById.get('question');
const complicityShot = shotById.get('complicity');
const childrenShot = shotById.get('children');
const pleaShot = shotById.get('plea');
assert.equal(spec.sound.finalBedFadeFromFrame, 1_788);
assert.equal(spec.sound.finalSilenceFromFrame, finalSilenceFromFrame);
const watchKnockStart = watchShot.from / fps + 0.025;
const historyStartSeconds = historyStartFrame / fps;
const historyEndSeconds = historyEndFrame / fps;
const questionStartSeconds = questionShot.from / fps;
const questionEndSeconds = (questionShot.from + questionShot.duration) / fps;
const historyStartSample = historyStartFrame * samplesPerFrame;
const historyEndSample = historyEndFrame * samplesPerFrame;
let bedPeak = 0;
let windPeak = 0;
let knockPeak = 0;
let duckedBedPeak = 0;

function segmentGain(time, shot, amount) {
  const shotStart = shot.from / fps;
  const progress = (time - shotStart) / (shot.duration / fps);
  return amount(progress);
}

for (let frame = 0; frame < totalFrames; frame++) {
  const time = frame / fps;
  const inHistory = frame >= historyStartFrame && frame < historyEndFrame;
  let amount = 0;
  let stereo = 'mild';
  if (time < historyStartSeconds) {
    if (time < titleShot.duration / fps) {
      amount = 0.035;
    } else if (time < watchShot.from / fps) {
      amount = 0.07;
    } else {
      amount = segmentGain(time, watchShot, (progress) => 0.065 + 0.035 * smooth(progress));
    }
    if (time > historyStartSeconds - 0.3) amount *= smooth((historyStartSeconds - time) / 0.3);
  } else if (!inHistory && time < questionEndSeconds) {
    // Fade the question bed to exact zero during its first 0.6 seconds, then keep it silent for the shot.
    amount = 0.065 * (1 - smooth((time - questionStartSeconds) / 0.6));
    if (time < historyEndSeconds + 0.15) amount *= smooth((time - historyEndSeconds) / 0.15);
  } else if (time >= questionEndSeconds && time < childrenShot.from / fps) {
    amount = segmentGain(time, complicityShot, () => 0.035);
    stereo = 'narrow';
    if (time < questionEndSeconds + 0.4) amount *= smooth((time - questionEndSeconds) / 0.4);
  } else if (time >= childrenShot.from / fps && time < pleaShot.from / fps) {
    amount = segmentGain(time, childrenShot, () => 0.025);
    stereo = 'narrow';
  } else if (time >= pleaShot.from / fps && frame < spec.sound.finalSilenceFromFrame) {
    amount = 0.02;
    stereo = 'narrow';
  }
  if (frame >= spec.sound.finalBedFadeFromFrame && frame < finalSilenceFromFrame) {
    amount *= 1 - smooth((frame - spec.sound.finalBedFadeFromFrame) /
      (finalSilenceFromFrame - spec.sound.finalBedFadeFromFrame));
  }
  if (frame >= finalSilenceFromFrame || inHistory || (time >= questionStartSeconds + 0.6 && time < questionEndSeconds)) amount = 0;

  for (let offset = 0; offset < samplesPerFrame; offset++) {
    const sampleIndex = frame * samplesPerFrame + offset;
    const nLeft = noise();
    const nRight = noise();
    lowLeft = 0.985 * lowLeft + 0.015 * nLeft;
    lowRight = 0.985 * lowRight + 0.015 * nRight;
    const voiceDuck = speaking[frame] ? 0.5 : 1;
    const baseLeft = lowLeft * amount * voiceDuck;
    const baseRight = lowRight * amount * voiceDuck;
    let left = baseLeft;
    let right = baseRight;
    if (stereo === 'mild') {
      left *= 1.02;
      right *= 0.88;
    } else {
      const center = (baseLeft + baseRight) * 0.5;
      const side = (baseLeft - baseRight) * 0.035;
      left = center + side;
      right = center - side;
    }
    let knock = 0;
    const knockElapsed = sampleIndex / rate - watchKnockStart;
    if (knockElapsed >= 0 && knockElapsed < 0.65 && !inHistory && frame < finalSilenceFromFrame) {
      const attack = smooth(knockElapsed / 0.006);
      knock = 0.045 * Math.exp(-knockElapsed * 13) * attack * Math.sin(2 * Math.PI * 48 * knockElapsed);
      knock *= voiceDuck;
    }
    left += knock;
    right += knock;
    if (frame >= finalSilenceFromFrame || inHistory || (time >= questionStartSeconds + 0.6 && time < questionEndSeconds)) {
      left = 0;
      right = 0;
    }
    const target = sampleIndex * channels;
    bed[target] = left;
    bed[target + 1] = right;
    bedPeak = Math.max(bedPeak, Math.abs(left), Math.abs(right));
    windPeak = Math.max(windPeak, Math.abs(baseLeft), Math.abs(baseRight));
    knockPeak = Math.max(knockPeak, Math.abs(knock));
    if (voiceDuck === 0.5) duckedBedPeak = Math.max(duckedBedPeak, Math.abs(left), Math.abs(right));
  }
}
assert(windPeak <= 0.1 + 1e-12, `Wind source amplitude exceeded 0.10: ${windPeak}.`);
assert(knockPeak <= 0.045 + 1e-12, `Watch knock exceeded 0.045: ${knockPeak}.`);
assert.equal(bed.subarray(historyStartSample * channels, historyEndSample * channels).some((sample) => sample !== 0), false,
  'New background must not be mixed under the approved history segment.');

const finalFloat = new Float32Array(totalSamplesPerChannel * channels);
let floatPeak = 0;
for (let frame = 0; frame < totalSamplesPerChannel; frame++) {
  const sampleOffset = frame * channels;
  for (let channel = 0; channel < channels; channel++) {
    const index = sampleOffset + channel;
    const value = voiceMix[index] + bed[index];
    assert(Number.isFinite(value) && Math.abs(value) < 1, `Audio would clip at sample ${index}.`);
    finalFloat[index] = value;
    floatPeak = Math.max(floatPeak, Math.abs(value));
  }
}
const pcmBytes = Buffer.alloc(totalSamplesPerChannel * channels * 2);
let pcmPeak = 0;
for (let index = 0; index < finalFloat.length; index++) {
  const value = finalFloat[index];
  const pcm = Math.max(-32_768, Math.min(32_767, Math.round(value * 32_768)));
  pcmPeak = Math.max(pcmPeak, Math.abs(pcm / 32_768));
  pcmBytes.writeInt16LE(pcm, index * 2);
}
let wav = makeWav(pcmBytes);
const embeddedHistoryOffset = 44 + historyStartSample * channels * 2;
historyWav.data.bytes.copy(wav, embeddedHistoryOffset);
const embeddedHistoryPcm = wav.subarray(embeddedHistoryOffset, embeddedHistoryOffset + historyWav.data.length);
const sourceHistoryPcmSha256 = sha256(historyWav.data.bytes);
const embeddedHistoryPcmSha256 = sha256(embeddedHistoryPcm);
assert.equal(embeddedHistoryPcmSha256, sourceHistoryPcmSha256, 'Embedded history PCM is not byte-identical.');

const finalPcmPeak = (() => {
  let peak = 0;
  for (let offset = 44; offset < wav.length; offset += 2) peak = Math.max(peak, Math.abs(wav.readInt16LE(offset) / 32_768));
  return peak;
})();
assert(finalPcmPeak < 0.8, `Final PCM peak ${finalPcmPeak} must remain below 0.8.`);
const silenceByteStart = 44 + finalSilenceFromFrame * samplesPerFrame * channels * 2;
assert.equal(wav.subarray(silenceByteStart).some((byte) => byte !== 0), false,
  'The complete 76–79 second tail must be exact PCM zero.');
assert(previousVoiceEnd <= finalSilenceFromFrame * samplesPerFrame,
  'A voice record extends into the required final-silence region.');

const captionCues = spec.shots.flatMap((shot) => (shot.captions ?? shot.cues.map((cue) => ({
  from: cue.from,
  end: cue.from + cue.duration,
  text: cue.text,
}))).map((caption) => ({
  from: shot.from + caption.from,
  end: shot.from + caption.end,
  text: caption.text,
})));
assert.equal(captionCues.length, 12, 'Expected twelve source-faithful subtitle cues.');
for (const caption of captionCues) {
  assert(caption.from >= 0 && caption.end > caption.from && caption.end <= totalFrames,
    'Subtitle cue is outside the 79-second timeline.');
}
for (let index = 1; index < captionCues.length; index++) {
  assert(captionCues[index].from >= captionCues[index - 1].end, `Subtitle cues overlap at ${index + 1}.`);
}
assert.equal(captionCues.map((caption) => caption.text).join(''), sourceCuesInOrder.join(''),
  'Caption text concatenation must preserve the source cue sequence exactly.');
const expectedHistoryText = historyShot.cues.map((cue) => cue.text).join('');
assert.equal(historyShot.captions.map((caption) => caption.text).join(''), expectedHistoryText,
  'The split history captions must concatenate to the original history narration.');
const srt = captionCues.map((caption, index) =>
  `${index + 1}\n${timestamp(caption.from, ',')} --> ${timestamp(caption.end, ',')}\n${caption.text}\n`).join('\n');
const vtt = `WEBVTT\n\n${captionCues.map((caption) =>
  `${timestamp(caption.from, '.')} --> ${timestamp(caption.end, '.')}\n${caption.text}\n`).join('\n')}`;

const manifest = {
  edition: spec.edition,
  spec: {path: path.relative(root, timelinePath), sha256: hashFile(timelinePath)},
  sourceTimeline: {
    path: spec.sourceTimeline,
    sha256: hashFile(sourceTimelinePath),
    edition: sourceTimeline.edition,
    durationFrames: sourceTimeline.durationInFrames,
    shots: sourceTimeline.shots.length,
  },
  provider: {
    manifestPath: path.relative(root, providerPath),
    manifestSha256: hashFile(providerPath),
    name: provider.provider,
    model: provider.model,
    voice: provider.voice,
    reportedByCli: {model: true, voice: true},
    sourceCueCount: provider.cues.length,
  },
  output: {
    wavPath: path.relative(root, wavPath),
    wavSha256: sha256(wav),
    sampleRateHz: rate,
    channels,
    bitDepth: 16,
    codec: 'pcm_s16le',
    fps,
    durationFrames: totalFrames,
    durationSeconds: totalFrames / fps,
    sampleCountPerChannel: totalSamplesPerChannel,
    floatPeak,
    pcmPeak: finalPcmPeak,
    pcmPeakDbfs: 20 * Math.log10(finalPcmPeak),
    finalSilence: {
      fromFrame: finalSilenceFromFrame,
      fromSeconds: finalSilenceFromFrame / fps,
      toFrame: totalFrames,
      toSeconds: totalFrames / fps,
      pcmPeak: 0,
    },
  },
  mix: {
    sourceVoiceCount: provider.cues.length,
    separatelyDecodedVoiceCount: voiceRecords.length,
    reusedHistoryVoiceCount: historyVoiceRecords.length,
    voicePeakTargetsApplied: true,
    voiceFadeMilliseconds: 8,
    voiceRateOrPitchChanged: false,
    wind: {
      kind: 'fixed-seed low-level local filtered wind/room texture',
      seed: spec.sound.seed,
      filter: 'one-pole low-pass coefficient 0.985',
      targetAmplitude: 0.1,
      measuredPeak: windPeak,
      duckDuringVoice: 0.5,
      measuredDuckedBedPeak: duckedBedPeak,
      moonStereo: 'mild left/right level difference',
      watch: 'gently rises to target amplitude',
      complicity: 'centered and quiet',
      children: 'centered and quieter',
      question: {fadeFromFrame: questionShot.from, fadeToSeconds: questionStartSeconds + 0.6, silentThroughFrame: questionShot.from + questionShot.duration},
      historyBoundaryFadeSeconds: 0.3,
      finalFade: {fromFrame: spec.sound.finalBedFadeFromFrame, toFrame: finalSilenceFromFrame},
    },
    watchKnock: {
      frequencyHz: 48,
      startSeconds: watchKnockStart,
      gainLimit: 0.045,
      measuredPeak: knockPeak,
      decay: 'exponential, 13 per second, 0.65 second maximum duration',
    },
  },
  historyReuse: {
    sourcePath: historyManifest.layers['history-study-v3'].file,
    sourceManifestPath: path.relative(root, historyManifestPath),
    sourceManifestSha256: hashFile(historyManifestPath),
    sourceWavSha256: historyManifest.layers['history-study-v3'].sha256,
    sourcePcmSha256: sourceHistoryPcmSha256,
    embeddedPcmSha256: embeddedHistoryPcmSha256,
    pcmByteIdentical: sourceHistoryPcmSha256 === embeddedHistoryPcmSha256,
    fromFrame: historyStartFrame,
    toFrame: historyEndFrame,
    durationSeconds: historyProbe.durationSeconds,
    sampleRateHz: historyProbe.sampleRateHz,
    channels: historyProbe.channels,
    bitDepth: historyProbe.bitDepth,
    voiceRecords: historyVoiceRecords,
    narration: historyManifest.narration,
    sourceTimelineShot: historySourceShot.id,
  },
  narration: sortedVoiceRecords,
  subtitles: {
    srtPath: path.relative(root, `${subtitleBase}.srt`),
    vttPath: path.relative(root, `${subtitleBase}.vtt`),
    cueCount: captionCues.length,
    sourceTextPreserved: true,
    srtSha256: sha256(srt),
    vttSha256: sha256(vtt),
  },
  cloudCalls: 0,
  humanListeningReview: false,
};

fs.mkdirSync(path.dirname(wavPath), {recursive: true});
fs.mkdirSync(path.dirname(subtitleBase), {recursive: true});
fs.writeFileSync(wavPath, wav);
fs.writeFileSync(`${subtitleBase}.srt`, srt, 'utf8');
fs.writeFileSync(`${subtitleBase}.vtt`, vtt, 'utf8');
fs.writeFileSync(outputManifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

console.log(`Prepared 79s v4 mix: ${sortedVoiceRecords.length} voice clips, ${captionCues.length} subtitles, peak ${finalPcmPeak.toFixed(4)}, exact history PCM, 3s silence.`);

function historyTimelineShot(history, source) {
  const historySource = source.shots.find((shot) => shot.id === history.shotId);
  return historySource ?? source.shots.find((shot) => shot.id === 'history') ?? history.shot;
}
