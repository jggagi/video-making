#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = path.resolve(SCRIPT_DIR, '..');
const DELIVERY_DIR = path.resolve(PROJECT_DIR, '..');
const REPO_DIR = path.resolve(PROJECT_DIR, '../../..');
const ENTRY_POINT = path.join(PROJECT_DIR, 'src', 'index.ts');
const REVIEW_DIR = path.join(DELIVERY_DIR, 'review');
const FPS = 60;
const FRAMES = 7200;
const DEFAULT_STILLS = [360, 960, 1500, 2190, 3120, 3900, 4800, 5759, 5760, 5790, 6500, 7100, 7199];
const LAYOUTS = {
  landscape: {compositionId: 'Landscape4K', manifestKey: 'bilibili', width: 3840, height: 2160},
  portrait: {compositionId: 'PortraitVertical', manifestKey: 'xiaohongshu', width: 2160, height: 3840},
};
const REVIEW_WINDOWS = [
  ['opening', 660, 839],
  ['mirror', 3000, 3179],
  ['choice', 4740, 4919],
  ['crystal', 5700, 5879],
  ['final', 6960, 7139],
];
const CHROMIUM_OPTIONS = {gl: 'angle'};
const RENDER_CONCURRENCY = Number(process.env.EP06_RENDER_CONCURRENCY ?? '1');
if(![1,2].includes(RENDER_CONCURRENCY))throw new Error('EP06_RENDER_CONCURRENCY must be 1 or 2.');

function usage() {
  return [
    'Usage:',
    '  node scripts/render.mjs stills [landscape|portrait] [frame ...]',
    '  node scripts/render.mjs preview <landscape|portrait> <start-frame> <end-frame>',
    '  node scripts/render.mjs review <landscape|portrait>',
    '  node scripts/render.mjs video <landscape|portrait>',
    '',
    `Still defaults: ${DEFAULT_STILLS.join(', ')}`,
    'Video outputs use the paths declared in delivery.json; existing full outputs are never overwritten.',
  ].join('\n');
}

function parseFrame(value, label) {
  if (!/^\d+$/.test(String(value))) throw new Error(`${label} must be an integer frame number.`);
  const frame = Number(value);
  if (!Number.isSafeInteger(frame) || frame < 0 || frame >= FRAMES) {
    throw new Error(`${label} must be in the range 0–${FRAMES - 1}.`);
  }
  return frame;
}

function parseArgs(argv) {
  const [mode, ...args] = argv;
  if (!mode || mode === '--help' || mode === '-h') return {help: true};
  if (mode === 'stills') {
    let layout = 'landscape';
    let frameArgs = args;
    if (args[0] === 'landscape' || args[0] === 'portrait') [layout, ...frameArgs] = args;
    if (!LAYOUTS[layout]) throw new Error(usage());
    const frames = frameArgs.length ? frameArgs.map((value, i) => parseFrame(value, `Frame ${i + 1}`)) : DEFAULT_STILLS;
    if (new Set(frames).size !== frames.length) throw new Error('Still frame list contains duplicates.');
    return {mode, layout, frames};
  }
  if (mode === 'preview' && args.length === 3 && LAYOUTS[args[0]]) {
    const start = parseFrame(args[1], 'Start frame');
    const end = parseFrame(args[2], 'End frame');
    if (start > end) throw new Error('Start frame must be less than or equal to end frame.');
    return {mode, layout: args[0], start, end};
  }
  if ((mode === 'review' || mode === 'video') && args.length === 1 && LAYOUTS[args[0]]) {
    return {mode, layout: args[0]};
  }
  throw new Error(usage());
}

function assertInside(root, candidate, label) {
  const resolved = path.resolve(candidate);
  const relative = path.relative(path.resolve(root), resolved);
  if (!relative || relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`${label} escapes its expected directory: ${resolved}`);
  }
  return resolved;
}

function versionedPath(candidate) {
  if (!fs.existsSync(candidate)) return candidate;
  const extension = path.extname(candidate);
  const stem = candidate.slice(0, -extension.length);
  for (let revision = 2; revision < 10000; revision += 1) {
    const next = `${stem}-r${String(revision).padStart(2, '0')}${extension}`;
    if (!fs.existsSync(next)) return next;
  }
  throw new Error(`Could not find a free versioned output path for ${candidate}`);
}

