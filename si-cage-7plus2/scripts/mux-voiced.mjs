import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createHash} from 'node:crypto';
const run = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'out');
const original = path.join(out, 'cage-of-seven-plus-two-1080p.mp4');
const soundtrack = path.join(root, 'public/audio-voiced-v2/soundtrack.wav');
const output = path.join(out, 'cage-of-seven-plus-two-voiced-v2-1080p.mp4');
if (!fs.existsSync(soundtrack)) throw new Error('Run voice:generate and voice:mix first.');
if (!fs.existsSync(original)) {
  throw new Error('Historical 1080p base video is missing. Use its v2 source archive to rebuild it, or npm run render for the current native UHD edition.');
}
await run('ffmpeg', ['-v', 'error', '-i', original, '-i', soundtrack, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-t', '180', '-movflags', '+faststart', '-metadata', 'title=7±2 的囚笼 / 百炼配音版 v2', '-metadata', 'comment=Original video stream preserved; Bailian narration with original procedural score and effects.', '-y', output], {timeout: 180000, maxBuffer: 2 * 1024 * 1024});
const hashVideo = async (file) => (await run('ffmpeg', ['-v', 'error', '-i', file, '-map', '0:v:0', '-c:v', 'copy', '-f', 'hash', '-hash', 'sha256', '-'], {timeout: 180000})).stdout.trim();
const before = await hashVideo(original), after = await hashVideo(output);
if (before !== after) throw new Error('Video stream changed during audio replacement.');
const report = {status: 'PASS', sourceVideo: path.relative(root, original), output: path.relative(root, output), videoStreamHash: after, videoStreamPreserved: true, sha256: createHash('sha256').update(fs.readFileSync(output)).digest('hex')};
fs.writeFileSync(path.join(out, 'voiced-v2-mux-manifest.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
