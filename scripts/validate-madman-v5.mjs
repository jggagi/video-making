import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const outputDir = path.resolve(root, 'out/madman');
const timelinePath = path.resolve(root, 'src/madman/suspense-v5-timeline.json');
const planPath = path.resolve(root, 'public/madman/voice-v5/plan.json');
const voiceManifestPath = path.resolve(root, 'public/madman/voice-v5/manifest.json');
const editPlanPath = path.resolve(root, 'src/madman/suspense-v5-edit.json');
const mixManifestPath = path.resolve(root, 'public/madman/audio/suspense-v5-manifest.json');
const assetManifestPath = path.resolve(root, 'public/madman/cinema-v5/asset-manifest.json');
const vttPath = path.join(outputDir, '狂人日记-心理悬疑版-v5.vtt');
const srtPath = path.join(outputDir, '狂人日记-心理悬疑版-v5.srt');
const sourceVttPath = path.resolve(root, 'public/madman/suspense-v5.vtt');
const sourceSrtPath = path.resolve(root, 'public/madman/suspense-v5.srt');
const videoPath = path.join(outputDir, '狂人日记-心理悬疑版-v5-1080p.mp4');
const samplePath = path.join(outputDir, 'cinema-v5-diagnosis-sample.mp4');
const reportPath = path.join(outputDir, 'validation-cinema-v5.json');
const ffmpeg = process.env.FFMPEG_EXECUTABLE ?? '/opt/homebrew/bin/ffmpeg';
const ffprobe = process.env.FFPROBE_EXECUTABLE ?? '/opt/homebrew/bin/ffprobe';
const expectedFramesPerSecond = 24;
const expectedCueCount = 23;
const expectedSourceCharacters = 553;
const expectedAssets = [
  'courtyard.png', 'street.png', 'lock.png', 'study.png', 'meal.png',
  'consult.png', 'aside.png', 'onlookers.png', 'beams.png', 'children.png',
];
const expectedPriorMovieHashes = {
  '狂人日记-男声配音版-v2-1080p.mp4': '7d709339a515cb45d01bfabfd82f7101045e40658b1be79565e851b40303681c',
  '狂人日记-字缝加强样片-v3-1080p.mp4': 'c84c2e803089c3a91c05cbbd586e62be8ff4ee41cd70844d736784c5073236a1',
  '狂人日记-节奏意象加强版-v4-1080p.mp4': '795871b25d54bd7e266842904dfa10247de69603e8035bb0e72e5d9455ab3cfa',
};

