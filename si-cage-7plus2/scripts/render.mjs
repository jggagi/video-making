import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderStill, renderMedia} from '@remotion/renderer';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(project, 'out');
const mode = process.argv[2] ?? 'video';
if (!['stills', 'frame', 'overload', 'manifold', 'ending', 'video', 'score'].includes(mode)) throw new Error(`Unknown mode ${mode}`);
const timeline = JSON.parse(fs.readFileSync(path.join(project, 'timeline.json'), 'utf8'));
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || (fs.existsSync(chrome) ? chrome : undefined);
const concurrency = Number(process.env.REMOTION_CONCURRENCY ?? 2);
if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 4) throw new Error('REMOTION_CONCURRENCY must be 1–4.');
fs.mkdirSync(out, {recursive: true});
const serveUrl = await bundle({entryPoint: path.join(project, 'src/index.ts'), publicDir: path.join(project, 'public'), outDir: path.join(out, 'bundle-uhd-v3'), onProgress: () => {}});
const browser = await openBrowser('chrome', {browserExecutable, logLevel: 'error'});
try {
  const common = {serveUrl, browserExecutable, puppeteerInstance: browser, logLevel: 'error'};
  const composition = await selectComposition({...common, id: mode === 'stills' || mode === 'frame' ? 'CageOfSevenPlusTwoSilent' : mode === 'score' ? 'CageOfSevenPlusTwo' : 'CageOfSevenPlusTwoUhdV3'});
  if (composition.width !== 3840 || composition.height !== 2160 || composition.fps !== 60 || composition.durationInFrames !== 10800) throw new Error('Incorrect UHD composition metadata.');
  if (timeline.logicalWidth * timeline.renderScale !== composition.width || timeline.logicalHeight * timeline.renderScale !== composition.height) throw new Error('Logical canvas must scale uniformly to native UHD.');
  if (mode === 'stills' || mode === 'frame') {
    const frames = mode === 'frame' ? process.argv.slice(3).map(Number) : [0, 1080, 1199, 1200, 2100, 3300, 4600, 6000, 7200, 9000, 10200, 10799];
    if (!frames.length || frames.some((f) => !Number.isInteger(f) || f < 0 || f >= 10800)) throw new Error('Frame must be 0–10799.');
    for (const frame of frames) {
      const output = path.join(out, `uhd-v3-frame-${String(frame).padStart(5, '0')}.png`);
      await renderStill({...common, composition, frame, output, imageFormat: 'png'});
      console.log(`Frame ${frame}: ${output}`);
    }
  } else {
    const range = mode === 'overload' ? [1080, 1349] : mode === 'manifold' ? [6580, 7179] : mode === 'ending' ? [10000, 10799] : undefined;
    const outputLocation = path.join(out, mode === 'video' ? 'cage-of-seven-plus-two-uhd-v3-4k.mp4' : mode === 'score' ? 'cage-of-seven-plus-two-score-v3-4k.mp4' : `uhd-v3-${mode}-preview.mp4`);
    let previous = -1;
    await renderMedia({...common, composition, outputLocation, frameRange: range, codec: 'h264', pixelFormat: 'yuv420p', crf: 17, imageFormat: 'jpeg', jpegQuality: 98, concurrency, x264Preset: 'fast', audioCodec: 'aac', audioBitrate: '192k', sampleRate: 48000,
      metadata: {title: '7±2 的囚笼 · 4K UHD · 中文版', comment: 'Native 3840x2160/60 procedural vector rendering; Chinese narrative with technical English telemetry. Existing local soundtrack reused.'},
      onProgress: ({progress, renderedFrames}) => {const pc = Math.floor(progress * 100); if (pc !== previous) {previous = pc; console.log(`${mode}: ${pc}% (${renderedFrames} frames)`);}},
    });
    console.log(outputLocation);
  }
} finally {await browser.close({silent: true});}