function ensureStorageAndEntry() {
  if (process.platform === 'darwin' && fs.existsSync('/Users/guoq/Developer/agent-workstation')) {
    if (!process.env.TMPDIR?.startsWith('/Volumes/AgentDev/')) {
      throw new Error('On Q’s Mac, run through agent-dev run so the bundle uses the validated AgentDev TMPDIR.');
    }
  }
  if (!fs.existsSync(ENTRY_POINT)) throw new Error(`Remotion entry point is missing: ${ENTRY_POINT}`);
}

function resolveBrowserExecutable() {
  const configured = process.env.EP06_CHROME_EXECUTABLE;
  if (configured) {
    if (!fs.existsSync(configured)) throw new Error(`EP06_CHROME_EXECUTABLE does not exist: ${configured}`);
    return path.resolve(configured);
  }
  const platform = process.platform === 'darwin' ? 'mac' : process.platform === 'win32' ? 'win' : process.platform;
  const arch = process.arch === 'x64' ? 'x64' : process.arch;
  const shellName = process.platform === 'win32' ? 'chrome-headless-shell.exe' : 'chrome-headless-shell';
  const candidates = [
    path.join(PROJECT_DIR, 'node_modules', '.remotion', 'chrome-headless-shell', `${platform}-${arch}`, shellName),
    path.join(REPO_DIR, 'node_modules', '.remotion', 'chrome-headless-shell', `${platform}-${arch}`, shellName),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ];
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (!found) throw new Error(`No installed Chrome/Chromium executable found. Checked:\n${candidates.join('\n')}`);
  return found;
}

function assertComposition(composition, layout) {
  const expected = LAYOUTS[layout];
  const actual = {
    id: composition.id,
    width: composition.width,
    height: composition.height,
    fps: composition.fps,
    durationInFrames: composition.durationInFrames,
  };
  const wanted = {
    id: expected.compositionId,
    width: expected.width,
    height: expected.height,
    fps: FPS,
    durationInFrames: FRAMES,
  };
  const mismatches = Object.entries(wanted)
    .filter(([key, value]) => actual[key] !== value)
    .map(([key, value]) => `${key}: expected ${value}, got ${actual[key]}`);
  if (mismatches.length) throw new Error(`Composition mismatch: ${mismatches.join('; ')}`);
}

function checkVideoInputs() {
  const manifestPath = path.join(DELIVERY_DIR, 'delivery.json');
  const timingPath = path.join(PROJECT_DIR, 'audio-timing.json');
  const masterPath = path.join(PROJECT_DIR, 'public', 'audio', 'master.wav');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const timing = JSON.parse(fs.readFileSync(timingPath, 'utf8'));
  if (manifest.duration_seconds !== 120 || manifest.fps !== FPS || manifest.total_frames !== FRAMES) {
    throw new Error('delivery.json must declare 120 seconds, 60 fps and 7200 frames before rendering.');
  }
  if (timing.durationSeconds !== 120 || timing.fps !== FPS || timing.sampleRate !== 48000 || timing.samplesPerChannel !== 5760000 || timing.status !== 'measured_pcm_with_estimated_phrase_timing') {
    throw new Error('audio-timing.json does not contain the required measured 120-second PCM timeline.');
  }
  if (timing.segments?.length !== 10 || timing.captions?.length === 0 || !fs.existsSync(masterPath)) {
    throw new Error('Full renders require ten measured PCM spans, timed captions and the existing shared PCM master.');
  }
  return manifest;
}