function run(binary, args, options = {}) {
  const result = spawnSync(binary, args, {encoding: 'utf8', maxBuffer: 128 * 1024 * 1024, ...options});
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

function extractFrame(frame, name, frameCount) {
  assert(Number.isInteger(frame) && frame >= 0 && frame < frameCount, `Invalid final still frame ${frame}.`);
  const file = path.join(outputDir, `final-v5-${name}.png`);
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
for (const [file, label] of [[timelinePath, 'v5 timeline'], [planPath, 'v5 voice plan'], [voiceManifestPath, 'v5 voice manifest'], [editPlanPath, 'v5 edit plan'], [mixManifestPath, 'v5 mix manifest'], [assetManifestPath, 'v5 asset manifest'], [vttPath, 'v5 captions'], [srtPath, 'v5 SRT captions'], [sourceVttPath, 'source v5 VTT'], [sourceSrtPath, 'source v5 SRT'], [videoPath, 'v5 rendered film'], [samplePath, 'v5 consult/aside sample']]) {
  assert(fs.existsSync(file), `${label} is missing: ${file}`);
}

const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const voiceManifest = JSON.parse(fs.readFileSync(voiceManifestPath, 'utf8'));
const editPlan = JSON.parse(fs.readFileSync(editPlanPath, 'utf8'));
const mixManifest = JSON.parse(fs.readFileSync(mixManifestPath, 'utf8'));
const assetManifest = JSON.parse(fs.readFileSync(assetManifestPath, 'utf8'));
const planSha256 = sha256File(planPath);
const voiceManifestSha256 = sha256File(voiceManifestPath);
const editPlanSha256 = sha256File(editPlanPath);
const mixManifestSha256 = sha256File(mixManifestPath);
const assetManifestSha256 = sha256File(assetManifestPath);
const timelineSha256 = sha256File(timelinePath);
assert.equal(timeline.fps, expectedFramesPerSecond);
assert.equal(timeline.width, 1920);
assert.equal(timeline.height, 1080);
assert(Number.isInteger(timeline.durationInFrames) && timeline.durationInFrames > 0);
assert.equal(timeline.shots.length, 15);
assert.equal(editPlan.shots.length, 15);
assert.deepEqual(timeline.shots.map((shot) => shot.id), editPlan.shots.map((shot) => shot.id), 'Timeline shot order differs from the edit plan.');
assert.equal(plan.cues.length, expectedCueCount);
assert.equal(voiceManifest.complete, true);
assert.equal(voiceManifest.cueCount, expectedCueCount);
assert.equal(voiceManifest.planPath, path.relative(root, planPath));
assert.equal(voiceManifest.planSha256, planSha256, 'Voice manifest does not identify the current source plan.');
assert.equal(voiceManifest.cues.length, expectedCueCount);
assert.equal(timeline.audioFile, 'madman/audio/suspense-v5.wav');
assert.equal(assetManifest.assets.length, expectedAssets.length);
assert.equal(timeline.source, plan.source, 'Timeline source URL differs from the approved source plan.');
assert.equal(mixManifest.source.planPath, path.relative(root, planPath));
assert.equal(mixManifest.source.planSha256, planSha256, 'Mix manifest does not identify the current source plan.');
assert.equal(mixManifest.source.providerPath, path.relative(root, voiceManifestPath));
assert.equal(mixManifest.source.providerSha256, voiceManifestSha256, 'Mix manifest does not identify the current voice manifest.');
assert.equal(mixManifest.source.editPath, path.relative(root, editPlanPath));
assert.equal(mixManifest.source.editSha256, editPlanSha256, 'Mix manifest does not identify the current edit plan.');
assert.equal(mixManifest.timeline.file, path.relative(root, timelinePath));
assert.equal(mixManifest.timeline.sha256, timelineSha256, 'Mix manifest does not identify the current timeline.');
assert.equal(mixManifest.timeline.durationInFrames, timeline.durationInFrames);
assert.equal(mixManifest.timeline.fps, timeline.fps);
assert.equal(mixManifest.output.file, `public/${timeline.audioFile}`);
assert.equal(mixManifest.output.sampleRate, 48_000);
assert.equal(mixManifest.output.channels, 2);
assert.equal(mixManifest.output.durationSeconds, timeline.durationInFrames / timeline.fps);
assert.equal(mixManifest.output.finalSilenceSeconds, 2);
assert.equal(mixManifest.cloudCalls, 0, 'The mix should reuse prepared narration without additional cloud calls.');
assert.equal(mixManifest.humanListeningReview, false, 'The audio manifest must not imply human listening was completed.');
assert.equal(mixManifest.subtitles.vtt, path.relative(root, sourceVttPath));
assert.equal(mixManifest.subtitles.srt, path.relative(root, sourceSrtPath));
assert.equal(mixManifest.subtitles.rows, 38);
assert.equal(mixManifest.subtitles.characters, expectedSourceCharacters);

const sourceText = plan.cues.map((cue) => cue.text).join('');
assert.equal(sourceText.length, expectedSourceCharacters, 'Source plan must contain exactly 553 characters.');
assert.equal(voiceManifest.cues.map((cue) => cue.text).join(''), sourceText, 'Voice manifest source text/order differs from the plan.');
const voiceCuesById = new Map(voiceManifest.cues.map((cue) => [cue.id, cue]));
assert.equal(voiceCuesById.size, expectedCueCount, 'Voice manifest has duplicate cue IDs.');

let shotCursor = 0;
const cueTimelineRecords = [];
const shotsById = new Map();
for (const [shotIndex, shot] of timeline.shots.entries()) {
  assert(!shotsById.has(shot.id), `Duplicate timeline shot ID ${shot.id}.`);
  const editShot = editPlan.shots[shotIndex];
  assert.equal(shot.section, editShot.section, `Timeline section differs from the edit plan at ${shot.id}.`);
  assert.deepEqual(shot.cues.map((cue) => cue.id), editShot.cueIds, `Timeline cue assignments differ from the edit plan at ${shot.id}.`);
  shotsById.set(shot.id, shot);
  assert.equal(shot.from, shotCursor, `Timeline gap or overlap before ${shot.id}.`);
  assert(Number.isInteger(shot.duration) && shot.duration > 0, `Invalid shot duration in ${shot.id}.`);
  assert(Array.isArray(shot.cues), `Missing cue list in ${shot.id}.`);
  for (const cue of shot.cues) {
    assert(Number.isInteger(cue.from) && Number.isInteger(cue.duration) && cue.duration > 0, `Invalid cue timing for ${cue.id}.`);
    assert(cue.from >= 0 && cue.from + cue.duration <= shot.duration, `Cue exceeds shot bounds for ${cue.id}.`);
    assert(Number.isInteger(cue.audioFrames) && cue.audioFrames > 0, `Invalid audio frame count for ${cue.id}.`);
    cueTimelineRecords.push({id: cue.id, shotId: shot.id, text: cue.text, fromFrame: shot.from + cue.from, cue});
  }
  shotCursor += shot.duration;
}
assert.equal(shotCursor, timeline.durationInFrames, 'Shot bounds do not cover the exact v5 duration.');
assert.equal(cueTimelineRecords.length, expectedCueCount);
assert.equal(mixManifest.narration.length, expectedCueCount);
const mixNarrationById = new Map(mixManifest.narration.map((cue) => [cue.id, cue]));
assert.equal(mixNarrationById.size, expectedCueCount, 'Mix manifest has duplicate narration IDs.');
assert.deepEqual(mixManifest.narration.map((cue) => cue.id), plan.cues.map((cue) => cue.id), 'Mix narration order differs from the source plan.');
for (let index = 0; index < plan.cues.length; index++) {
  const expected = plan.cues[index];
  const actual = cueTimelineRecords[index];
  const voiceRecord = voiceManifest.cues[index];
  assert.equal(actual.id, expected.id, `Timeline cue order differs at cue ${index + 1}.`);
  assert.equal(actual.shotId, expected.shotId, `Timeline shot assignment differs for ${expected.id}.`);
  assert.equal(actual.text, expected.text, `Timeline source text differs for ${expected.id}.`);
  assert.equal(voiceRecord.id, expected.id, `Voice manifest order differs at cue ${index + 1}.`);
  assert.equal(voiceRecord.shotId, expected.shotId, `Voice manifest shot differs for ${expected.id}.`);
  assert.equal(voiceRecord.text, expected.text, `Voice manifest text differs for ${expected.id}.`);
  assert.equal(voiceRecord.path, expected.audioFile, `Voice manifest audio path differs for ${expected.id}.`);
  const voicePath = path.resolve(root, voiceRecord.path);
  assert(fs.existsSync(voicePath), `Source voice file is missing for ${expected.id}.`);
  assert.equal(sha256File(voicePath), voiceRecord.sha256, `Source voice hash changed for ${expected.id}.`);
  const mixCue = mixNarrationById.get(expected.id);
  assert(mixCue, `Mix manifest is missing narration record ${expected.id}.`);
  assert.equal(mixCue.text, expected.text, `Mix manifest text differs for ${expected.id}.`);
  assert.equal(mixCue.sourcePath, expected.audioFile, `Mix manifest source path differs for ${expected.id}.`);
  assert.equal(mixCue.sourceSha256, voiceRecord.sha256, `Mix manifest voice hash differs for ${expected.id}.`);
  assert.equal(mixCue.startFrame, actual.fromFrame, `Mix narration start differs from the timeline for ${expected.id}.`);
  assert.equal(mixCue.startSample, actual.fromFrame * 2_000, `Mix narration start sample differs for ${expected.id}.`);
  assert.equal(mixCue.endSample, mixCue.startSample + mixCue.sourceSamples, `Mix source sample range is inconsistent for ${expected.id}.`);
}

const captionRows = timeline.captions;
assert(Array.isArray(captionRows) && captionRows.length > 0, 'Timeline captions are missing.');
assert.equal(captionRows.length, mixManifest.subtitles.rows, 'Timeline caption row count differs from the mix manifest.');
let lastCaptionEnd = 0;
for (const [index, caption] of captionRows.entries()) {
  assert(Number.isInteger(caption.from) && Number.isInteger(caption.duration) && caption.duration > 0, `Invalid caption timing at row ${index + 1}.`);
  assert(caption.from >= lastCaptionEnd && caption.from + caption.duration <= timeline.durationInFrames, `Captions overlap or exceed the film at row ${index + 1}.`);
  assert(typeof caption.text === 'string' && caption.text.length > 0, `Empty caption at row ${index + 1}.`);
  lastCaptionEnd = caption.from + caption.duration;
}
assert.equal(captionRows.map((caption) => caption.text).join(''), sourceText, 'Caption row concatenation differs from the 553-character source plan.');

const assetByName = new Map(assetManifest.assets.map((asset) => [path.basename(asset.file), asset]));
assert.equal(assetByName.size, expectedAssets.length, 'Asset manifest has duplicate filenames.');
const imageRecords = [];
for (const filename of expectedAssets) {
  const asset = assetByName.get(filename);
  assert(asset, `Cinema asset manifest is missing ${filename}.`);
  assert.equal(asset.source, 'AI generated for this adaptation', `Unexpected source for ${filename}.`);
  const imagePath = path.resolve(root, asset.file);
  assert(imagePath.startsWith(path.resolve(root, 'public/madman/cinema-v5') + path.sep), `Image path escapes the v5 asset directory: ${asset.file}`);
  assert(fs.existsSync(imagePath), `Generated v5 image is missing: ${imagePath}`);
  const imageProbe = probeMedia(imagePath);
  const imageStream = imageProbe.streams.find((stream) => stream.codec_type === 'video');
  assert(imageStream && imageStream.codec_name === 'png', `Generated asset is not a decodable PNG: ${filename}`);
  assert(imageStream.width >= 1600 && imageStream.height >= 900 && imageStream.width / imageStream.height > 1.7,
    `Generated image is not source-wide: ${filename} (${imageStream.width}x${imageStream.height}).`);
  assert.equal(imageStream.width, asset.nativeWidth, `Asset manifest width differs for ${filename}.`);
  assert.equal(imageStream.height, asset.nativeHeight, `Asset manifest height differs for ${filename}.`);
  run(ffmpeg, ['-v', 'error', '-i', imagePath, '-frames:v', '1', '-f', 'null', '-']);
  imageRecords.push({file: path.relative(root, imagePath), width: imageStream.width, height: imageStream.height, sha256: sha256File(imagePath)});
}

const vtt = fs.readFileSync(vttPath, 'utf8').replace(/^\uFEFF/, '').trim();
assert.deepEqual(fs.readFileSync(vttPath), fs.readFileSync(sourceVttPath), 'Player VTT copy differs from the mix-generated subtitles.');
assert.deepEqual(fs.readFileSync(srtPath), fs.readFileSync(sourceSrtPath), 'Player SRT copy differs from the mix-generated subtitles.');
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
assert.equal(vttCues.length, captionRows.length, 'VTT row count differs from timeline captions.');
for (let index = 0; index < captionRows.length; index++) {
  const expected = captionRows[index];
  const actual = vttCues[index];
  assert.equal(actual.text, expected.text, `VTT text/order differs at row ${index + 1}.`);
  const startMilliseconds = Math.round(expected.from * 1_000 / expectedFramesPerSecond);
  const endMilliseconds = Math.round((expected.from + expected.duration) * 1_000 / expectedFramesPerSecond);
  assert(Math.abs(actual.startMilliseconds - startMilliseconds) <= 1, `VTT start differs at row ${index + 1}.`);
  assert(Math.abs(actual.endMilliseconds - endMilliseconds) <= 1, `VTT end differs at row ${index + 1}.`);
}

const audioPath = path.resolve(root, 'public', timeline.audioFile);
assert(audioPath.startsWith(path.resolve(root, 'public') + path.sep), 'Mixed audio path escapes public assets.');
assert(fs.existsSync(audioPath), `Mixed v5 audio is missing: ${audioPath}`);
assert.equal(mixManifest.output.sha256, sha256File(audioPath), 'Mix manifest WAV hash differs from the mixed audio file.');
const audioProbe = probeMedia(audioPath);
const mixedAudio = audioProbe.streams.find((stream) => stream.codec_type === 'audio');
assert(mixedAudio, 'Mixed v5 audio stream is missing.');
assert.equal(Number(mixedAudio.sample_rate), 48_000);
assert.equal(mixedAudio.channels, 2);
assert.equal(mixedAudio.codec_name, 'pcm_s16le');
const durationSeconds = timeline.durationInFrames / expectedFramesPerSecond;
assert(Math.abs(Number(mixedAudio.duration) - durationSeconds) < 1 / 48_000, 'Mixed WAV duration differs from exact timeline duration.');
const mixedPcm = run(ffmpeg, [
  '-v', 'error', '-i', audioPath, '-ar', '48000', '-ac', '2', '-f', 's16le', '-acodec', 'pcm_s16le', 'pipe:1',
], {encoding: 'buffer'}).stdout;
const bytesPerSecond = 48_000 * 2 * 2;
assert.equal(mixedPcm.length, Math.round(durationSeconds * bytesPerSecond), 'Decoded mixed PCM length differs from exact timeline duration.');
const finalTwoSeconds = mixedPcm.subarray(mixedPcm.length - 2 * bytesPerSecond);
assert.equal(finalTwoSeconds.length, 2 * bytesPerSecond);
assert.equal(finalTwoSeconds.some((byte) => byte !== 0), false, 'The final two seconds of mixed PCM must be actual digital silence.');

const previousMovies = {};
for (const [filename, expectedHash] of Object.entries(expectedPriorMovieHashes)) {
  const moviePath = path.join(outputDir, filename);
  assert(fs.existsSync(moviePath), `Previously delivered movie is missing: ${moviePath}`);
  const actualHash = sha256File(moviePath);
  assert.equal(actualHash, expectedHash, `Previously delivered movie changed: ${filename}`);
  previousMovies[filename] = actualHash;
}

const videoBytes = fs.readFileSync(videoPath);
const videoSha256 = createHash('sha256').update(videoBytes).digest('hex');
const videoProbe = probeMedia(videoPath);
const videoStream = videoProbe.streams.find((stream) => stream.codec_type === 'video');
const audioStream = videoProbe.streams.find((stream) => stream.codec_type === 'audio');
assert(videoStream && audioStream, 'Rendered film is missing a video or audio stream.');
assert.equal(videoStream.codec_name, 'h264');
assert.equal(videoStream.width, 1920);
assert.equal(videoStream.height, 1080);
assert.equal(videoStream.r_frame_rate, '24/1');
assert.equal(Number(videoStream.nb_frames), timeline.durationInFrames, 'Rendered frame count differs from timeline.');
assert.equal(videoStream.pix_fmt, 'yuv420p');
assert.equal(videoStream.color_space, 'bt709');
assert.equal(videoStream.color_primaries, 'bt709');
assert.equal(videoStream.color_transfer, 'bt709');
assert.equal(videoStream.color_range, 'tv');
assert(Math.abs(Number(videoStream.duration) - durationSeconds) < 1 / expectedFramesPerSecond, 'Rendered video duration differs from exact timeline.');
assert(Math.abs(Number(videoProbe.format.duration) - durationSeconds) < 0.1, 'MP4 container duration differs from exact timeline.');
assert.equal(audioStream.codec_name, 'aac');
assert.equal(Number(audioStream.sample_rate), 48_000);
assert.equal(audioStream.channels, 2);
assert(Math.abs(Number(audioStream.duration) - durationSeconds) < 0.1, 'Encoded audio duration differs from exact timeline.');
run(ffmpeg, ['-v', 'error', '-i', videoPath, '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-']);
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
assert(peak > 0 && peak < 1, `Encoded audio peak ${peak} is silent or clipped.`);
const peakDbfs = 20 * Math.log10(peak);
const rmsDbfs = 20 * Math.log10(Math.sqrt(sumSquares / samples.length));
const fastStart = hasFastStartAtoms(videoBytes);
assert(fastStart, 'MP4 moov atom must precede mdat for fast start.');

const consult = shotsById.get('consult');
const aside = shotsById.get('aside');
assert(consult && aside, 'Diagnosis sample shots are missing.');
assert.equal(timeline.shots[timeline.shots.indexOf(consult) + 1], aside, 'Consult and aside sample shots must be adjacent.');
assert.equal(consult.from + consult.duration, aside.from, 'Consult and aside sample shots must be contiguous.');
const sampleProbe = probeMedia(samplePath);
const sampleVideo = sampleProbe.streams.find((stream) => stream.codec_type === 'video');
const sampleAudio = sampleProbe.streams.find((stream) => stream.codec_type === 'audio');
const sampleFrames = consult.duration + aside.duration;
assert(sampleVideo && sampleAudio && sampleVideo.codec_name === 'h264' && sampleAudio.codec_name === 'aac', 'Diagnosis sample H.264/AAC streams are missing.');
assert.equal(Number(sampleAudio.sample_rate), 48_000);
assert.equal(sampleAudio.channels, 2);
assert.equal(Number(sampleVideo.nb_frames), sampleFrames, 'Diagnosis sample does not cover the full consult and aside shots.');
assert(Math.abs(Number(sampleProbe.format.duration) - sampleFrames / expectedFramesPerSecond) < 0.1, 'Diagnosis sample duration differs from its shot bounds.');
run(ffmpeg, ['-v', 'error', '-i', samplePath, '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-']);

const pickForShot = (id) => {
  const shot = shotsById.get(id);
  assert(shot, `Missing shot for final still ${id}.`);
  return shot.from + Math.floor((shot.duration - 1) / 2);
};
const cueFor = (id) => {
  const found = cueTimelineRecords.find((record) => record.id === id);
  assert(found, `Missing cue for final still ${id}.`);
  return found;
};
const cueFrame = (id, offset) => {
  const {shotId, cue} = cueFor(id);
  const shot = shotsById.get(shotId);
  return Math.max(shot.from, Math.min(shot.from + shot.duration - 1, shot.from + cue.from + offset));
};
const picks = timeline.shots.map((shot) => [`mid-${shot.id}`, pickForShot(shot.id)]);
picks.push(
  ['dog', cueFrame('dog', 73)],
  ['smile', cueFrame('smile', Math.floor(cueFor('smile').cue.audioFrames / 2))],
  ['history-reveal', cueFrame('history-c', Math.floor(cueFor('history-c').cue.audioFrames * 0.9))],
  ['doctor-pulse', cueFrame('doctor', Math.floor(cueFor('doctor').cue.audioFrames / 3))],
  ['beams-before-false', cueFrame('false-weight', -1)],
  ['beams-reset-after-false', cueFrame('false-weight', 1)],
  ['epilogue-quote-end', cueFrame('cured', cueFor('cured').cue.audioFrames - 1)],
  ['ending-last', timeline.durationInFrames - 1],
);
fs.mkdirSync(outputDir, {recursive: true});
const extractedFrames = picks.map(([name, frame]) => extractFrame(frame, name, timeline.durationInFrames));

const report = {
  checkedAt: new Date().toISOString(),
  film: path.basename(videoPath),
  sha256: videoSha256,
  sizeBytes: videoBytes.length,
  sourceIntegrity: {
    source: plan.source,
    sourcePlan: {path: path.relative(root, planPath), sha256: planSha256},
    sourceVoiceManifest: {path: path.relative(root, voiceManifestPath), sha256: voiceManifestSha256},
  editPlan: {path: path.relative(root, editPlanPath), sha256: editPlanSha256},
  mixManifest: {path: path.relative(root, mixManifestPath), sha256: mixManifestSha256},
    timeline: {path: path.relative(root, timelinePath), sha256: timelineSha256},
    originalCueHashesMatchManifest: true,
    allOriginalCueTextAndOrderPreserved: true,
    earlierMoviesUnchanged: previousMovies,
  },
  timeline: {
    path: path.relative(root, timelinePath),
    sha256: timelineSha256,
    width: timeline.width,
    height: timeline.height,
    fps: timeline.fps,
    frames: timeline.durationInFrames,
    durationSeconds,
    shotCount: timeline.shots.length,
    shotsContinuousAndInBounds: true,
    cueCount: cueTimelineRecords.length,
    sourceCharacters: sourceText.length,
    captions: {rows: captionRows.length, exactSourceConcatenation: true, vttMatches: true},
  },
  subtitles: {
    vtt: {path: path.relative(root, vttPath), sha256: sha256File(vttPath), rowCount: vttCues.length},
    srt: {path: path.relative(root, srtPath), sha256: sha256File(srtPath)},
  },
  generatedImages: {source: 'AI generated for this adaptation', files: imageRecords},
  assetManifest: {path: path.relative(root, assetManifestPath), sha256: assetManifestSha256},
  audioPreparation: {
    cloudCalls: mixManifest.cloudCalls,
    humanListeningReview: mixManifest.humanListeningReview,
    finalSilenceSeconds: mixManifest.output.finalSilenceSeconds,
    sourceNarrationRecords: mixManifest.narration.length,
  },
  mixedAudio: {
    path: path.relative(root, audioPath),
    sha256: sha256File(audioPath),
    codec: mixedAudio.codec_name,
    sampleRateHz: Number(mixedAudio.sample_rate),
    channels: mixedAudio.channels,
    durationSeconds: Number(mixedAudio.duration),
    finalTwoSecondsPcmZero: true,
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
    peakDbfs,
    rmsDbfs,
    noClipping: true,
  },
  diagnosisSample: {
    file: path.basename(samplePath),
    fromFrame: consult.from,
    toFrameExclusive: aside.from + aside.duration,
    frames: sampleFrames,
    durationSeconds: sampleFrames / expectedFramesPerSecond,
    fullDecode: 'passed; video and audio, no errors',
  },
  finalFrames: {extracted: true, inspected: false, files: extractedFrames},
  browserPlayback: 'unverified; root reported local browser security policy rejected playback automation',
  humanListening: 'not performed; automated transcription is separate from human listening',
};
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({
  film: report.film,
  sha256: report.sha256,
  durationSeconds,
  frames: report.video.frames,
  sourceCharacters: sourceText.length,
  peakDbfs,
  fastStart,
  generatedImages: imageRecords.length,
  extractedFrames: extractedFrames.length,
  diagnosisSampleSeconds: report.diagnosisSample.durationSeconds,
  report: path.relative(root, reportPath),
}, null, 2));
