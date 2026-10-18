import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const mode = process.argv[2] ?? 'video';
const outputDir = path.resolve('out/madman');
const bundleDir = path.join(outputDir, 'bundle');
const timeline = JSON.parse(fs.readFileSync('src/madman/timeline.json', 'utf8'));
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const allowedModes = new Set(['stills', 'frame', 'sample', 'video']);

if (!allowedModes.has(mode)) throw new Error(`Unknown mode "${mode}". Choose stills, frame <number>, sample, or video.`);
if (timeline.fps !== 24 || timeline.durationInFrames !== 2_160) {
  throw new Error('Madman render utility expects the packet timeline at 24 fps and 2160 frames.');
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
    id: 'MadmanDiary',
    browserExecutable,
    puppeteerInstance: browser,
    logLevel: 'error',
  });

  if (mode === 'stills' || mode === 'frame') {
    let picks;
    if (mode === 'frame') {
      const frame = Number(process.argv[3]);
      if (frame < 0 || frame >= composition.durationInFrames) {
        throw new Error(`Frame must be between 0 and ${composition.durationInFrames - 1}.`);
      }
      picks = [['frame', frame]];
    } else {
      picks = timeline.shots.map((shot) => [
        shot.id,
        shot.from + Math.min(shot.duration - 1, Math.round(shot.duration * (shot.id === 'title' ? 0.9 : 0.72))),
      ]);
      const history = timeline.shots.find((shot) => shot.id === 'history');
      if (!history || history.cues.length < 3) throw new Error('Expected the three history captions from the packet timeline.');
      const revealCue = history.cues[1];
      const extremeCue = history.cues[2];
      picks.push(
        ['history-reveal', history.from + revealCue.from + revealCue.duration - 1],
        ['history-extreme', history.from + extremeCue.from + Math.floor(extremeCue.duration * 0.55)],
        ['ending', timeline.durationInFrames - 1],
      );
    }

    for (const [name, frame] of picks) {
      await renderStill({
        serveUrl,
        composition,
        output: path.join(outputDir, `still-${name}.png`),
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
      outputLocation: path.join(outputDir, isSample
        ? 'sample.mp4'
        : '狂人日记-木刻意象版-v1-1080p.mp4'),
      codec: 'h264',
      audioCodec: 'aac',
      audioBitrate: '192k',
      pixelFormat: 'yuv420p',
      colorSpace: 'bt709',
      imageFormat: 'png',
      crf: 18,
      concurrency: 1,
      ...(isSample ? {frameRange: [1080, 1223]} : {}),
      browserExecutable,
      puppeteerInstance: browser,
      logLevel: 'error',
      metadata: {
        title: '狂人日记 · 木刻意象版 v1',
        artist: '鲁迅',
        comment: '90 秒原文节选 · 本地程序合成氛围声',
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
