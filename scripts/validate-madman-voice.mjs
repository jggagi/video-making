import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const outputDir = path.resolve(root, 'out/madman');
const timelinePath = path.resolve(root, 'src/madman/voiced-timeline.json');
const originalTimelinePath = path.resolve(root, 'src/madman/timeline.json');
const mixManifestPath = path.resolve(root, 'public/madman/audio/voiced-v2-manifest.json');
const mixWavPath = path.resolve(root, 'public/madman/audio/voiced-v2.wav');
const voiceManifestPath = path.resolve(root, 'public/madman/voice-v2/manifest.json');
const atmospherePath = path.resolve(root, 'public/madman/audio/atmosphere.wav');
const videoPath = path.join(outputDir, '狂人日记-男声配音版-v2-1080p.mp4');
const reportPath = path.join(outputDir, 'validation-voice-v2.json');
const ffmpeg = process.env.FFMPEG_EXECUTABLE ?? '/opt/homebrew/bin/ffmpeg';
const ffprobe = process.env.FFPROBE_EXECUTABLE ?? '/opt/homebrew/bin/ffprobe';
const fps = 24;
const sampleRate = 48_000;
const samplesPerFrame = sampleRate / fps;
const expectedShotCount = 8;
const expectedCueCount = 11;

function run(binary, args, maxBuffer = 32 * 1024 * 1024) {
  const result = spawnSync(binary, args, {encoding: 'utf8', maxBuffer});
  if (result.error) throw result.error;
  assert.equal(result.status, 0, `${path.basename(binary)} failed: ${result.stderr ?? ''}`);
  return result;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function sha256File(file) {
  return createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function sha256Text(text) {
  return createHash('sha256').update(text).digest('hex');
}

function probeMedia(file) {
  return JSON.parse(run(ffprobe, ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', file]).stdout);
}

function audioStats(file) {
  const text = run(ffmpeg, [
    '-hide_banner', '-nostats', '-i', file,
    '-vn', '-af', 'astats=metadata=0:reset=0', '-f', 'null', '-',
  ]).stderr;
  const peakValues = [...text.matchAll(/Peak level dB:\s*(-?(?:\d+(?:\.\d+)?|inf))/gi)].map((match) => Number(match[1]));
  const rmsValues = [...text.matchAll(/RMS level dB:\s*(-?(?:\d+(?:\.\d+)?|inf))/gi)].map((match) => Number(match[1]));
  const peakDbfs = Math.max(...peakValues);
  const rmsDbfs = rmsValues.at(-1);
  assert(Number.isFinite(peakDbfs), `Could not measure peak level in ${path.basename(file)}.`);
  assert(Number.isFinite(rmsDbfs), `Could not measure RMS level in ${path.basename(file)}.`);
  return {peakDbfs, rmsDbfs};
}

function hasFastStartAtoms(bytes) {
  const atoms = [];
  for (let offset = 0; offset + 8 <= bytes.length;) {
    let size = bytes.readUInt32BE(offset);
    const type = bytes.toString('ascii', offset + 4, offset + 8);
    if (size === 1) {
      assert(offset + 16 <= bytes.length, 'Truncated extended MP4 atom header.');
      const extendedSize = bytes.readBigUInt64BE(offset + 8);
      assert(extendedSize <= BigInt(Number.MAX_SAFE_INTEGER), 'MP4 atom is too large to inspect safely.');
      size = Number(extendedSize);
    } else if (size === 0) {
      size = bytes.length - offset;
    }
    assert(size >= 8 && offset + size <= bytes.length, 'Invalid MP4 atom bounds.');
    atoms.push({type, offset, size});
    offset += size;
  }
  const moov = atoms.find((atom) => atom.type === 'moov');
  const mdat = atoms.find((atom) => atom.type === 'mdat');
  return Boolean(moov && mdat && moov.offset < mdat.offset);
}

function extractFrame(frame, name) {
  assert(Number.isInteger(frame) && frame >= 0 && frame < timeline.durationInFrames, `Invalid still frame ${frame}.`);
  const file = path.join(outputDir, `final-voice-v2-${name}.png`);
  run(ffmpeg, [
    '-v', 'error', '-ss', (frame / fps).toFixed(6), '-i', videoPath,
    '-frames:v', '1', '-y', file,
  ]);
  assert(fs.existsSync(file) && fs.statSync(file).size > 0, `Failed to extract final frame ${frame}.`);
  const bytes = fs.readFileSync(file);
  assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a', `Extracted frame ${frame} is not PNG.`);
  return {name, frame, path: path.relative(root, file), sha256: createHash('sha256').update(bytes).digest('hex'), inspected: false};
}

assert(fs.existsSync(ffmpeg), `ffmpeg is missing: ${ffmpeg}`);
assert(fs.existsSync(ffprobe), `ffprobe is missing: ${ffprobe}`);
const timeline = readJson(timelinePath);
const originalTimeline = readJson(originalTimelinePath);
const mixManifest = readJson(mixManifestPath);
const voiceManifest = readJson(voiceManifestPath);
assert.equal(timeline.fps, fps);
assert.equal(timeline.width, 1920);
assert.equal(timeline.height, 1080);
assert(Number.isInteger(timeline.durationInFrames) && timeline.durationInFrames > 0 && timeline.durationInFrames <= 2_880,
  'Voiced duration must be an integer of at most 120 seconds.');
assert.equal(originalTimeline.fps, fps);
assert.equal(originalTimeline.durationInFrames, 2_160);
assert.equal(timeline.source, originalTimeline.source, 'Original text source changed.');
assert.equal(timeline.shots.length, expectedShotCount);
assert.equal(originalTimeline.shots.length, expectedShotCount);
assert.equal(voiceManifest.cues.length, expectedCueCount);
assert.equal(mixManifest.cues.length, expectedCueCount);

const hashOriginalTimeline = sha256File(originalTimelinePath);
const hashMixManifest = sha256File(mixManifestPath);
const hashVoiceManifest = sha256File(voiceManifestPath);
assert.equal(mixManifest.sourceTimeline.sha256, hashOriginalTimeline, 'Mix manifest source timeline hash does not match the current source timeline.');
assert.equal(mixManifest.voiceManifest.sha256, hashVoiceManifest, 'Mix manifest voice-manifest hash does not match the provider manifest.');
assert.equal(mixManifest.provider, voiceManifest.provider);
assert.equal(mixManifest.voice, voiceManifest.voice);
assert.equal(mixManifest.model, voiceManifest.model);
assert.equal(mixManifest.output.durationFrames, timeline.durationInFrames);
assert.equal(mixManifest.output.wavPath, 'public/madman/audio/voiced-v2.wav');
assert.equal(mixManifest.output.timelinePath, 'src/madman/voiced-timeline.json');
assert.equal(sha256File(timelinePath), mixManifest.output.timelineSha256, 'Voiced timeline hash does not match the mix manifest.');
assert.equal(sha256File(mixWavPath), mixManifest.output.wavSha256, 'Mixed WAV hash does not match the mix manifest.');
assert.equal(mixManifest.original90SecondSource.sha256, sha256File(atmospherePath), 'Original atmosphere hash does not match the mix manifest.');
assert.equal(mixManifest.fitsVisualBounds, true, 'Mix manifest reports a voice cue outside its visual bounds.');

let frameCursor = 0;
let originalFrameCursor = 0;
let cueCount = 0;
let previousCueEnd = 0;
const coverage = [];
const sourceVoiceEntries = new Map(voiceManifest.cues.map((cue) => [cue.id, cue]));
const mixCueEntries = new Map(mixManifest.cues.map((cue) => [cue.id, cue]));
assert.equal(sourceVoiceEntries.size, expectedCueCount, 'Voice manifest contains duplicate cue IDs.');
assert.equal(mixCueEntries.size, expectedCueCount, 'Mix manifest contains duplicate cue IDs.');

for (let shotIndex = 0; shotIndex < timeline.shots.length; shotIndex++) {
  const shot = timeline.shots[shotIndex];
  const originalShot = originalTimeline.shots[shotIndex];
  assert.equal(shot.id, originalShot.id, `Shot order changed at ${originalShot.id}.`);
  assert.equal(originalShot.from, originalFrameCursor, `Original timeline gap or overlap before ${originalShot.id}.`);
  assert.equal(shot.asset, originalShot.asset, `Asset changed in ${shot.id}.`);
  assert.equal(shot.section, originalShot.section, `Section changed in ${shot.id}.`);
  assert.equal(shot.from, frameCursor, `Timeline gap or overlap before ${shot.id}.`);
  assert(Number.isInteger(shot.duration) && shot.duration > 0, `Invalid duration in ${shot.id}.`);
  assert.equal(shot.cues.length, originalShot.cues.length, `Cue count changed in ${shot.id}.`);
  assert.equal(shot.cues.map((cue) => cue.text).join(''), originalShot.cues.map((cue) => cue.text).join(''),
    `Source text or word order changed in ${shot.id}.`);
  frameCursor += shot.duration;
  originalFrameCursor += originalShot.duration;

  for (let cueIndex = 0; cueIndex < shot.cues.length; cueIndex++) {
    const cue = shot.cues[cueIndex];
    const originalCue = originalShot.cues[cueIndex];
    const sourceVoice = voiceManifest.cues[cueCount];
    assert(sourceVoice, `Provider manifest is missing cue ${cueCount + 1}.`);
    const mixCue = mixCueEntries.get(sourceVoice.id);
    assert(mixCue, `Mix manifest is missing ${sourceVoice.id}.`);
    assert.equal(sourceVoice.shotId, shot.id, `Provider cue order differs in ${shot.id}.`);
    assert.equal(sourceVoice.cueIndex, cueIndex, `Provider cue index differs in ${shot.id}.`);
    assert.equal(sourceVoice.text, originalCue.text, `Provider text changed in ${shot.id}.`);
    assert.equal(mixCue.text, originalCue.text, `Mixed cue text changed in ${shot.id}.`);
    assert.equal(mixCue.shotId, shot.id);
    assert.equal(mixCue.cueIndex, cueIndex);
    assert.equal(sourceVoice.path, mixCue.audioFile, `Voice path differs between source and mix manifests for ${sourceVoice.id}.`);
    assert.equal(sourceVoice.sha256, mixCue.sha256, `Voice hash differs between source and mix manifests for ${sourceVoice.id}.`);
    assert.equal(sourceVoice.model, voiceManifest.model);
    assert.equal(sourceVoice.voice, voiceManifest.voice);
    assert.equal(sourceVoice.sampleRate, 24_000);
    assert.equal(sourceVoice.channels, 1);
    assert.equal(mixCue.sourceSampleRateHz, 24_000);
    assert.equal(mixCue.sourceChannels, 1);
    assert(mixCue.normalizedPeak <= 0.60001, `Normalized source clip exceeds 0.60 for ${sourceVoice.id}.`);

    const sourceVoicePath = path.resolve(root, sourceVoice.path);
    assert(sourceVoicePath.startsWith(`${path.resolve(root, 'public/madman/voice-v2')}${path.sep}`),
      `Voice clip path escapes the voice-v2 directory for ${sourceVoice.id}.`);
    assert.equal(sha256File(sourceVoicePath), sourceVoice.sha256, `Voice clip hash changed for ${sourceVoice.id}.`);
    assert(Number.isInteger(cue.from) && Number.isInteger(cue.duration) && cue.duration > 0);
    assert(cue.from >= 0 && cue.from + cue.duration <= shot.duration, `Caption exceeds ${shot.id}.`);
    const absoluteCaptionStart = shot.from + cue.from;
    const absoluteCaptionEnd = absoluteCaptionStart + cue.duration;
    assert(absoluteCaptionStart >= previousCueEnd, `Caption cues overlap at ${sourceVoice.id}.`);
    assert.equal(cue.audioStartFrame, absoluteCaptionStart, `Speech does not start on its cue in ${sourceVoice.id}.`);
    assert.equal(mixCue.audioStartFrame, absoluteCaptionStart, `Speech start manifest differs from its cue in ${sourceVoice.id}.`);
    assert.equal(mixCue.audioStartSample, absoluteCaptionStart * samplesPerFrame);
    const voiceSamples = mixCue.audioEndSampleExclusive - mixCue.audioStartSample;
    assert(Number.isInteger(voiceSamples) && voiceSamples > 0, `Invalid speech sample range for ${sourceVoice.id}.`);
    assert(Math.abs(voiceSamples / sampleRate - mixCue.sourceDurationSeconds) < 1 / sampleRate,
      `Source duration does not match absolute sample range for ${sourceVoice.id}.`);
    assert.equal(mixCue.captionStartFrame, absoluteCaptionStart);
    assert.equal(mixCue.captionEndFrame, absoluteCaptionEnd);
    assert(absoluteCaptionStart * samplesPerFrame <= mixCue.audioStartSample);
    assert(mixCue.audioEndSampleExclusive <= absoluteCaptionEnd * samplesPerFrame,
      `Caption does not cover the full narration for ${sourceVoice.id}.`);
    assert(mixCue.audioEndSampleExclusive <= (shot.from + shot.duration) * samplesPerFrame,
      `Shot does not cover the full narration for ${sourceVoice.id}.`);
    assert.equal(mixCue.fitsVisualBounds, true);
    assert(absoluteCaptionEnd <= timeline.durationInFrames);
    coverage.push({
      id: sourceVoice.id,
      shotId: shot.id,
      captionStartFrame: absoluteCaptionStart,
      captionEndFrame: absoluteCaptionEnd,
      speechStartFrame: mixCue.audioStartFrame,
      speechStartSample: mixCue.audioStartSample,
      speechEndSampleExclusive: mixCue.audioEndSampleExclusive,
      captionCoversSpeech: true,
      shotCoversSpeech: true,
      voiceSha256: sourceVoice.sha256,
    });
    previousCueEnd = absoluteCaptionEnd;
    cueCount++;
  }
}
assert.equal(frameCursor, timeline.durationInFrames, 'Shot frames do not equal timeline duration.');
assert.equal(originalFrameCursor, originalTimeline.durationInFrames, 'Original source shots do not cover the original timeline.');
assert.equal(cueCount, expectedCueCount);
assert.equal(timeline.shots[0].id, 'title');
assert.equal(timeline.shots[0].from, originalTimeline.shots[0].from);
assert.equal(timeline.shots[0].duration, originalTimeline.shots[0].duration, 'Title duration changed from 144 frames.');

const wavProbe = probeMedia(mixWavPath);
const wavStream = wavProbe.streams.find((stream) => stream.codec_type === 'audio');
assert(wavStream, 'Mixed WAV audio stream missing.');
assert.equal(wavStream.codec_name, 'pcm_s16le');
assert.equal(Number(wavStream.sample_rate), sampleRate);
assert.equal(wavStream.channels, 2);
assert.equal(Number(wavStream.bits_per_sample), 16);
assert(Math.abs(Number(wavStream.duration) - timeline.durationInFrames / fps) < 1 / sampleRate,
  'Mixed WAV duration does not exactly match the voiced timeline.');
const wavLevels = audioStats(mixWavPath);
assert(wavLevels.peakDbfs < 0, 'Mixed WAV peak reaches or exceeds full scale.');

assert(fs.existsSync(videoPath), `Rendered voice-v2 film is missing: ${videoPath}`);
const videoBytes = fs.readFileSync(videoPath);
const videoSha256 = createHash('sha256').update(videoBytes).digest('hex');
const videoProbe = probeMedia(videoPath);
const videoStream = videoProbe.streams.find((stream) => stream.codec_type === 'video');
const audioStream = videoProbe.streams.find((stream) => stream.codec_type === 'audio');
assert(videoStream && audioStream, 'Rendered video or audio stream is missing.');
assert.equal(videoStream.codec_name, 'h264');
assert.equal(videoStream.width, 1920);
assert.equal(videoStream.height, 1080);
assert.equal(videoStream.r_frame_rate, '24/1');
assert.equal(videoStream.pix_fmt, 'yuv420p');
assert.equal(videoStream.color_space, 'bt709');
assert.equal(videoStream.color_range, 'tv');
assert.equal(Number(videoStream.nb_frames), timeline.durationInFrames, 'Encoded frame count differs from the retimed timeline.');
const expectedDuration = timeline.durationInFrames / fps;
assert(Math.abs(Number(videoStream.duration) - expectedDuration) <= 1 / fps,
  'Video stream duration differs from exact timeline frames.');
assert.equal(audioStream.codec_name, 'aac');
assert.equal(audioStream.channels, 2);
assert.equal(Number(audioStream.sample_rate), sampleRate);
assert(Math.abs(Number(videoProbe.format.duration) - expectedDuration) < 0.1, 'Container duration differs from the retimed timeline by 0.1 seconds or more.');

const decode = run(ffmpeg, ['-v', 'error', '-i', videoPath, '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-']);
assert.equal(decode.stderr.trim(), '', 'Full video/audio decode reported an error.');
const encodedAudioLevels = audioStats(videoPath);
assert(encodedAudioLevels.peakDbfs < -1, `Encoded audio peak ${encodedAudioLevels.peakDbfs} dBFS is not below -1 dBFS.`);
const fastStart = hasFastStartAtoms(videoBytes);
assert(fastStart, 'MP4 moov atom must precede mdat for fast start.');

const history = timeline.shots.find((shot) => shot.id === 'history');
assert(history && history.cues.length >= 3, 'History reveal still requires the third caption cue.');
const historyRevealFrame = history.from + Math.min(history.duration - 1, history.cues[2].from + Math.round(1.2 * fps));
const stillPicks = timeline.shots.map((shot) => ({
  name: shot.id,
  frame: shot.from + Math.min(shot.duration - 1, Math.round(shot.duration * 0.72)),
}));
stillPicks.push(
  {name: 'history-third-cue-plus-1-2s', frame: historyRevealFrame},
  {name: 'lastframe', frame: timeline.durationInFrames - 1},
);
const extractedStills = stillPicks.map(({name, frame}) => extractFrame(frame, name));

const report = {
  checkedAt: new Date().toISOString(),
  film: path.basename(videoPath),
  sha256: videoSha256,
  sizeBytes: videoBytes.length,
  provider: voiceManifest.provider,
  model: voiceManifest.model,
  voice: voiceManifest.voice,
  sourceVoiceManifest: {path: path.relative(root, voiceManifestPath), sha256: hashVoiceManifest},
  mixManifest: {path: path.relative(root, mixManifestPath), sha256: hashMixManifest},
  sourceTimeline: {sha256: hashOriginalTimeline, frames: originalTimeline.durationInFrames, durationSeconds: originalTimeline.durationInFrames / fps},
  timeline: {
    path: path.relative(root, timelinePath),
    sha256: sha256File(timelinePath),
    width: timeline.width,
    height: timeline.height,
    fps,
    frames: timeline.durationInFrames,
    durationSeconds: expectedDuration,
    shotCount: timeline.shots.length,
    shotsContinuousAndInBounds: true,
    sourceShotIDsAssetsAndTextUnchanged: true,
    cueCount,
    cuesOrderedAndNonoverlapping: true,
  },
  voiceCoverage: {
    allSpeechStartsOnCaptionStart: true,
    everyCueFullyCoveredByCaptionAndShot: true,
    cues: coverage,
  },
  mixedWav: {
    path: path.relative(root, mixWavPath),
    sha256: mixManifest.output.wavSha256,
    codec: wavStream.codec_name,
    sampleRateHz: Number(wavStream.sample_rate),
    channels: wavStream.channels,
    bitDepth: Number(wavStream.bits_per_sample),
    durationSeconds: Number(wavStream.duration),
    peakDbfs: wavLevels.peakDbfs,
    rmsDbfs: wavLevels.rmsDbfs,
  },
  video: {
    codec: videoStream.codec_name,
    width: videoStream.width,
    height: videoStream.height,
    frameRate: videoStream.r_frame_rate,
    frames: Number(videoStream.nb_frames),
    streamDurationSeconds: Number(videoStream.duration),
    containerDurationSeconds: Number(videoProbe.format.duration),
    pixelFormat: videoStream.pix_fmt,
    colorSpace: videoStream.color_space,
    colorRange: videoStream.color_range,
    fastStart,
    fullDecode: 'passed; video and audio, no errors',
  },
  encodedAudio: {
    codec: audioStream.codec_name,
    sampleRateHz: Number(audioStream.sample_rate),
    channels: audioStream.channels,
    durationSeconds: Number(audioStream.duration),
    peakDbfs: encodedAudioLevels.peakDbfs,
    rmsDbfs: encodedAudioLevels.rmsDbfs,
  },
  finalFrames: {extracted: true, inspected: false, files: extractedStills},
  browserPlayback: false,
  finalSamplesInspected: false,
  humanListening: false,
};
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({
  film: report.film,
  sha256: report.sha256,
  durationSeconds: report.timeline.durationSeconds,
  frames: report.video.frames,
  videoCodec: report.video.codec,
  audioCodec: report.encodedAudio.codec,
  peakDbfs: report.encodedAudio.peakDbfs,
  fastStart: report.video.fastStart,
  report: path.relative(root, reportPath),
}, null, 2));
