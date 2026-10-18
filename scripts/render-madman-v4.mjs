import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const mode = process.argv[2] ?? 'video';
const outputDir = path.resolve('out/madman');
const bundleDir = path.join(outputDir, 'bundle-full-v4');
const timelinePath = path.resolve('src/madman/full-v4-timeline.json');
const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const allowedModes = new Set(['video', 'stills', 'frame', 'sample']);
const filmPath = path.join(outputDir, '狂人日记-节奏意象加强版-v4-1080p.mp4');
const samplePath = path.join(outputDir, 'full-v4-transition-sample.mp4');

if (!allowedModes.has(mode)) throw new Error(`Unknown mode "${mode}". Choose video, stills, frame <number>, or sample.`);
if (timeline.fps !== 24 || timeline.width !== 1920 || timeline.height !== 1080 || timeline.durationInFrames !== 1_896) {
  throw new Error('Full v4 timeline must be 1920x1080 at 24 fps for exactly 1896 frames.');
}
if (!Array.isArray(timeline.shots) || timeline.shots.length !== 8) {
  throw new Error('Full v4 timeline must contain exactly eight shots.');
}
if (mode === 'frame' && !Number.isInteger(Number(process.argv[3]))) {
  throw new Error('frame mode requires an integer frame number.');
}

let shotCursor = 0;
let cueCount = 0;
for (const shot of timeline.shots) {
  if (!Number.isInteger(shot.from) || shot.from !== shotCursor || !Number.isInteger(shot.duration) || shot.duration < 1) {
    throw new Error(`Full v4 timeline has a gap, overlap, or invalid duration at ${shot.id}.`);
  }
  shotCursor += shot.duration;
  cueCount += shot.cues.length;
}
if (shotCursor !== timeline.durationInFrames || cueCount !== 11) {
  throw new Error(`Full v4 timeline must cover 1896 continuous frames and contain 11 original cues; found ${shotCursor} frames and ${cueCount} cues.`);
}

const pickForShot = (id, offset) => {
  const shot = timeline.shots.find((item) => item.id === id);
  if (!shot || offset < 0 || offset >= shot.duration) throw new Error(`Cannot select frame ${offset} for shot ${id}.`);
  return shot.from + offset;
};
const stillPicks = [
  ['title', 85],
  ['moon', pickForShot('moon', 108)],
  ['watch', pickForShot('watch', 72)],
  ['watch-left', pickForShot('watch', 168)],
  ['watch-right', pickForShot('watch', 228)],
  ['history', pickForShot('history', 216)],
  ['history-reveal', pickForShot('history', 420)],
  ['question', pickForShot('question', 96)],
  ['complicity', pickForShot('complicity', 192)],
  ['children', pickForShot('children', 144)],
  ['plea', pickForShot('plea', 96)],
  ['ending', timeline.durationInFrames - 1],
];
if (mode === 'frame') {
  const frame = Number(process.argv[3]);
  if (frame < 0 || frame >= timeline.durationInFrames) {
    throw new Error(`Frame must be between 0 and ${timeline.durationInFrames - 1}.`);
  }
}

const watch = timeline.shots.find((shot) => shot.id === 'watch');
const history = timeline.shots.find((shot) => shot.id === 'history');
if (!watch || !history || watch.from + watch.duration !== history.from) {
  throw new Error('Expected adjacent watch and history shots for the transition sample.');
}
const sampleFrameRange = [watch.from + watch.duration - 48, history.from + 48 - 1];
if (sampleFrameRange[0] < watch.from || sampleFrameRange[1] >= history.from + history.duration) {
  throw new Error('The four-second watch/history sample is outside its shot bounds.');
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
    id: 'MadmanDiaryEnhanced',
    browserExecutable,
    puppeteerInstance: browser,
    logLevel: 'error',
  });
  if (composition.durationInFrames !== timeline.durationInFrames
    || composition.fps !== timeline.fps
    || composition.width !== timeline.width
    || composition.height !== timeline.height) {
    throw new Error(
      `Composition ${composition.width}x${composition.height} at ${composition.fps} fps for ${composition.durationInFrames} frames does not match full-v4 timeline.`,
    );
  }

  if (mode === 'stills' || mode === 'frame') {
    const picks = mode === 'frame'
      ? [[`frame-v4-${Number(process.argv[3])}`, Number(process.argv[3])]]
      : stillPicks.map(([name, frame]) => [`still-v4-${name}`, frame]);
    for (const [name, frame] of picks) {
      await renderStill({
        serveUrl,
        composition,
        output: path.join(outputDir, `${name}.png`),
        frame,
        browserExecutable,
        puppeteerInstance: browser,
        imageFormat: 'png',
        logLevel: 'error',
      });
      console.log(`${name}: ${frame}`);
    }
  } else {
    const isSample = mode === 'sample';
    let lastProgress = -1;
    await renderMedia({
      serveUrl,
      composition,
      outputLocation: isSample ? samplePath : filmPath,
      codec: 'h264',
      audioCodec: 'aac',
      audioBitrate: '192k',
      pixelFormat: 'yuv420p',
      colorSpace: 'bt709',
      imageFormat: 'png',
      crf: 18,
      concurrency: 1,
      ...(isSample ? {frameRange: sampleFrameRange} : {}),
      browserExecutable,
      puppeteerInstance: browser,
      logLevel: 'error',
      metadata: {
        title: '狂人日记 · 节奏与意象加强版 v4',
        artist: '鲁迅',
        comment: '《狂人日记》原文节选 · 百炼合成男声 · 原创意象',
      },
      onProgress: ({progress}) => {
        const percent = Math.floor(progress * 20) * 5;
        if (percent !== lastProgress) {
          console.log(`${isSample ? 'Sample' : 'Rendering'} ${percent}%`);
          lastProgress = percent;
        }
      },
    });
    if (isSample) console.log(`Transition sample frames ${sampleFrameRange[0]}-${sampleFrameRange[1]} (4 seconds).`);
  }
} finally {
  await browser.close({silent: true});
}
