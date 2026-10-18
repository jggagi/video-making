import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';

const spec = JSON.parse(fs.readFileSync('src/madman/history-study-v3.json', 'utf8'));
const mix = JSON.parse(fs.readFileSync('public/madman/audio/history-study-v3-manifest.json', 'utf8'));
const movie = 'out/madman/狂人日记-字缝加强样片-v3-1080p.mp4';
const sha = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const command = (tool, args, options = {}) => execFileSync(tool, args, {encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, ...options});
assert.equal(sha('src/madman/history-study-v3.json'), mix.specSha256);
assert.equal(sha(spec.sourceTimeline), mix.sourceTimelineSha256);
assert.equal(sha('public/madman/voice-v2/manifest.json'), mix.providerManifestSha256);
for (const layer of Object.values(mix.layers)) assert.equal(sha(layer.file), layer.sha256);
for (const cue of mix.narration) assert.equal(sha(cue.file), cue.sha256);
const original = JSON.parse(fs.readFileSync(spec.sourceTimeline, 'utf8')).shots.find(s => s.id === spec.sourceShotId);
assert.equal(spec.captions.map(c => c.text).join(''), original.cues.map(c => c.text).join(''));
assert.equal(mix.narration.map(c => c.text).join(''), original.cues.map(c => c.text).join(''));
assert.equal(mix.cloudCalls, 0);
assert.equal(mix.silentInterval.peakLinear, 0);
assert.equal(spec.durationInFrames, 480);

const probe = JSON.parse(command('/opt/homebrew/bin/ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', movie]));
const video = probe.streams.find(s => s.codec_type === 'video');
const audio = probe.streams.find(s => s.codec_type === 'audio');
assert.equal(video.codec_name, 'h264');
assert.equal(video.width, 1920); assert.equal(video.height, 1080);
assert.equal(video.r_frame_rate, '24/1'); assert.equal(Number(video.nb_frames), 480);
assert.equal(Number(video.duration), 20);
assert.equal(video.pix_fmt, 'yuv420p'); assert.equal(video.color_range, 'tv');
assert.equal(video.color_space, 'bt709'); assert.equal(video.color_transfer, 'bt709'); assert.equal(video.color_primaries, 'bt709');
assert.equal(audio.codec_name, 'aac'); assert.equal(Number(audio.sample_rate), 48000); assert.equal(audio.channels, 2);
command('/opt/homebrew/bin/ffmpeg', ['-v', 'error', '-i', movie, '-f', 'null', '-']);
const decoded = command('/opt/homebrew/bin/ffmpeg', ['-v', 'error', '-i', movie, '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le', 'pipe:1'], {encoding: 'buffer'});
assert.equal(decoded.length % 8, 0);
const samples = new Float32Array(decoded.buffer, decoded.byteOffset, decoded.length / 4);
let peak = 0;
for (const value of samples) {assert(Number.isFinite(value)); peak = Math.max(peak, Math.abs(value));}
assert(peak > 0 && peak < 1);
const bytes = fs.readFileSync(movie);
const atoms = [];
for (let offset = 0; offset + 8 <= bytes.length;) {
  let size = bytes.readUInt32BE(offset);
  const name = bytes.toString('ascii', offset + 4, offset + 8);
  if (size === 1) size = Number(bytes.readBigUInt64BE(offset + 8));
  if (size === 0) size = bytes.length - offset;
  assert(size >= 8 && offset + size <= bytes.length);
  atoms.push({name, offset}); offset += size;
}
assert(atoms.find(a => a.name === 'moov').offset < atoms.find(a => a.name === 'mdat').offset);
const picks = [['opening', 40], ['print', 216], ['pause', 310], ['crack', 364], ['reveal', 420], ['ending', 479]];
for (const [name, frame] of picks) {
  command('/opt/homebrew/bin/ffmpeg', ['-v', 'error', '-y', '-i', movie, '-vf', `select=eq(n\\,${frame})`, '-frames:v', '1', `out/madman/final-history-v3-${name}.png`]);
}
const report = {movie, sha256: sha(movie), dimensions: [1920,1080], fps: 24, frames: 480, videoDurationSeconds: Number(video.duration), containerDurationSeconds: Number(probe.format.duration), colorSpace: video.color_space, colorRange: video.color_range, audio: {codec: audio.codec_name, sampleRateHz: Number(audio.sample_rate), channels: audio.channels, peakDbfs: 20 * Math.log10(peak)}, sourceTextExact: true, sourceVoiceHashesMatch: true, newCloudCalls: 0, designedPcmSilence: mix.silentInterval, fullDecode: true, fastStart: true, extractedFrames: picks, extractedFramesVisuallyReviewed: false, playerVerification: 'pending', humanListeningReview: false};
fs.writeFileSync('out/madman/validation-history-v3.json', `${JSON.stringify(report, null, 2)}\n`);
console.log(`Validated 20s/480-frame sample, AAC peak ${(20 * Math.log10(peak)).toFixed(2)} dBFS; extracted ${picks.length} final frames.`);
