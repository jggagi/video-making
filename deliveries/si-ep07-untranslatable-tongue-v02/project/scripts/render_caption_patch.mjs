import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const work = path.dirname(root);
const manifest = JSON.parse(fs.readFileSync(path.join(work, 'delivery.json'), 'utf8'));
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const usage = `Usage:
  node scripts/render_caption_patch.mjs stills <portrait|landscape> [frame ...] [--output-dir DIR]
  node scripts/render_caption_patch.mjs preview <portrait|landscape> <start-frame> <end-frame> [--output-dir DIR]
  node scripts/render_caption_patch.mjs video <portrait|landscape> --output PATCH.mp4

Stills render both the subtitle patch and its full-frame Film reference. Video
renders the 7200-frame silent patch only; it does not compose or replace a final.`;

function parseInvocation(argv) {
  if (argv.includes('--help') || argv.includes('-h')) {
    console.log(usage);
    process.exit(0);
  }
  const mode = argv.shift() ?? 'stills';
  const layout = argv.shift() ?? 'portrait';
  if (!['stills', 'preview', 'video'].includes(mode)) throw new Error(`Unknown mode: ${mode}\n${usage}`);
  if (!['portrait', 'landscape'].includes(layout)) throw new Error(`Unknown layout: ${layout}\n${usage}`);
  const positional = [];
  const options = {};
  while (argv.length) {
    const token = argv.shift();
    if (token === '--output-dir' || token === '--output') {
      const value = argv.shift();
      if (!value || value.startsWith('--')) throw new Error(`${token} requires a path`);
      options[token === '--output-dir' ? 'outputDir' : 'output'] = path.resolve(value);
    } else if (token.startsWith('--')) {
      throw new Error(`Unknown option: ${token}\n${usage}`);
    } else {
      positional.push(token);
    }
  }
  return {mode, layout, positional, options};
}

function checkAgentDevTemp() {
  if (process.platform === 'darwin' && fs.existsSync('/Users/guoq/Developer/agent-workstation') && !process.env.TMPDIR?.startsWith('/Volumes/AgentDev/')) {
    throw new Error('On Q’s Mac, run rendering through agent-dev after volume preflight so TMPDIR uses AgentDev.');
  }
}

function requireFresh(pathname) {
  if (fs.existsSync(pathname)) throw new Error(`Refusing to overwrite existing output: ${pathname}`);
}

function validateTimingForVideo() {
  const timingPath = path.join(root, 'audio-timing.json');
  const timing = JSON.parse(fs.readFileSync(timingPath, 'utf8'));
  const master = path.join(root, 'public/audio/master.wav');
  if (timing.segments?.length !== 11 || !timing.captions?.length || !fs.existsSync(master) || JSON.stringify(timing).includes('preview_estimate_pending_pcm')) {
    throw new Error('Full patch render requires all 11 PCM-measured cues, v02 captions, and the shared master.');
  }
}

const {mode, layout, positional, options} = parseInvocation(process.argv.slice(2));
const portrait = layout === 'portrait';
const patchId = portrait ? 'PortraitCaptionPatch' : 'LandscapeCaptionPatch';
const sourceId = portrait ? 'PortraitVertical' : 'Landscape4K';
const outputSpec = manifest.outputs[portrait ? 'xiaohongshu' : 'bilibili'];
const defaultOutputDir = path.join(os.tmpdir(), 'si-ep07-v02-caption-patch-check');
const outputDir = options.outputDir ?? defaultOutputDir;
checkAgentDevTemp();

if (mode === 'video') {
  if (!options.output) throw new Error(`video mode requires --output PATH\n${usage}`);
  const finalPaths = Object.values(manifest.outputs).map((entry) => path.resolve(work, entry.path));
  if (finalPaths.includes(options.output)) throw new Error('Patch output cannot be a manifest-selected final movie.');
  validateTimingForVideo();
  requireFresh(options.output);
} else if (mode === 'preview') {
  if (positional.length !== 2) throw new Error(`preview mode requires start and end frames\n${usage}`);
  const [start, end] = positional.map(Number);
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end < start || end >= 7200) {
    throw new Error('Preview frame range must be inclusive and within 0..7199.');
  }
  fs.mkdirSync(outputDir, {recursive: true});
  options.output = path.join(outputDir, `caption-patch-${layout}-${start}-${end}.mp4`);
  requireFresh(options.output);
} else {
  const frames = positional.length ? positional.map(Number) : [portrait ? 960 : 6600];
  if (frames.some((frame) => !Number.isInteger(frame) || frame < 0 || frame >= 7200)) {
    throw new Error('Still frame indices must be integers within 0..7199.');
  }
  fs.mkdirSync(outputDir, {recursive: true});
  for (const frame of frames) {
    requireFresh(path.join(outputDir, `caption-patch-${layout}-${frame}.png`));
    requireFresh(path.join(outputDir, `caption-source-${layout}-${frame}.png`));
  }
}

