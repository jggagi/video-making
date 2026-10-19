import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderFrames, selectComposition} from '@remotion/renderer';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const work = path.dirname(root);
const review = path.join(work, 'review');
const [layout = 'landscape'] = process.argv.slice(2);
if (!['landscape', 'portrait'].includes(layout)) {
  throw new Error('Usage: node scripts/render_quote_patch.mjs <landscape|portrait>');
}
if (process.platform === 'darwin' && fs.existsSync('/Users/guoq/Developer/agent-workstation') && !process.env.TMPDIR?.startsWith('/Volumes/AgentDev/')) {
  throw new Error('On Q’s Mac, run quote capture through agent-dev run after volume preflight.');
}

const portrait = layout === 'portrait';
const compositionId = portrait ? 'PortraitVertical' : 'Landscape4K';
const expectedStart = 5880;
const expectedEnd = 6299;
const expectedCount = expectedEnd - expectedStart + 1;
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const outputDir = path.join(review, `quote-patch-${layout}`);
const outputDirExists = (() => {
  try {
    fs.lstatSync(outputDir);
    return true;
  } catch (error) {
    if (error?.code === 'ENOENT') return false;
    throw error;
  }
})();
if (outputDirExists) throw new Error(`Refusing to overwrite existing quote patch directory: ${outputDir}`);
fs.mkdirSync(outputDir);

const digest = (buffer) => crypto.createHash('sha256').update(buffer).digest('hex');
const frames = Array.from({length: expectedCount}, (_, index) => expectedStart + index);
const captured = new Set();
let bundleDir;
let browser;

try {
  bundleDir = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'si-ep08-quote-bundle-'));
  const serveUrl = await bundle({
    entryPoint: path.join(root, 'src/index.ts'),
    publicDir: path.join(root, 'public'),
    outDir: bundleDir,
    onProgress: () => {},
  });
  browser = await openBrowser('chrome', {browserExecutable: chrome, logLevel: 'error'});
  const common = {
    serveUrl,
    browserExecutable: chrome,
    puppeteerInstance: browser,
    logLevel: 'error',
    inputProps: {portrait, silent: true},
  };
  const composition = await selectComposition({...common, id: compositionId});
  if (composition.durationInFrames !== 7200 || composition.fps !== 60) throw new Error('Timeline mismatch');
  const dimensions = portrait ? [2160, 3840] : [3840, 2160];
  if (composition.width !== dimensions[0] || composition.height !== dimensions[1]) throw new Error(`Composition dimensions mismatch: ${composition.width}x${composition.height}`);

  await renderFrames({
    ...common,
    composition,
    frames,
    outputDir: null,
    imageFormat: 'png',
    concurrency: 2,
    onStart: () => {},
    onFrameUpdate: (renderedFrames) => {
      if (renderedFrames > 0 && renderedFrames % 42 === 0) console.log(`${layout} quote patch ${renderedFrames}/${expectedCount}`);
    },
    onFrameBuffer: async (buffer, frame) => {
      if (!Number.isInteger(frame) || frame < expectedStart || frame > expectedEnd) throw new Error(`Unexpected rendered frame index: ${frame}`);
      if (captured.has(frame)) throw new Error(`Duplicate rendered frame index: ${frame}`);
      if (buffer.length < 24 || !buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) throw new Error(`Frame ${frame} is not a PNG`);
      const actualWidth = buffer.readUInt32BE(16);
      const actualHeight = buffer.readUInt32BE(20);
      if (actualWidth !== dimensions[0] || actualHeight !== dimensions[1]) throw new Error(`Frame ${frame} has unexpected dimensions ${actualWidth}x${actualHeight}`);
      const filename = `frame-${frame}.png`;
      fs.writeFileSync(path.join(outputDir, filename), buffer, {flag: 'wx'});
      captured.add(frame);
    },
  });

  const actual = [...captured].sort((a, b) => a - b);
  if (actual.length !== expectedCount || actual.some((frame, index) => frame !== expectedStart + index)) {
    throw new Error(`Capture did not produce the exact contiguous frame range ${expectedStart}-${expectedEnd}`);
  }
  const manifest = {
    schema_version: 1,
    purpose: 'EP08 native quote-window overlay frames',
    layout,
    composition_id: compositionId,
    dimensions: {width: dimensions[0], height: dimensions[1]},
    fps: 60,
    frame_range_inclusive: [expectedStart, expectedEnd],
    frame_count: expectedCount,
    input_props: {portrait, silent: true},
    source_sha256: Object.fromEntries(['src/Film.tsx','src/World.tsx','src/Sculpture.tsx','src/Root.tsx','audio-timing.json','scripts/render_quote_patch.mjs'].map((relative) => [relative,digest(fs.readFileSync(path.join(root,relative)))])),
    files: actual.map((frame) => {
      const filename = `frame-${frame}.png`;
      return {frame, filename, sha256: digest(fs.readFileSync(path.join(outputDir, filename)))};
    }),
  };
  fs.writeFileSync(path.join(outputDir, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, {flag: 'wx'});
  console.log(`saved ${expectedCount} PNG frames and manifest to ${outputDir}`);
} finally {
  if (browser) await browser.close({silent: true});
  if (bundleDir) fs.rmSync(bundleDir, {recursive: true, force: true});
}
