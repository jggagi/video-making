import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const mode = process.argv[2] ?? 'video';
const outputDir = path.resolve('out/madman');
const bundleDir = path.join(outputDir, 'bundle-history-v3');
const specPath = path.resolve('src/madman/history-study-v3.json');
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const allowedModes = new Set(['video', 'stills', 'frame']);

if (!allowedModes.has(mode)) throw new Error(`Unknown mode "${mode}". Choose video, stills, or frame <number>.`);

const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
if (spec.fps !== 24 || spec.width !== 1920 || spec.height !== 1080 || spec.durationInFrames !== 480) {
  throw new Error('History study spec must be 1920x1080 at 24 fps for exactly 480 frames.');
}
if (mode === 'frame' && !Number.isInteger(Number(process.argv[3]))) {
  throw new Error('frame mode requires an integer frame number.');
}

fs.mkdirSync(outputDir, {recursive: true});
const serveUrl = await bundle({
  entryPoint: path.resolve('src/index.ts'),
  outDir: bundleDir,
  onProgress: () => {},
});
const browser = await openBrowser('chrome', {
  browserExecutable,
  logLevel: 'error',
});

try {
  const composition = await selectComposition({
    serveUrl,
    id: 'MadmanHistoryStudy',
    browserExecutable,
    puppeteerInstance: browser,
    logLevel: 'error',
  });
  if (composition.durationInFrames !== spec.durationInFrames
    || composition.fps !== spec.fps
    || composition.width !== spec.width
    || composition.height !== spec.height) {
    throw new Error(
      `Composition ${composition.width}x${composition.height} at ${composition.fps} fps for ${composition.durationInFrames} frames does not match the history study spec.`,
    );
  }

  if (mode === 'stills' || mode === 'frame') {
    let picks;
    if (mode === 'frame') {
      const frame = Number(process.argv[3]);
      if (frame < 0 || frame >= spec.durationInFrames) {
        throw new Error(`Frame must be between 0 and ${spec.durationInFrames - 1}.`);
      }
      picks = [[`still-history-v3-frame-${frame}.png`, frame]];
    } else {
      picks = [
        ['still-history-v3-opening.png', 40],
        ['still-history-v3-print.png', 216],
        ['still-history-v3-pause.png', 310],
        ['still-history-v3-crack.png', 364],
        ['still-history-v3-reveal.png', 404],
        ['still-history-v3-ending.png', 479],
      ];
    }

    for (const [filename, frame] of picks) {
      await renderStill({
        serveUrl,
        composition,
        output: path.join(outputDir, filename),
        frame,
        browserExecutable,
        puppeteerInstance: browser,
        imageFormat: 'png',
        logLevel: 'error',
      });
      console.log(`${filename}: ${frame}`);
    }
  } else {
    let lastProgress = -1;
    await renderMedia({
      serveUrl,
      composition,
      outputLocation: path.join(outputDir, '狂人日记-字缝加强样片-v3-1080p.mp4'),
      codec: 'h264',
      audioCodec: 'aac',
      audioBitrate: '192k',
      pixelFormat: 'yuv420p',
      colorSpace: 'bt709',
      imageFormat: 'png',
      crf: 18,
      concurrency: 1,
      browserExecutable,
      puppeteerInstance: browser,
      logLevel: 'error',
      metadata: {
        title: '狂人日记 · 字缝加强样片 v3',
        artist: '鲁迅',
        comment: '《狂人日记》原文节选 · 百炼合成男声',
      },
      onProgress: ({progress}) => {
        const percent = Math.floor(progress * 20) * 5;
        if (percent !== lastProgress) {
          console.log(`Rendering ${percent}%`);
          lastProgress = percent;
        }
      },
    });
  }
} finally {
  await browser.close({silent: true});
}