async function main() {
  const request = parseArgs(process.argv.slice(2));
  if (request.help) {
    console.log(usage());
    return;
  }
  ensureStorageAndEntry();

  let manifest;
  let selectedOutputs = [];
  if (request.mode === 'stills') {
    selectedOutputs = request.frames.map((frame) => ({
      frame,
      path: versionedPath(path.join(REVIEW_DIR, 'stills', `${request.layout}-${frame}.png`)),
    }));
  } else if (request.mode === 'preview') {
    selectedOutputs = [{
      start: request.start,
      end: request.end,
      path: versionedPath(path.join(REVIEW_DIR, 'previews', `${request.layout}-${request.start}-${request.end}.mp4`)),
    }];
  } else if (request.mode === 'review') {
    selectedOutputs = REVIEW_WINDOWS.map(([name, start, end]) => ({
      name,
      start,
      end,
      path: versionedPath(path.join(REVIEW_DIR, 'previews', `${request.layout}-${name}-${start}-${end}.mp4`)),
    }));
  } else {
    manifest = checkVideoInputs();
    const outputSpec = manifest.outputs?.[LAYOUTS[request.layout].manifestKey];
    if (!outputSpec?.path || outputSpec.width !== LAYOUTS[request.layout].width || outputSpec.height !== LAYOUTS[request.layout].height) {
      throw new Error(`delivery.json has an invalid ${request.layout} output specification.`);
    }
    const outputPath = assertInside(DELIVERY_DIR, path.join(DELIVERY_DIR, outputSpec.path), 'Full video output');
    if (fs.existsSync(outputPath)) throw new Error(`Refusing to overwrite full video output: ${outputPath}`);
    selectedOutputs = [{path: outputPath}];
  }

  for (const output of selectedOutputs) fs.mkdirSync(path.dirname(output.path), {recursive: true});
  const browserExecutable = resolveBrowserExecutable();
  const tmpRoot = process.env.TMPDIR || os.tmpdir();
  const bundleDir = fs.mkdtempSync(path.join(tmpRoot, 'si-ep06-v02-bundle-'));
  let browser;
  try {
    const serveUrl = await bundle({
      entryPoint: ENTRY_POINT,
      publicDir: fs.existsSync(path.join(PROJECT_DIR, 'public')) ? path.join(PROJECT_DIR, 'public') : null,
      outDir: bundleDir,
      onProgress: () => {},
    });
    browser = await openBrowser('chrome', {
      browserExecutable,
      chromiumOptions: CHROMIUM_OPTIONS,
      logLevel: 'error',
    });
    const common = {
      serveUrl,
      browserExecutable,
      chromiumOptions: CHROMIUM_OPTIONS,
      puppeteerInstance: browser,
      logLevel: 'error',
    };
    const composition = await selectComposition({...common, id: LAYOUTS[request.layout].compositionId});
    assertComposition(composition, request.layout);

    if (request.mode === 'stills') {
      for (const output of selectedOutputs) {
        await renderStill({...common, composition, frame: output.frame, output: output.path, imageFormat: 'png'});
        console.log(`Rendered ${output.path}`);
      }
      return;
    }

    let lastProgress = -10;
    for (const output of selectedOutputs) {
      const preview = request.mode !== 'video';
      await renderMedia({
        ...common,
        composition,
        outputLocation: output.path,
        frameRange: preview ? [output.start, output.end] : undefined,
        scale: preview ? 1 / 3 : 1,
        codec: 'h264',
        pixelFormat: 'yuv420p',
        colorSpace: 'bt709',
        audioCodec: 'aac',
        audioBitrate: '320k',
        sampleRate: 48000,
        crf: 17,
        x264Preset: 'fast',
        imageFormat: 'jpeg',
        jpegQuality: 94,
        concurrency: RENDER_CONCURRENCY,
        overwrite: false,
        metadata: {
          title: manifest?.title ?? `EP06 v02 ${request.layout} ${request.mode}`,
          comment: '120 seconds, 60 fps, shared 48 kHz stereo PCM; native layout render.',
        },
        onProgress: request.mode === 'video' ? ({progress, renderedFrames}) => {
          const percent = Math.floor(progress * 100 / 10) * 10;
          if (percent >= lastProgress + 10) {
            lastProgress = percent;
            console.log(`${LAYOUTS[request.layout].compositionId} ${percent}% (${renderedFrames}/${FRAMES} frames)`);
          }
        } : undefined,
      });
      console.log(`Rendered ${output.path}`);
    }
  } finally {
    if (browser) await browser.close({silent: true});
    fs.rmSync(bundleDir, {recursive: true, force: true});
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
