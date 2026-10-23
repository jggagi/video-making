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
const title = delivery.title;
const frameCount = delivery.total_frames;
const fps = delivery.fps;
const output = delivery.outputs?.xiaohongshu;

if (delivery.slug !== 'si-ep18-sovereign-subcurrent-v03' || title !== '心印潜流 · v03') throw new Error('Unexpected EP18 v03 delivery identity');
if (delivery.platforms?.length !== 1 || delivery.platforms[0] !== 'xiaohongshu' || !output || output.path !== '小红书/si-ep18-sovereign-subcurrent-v03-xiaohongshu-90s-portrait.mp4') throw new Error('EP18 v03 render is limited to the exact declared Xiaohongshu output');
if (frameCount !== 5400 || fps !== 60 || output.width !== 2160 || output.height !== 3840) throw new Error('EP18 native spec mismatch');
if (!fs.existsSync(chrome)) throw new Error('The verified local Google Chrome executable is unavailable');
if (process.platform === 'darwin' && !process.env.TMPDIR?.startsWith('/Volumes/AgentDev/')) throw new Error('Run through agent-dev after volume preflight');

const segments = JSON.parse(fs.readFileSync(path.join(root, 'segments.json'), 'utf8'));
const expectedIds = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08'];
if (!Array.isArray(segments) || segments.length !== expectedIds.length || segments.some((row, i) => row.id !== expectedIds[i])) throw new Error('Expected exactly the eight current EP18 narration cues S01-S08');

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
  if (cues.size !== 8 || expectedIds.some((id) => !cues.has(id))) throw new Error('Fresh synthesis evidence must contain exactly EP18 cues S01-S08');
  for (const segment of segments) {
    const cue = cues.get(segment.id);
    const expectedText = segment.tts_phonetic_text;
    const expectedTextSha = createHash('sha256').update(expectedText).digest('hex');
    if (cue.actualModel !== 'qwen-audio-3.0-tts-plus' || cue.actualVoice !== 'qwen-audio-3.0-tts-plus-longlangmoyue') throw new Error('EP18 narration identity does not match its authorization');
    if (cue.spokenText !== expectedText || cue.textSha256 !== expectedTextSha) throw new Error('EP18 synthesis evidence does not match the current cue text: ' + segment.id);
  }
  return master;
};

if (['video', 'preview'].includes(mode)) requireVerifiedMaster();
const temp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'si-ep18-sovereign-subcurrent-v03-bundle-'));
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
  const composition = await selectComposition({...common, id: 'PortraitVertical'});
  if (composition.width !== 2160 || composition.height !== 3840 || composition.fps !== 60 || composition.durationInFrames !== 5400) throw new Error('Native composition specs mismatch');

  if (['stills', 'covers', 'headlines', 'redraw'].includes(mode)) {
    const frameSet = new Set();
    for (const segment of segments) {
      const start = segment.startFrame;
      const end = segment.endFrame;
      frameSet.add(Math.min(end - 1, start + 30));
      frameSet.add(Math.floor((start + end - 1) / 2));
    }
    const frames = mode === 'headlines' ? [] : mode === 'covers' ? [3720, 4920] : args.length ? args.map(Number) : Array.from(frameSet).sort((a, b) => a - b);
    for (const frame of frames) {
      if (!Number.isInteger(frame) || frame < 0 || frame >= frameCount) throw new Error('Invalid requested frame: ' + frame);
      const name = mode === 'redraw' ? 'frame-' + frame + '.png' : mode === 'covers' ? (frame === 3720 ? 'cover-A.png' : 'cover-B.png') : 'source-' + frame + '.png';
      const folder = mode === 'redraw' ? 'review/native-redraw' : mode === 'covers' ? '小红书' : 'review';
      const destination = path.join(work, folder, name);
      fs.mkdirSync(path.dirname(destination), {recursive: true});
      if (fs.existsSync(destination)) throw new Error('Refusing to overwrite existing still: ' + destination);
      await renderStill({...common, composition, frame, output: destination, imageFormat: 'png'});
      console.log('still ' + frame + ' ' + name);
    }
    if (mode === 'covers' || mode === 'headlines') {
      for (const [kind, frame] of [['A', 3720], ['B', 4920]]) {
        const coverProps = {silent: true, cover: kind};
        const coverComposition = await selectComposition({...common, inputProps: coverProps, id: 'PortraitVertical'});
        const destination = path.join(work, '小红书', 'cover-' + kind + '-headline.png');
        if (fs.existsSync(destination)) throw new Error('Refusing to overwrite existing headline still: ' + destination);
        await renderStill({...common, inputProps: coverProps, composition: coverComposition, frame, output: destination, imageFormat: 'png'});
        console.log('headline ' + kind);
      }
    }
  } else {
    if (!['video', 'preview'].includes(mode)) throw new Error('Unknown render mode: ' + mode);
    const preview = mode === 'preview';
    const start = Number(args[0] ?? 120);
    const end = Number(args[1] ?? 299);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end < start || end >= frameCount) throw new Error('Invalid preview frame range');
    const pointer = path.join(work, 'review', 'render-staging.json');
    if (!preview && fs.existsSync(pointer)) throw new Error('Render staging pointer already exists; preserve previous evidence');
    const stage = preview ? null : fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'si-ep18-sovereign-subcurrent-v03-native-'));
    const outputLocation = preview ? path.join(work, 'review', 'motion-' + start + '-' + end + '.mp4') : path.join(stage, 'video-only.mp4');
    if (fs.existsSync(outputLocation)) throw new Error('Refusing to overwrite render output: ' + outputLocation);
    let last = -5;
    await renderMedia({
      ...common,
      composition,
      outputLocation,
      frameRange: preview ? [start, end] : undefined,
      scale: 1,
      muted: !preview,
      codec: 'h264',
      audioCodec: 'aac',
      audioBitrate: '320k',
      sampleRate: 48000,
      pixelFormat: 'yuv420p',
      colorSpace: 'bt709',
      crf: 19,
      x264Preset: 'fast',
      imageFormat: 'png',
      concurrency: 1,
      metadata: {
        title: '心印潜流 · v03 / THE SUBCURRENT DOPPELGÄNGER',
        comment: 'Fictional future SI thought experiment about identity and substituted decisions. All telemetry and numerical metrics are invented. Native portrait 2160x3840, 60 fps, 5400 frames, 90 seconds.',
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
        capture: {remotion: '4.0.534', chrome, chromeVersion: execFileSync(chrome, ['--version'], {encoding: 'utf8'}).trim(), imageFormat: 'png', concurrency: 1, nativeWidth: 2160, nativeHeight: 3840, pixelFormat: 'yuv420p', colorSpace: 'bt709'},
        absoluteRange: [0, 5399],
        source: {title, slug: delivery.slug, narrationCues: 8,
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