if (mode === 'video') fs.mkdirSync(path.dirname(options.output), {recursive: true});

const tempBase = process.env.TMPDIR ?? os.tmpdir();
const bundleDir = fs.mkdtempSync(path.join(tempBase, 'si-ep07-v02-caption-bundle-'));
const serveUrl = await bundle({
  entryPoint: path.join(root, 'src/index.ts'),
  publicDir: path.join(root, 'public'),
  outDir: bundleDir,
  onProgress: () => {},
});
const browser = await openBrowser('chrome', {browserExecutable: chrome, logLevel: 'error'});

try {
  if (mode === 'stills') {
    const frames = positional.length ? positional.map(Number) : [portrait ? 960 : 6600];
    const patchProps = {portrait};
    const sourceProps = {portrait, silent: true};
    const patchComposition = await selectComposition({serveUrl, browserExecutable: chrome, puppeteerInstance: browser, logLevel: 'error', id: patchId, inputProps: patchProps});
    const sourceComposition = await selectComposition({serveUrl, browserExecutable: chrome, puppeteerInstance: browser, logLevel: 'error', id: sourceId, inputProps: sourceProps});
    if (patchComposition.width !== outputSpec.width || patchComposition.height !== 360 || patchComposition.fps !== 60 || patchComposition.durationInFrames !== 7200) {
      throw new Error(`Patch composition metadata mismatch: ${patchComposition.width}x${patchComposition.height} @${patchComposition.fps} / ${patchComposition.durationInFrames}`);
    }
    for (const frame of frames) {
      await renderStill({serveUrl, browserExecutable: chrome, puppeteerInstance: browser, logLevel: 'error', composition: patchComposition, inputProps: patchProps, frame, output: path.join(outputDir, `caption-patch-${layout}-${frame}.png`), imageFormat: 'png'});
      await renderStill({serveUrl, browserExecutable: chrome, puppeteerInstance: browser, logLevel: 'error', composition: sourceComposition, inputProps: sourceProps, frame, output: path.join(outputDir, `caption-source-${layout}-${frame}.png`), imageFormat: 'png'});
      console.log(`still ${patchId} and ${sourceId} frame=${frame}`);
    }
  } else {
    const patchProps = {portrait};
    const composition = await selectComposition({serveUrl, browserExecutable: chrome, puppeteerInstance: browser, logLevel: 'error', id: patchId, inputProps: patchProps});
    if (composition.width !== outputSpec.width || composition.height !== 360 || composition.fps !== 60 || composition.durationInFrames !== 7200) {
      throw new Error(`Patch composition metadata mismatch: ${composition.width}x${composition.height} @${composition.fps} / ${composition.durationInFrames}`);
    }
    let lastProgressPercent = -1;
    const common = {
      serveUrl,
      browserExecutable: chrome,
      puppeteerInstance: browser,
      logLevel: 'error',
      composition,
      inputProps: patchProps,
      outputLocation: options.output,
      scale: 1,
      codec: 'h264',
      crf: 17,
      x264Preset: 'fast',
      pixelFormat: 'yuv420p',
      colorSpace: 'bt709',
      imageFormat: 'png',
      concurrency: 1,
      onProgress: ({progress, renderedFrames}) => {
        const percent = Math.floor(progress * 100);
        if (progress === 1 || renderedFrames === 1 || (percent % 10 === 0 && percent !== lastProgressPercent)) {
          lastProgressPercent = percent;
          console.log(`${patchId} ${percent}% frames=${renderedFrames}`);
        }
      },
    };
    if (mode === 'preview') {
      await renderMedia({...common, frameRange: positional.map(Number)});
    } else {
      await renderMedia(common);
    }
    console.log(options.output);
  }
} finally {
  await browser.close({silent: true});
  fs.rmSync(bundleDir, {recursive: true, force: true});
}
