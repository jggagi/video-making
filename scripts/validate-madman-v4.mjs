import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const outputDir = path.resolve(root, 'out/madman');
const timelinePath = path.resolve(root, 'src/madman/full-v4-timeline.json');
const sourceTimelinePath = path.resolve(root, 'src/madman/voiced-timeline.json');
const voiceManifestPath = path.resolve(root, 'public/madman/voice-v2/manifest.json');
const fullV4ManifestPath = path.resolve(root, 'public/madman/audio/full-v4-manifest.json');
const historySpecPath = path.resolve(root, 'src/madman/history-study-v3.json');
const historyManifestPath = path.resolve(root, 'public/madman/audio/history-study-v3-manifest.json');
const vttPath = path.join(outputDir, '狂人日记-节奏意象加强版-v4.vtt');
const videoPath = path.join(outputDir, '狂人日记-节奏意象加强版-v4-1080p.mp4');
const reportPath = path.join(outputDir, 'validation-full-v4.json');
const ffmpeg = process.env.FFMPEG_EXECUTABLE ?? '/opt/homebrew/bin/ffmpeg';
const ffprobe = process.env.FFPROBE_EXECUTABLE ?? '/opt/homebrew/bin/ffprobe';
const fps = 24;
const expectedFrames = 1_896;
const expectedCaptionCharacters = 143;
const expectedOldMovieHashes = {
  '狂人日记-男声配音版-v2-1080p.mp4': '7d709339a515cb45d01bfabfd82f7101045e40658b1be79565e851b40303681c',
  '狂人日记-字缝加强样片-v3-1080p.mp4': 'c84c2e803089c3a91c05cbbd586e62be8ff4ee41cd70844d736784c5073236a1',
};

function run(binary, args, options = {}) {
  const result = spawnSync(binary, args, {encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, ...options});
  if (result.error) throw result.error;
  const stderr = Buffer.isBuffer(result.stderr) ? result.stderr.toString('utf8') : result.stderr ?? '';
  assert.equal(result.status, 0, `${path.basename(binary)} failed: ${stderr}`);
  return result;
}

