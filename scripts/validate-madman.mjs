import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';

const output = path.resolve('out/madman');
const video = path.join(output, '狂人日记-木刻意象版-v1-1080p.mp4');
const timeline = JSON.parse(fs.readFileSync('src/madman/timeline.json', 'utf8'));
const ffmpeg = process.env.FFMPEG_EXECUTABLE ?? '/opt/homebrew/bin/ffmpeg';
const ffprobe = process.env.FFPROBE_EXECUTABLE ?? '/opt/homebrew/bin/ffprobe';
function run(bin, args) {
  const result = spawnSync(bin, args, {encoding: 'utf8', maxBuffer: 6 * 1024 * 1024});
  if (result.error) throw result.error;
  assert.equal(result.status, 0, `${path.basename(bin)} failed: ${result.stderr}`);
  return result;
}
let cursor = 0;
let endOfCue = 0;
let count = 0;
for (const shot of timeline.shots) {
  assert.equal(shot.from, cursor, `Gap/overlap before ${shot.id}`);
  cursor += shot.duration;
  for (const cue of shot.cues) {
    const start = shot.from + cue.from;
    const end = start + cue.duration;
    assert(start >= endOfCue && end <= shot.from + shot.duration);
    assert(cue.duration / timeline.fps >= cue.text.length / 9, 'Insufficient reading time');
    endOfCue = end;
    count++;
  }
}
assert.equal(cursor, 2160);
assert.equal(count, 11);
const probe = JSON.parse(run(ffprobe, ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', video]).stdout);
const vs = probe.streams.find(s => s.codec_type === 'video');
const as = probe.streams.find(s => s.codec_type === 'audio');
assert(vs && as, 'Video or audio stream missing');
assert.equal(vs.codec_name, 'h264');
assert.equal(vs.width, 1920);
assert.equal(vs.height, 1080);
assert.equal(vs.r_frame_rate, '24/1');
assert.equal(vs.pix_fmt, 'yuv420p');
assert.equal(vs.color_space, 'bt709');
assert.equal(vs.color_range, 'tv');
assert.equal(Number(vs.nb_frames), timeline.durationInFrames);
assert.equal(as.codec_name, 'aac');
assert.equal(as.channels, 2);
assert.equal(Number(as.sample_rate), 48000);
assert(Math.abs(Number(probe.format.duration) - 90) < 0.1, 'Unexpected media duration');
const decode = run(ffmpeg, ['-v', 'error', '-i', video, '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-']);
assert.equal(decode.stderr.trim(), '', 'Decoder reported an error');
const levels = run(ffmpeg, ['-hide_banner', '-nostats', '-i', video, '-vn', '-af', 'astats=metadata=0:reset=0', '-f', 'null', '-']).stderr;
const peakDb = Math.max(...[...levels.matchAll(/Peak level dB: ([-\d.]+)/g)].map(m => Number(m[1])));
const rmsDb = [...levels.matchAll(/RMS level dB: ([-\d.]+)/g)].map(m => Number(m[1])).at(-1);
assert(Number.isFinite(peakDb) && peakDb < -1, 'Unexpected peak or clipping');
const bytes = fs.readFileSync(video);
const atoms = [];
for (let offset = 0; offset + 8 <= bytes.length;) {
  let size = bytes.readUInt32BE(offset);
  const type = bytes.toString('ascii', offset + 4, offset + 8);
  if (size === 1) size = Number(bytes.readBigUInt64BE(offset + 8));
  if (size === 0) size = bytes.length - offset;
  assert(size >= 8 && offset + size <= bytes.length, 'Invalid MP4 atom');
  atoms.push({type, offset, size});
  offset += size;
}
assert(atoms.find(a => a.type === 'moov')?.offset < atoms.find(a => a.type === 'mdat')?.offset, 'MP4 is not fast start');
const picks = [5.4, 13.9, 25.6, 40.625, 43.875, 47.375, 55.625, 68.375, 79.9, 88.1, 89.95];
for (const seconds of picks) run(ffmpeg, ['-v', 'error', '-ss', String(seconds), '-i', video, '-frames:v', '1', '-y', path.join(output, `final-${String(seconds).replace('.', '-')}.png`)]);
const report = {
  checkedAt: new Date().toISOString(),
  film: path.basename(video),
  sizeBytes: bytes.length,
  sha256: createHash('sha256').update(bytes).digest('hex'),
  video: {codec: vs.codec_name, width: vs.width, height: vs.height, fps: vs.r_frame_rate, frames: Number(vs.nb_frames), durationSeconds: Number(vs.duration), pixelFormat: vs.pix_fmt, colorSpace: vs.color_space, colorRange: vs.color_range},
  audio: {codec: as.codec_name, sampleRateHz: Number(as.sample_rate), channels: as.channels, durationSeconds: Number(as.duration), peakDbfs: peakDb, rmsDbfs: rmsDb, humanListeningReview: false},
  containerDurationSeconds: Number(probe.format.duration),
  fastStart: true,
  fullDecode: 'passed; video and audio, no errors',
  timeline: {continuous: true, cueCount: count, cuesWithinBounds: true, captionsOrderedAndNonoverlapping: true, readingTimeChecked: true},
  representativeStills: {frames: [130,334,615,975,1007,1053,1335,1641,1918,2113,2159], inspected: true},
  motionSample: {frames: [1080,1223], browserPlayback: 'completed with no media error', transitionMidpointInspected: true},
  finalFrameSamples: {timesSeconds: picks, inspected: false},
  finalPlayer: {checked: false},
  source: timeline.source,
  visuals: {sourceType: 'AI-generated woodcut-style original illustrations plus React/SVG', nativeRasterWidth: 1672, nativeRasterHeight: 941},
 现场试播: '未进行'
};
fs.writeFileSync(path.join(output, 'validation.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({decode: report.fullDecode, video: report.video, audio: report.audio, fastStart: report.fastStart, sha256: report.sha256}, null, 2));
