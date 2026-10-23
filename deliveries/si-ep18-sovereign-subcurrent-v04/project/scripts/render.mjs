import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderStill, renderMedia} from '@remotion/renderer';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const work = path.dirname(root);
const [mode = 'stills', ...args] = process.argv.slice(2);
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const deliveryPath = path.join(work, 'delivery.json');
const delivery = JSON.parse(fs.readFileSync(deliveryPath, 'utf8'));
const plan = JSON.parse(fs.readFileSync(path.join(root, 'render-plan.json'), 'utf8'));
const audioPlan = JSON.parse(fs.readFileSync(path.join(root, 'audio-plan.json'), 'utf8'));
const title = delivery.title;
const frameCount = delivery.total_frames;
const fps = delivery.fps;
const output = delivery.outputs?.xiaohongshu;

if (delivery.slug !== plan.work.id || title !== plan.work.title) throw new Error('Unexpected EP18 v04 delivery identity');
if (delivery.platforms?.length !== 1 || delivery.platforms[0] !== plan.work.platform || !output || output.path !== plan.output.path) throw new Error('EP18 v04 render is limited to the exact declared Xiaohongshu output');
if (frameCount !== plan.composition.durationInFrames || fps !== plan.composition.fps || output.width !== plan.composition.width || output.height !== plan.composition.height) throw new Error('EP18 native spec mismatch');
if (!fs.existsSync(chrome)) throw new Error('The verified local Google Chrome executable is unavailable');
if (process.platform === 'darwin' && !process.env.TMPDIR?.startsWith('/Volumes/AgentDev/')) throw new Error('Run through agent-dev after volume preflight');

const segments = JSON.parse(fs.readFileSync(path.join(root, 'segments.json'), 'utf8'));
const expectedIds = Array.from({length: plan.content.segmentCount}, (_, i) => `S${String(i + 1).padStart(2, '0')}`);
if (!Array.isArray(segments) || segments.length !== expectedIds.length || segments.some((row, i) => row.id !== expectedIds[i])) throw new Error('Expected exactly the current eight EP18 narration cues S01-S08');

