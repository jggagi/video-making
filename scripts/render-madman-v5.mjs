import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const mode = process.argv[2] ?? 'video';
const outputDir = path.resolve('out/madman');
const bundleDir = path.join(outputDir, 'bundle-cinema-v5');
const timelinePath = path.resolve('src/madman/suspense-v5-timeline.json');
const planPath = path.resolve('public/madman/voice-v5/plan.json');
const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const allowedModes = new Set(['video', 'stills', 'frame', 'sample']);
const filmPath = path.join(outputDir, '狂人日记-心理悬疑版-v5-1080p.mp4');
const samplePath = path.join(outputDir, 'cinema-v5-diagnosis-sample.mp4');

if (!allowedModes.has(mode)) throw new Error(`Unknown mode "${mode}". Choose video, stills, frame <number>, or sample.`);
if (timeline.fps !== 24 || timeline.width !== 1920 || timeline.height !== 1080
  || !Number.isInteger(timeline.durationInFrames) || timeline.durationInFrames < 1) {
  throw new Error('The v5 timeline must provide a positive frame duration at 1920x1080 and 24 fps.');
}
if (!Array.isArray(timeline.shots) || timeline.shots.length !== 15) {
  throw new Error('The v5 timeline must contain exactly fifteen shots.');
}
if (!Array.isArray(plan.cues) || plan.cues.length !== 23) {
  throw new Error('The v5 source plan must contain exactly 23 cues.');
}
if (mode === 'frame' && !Number.isInteger(Number(process.argv[3]))) {
  throw new Error('frame mode requires an integer frame number.');
}

let shotCursor = 0;
let cueCount = 0;
const cuesById = new Map();
for (const shot of timeline.shots) {
  if (!Number.isInteger(shot.from) || shot.from !== shotCursor
    || !Number.isInteger(shot.duration) || shot.duration < 1 || !Array.isArray(shot.cues)) {
    throw new Error(`The v5 timeline has a gap, overlap, or invalid duration at ${shot.id}.`);
  }
  for (const cue of shot.cues) {
    if (cuesById.has(cue.id) || !Number.isInteger(cue.from) || !Number.isInteger(cue.duration)
      || cue.from < 0 || cue.duration < 1 || cue.from + cue.duration > shot.duration
      || !Number.isInteger(cue.audioFrames) || cue.audioFrames < 1) {
      throw new Error(`The v5 timeline has an invalid or duplicate cue in ${shot.id}.`);
    }
    cuesById.set(cue.id, {shot, cue});
    cueCount++;
  }
  shotCursor += shot.duration;
}
if (shotCursor !== timeline.durationInFrames || cueCount !== 23) {
  throw new Error(`The v5 timeline must cover ${timeline.durationInFrames} continuous frames and contain 23 cues; found ${shotCursor} frames and ${cueCount} cues.`);
}
const sourceText = plan.cues.map((cue) => cue.text).join('');
const timelineText = timeline.shots.flatMap((shot) => shot.cues.map((cue) => cue.text)).join('');
if (sourceText.length !== 553 || timelineText !== sourceText) {
  throw new Error('The v5 timeline cue text must preserve the 553-character source plan in order.');
}

const shotById = (id) => {
  const shot = timeline.shots.find((item) => item.id === id);
  if (!shot) throw new Error(`The v5 timeline is missing shot ${id}.`);
  return shot;
};
const cueById = (id) => {
  const found = cuesById.get(id);
  if (!found) throw new Error(`The v5 timeline is missing cue ${id}.`);
  return found;
};
const clampFrame = (frame, shot) => Math.max(shot.from, Math.min(shot.from + shot.duration - 1, frame));
const cueFrame = (id, offset) => {
  const {shot, cue} = cueById(id);
  return clampFrame(shot.from + cue.from + offset, shot);
};

const stillPicks = timeline.shots.map((shot) => [
  `mid-${shot.id}`,
  shot.from + Math.floor((shot.duration - 1) / 2),
]);
stillPicks.push(
  ['dog', cueFrame('dog', 73)],
  ['smile', cueFrame('smile', Math.floor(cueById('smile').cue.audioFrames / 2))],
  ['history-reveal', cueFrame('history-c', Math.floor(cueById('history-c').cue.audioFrames * 0.9))],
  ['doctor-pulse', cueFrame('doctor', Math.floor(cueById('doctor').cue.audioFrames / 3))],
  ['beams-before-false', cueFrame('false-weight', -1)],
  ['beams-reset-after-false', cueFrame('false-weight', 1)],
  ['epilogue-quote-end', cueFrame('cured', cueById('cured').cue.audioFrames - 1)],
  ['ending-last', timeline.durationInFrames - 1],
);

if (mode === 'frame') {
  const frame = Number(process.argv[3]);
  if (frame < 0 || frame >= timeline.durationInFrames) {
    throw new Error(`Frame must be between 0 and ${timeline.durationInFrames - 1}.`);
  }
}

const consult = shotById('consult');
const aside = shotById('aside');
if (timeline.shots[timeline.shots.indexOf(consult) + 1] !== aside
  || consult.from + consult.duration !== aside.from) {
  throw new Error('The v5 diagnosis sample expects contiguous consult and aside shots.');
}
const sampleFrameRange = [consult.from, aside.from + aside.duration - 1];

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
    id: 'MadmanDiarySuspense',
    browserExecutable,
    puppeteerInstance: browser,
    logLevel: 'error',
  });
  if (composition.durationInFrames !== timeline.durationInFrames
    || composition.fps !== timeline.fps
    || composition.width !== timeline.width
    || composition.height !== timeline.height) {
    throw new Error(
      `Composition ${composition.width}x${composition.height} at ${composition.fps} fps for ${composition.durationInFrames} frames does not match the v5 timeline.`,
    );
  }

  if (mode === 'stills' || mode === 'frame') {
    const picks = mode === 'frame'
      ? [[`still-v5-frame-${Number(process.argv[3])}`, Number(process.argv[3])]]
      : stillPicks.map(([name, frame]) => [`still-v5-${name}`, frame]);
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
      console.log(`${name}: frame ${frame}`);
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
        title: '狂人日记 · 心理悬疑版 v5',
        artist: '鲁迅',
        comment: '《狂人日记》原文节选 · 百炼合成男声 · AI 生成画面',
      },
      onProgress: ({progress}) => {
        const percent = Math.floor(progress * 20) * 5;
        if (percent !== lastProgress) {
          console.log(`${isSample ? 'Diagnosis sample' : 'Rendering'} ${percent}%`);
          lastProgress = percent;
        }
      },
    });
    if (isSample) {
      console.log(`Diagnosis sample frames ${sampleFrameRange[0]}-${sampleFrameRange[1]} (consult + aside).`);
    }
  }
} finally {
  await browser.close({silent: true});
}