function sha256File(file) {
  return createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function probeMedia(file) {
  return JSON.parse(run(ffprobe, ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', file]).stdout);
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
    atoms.push({type, offset});
    offset += size;
  }
  const moov = atoms.find((atom) => atom.type === 'moov');
  const mdat = atoms.find((atom) => atom.type === 'mdat');
  return Boolean(moov && mdat && moov.offset < mdat.offset);
}

function vttTimeToMilliseconds(value) {
  const match = value.match(/^(\d{2,}):(\d{2}):(\d{2})\.(\d{3})$/);
  assert(match, `Invalid VTT timestamp: ${value}`);
  return (((Number(match[1]) * 60 + Number(match[2])) * 60 + Number(match[3])) * 1_000) + Number(match[4]);
}

function extractFrame(frame, name) {
  assert(Number.isInteger(frame) && frame >= 0 && frame < expectedFrames, `Invalid still frame ${frame}.`);
  const file = path.join(outputDir, `final-v4-${name}.png`);
  run(ffmpeg, [
    '-v', 'error', '-y', '-i', videoPath,
    '-vf', `select=eq(n\\,${frame})`, '-frames:v', '1', file,
  ]);
  assert(fs.existsSync(file) && fs.statSync(file).size > 0, `Failed to extract final frame ${frame}.`);
  const bytes = fs.readFileSync(file);
  assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a', `Extracted frame ${frame} is not PNG.`);
  return {name, frame, path: path.relative(root, file), sha256: createHash('sha256').update(bytes).digest('hex'), inspected: false};
}

assert(fs.existsSync(ffmpeg), `ffmpeg is missing: ${ffmpeg}`);
assert(fs.existsSync(ffprobe), `ffprobe is missing: ${ffprobe}`);
assert(fs.existsSync(videoPath), `Rendered full-v4 film is missing: ${videoPath}`);
assert(fs.existsSync(timelinePath), `Full-v4 timeline is missing: ${timelinePath}`);
assert(fs.existsSync(sourceTimelinePath), `Source voiced timeline is missing: ${sourceTimelinePath}`);
assert(fs.existsSync(voiceManifestPath), `Source voice manifest is missing: ${voiceManifestPath}`);
assert(fs.existsSync(fullV4ManifestPath), `Full-v4 audio manifest is missing: ${fullV4ManifestPath}`);
assert(fs.existsSync(historySpecPath), `History study spec is missing: ${historySpecPath}`);
assert(fs.existsSync(historyManifestPath), `History study mix manifest is missing: ${historyManifestPath}`);
assert(fs.existsSync(vttPath), `Full-v4 VTT captions are missing: ${vttPath}`);

const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
const sourceTimeline = JSON.parse(fs.readFileSync(sourceTimelinePath, 'utf8'));
const voiceManifest = JSON.parse(fs.readFileSync(voiceManifestPath, 'utf8'));
const fullV4Manifest = JSON.parse(fs.readFileSync(fullV4ManifestPath, 'utf8'));
const historySpec = JSON.parse(fs.readFileSync(historySpecPath, 'utf8'));
const historyManifest = JSON.parse(fs.readFileSync(historyManifestPath, 'utf8'));
const fullV4WavPath = path.resolve(root, fullV4Manifest.output.wavPath);
assert.equal(timeline.fps, fps);
assert.equal(timeline.width, 1920);
assert.equal(timeline.height, 1080);
assert.equal(timeline.durationInFrames, expectedFrames);
assert.equal(timeline.source, sourceTimeline.source, 'Original text source changed.');
assert.equal(timeline.sourceTimeline, 'src/madman/voiced-timeline.json');
assert.equal(timeline.historySpec, 'src/madman/history-study-v3.json');
assert.equal(timeline.historyMixManifest, 'public/madman/audio/history-study-v3-manifest.json');
assert.equal(timeline.shots.length, 8);
assert.equal(voiceManifest.cues.length, 11);
const sourceTimelineSha256 = sha256File(sourceTimelinePath);
const voiceManifestSha256 = sha256File(voiceManifestPath);
const timelineSha256 = sha256File(timelinePath);
assert.equal(fullV4Manifest.spec.path, path.relative(root, timelinePath));
assert.equal(fullV4Manifest.spec.sha256, timelineSha256, 'Full-v4 audio manifest does not identify the current timeline.');
assert.equal(fullV4Manifest.sourceTimeline.path, path.relative(root, sourceTimelinePath));
assert.equal(fullV4Manifest.sourceTimeline.sha256, sourceTimelineSha256, 'Full-v4 audio manifest source timeline hash changed.');
assert.equal(fullV4Manifest.provider.manifestPath, path.relative(root, voiceManifestPath));
assert.equal(fullV4Manifest.provider.manifestSha256, voiceManifestSha256, 'Full-v4 audio manifest source voice manifest hash changed.');
assert.equal(fullV4Manifest.provider.sourceCueCount, 11);
assert.equal(fullV4Manifest.narration.length, 11);
assert.equal(fullV4Manifest.cloudCalls, 0, 'Full-v4 audio preparation should not have made new cloud calls.');
assert.equal(fullV4Manifest.output.wavPath, `public/${timeline.audioFile}`);
assert.equal(fullV4Manifest.output.wavSha256, sha256File(path.resolve(root, fullV4Manifest.output.wavPath)), 'Full-v4 WAV hash differs from its manifest.');
assert.equal(fullV4Manifest.output.sampleRateHz, 48_000);
assert.equal(fullV4Manifest.output.channels, 2);
assert.equal(fullV4Manifest.output.bitDepth, 16);
assert.equal(fullV4Manifest.output.codec, 'pcm_s16le');
assert.equal(fullV4Manifest.output.fps, fps);
assert.equal(fullV4Manifest.output.durationFrames, expectedFrames);
assert.equal(fullV4Manifest.output.durationSeconds, expectedFrames / fps);
assert.equal(fullV4Manifest.output.finalSilence.fromFrame, 1_824);
assert.equal(fullV4Manifest.output.finalSilence.toFrame, expectedFrames);
assert.equal(fullV4Manifest.output.finalSilence.pcmPeak, 0);
assert(fs.existsSync(fullV4WavPath), `Full-v4 mixed WAV is missing: ${fullV4WavPath}`);
const fullV4WavProbe = probeMedia(fullV4WavPath);
const fullV4WavStream = fullV4WavProbe.streams.find((stream) => stream.codec_type === 'audio');
assert(fullV4WavStream, 'Full-v4 mixed WAV audio stream is missing.');
assert.equal(fullV4WavStream.codec_name, 'pcm_s16le');
assert.equal(Number(fullV4WavStream.sample_rate), 48_000);
assert.equal(fullV4WavStream.channels, 2);
assert.equal(Number(fullV4WavStream.bits_per_sample), 16);
assert(Math.abs(Number(fullV4WavStream.duration) - expectedFrames / fps) < 1 / 48_000,
  'Full-v4 WAV duration differs from exact timeline frames.');

assert.equal(historyManifest.specFile, path.relative(root, historySpecPath));
assert.equal(historyManifest.specSha256, sha256File(historySpecPath), 'History mix manifest does not identify the current history spec.');
assert.equal(historyManifest.sourceTimelineSha256, sourceTimelineSha256, 'History mix manifest source timeline hash changed.');
assert.equal(historyManifest.providerManifestSha256, voiceManifestSha256, 'History mix manifest source voice manifest hash changed.');
assert.equal(historyManifest.durationFrames, 480);
assert.equal(historyManifest.durationSeconds, 20);
const historyReuse = fullV4Manifest.historyReuse;
assert.equal(historyReuse.sourcePath, 'public/madman/audio/history-study-v3.wav');
assert.equal(historyReuse.sourceManifestPath, path.relative(root, historyManifestPath));
assert.equal(historyReuse.sourceManifestSha256, sha256File(historyManifestPath));
assert.equal(historyReuse.sourceWavSha256, sha256File(path.resolve(root, historyReuse.sourcePath)));
assert.equal(historyReuse.pcmByteIdentical, true);
assert.equal(historyReuse.sourcePcmSha256, historyReuse.embeddedPcmSha256);
const historyShot = timeline.shots.find((shot) => shot.id === 'history');
assert(historyShot, 'Full-v4 history shot is missing.');
assert.equal(historyReuse.fromFrame, historyShot.from);
assert.equal(historyReuse.toFrame, historyShot.from + historyShot.duration);
assert.equal(historyReuse.toFrame - historyReuse.fromFrame, 20 * fps);
assert.equal(historyReuse.sampleRateHz, 48_000);
assert.equal(historyReuse.channels, 2);
assert.equal(historyReuse.bitDepth, 16);
assert.equal(historyReuse.voiceRecords.length, 3);
assert.equal(historyManifest.narration.length, 3);
const samplesPerVideoFrame = 48_000 / fps;
const bytesPerVideoFrame = samplesPerVideoFrame * 2 * 2;
const sourceHistoryPcm = run(ffmpeg, [
  '-v', 'error', '-i', historyReuse.sourcePath, '-f', 's16le', '-acodec', 'pcm_s16le', 'pipe:1',
], {encoding: 'buffer'}).stdout;
const fullV4Pcm = run(ffmpeg, [
  '-v', 'error', '-i', fullV4WavPath, '-f', 's16le', '-acodec', 'pcm_s16le', 'pipe:1',
], {encoding: 'buffer'}).stdout;
assert.equal(sourceHistoryPcm.length, (historyReuse.toFrame - historyReuse.fromFrame) * bytesPerVideoFrame);
assert.equal(fullV4Pcm.length, fullV4Manifest.output.sampleCountPerChannel * 2 * 2);
assert.equal(fullV4Pcm.subarray(1824 * bytesPerVideoFrame).some(byte => byte !== 0), false,
  'The written full-v4 PCM must preserve three seconds of actual ending silence.');
const embeddedHistoryPcm = fullV4Pcm.subarray(
  historyReuse.fromFrame * bytesPerVideoFrame,
  historyReuse.toFrame * bytesPerVideoFrame,
);
const sourceHistoryPcmSha256 = createHash('sha256').update(sourceHistoryPcm).digest('hex');
const embeddedHistoryPcmSha256 = createHash('sha256').update(embeddedHistoryPcm).digest('hex');
assert.equal(sourceHistoryPcmSha256, historyReuse.sourcePcmSha256, 'History source PCM hash differs from the full-v4 manifest.');
assert.equal(embeddedHistoryPcmSha256, historyReuse.embeddedPcmSha256, 'Embedded history PCM hash differs from the full-v4 manifest.');
assert.deepEqual(embeddedHistoryPcm, sourceHistoryPcm, 'Reused history PCM is not byte-identical in the full-v4 mix.');
assert.equal(fullV4Manifest.subtitles.vttPath, path.relative(root, vttPath));
assert.equal(fullV4Manifest.subtitles.cueCount, 12);
assert.equal(fullV4Manifest.subtitles.sourceTextPreserved, true);
assert.equal(fullV4Manifest.subtitles.vttSha256, sha256File(vttPath), 'Subtitle VTT hash differs from the audio manifest.');

const fullMixNarration = new Map(fullV4Manifest.narration.map((cue) => [cue.id, cue]));
assert.equal(fullMixNarration.size, 11, 'Full-v4 narration has duplicate cue IDs.');
const historyVoiceRecords = new Map(historyReuse.voiceRecords.map((cue) => [cue.id, cue]));
assert.equal(historyVoiceRecords.size, 3, 'History reuse records have duplicate cue IDs.');
const historyMixNarration = new Map(historyManifest.narration.map((cue) => [cue.id, cue]));
assert.equal(historyMixNarration.size, 3, 'History study narration has duplicate cue IDs.');
const reusedHistoryRecords = [];

let frameCursor = 0;
let cueCount = 0;
const originalCues = [];
const sourceShots = new Map(sourceTimeline.shots.map((shot) => [shot.id, shot]));
for (const [shotIndex, shot] of timeline.shots.entries()) {
  const sourceShot = sourceTimeline.shots[shotIndex];
  assert(sourceShot, `Source timeline is missing shot ${shot.id}.`);
  assert.equal(shot.id, sourceShot.id, `Shot order changed at ${sourceShot.id}.`);
  assert.equal(shot.from, frameCursor, `Timeline gap or overlap before ${shot.id}.`);
  assert(Number.isInteger(shot.duration) && shot.duration > 0, `Invalid duration in ${shot.id}.`);
  assert.equal(shot.asset, sourceShot.asset, `Source art asset changed in ${shot.id}.`);
  assert.equal(shot.section, sourceShot.section, `Source section changed in ${shot.id}.`);
  assert.equal(shot.cues.length, sourceShot.cues.length, `Original cue count changed in ${shot.id}.`);
  for (let cueIndex = 0; cueIndex < shot.cues.length; cueIndex++) {
    const cue = shot.cues[cueIndex];
    const sourceCue = sourceShot.cues[cueIndex];
    const manifestCue = voiceManifest.cues[cueCount];
    assert(manifestCue, `Source voice manifest is missing cue ${cueCount + 1}.`);
    assert.equal(cue.text, sourceCue.text, `Original text changed in ${shot.id} cue ${cueIndex + 1}.`);
    assert.equal(cue.audioFile, sourceCue.audioFile, `Original audio path changed in ${shot.id} cue ${cueIndex + 1}.`);
    assert.equal(manifestCue.shotId, shot.id, `Source voice order differs at ${shot.id}.`);
    assert.equal(manifestCue.cueIndex, cueIndex, `Source voice cue index differs at ${shot.id}.`);
    assert.equal(manifestCue.text, sourceCue.text, `Source voice manifest text changed at ${shot.id}.`);
    assert.equal(manifestCue.path, sourceCue.audioFile, `Source voice path differs at ${shot.id}.`);
    assert.equal(sha256File(path.resolve(root, manifestCue.path)), manifestCue.sha256, `Original voice hash changed for ${manifestCue.id}.`);
    assert(Number.isInteger(cue.from) && Number.isInteger(cue.duration) && cue.duration > 0, `Invalid cue timing for ${manifestCue.id}.`);
    assert(cue.from >= 0 && cue.from + cue.duration <= shot.duration, `Cue exceeds shot bounds for ${manifestCue.id}.`);
    originalCues.push({id: manifestCue.id, shotId: shot.id, cueIndex, fromFrame: shot.from + cue.from, text: cue.text, audioPath: cue.audioFile, sha256: manifestCue.sha256});
    cueCount++;
  }
  frameCursor += shot.duration;
}
assert.equal(frameCursor, expectedFrames, 'Shot frames do not equal the 1896-frame timeline.');
assert.equal(cueCount, 11, 'Expected all 11 original voice cues.');
assert.equal(sourceShots.size, timeline.shots.length, 'Source timeline has unexpected duplicate or missing shot IDs.');
assert.deepEqual(fullV4Manifest.narration.map((cue) => cue.id), voiceManifest.cues.map((cue) => cue.id), 'Full-v4 manifest narration order differs from the source voice manifest.');
assert.deepEqual(historyManifest.narration.map((cue) => cue.id), originalCues.filter((cue) => cue.shotId === 'history').map((cue) => cue.id));
for (const sourceCue of voiceManifest.cues) {
  const fullCue = fullMixNarration.get(sourceCue.id);
  const cuePosition = originalCues.find((cue) => cue.id === sourceCue.id);
  assert(fullCue && cuePosition, `Full-v4 narration is missing ${sourceCue.id}.`);
  assert.equal(fullCue.text, sourceCue.text, `Full-v4 manifest text differs for ${sourceCue.id}.`);
  assert.equal(fullCue.file, sourceCue.path, `Full-v4 manifest voice path differs for ${sourceCue.id}.`);
  assert.equal(fullCue.sha256, sourceCue.sha256, `Full-v4 manifest voice hash differs for ${sourceCue.id}.`);
  assert.equal(fullCue.shotId, sourceCue.shotId, `Full-v4 manifest voice shot differs for ${sourceCue.id}.`);
  assert.equal(fullCue.fromFrame, cuePosition.fromFrame, `Full-v4 audio cue moved from its timeline position: ${sourceCue.id}.`);
  if (fullCue.cueIndex !== undefined) assert.equal(fullCue.cueIndex, sourceCue.cueIndex, `Full-v4 cue index differs for ${sourceCue.id}.`);
  if (sourceCue.shotId === 'history') {
    const historyRecord = historyVoiceRecords.get(sourceCue.id);
    const historyMixCue = historyMixNarration.get(sourceCue.id);
    assert(historyRecord && historyMixCue, `History reuse manifest is missing ${sourceCue.id}.`);
    for (const record of [historyRecord, historyMixCue]) {
      assert.equal(record.text, sourceCue.text, `History mix text differs for ${sourceCue.id}.`);
      assert.equal(record.file, sourceCue.path, `History mix voice path differs for ${sourceCue.id}.`);
      assert.equal(record.sha256, sourceCue.sha256, `History mix voice hash differs for ${sourceCue.id}.`);
    }
    reusedHistoryRecords.push({id: sourceCue.id, text: sourceCue.text, sha256: sourceCue.sha256});
  }
}

const captionRows = [];
let previousCaptionEnd = 0;
for (const shot of timeline.shots) {
  const rows = Array.isArray(shot.captions)
    ? shot.captions
    : shot.cues.map((cue) => ({from: cue.from, end: cue.from + cue.duration, text: cue.text}));
  for (const caption of rows) {
    const localEnd = caption.end ?? caption.from + caption.duration;
    assert(Number.isInteger(caption.from) && Number.isInteger(localEnd) && localEnd > caption.from, `Invalid caption timing in ${shot.id}.`);
    assert(caption.from >= 0 && localEnd <= shot.duration, `Caption exceeds shot bounds in ${shot.id}.`);
    const startFrame = shot.from + caption.from;
    const endFrame = shot.from + localEnd;
    assert(startFrame >= previousCaptionEnd, `Captions overlap or are out of order before ${shot.id}.`);
    assert(typeof caption.text === 'string' && caption.text.length > 0, `Empty caption in ${shot.id}.`);
    captionRows.push({startFrame, endFrame, text: caption.text});
    previousCaptionEnd = endFrame;
  }
}
assert.equal(captionRows.length, 12, 'Expected 12 original-text caption rows.');
const captionCharacterCount = captionRows.reduce((count, caption) => count + caption.text.length, 0);
assert.equal(captionCharacterCount, expectedCaptionCharacters, 'Caption text must total exactly 143 characters.');
assert.equal(captionRows.map((caption) => caption.text).join(''), originalCues.map((cue) => cue.text).join(''),
  'Caption text/order differs from the 11 original source cues.');

const vtt = fs.readFileSync(vttPath, 'utf8').replace(/^\uFEFF/, '').trim();
const vttBlocks = vtt.split(/\r?\n\s*\r?\n/);
assert.equal(vttBlocks.shift()?.trim(), 'WEBVTT', 'VTT header is missing.');
const vttCues = vttBlocks.filter((block) => block.includes('-->')).map((block) => {
  const lines = block.split(/\r?\n/);
  const timingIndex = lines.findIndex((line) => line.includes('-->'));
  const [start, end] = lines[timingIndex].split('-->').map((part) => part.trim().split(/\s+/)[0]);
  return {
    startMilliseconds: vttTimeToMilliseconds(start),
    endMilliseconds: vttTimeToMilliseconds(end),
    text: lines.slice(timingIndex + 1).join('\n'),
  };
});
assert.equal(vttCues.length, captionRows.length, 'VTT row count differs from the timeline captions.');
for (let index = 0; index < captionRows.length; index++) {
  const expected = captionRows[index];
  const actual = vttCues[index];
  assert.equal(actual.text, expected.text, `VTT text/order differs at caption ${index + 1}.`);
  assert(Math.abs(actual.startMilliseconds - Math.round(expected.startFrame * 1_000 / fps)) <= 1, `VTT start differs at caption ${index + 1}.`);
  assert(Math.abs(actual.endMilliseconds - Math.round(expected.endFrame * 1_000 / fps)) <= 1, `VTT end differs at caption ${index + 1}.`);
}

const priorMovieHashes = {};
for (const [filename, expectedHash] of Object.entries(expectedOldMovieHashes)) {
  const file = path.join(outputDir, filename);
  assert(fs.existsSync(file), `Previously delivered movie is missing: ${file}`);
  const actualHash = sha256File(file);
  assert.equal(actualHash, expectedHash, `Previously delivered movie changed: ${filename}`);
  priorMovieHashes[filename] = actualHash;
}

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
assert.equal(Number(videoStream.nb_frames), expectedFrames, 'Encoded frame count differs from the timeline.');
assert.equal(videoStream.pix_fmt, 'yuv420p');
assert.equal(videoStream.color_space, 'bt709');
assert.equal(videoStream.color_primaries, 'bt709');
assert.equal(videoStream.color_transfer, 'bt709');
assert.equal(videoStream.color_range, 'tv');
const expectedDuration = expectedFrames / fps;
assert(Math.abs(Number(videoStream.duration) - expectedDuration) < 1 / fps, 'Video stream duration differs from 79 seconds.');
assert(Math.abs(Number(videoProbe.format.duration) - expectedDuration) < 0.1, 'Container duration differs from 79 seconds by 0.1 seconds or more.');
assert.equal(audioStream.codec_name, 'aac');
assert.equal(Number(audioStream.sample_rate), 48_000);
assert.equal(audioStream.channels, 2);
assert(Math.abs(Number(audioStream.duration) - expectedDuration) < 0.1, 'Audio stream duration differs from 79 seconds.');

const decode = run(ffmpeg, ['-v', 'error', '-i', videoPath, '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-']);
assert.equal(decode.stderr.trim(), '', 'Full video/audio decode reported an error.');
const decodedAudio = run(ffmpeg, [
  '-v', 'error', '-i', videoPath, '-map', '0:a:0', '-ar', '48000', '-ac', '2', '-f', 'f32le', 'pipe:1',
], {encoding: 'buffer'}).stdout;
assert.equal(decodedAudio.length % 8, 0, 'Decoded stereo float audio has a partial sample frame.');
const samples = new Float32Array(decodedAudio.buffer, decodedAudio.byteOffset, decodedAudio.length / 4);
let peak = 0;
let sumSquares = 0;
for (const value of samples) {
  assert(Number.isFinite(value), 'Decoded audio contains a non-finite sample.');
  peak = Math.max(peak, Math.abs(value));
  sumSquares += value * value;
}
assert(peak > 0 && peak < 1, `Encoded audio peak ${peak} reaches digital full scale or is silent.`);
const peakDbfs = 20 * Math.log10(peak);
const rmsDbfs = 20 * Math.log10(Math.sqrt(sumSquares / samples.length));
const fastStart = hasFastStartAtoms(videoBytes);
assert(fastStart, 'MP4 moov atom must precede mdat for fast start.');

const shotsById = new Map(timeline.shots.map((shot) => [shot.id, shot]));
const picks = [
  ['title', 85],
  ['moon', shotsById.get('moon').from + 108],
  ['watch', shotsById.get('watch').from + 72],
  ['watch-left', shotsById.get('watch').from + 168],
  ['watch-right', shotsById.get('watch').from + 228],
  ['history', shotsById.get('history').from + 216],
  ['history-reveal', shotsById.get('history').from + 420],
  ['question', shotsById.get('question').from + 96],
  ['complicity', shotsById.get('complicity').from + 192],
  ['children', shotsById.get('children').from + 144],
  ['plea', shotsById.get('plea').from + 96],
  ['ending', expectedFrames - 1],
];
fs.mkdirSync(outputDir, {recursive: true});
const extractedFrames = picks.map(([name, frame]) => extractFrame(frame, name));

const fullV4ManifestSha256 = sha256File(fullV4ManifestPath);
const report = {
  checkedAt: new Date().toISOString(),
  film: path.basename(videoPath),
  sha256: videoSha256,
  sizeBytes: videoBytes.length,
  sourceIntegrity: {
    source: timeline.source,
    sourceTimeline: {path: path.relative(root, sourceTimelinePath), sha256: sourceTimelineSha256},
    providerVoiceManifest: {path: path.relative(root, voiceManifestPath), sha256: voiceManifestSha256},
    fullV4AudioManifest: {path: path.relative(root, fullV4ManifestPath), sha256: fullV4ManifestSha256},
    originalVoiceCuesMatchManifest: true,
    originalVoiceCues: originalCues,
    earlierMoviesUnchanged: priorMovieHashes,
  },
  audioPreparation: {
    provider: fullV4Manifest.provider.name,
    model: fullV4Manifest.provider.model,
    voice: fullV4Manifest.provider.voice,
    newCloudCalls: fullV4Manifest.cloudCalls,
    mixedWav: {
      path: path.relative(root, fullV4WavPath),
      sha256: fullV4Manifest.output.wavSha256,
      sampleRateHz: Number(fullV4WavStream.sample_rate),
      channels: fullV4WavStream.channels,
      bitDepth: Number(fullV4WavStream.bits_per_sample),
      durationSeconds: Number(fullV4WavStream.duration),
    },
    historyReuse: {
      sourcePath: historyReuse.sourcePath,
      sourceWavSha256: historyReuse.sourceWavSha256,
      sourcePcmSha256: sourceHistoryPcmSha256,
      embeddedPcmSha256: embeddedHistoryPcmSha256,
      pcmByteIdentical: true,
      fromFrame: historyReuse.fromFrame,
      toFrame: historyReuse.toFrame,
      reusedVoiceCues: reusedHistoryRecords,
    },
  },
  timeline: {
    path: path.relative(root, timelinePath),
    sha256: timelineSha256,
    width: timeline.width,
    height: timeline.height,
    fps,
    frames: expectedFrames,
    durationSeconds: expectedDuration,
    shotCount: timeline.shots.length,
    shotsContinuousAndInBounds: true,
    cueCount,
    originalCueTextAndOrderPreserved: true,
    captionCount: captionRows.length,
    captionCharacters: captionCharacterCount,
    captionsMatchOriginalTextAndVtt: true,
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
    colorPrimaries: videoStream.color_primaries,
    colorTransfer: videoStream.color_transfer,
    colorRange: videoStream.color_range,
    fastStart,
    fullDecode: 'passed; video and audio, no errors',
  },
  audio: {
    codec: audioStream.codec_name,
    sampleRateHz: Number(audioStream.sample_rate),
    channels: audioStream.channels,
    durationSeconds: Number(audioStream.duration),
    peakDbfs,
    rmsDbfs,
    noClipping: true,
  },
  finalFrames: {extracted: true, inspected: false, files: extractedFrames},
  browserPlayback: 'pending root review',
  humanListening: 'pending root review',
};
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({
  film: report.film,
  sha256: report.sha256,
  durationSeconds: report.timeline.durationSeconds,
  frames: report.video.frames,
  captionCharacters: report.timeline.captionCharacters,
  peakDbfs: report.audio.peakDbfs,
  fastStart: report.video.fastStart,
  extractedFrames: report.finalFrames.files.length,
  report: path.relative(root, reportPath),
}, null, 2));