const sha256File = async (file) => {
  const hash = createHash('sha256');
  for await (const chunk of fs.createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
};
const requireVerifiedMaster = () => {
  const master = path.resolve(work, delivery.audio?.master ?? '');
  if (!master.startsWith(work + path.sep) || !fs.existsSync(master)) throw new Error('A current real EP18 PCM master is required');
  const mixQaPath = path.join(work, 'review', 'audio-mix-qa.json');
  const synthesisPath = path.join(work, 'review', 'audio-synthesis.json');
  if (!fs.existsSync(mixQaPath) || !fs.existsSync(synthesisPath)) throw new Error('Fresh EP18 audio synthesis and mix QA evidence is required');
  const mixQa = JSON.parse(fs.readFileSync(mixQaPath, 'utf8'));
  const synthesis = JSON.parse(fs.readFileSync(synthesisPath, 'utf8'));
  const cues = new Map((synthesis.cues ?? []).map((cue) => [cue.id, cue]));
  if (mixQa.status !== 'pass') throw new Error('The EP18 audio mix QA has not passed');
  const currentMasterSha = createHash('sha256').update(fs.readFileSync(master)).digest('hex');
  if (mixQa.masterSha256 !== currentMasterSha) throw new Error('The EP18 mix QA does not match the current PCM master');
  if (cues.size !== segments.length || expectedIds.some((id) => !cues.has(id))) throw new Error('Fresh synthesis evidence must contain exactly the current EP18 cues');
  for (const segment of segments) {
    const cue = cues.get(segment.id);
    const expectedText = segment.tts_phonetic_text;
    const expectedTextSha = createHash('sha256').update(expectedText).digest('hex');
    if (cue.actualModel !== audioPlan.model || cue.actualVoice !== audioPlan.voice) throw new Error('EP18 narration identity does not match the current audio plan');
    if (cue.spokenText !== expectedText || cue.textSha256 !== expectedTextSha) throw new Error('EP18 synthesis evidence does not match the current cue text: ' + segment.id);
  }
  return master;
};

if (['video', 'preview'].includes(mode)) requireVerifiedMaster();
const temp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'si-ep18-sovereign-subcurrent-v04-bundle-'));
const serveUrl = await bundle({
  entryPoint: path.join(root, 'src/index.ts'),
  publicDir: path.join(root, 'public'),
  outDir: temp,
  enableCaching: false,
  onProgress: () => {},
});
const browser = await openBrowser('chrome', {browserExecutable: chrome, logLevel: 'error'});
try {
  const props = {silent: mode !== 'preview', cover: false};
  const common = {
    serveUrl,
    browserExecutable: chrome,
    puppeteerInstance: browser,
    logLevel: 'error',
    onBrowserLog: (log) => console.log('browser-log', JSON.stringify(log)),
    inputProps: props,
  };
  const composition = await selectComposition({...common, id: plan.composition.id});
  if (composition.width !== plan.composition.width || composition.height !== plan.composition.height || composition.fps !== plan.composition.fps || composition.durationInFrames !== plan.composition.durationInFrames) throw new Error('Native composition specs mismatch');

  if (['stills', 'covers', 'headlines', 'redraw'].includes(mode)) {
    const frameSet = new Set();
    for (const frame of plan.frames.stillFrameNumbers) frameSet.add(frame);
    for (const segment of segments) {
      const start = segment.startFrame;
      const end = segment.endFrame;
      frameSet.add(Math.min(end - 1, start + plan.frames.segmentRepresentativePairs.startOffsetFrames));
      frameSet.add(Math.floor((start + end - 1) / 2));
    }
    const coverFrames = Object.values(plan.frames.coverFrames);
    const frames = mode === 'headlines' ? [] : mode === 'covers' ? coverFrames : args.length ? args.map(Number) : Array.from(frameSet).sort((a, b) => a - b);
    if (new Set(frames).size !== frames.length) throw new Error('Requested still frame list must be unique');
    for (const frame of frames) {
      if (!Number.isInteger(frame) || frame < 0 || frame >= frameCount) throw new Error('Invalid requested frame: ' + frame);
      const coverName = Object.entries(plan.frames.coverFrames).find(([, plannedFrame]) => plannedFrame === frame)?.[0];
      const name = mode === 'redraw' ? 'frame-' + frame + '.png' : mode === 'covers' ? `cover-${coverName}.png` : 'source-' + frame + '.png';
      if (mode === 'covers' && !coverName) throw new Error('Requested cover frame is absent from render-plan.json');
      const folder = mode === 'redraw' ? 'review/native-redraw' : mode === 'covers' ? '小红书' : 'review';
      const destination = path.join(work, folder, name);
      fs.mkdirSync(path.dirname(destination), {recursive: true});
      if (fs.existsSync(destination)) throw new Error('Refusing to overwrite existing still: ' + destination);
      await renderStill({...common, composition, frame, output: destination, imageFormat: plan.composition.imageFormat});
      console.log('still ' + frame + ' ' + name);
    }
    if (mode === 'covers' || mode === 'headlines') {
      for (const [kind, frame] of Object.entries(plan.frames.coverFrames)) {
        const coverProps = {silent: true, cover: kind};
        const coverComposition = await selectComposition({...common, inputProps: coverProps, id: plan.composition.id});
        const destination = path.join(work, '小红书', 'cover-' + kind + '-headline.png');
        if (fs.existsSync(destination)) throw new Error('Refusing to overwrite existing headline still: ' + destination);
        await renderStill({...common, inputProps: coverProps, composition: coverComposition, frame, output: destination, imageFormat: plan.composition.imageFormat});
        console.log('headline ' + kind);
      }
    }
  } else {
    if (!['video', 'preview'].includes(mode)) throw new Error('Unknown render mode: ' + mode);
    const preview = mode === 'preview';
    const start = Number(args[0] ?? plan.previews.nativeRanges[0].startFrame);
    const endExclusive = Number(args[1] ?? plan.previews.nativeRanges[0].endFrameExclusive);
    if (!Number.isInteger(start) || !Number.isInteger(endExclusive) || start < 0 || endExclusive <= start || endExclusive > frameCount) throw new Error('Invalid half-open preview frame range');
    const end = endExclusive - 1;
    const pointer = path.join(work, 'review', 'render-staging.json');
    if (!preview && fs.existsSync(pointer)) throw new Error('Render staging pointer already exists; preserve previous evidence');
    const stage = preview ? null : fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'si-ep18-sovereign-subcurrent-v04-native-'));
    const outputLocation = preview ? path.join(work, 'review', 'motion-' + start + '-' + end + '.mp4') : path.join(stage, 'video-only.mp4');
    if (fs.existsSync(outputLocation)) throw new Error('Refusing to overwrite render output: ' + outputLocation);
    let last = -5;
    await renderMedia({
      ...common,
      composition,
      outputLocation,
      frameRange: preview ? [start, end] : undefined,
      scale: plan.capture.scale,
      muted: !preview,
      codec: plan.capture.codec,
      audioCodec: plan.capture.audioCodec,
      audioBitrate: '320k',
      sampleRate: plan.capture.audioSampleRateHz,
      pixelFormat: plan.capture.pixelFormat,
      colorSpace: plan.capture.colorSpace,
      crf: 19,
      x264Preset: 'fast',
      imageFormat: plan.composition.imageFormat,
      concurrency: plan.capture.concurrency,
      metadata: {
        title,
        comment: 'Fictional future SI thought experiment about a person and a shadow that learns to act first. Native portrait 2160x3840, 60 fps, 5400 frames, 90 seconds.',
      },
      onProgress: ({progress, renderedFrames, renderEstimatedTime}) => {
        const percent = Math.floor(progress * 100);
        if (percent >= last + 2) {
          last = percent;
          console.log(mode + ' ' + percent + '% frames=' + renderedFrames + ' eta=' + Math.round(renderEstimatedTime / 1000) + 's');
        }
      },
    });
    console.log(outputLocation);
    if (!preview) {
      const pointerData = {
        status: 'READY',
        file: outputLocation,
        sha256: await sha256File(outputLocation),
        bytes: fs.statSync(outputLocation).size,
        capture: {remotion: '4.0.534', chrome, chromeVersion: execFileSync(chrome, ['--version'], {encoding: 'utf8'}).trim(), imageFormat: plan.composition.imageFormat, concurrency: plan.capture.concurrency, nativeWidth: plan.composition.width, nativeHeight: plan.composition.height, pixelFormat: plan.capture.pixelFormat, colorSpace: plan.capture.colorSpace},
        absoluteRange: [0, frameCount - 1],
        source: {title, slug: delivery.slug, narrationCues: segments.length,
          hashes: Object.fromEntries(['src/Scene.tsx', 'src/Film.tsx', 'src/Root.tsx', 'segments.json', 'captions.json', 'public/audio/master.wav'].map((name) => [name, createHash('sha256').update(fs.readFileSync(path.join(root, name))).digest('hex')]))},
        scope: 'EP18 native video track on verified AgentDev scratch; formal output remains in the delivery folder',
      };
      fs.writeFileSync(pointer, JSON.stringify(pointerData, null, 2) + '\n', {flag: 'wx'});
    }
  }
} finally {
  await browser.close({silent: true});
  fs.rmSync(temp, {recursive: true, force: true});
}
