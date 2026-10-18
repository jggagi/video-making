import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'out');
const plan = JSON.parse(fs.readFileSync(path.join(root, 'xhs-timeline.json'), 'utf8'));
const mode = process.argv[2] ?? 'video';
const modes = ['stills', 'cover', 'preview', 'video', 'publish', 'captions'];
if (!modes.includes(mode)) throw new Error(`Mode must be ${modes.join(', ')}`);
fs.mkdirSync(out, {recursive: true});
const run = (args) => {
  const result = spawnSync('ffmpeg', args, {stdio: 'inherit'});
  if (result.status !== 0) throw new Error('FFmpeg export failed.');
};
const master = path.join(out, 'cage-of-seven-plus-two-xhs-v1-4k.mp4');
const publish = path.join(out, 'cage-of-seven-plus-two-xhs-v1-1080x1920.mp4');
const makePublish = () => {
  if (!fs.existsSync(master)) throw new Error('Render the native 4K portrait master first.');
  run(['-hide_banner', '-v', 'error', '-i', master, '-map', '0:v:0', '-map', '0:a:0', '-vf', 'scale=1080:1920:flags=lanczos', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', '-metadata', 'title=7±2 的囚笼 · 小红书60秒版', '-y', publish]);
  console.log(publish);
};
const timestamp = (f) => {
  const ms = Math.round(f / plan.fps * 1000);
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
};
const captions = plan.cues.flatMap((cue) => cue.captionParts ? cue.captionParts.map((part) => ({from: cue.startFrame + part.from, to: cue.startFrame + part.to, lines: part.lines})) : [{from: cue.startFrame, to: cue.endFrame, lines: cue.displayLines}]);
const srt = captions.map((c, i) => `${i + 1}\n${timestamp(c.from)} --> ${timestamp(c.to)}\n${c.lines.join('\n')}\n`).join('\n');
fs.writeFileSync(path.join(out, 'cage-of-seven-plus-two-xhs-v1-zh.srt'), srt);
if (mode === 'captions') {console.log('Exported Chinese sentence/clause captions.'); process.exit(0);}
if (mode === 'publish') {makePublish(); process.exit(0);}

const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || (fs.existsSync(chrome) ? chrome : undefined);
const concurrency = Number(process.env.REMOTION_CONCURRENCY ?? 2);
if (![1, 2, 3, 4].includes(concurrency)) throw new Error('REMOTION_CONCURRENCY must be 1–4.');
const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts'), publicDir: path.join(root, 'public'), outDir: path.join(out, 'bundle-xhs-v1'), onProgress: () => {}});
const browser = await openBrowser('chrome', {browserExecutable, logLevel: 'error'});
try {
  const common = {serveUrl, browserExecutable, puppeteerInstance: browser, logLevel: 'error'};
  const composition = await selectComposition({...common, id: mode === 'stills' ? 'CageOfSevenPlusTwoXhsSilent' : mode === 'cover' ? 'CageOfSevenPlusTwoXhsCover' : 'CageOfSevenPlusTwoXhsV1'});
  if (mode === 'cover') {
    await renderStill({...common, composition, frame: 0, output: path.join(out, 'xhs-v1-cover-4k.png'), imageFormat: 'png'});
    run(['-v', 'error', '-i', path.join(out, 'xhs-v1-cover-4k.png'), '-vf', 'scale=1080:1440:flags=lanczos', '-q:v', '2', '-frames:v', '1', '-y', path.join(out, 'cage-of-seven-plus-two-xhs-v1-cover-3x4.jpg')]);
    console.log('Exported 3:4 cover, 2160×2880 PNG and 1080×1440 JPEG.');
  } else {
    if (composition.width !== 2160 || composition.height !== 3840 || composition.fps !== 60 || composition.durationInFrames !== 3600) throw new Error('Incorrect portrait composition metadata.');
    if (mode === 'stills') {
      for (const frame of [0, 35, 36, 420, 900, 1500, 1800, 2130, 2400, 2850, 3020, 3200, 3500, 3599]) {
        await renderStill({...common, composition, frame, output: path.join(out, `xhs-v1-frame-${String(frame).padStart(4, '0')}.png`), imageFormat: 'png'});
        console.log(`Portrait still ${frame}`);
      }
    } else {
      const preview = mode === 'preview';
      let previous = -1;
      const outputLocation = preview ? path.join(out, 'xhs-v1-opening-preview.mp4') : master;
      await renderMedia({...common, composition, outputLocation, frameRange: preview ? [0, 359] : undefined, codec: 'h264', pixelFormat: 'yuv420p', crf: 17, imageFormat: 'jpeg', jpegQuality: 98, concurrency, x264Preset: 'fast', audioCodec: 'aac', audioBitrate: '192k', sampleRate: 48000,
        metadata: {title: '7±2 的囚笼 · 60秒竖屏精剪', comment: 'Native 2160x3840/60 portrait composition. Conceptual superintelligence thought experiment; cached Bailian narration and original procedural music.'},
        onProgress: ({progress, renderedFrames}) => {const pc = Math.floor(progress * 100); if (pc !== previous) {previous = pc; console.log(`${mode}: ${pc}% (${renderedFrames} frames)`);}},
      });
      console.log(outputLocation);
    }
  }
} finally {await browser.close({silent: true});}
if (mode === 'video') makePublish();
