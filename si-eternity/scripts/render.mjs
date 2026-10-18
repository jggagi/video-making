import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderStill, renderMedia} from '@remotion/renderer';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(project, 'out');
const mode = process.argv[2] ?? 'voiced';
if (!['stills', 'sample', 'video', 'frame', 'voiced', 'sample-voiced', 'titles', 'opening-voiced', 'ending-voiced'].includes(mode)) throw new Error(`Unknown render mode: ${mode}`);
const voiced = ['voiced', 'sample-voiced', 'opening-voiced', 'ending-voiced'].includes(mode);
const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || (fs.existsSync(macChrome) ? macChrome : undefined);
const concurrency = Number(process.env.REMOTION_CONCURRENCY ?? 2);
if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 4) throw new Error('REMOTION_CONCURRENCY must be an integer from 1 to 4.');
fs.mkdirSync(output, {recursive: true});
const serveUrl = await bundle({entryPoint: path.join(project, 'src/index.ts'), outDir: path.join(output, 'bundle'), onProgress: () => {}});
const browser = await openBrowser('chrome', {browserExecutable, logLevel: 'error'});
try {
  const common = {serveUrl, browserExecutable, puppeteerInstance: browser, logLevel: 'error'};
  const composition = await selectComposition({...common, id: voiced ? 'OneBlinkTenMillenniaVoicedV3' : 'OneBlinkTenMillennia'});
  if (composition.width !== 1920 || composition.height !== 1080 || composition.fps !== 60 || composition.durationInFrames !== 10800) {
    throw new Error('Composition metadata does not match the required 1080p / 60 fps / 180 s specification.');
  }
  if (mode === 'stills' || mode === 'frame' || mode === 'titles') {
    const frames = mode === 'frame' ? [Number(process.argv[3])] : mode === 'titles' ? [60, 120, 240, 359, 360, 9600, 9700, 10200, 10490, 10500, 10560, 10650, 10799] : [180, 870, 1240, 1740, 2400, 3240, 4350, 4920, 6120, 6900, 7170, 7860, 9120, 9480, 9599, 9600, 9810, 10440, 10720];
    if (frames.some((f) => !Number.isInteger(f) || f < 0 || f >= 10800)) throw new Error('Frame must be an integer from 0 to 10799.');
    for (const frame of frames) {
      const filename = path.join(output, `v3-frame-${String(frame).padStart(5, '0')}.png`);
      await renderStill({...common, composition, frame, output: filename, imageFormat: 'png'});
      console.log(`Rendered frame ${frame} → ${filename}`);
    }
  } else {
    const sample = ['sample', 'sample-voiced', 'opening-voiced', 'ending-voiced'].includes(mode);
    const filename = voiced
      ? (mode === 'opening-voiced' ? 'opening-title-v3.mp4' : mode === 'ending-voiced' ? 'ending-title-v3.mp4' : sample ? 'one-shot-preview-voiced-v3.mp4' : 'one-blink-ten-millennia-v3.mp4')
      : (sample ? 'one-shot-preview-v3.mp4' : 'one-blink-ten-millennia-silent-v3.mp4');
    const outputLocation = path.join(output, filename);
    let previous = -1;
    await renderMedia({
      ...common, composition, outputLocation,
      frameRange: mode === 'opening-voiced' ? [0, 479] : mode === 'ending-voiced' ? [10440, 10799] : sample ? [9360, 9839] : undefined,
      codec: 'h264', pixelFormat: 'yuv420p', crf: 18,
      ...(voiced ? {audioCodec: 'aac', audioBitrate: '192k', sampleRate: 48000} : {}),
      imageFormat: 'jpeg', jpegQuality: 95,
      concurrency, x264Preset: 'fast',
      metadata: {title: '一眼万年 (One Blink, Ten Millennia)', comment: 'Deterministic procedural visual essay. 500 ms / 10,000 subjective years; normalized reference time map.'},
      onProgress: ({progress, renderedFrames, encodedFrames}) => {
        const percent = Math.floor(progress * 20) * 5;
        if (percent !== previous) {
          previous = percent;
          console.log(`${sample ? 'Preview' : 'Film'} ${percent}% | rendered ${renderedFrames} | encoded ${encodedFrames}`);
        }
      },
    });
    console.log(`Saved ${outputLocation}`);
  }
} finally {
  await browser.close({silent: true});
}
