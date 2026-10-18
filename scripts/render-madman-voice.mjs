import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const mode = process.argv[2] ?? 'video';
const outputDir = path.resolve('out/madman');
const bundleDir = path.join(outputDir, 'bundle-voice-v2');
const timelinePath = path.resolve('src/madman/voiced-timeline.json');
const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const allowedModes = new Set(['video', 'sample', 'stills', 'frame']);

if (!allowedModes.has(mode)) throw new Error(`Unknown mode "${mode}". Choose video, sample, stills, or frame <number>.`);
if (timeline.fps !== 24 || timeline.width !== 1920 || timeline.height !== 1080) {
  throw new Error('Voiced Madman timeline must be 1920x1080 at 24 fps.');
}
if (!Number.isInteger(timeline.durationInFrames) || timeline.durationInFrames < 1 || timeline.durationInFrames > 2_880) {
  throw new Error('Voiced Madman timeline duration must be between 1 and 2880 frames.');
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
    id: 'MadmanDiaryVoiced',
    browserExecutable,
    puppeteerInstance: browser,
    logLevel: 'error',
  });
  if (composition.durationInFrames !== timeline.durationInFrames) {
    throw new Error(`Composition duration ${composition.durationInFrames} does not match voiced timeline ${timeline.durationInFrames}.`);
  }

  if (mode === 'stills' || mode === 'frame') {
    let picks;
    if (mode === 'frame') {
      const frame = Number(process.argv[3]);
      if (frame < 0 || frame >= timeline.durationInFrames) {
        throw new Error(`Frame must be between 0 and ${timeline.durationInFrames - 1}.`);
      }
      picks = [[`frame-${frame}`, frame]];
    } else {
      picks = timeline.shots.map((shot) => [
        shot.id,
        shot.from + Math.min(shot.duration - 1, Math.round(shot.duration * 0.72)),
      ]);
      const history = timeline.shots.find((shot) => shot.id === 'history');
      if (!history || history.cues.length < 3) throw new Error('Expected three caption cues in the history shot.');
      const thirdCue = history.cues[2];
      const revealOffset = Math.min(history.duration - 1, thirdCue.from + 60);
      picks.push(
        ['history-reveal', history.from + revealOffset],
        ['ending', timeline.durationInFrames - 1],
      );
    }

    for (const [name, frame] of picks) {
      const output = path.join(outputDir, `still-voice-v2-${name}.png`);
      await renderStill({
        serveUrl,
        composition,
        output,
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
    const moon = timeline.shots.find((shot) => shot.id === 'moon');
    if (!moon || moon.from !== 144 || moon.duration < 1) throw new Error('Expected the voiced moon shot to begin at frame 144.');
    const sampleEnd = moon.from + moon.duration - 1;
    if (sampleEnd >= timeline.durationInFrames) throw new Error('Moon sample frame range exceeds the voiced composition.');
    let lastProgress = -1;
    await renderMedia({
      serveUrl,
      composition,
      outputLocation: path.join(outputDir, isSample
        ? 'voice-v2-sample.mp4'
        : '狂人日记-男声配音版-v2-1080p.mp4'),
      codec: 'h264',
      audioCodec: 'aac',
      audioBitrate: '192k',
      pixelFormat: 'yuv420p',
      colorSpace: 'bt709',
      imageFormat: 'png',
      crf: 18,
      concurrency: 1,
      ...(isSample ? {frameRange: [moon.from, sampleEnd]} : {}),
      browserExecutable,
      puppeteerInstance: browser,
      logLevel: 'error',
      metadata: {
        title: '狂人日记 · 男声配音版 v2',
        artist: '鲁迅',
        comment: '鲁迅原文节选 · 百炼合成男声（龙三叔） · 原创氛围声音',
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
