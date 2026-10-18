import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderStill, renderMedia} from '@remotion/renderer';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'out');
const mode = process.argv[2] ?? 'video';
if (!['video', 'preview', 'stills', 'frame', 'landscape-check'].includes(mode)) throw new Error('Use video, preview, stills, frame, or landscape-check.');
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const concurrency = Number(process.env.REMOTION_CONCURRENCY ?? 2);
if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 4) throw new Error('Concurrency must be 1–4.');
fs.mkdirSync(out, {recursive: true});
const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts'), outDir: path.join(out, 'bundle'), onProgress: () => {}});
const browser = await openBrowser('chrome', {browserExecutable, logLevel: 'error'});
try {
  const common = {serveUrl, browserExecutable, puppeteerInstance: browser, logLevel: 'error'};
  const landscape = mode === 'landscape-check';
  const composition = await selectComposition({...common, id: landscape ? 'OneBlinkTenMillennia' : 'OneBlinkTenMillenniaPortraitV4'});
  if (composition.width !== (landscape ? 1920 : 1080) || composition.height !== (landscape ? 1080 : 1920) || composition.fps !== 60 || composition.durationInFrames !== 10800) throw new Error('Unexpected composition metadata.');
  if (['stills', 'frame', 'landscape-check'].includes(mode)) {
    const frames = mode === 'frame' ? process.argv.slice(3).map(Number) : landscape ? [120, 9600, 10799] : [0, 120, 300, 900, 1200, 1799, 2400, 3240, 4320, 4800, 4920, 6000, 6900, 7170, 7800, 9000, 9240, 9450, 9599, 9600, 9700, 10200, 10490, 10500, 10650, 10799];
    if (!frames.length || frames.some((f) => !Number.isInteger(f) || f < 0 || f >= 10800)) throw new Error('Frames must be integers 0–10799.');
    for (const frame of frames) {
      const filename = path.join(out, `portrait-v4-${landscape ? 'landscape-' : ''}frame-${String(frame).padStart(5, '0')}.png`);
      await renderStill({...common, composition, frame, output: filename, imageFormat: 'png'});
      console.log(`Frame ${frame}: ${filename}`);
    }
  } else {
    const preview = mode === 'preview';
    const outputLocation = path.join(out, preview ? 'portrait-layout-preview-v4.mp4' : 'one-blink-ten-millennia-portrait-v4.mp4');
    let lastPercent = -1;
    await renderMedia({...common, composition, outputLocation, frameRange: preview ? [9360, 10079] : undefined, codec: 'h264', pixelFormat: 'yuv420p', crf: 18, audioCodec: 'aac', audioBitrate: '192k', sampleRate: 48000, imageFormat: 'jpeg', jpegQuality: 95, concurrency, x264Preset: 'fast', metadata: {title: '一眼万年 · 竖屏版 (One Blink, Ten Millennia)', comment: 'Native 9:16 layout. Same 180 s / 60 fps timeline and unchanged Bailian narration, score and sound design.'}, onProgress: ({progress, renderedFrames, encodedFrames}) => {
      const percent = Math.floor(progress * 20) * 5;
      if (percent !== lastPercent) {lastPercent = percent; console.log(`${preview ? 'Preview' : 'Portrait'} ${percent}% | rendered ${renderedFrames} | encoded ${encodedFrames}`);}
    }});
    console.log(`Saved ${outputLocation}`);
  }
} finally {await browser.close({silent: true});}
