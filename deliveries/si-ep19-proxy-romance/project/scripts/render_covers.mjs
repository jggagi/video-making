import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { bundle } from '@remotion/bundler';
import { openBrowser, renderStill, selectComposition } from '@remotion/renderer';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const work = path.dirname(root);
const publicDir = path.join(root, 'public');
const outputDir = path.join(work, '小红书');
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const agentDev = path.join(os.homedir(), '.local/bin/agent-dev');
const GIB = 1024 ** 3;
const HOST_UUID = '7E4BC5BA-F525-344A-BECE-08C3272BB25B';
const AGENTDEV_UUID = 'F4DCCF30-ED44-4B5E-8DF9-ED2C039F2857';
const agentDevImage = '/Volumes/WD_BLACK/AgentDev.asif';
const covers = [
  { kind: 'A', background: 'covers/frame-2100.png', output: 'cover-A-headline-v03.png' },
  { kind: 'B', background: 'covers/frame-5040.png', output: 'cover-B-headline-v03.png' },
];

function requireVolumePreflight() {
  if (process.platform !== 'darwin') throw new Error('Cover rendering requires the configured macOS workstation');
  if (!process.env.TMPDIR?.startsWith('/Volumes/AgentDev/')) {
    throw new Error('Run through agent-dev after volume preflight; TMPDIR must be inside /Volumes/AgentDev');
  }

  const result = spawnSync(agentDev, ['status', '--json'], { encoding: 'utf8' });
  if (result.error || result.status !== 0) {
    throw new Error('agent-dev status --json failed; refusing external-volume work');
  }

  let status;
  try {
    status = JSON.parse(result.stdout);
  } catch {
    throw new Error('agent-dev returned invalid JSON; refusing external-volume work');
  }

  const host = status.host;
  const agentdev = status.agentdev;
  if (
    status.host_error ||
    !host ||
    host.uuid !== HOST_UUID ||
    host.mount !== '/Volumes/WD_BLACK' ||
    !Number.isFinite(host.free_bytes) ||
    host.free_bytes < 100 * GIB
  ) {
    throw new Error('WD_BLACK identity or 100 GiB headroom could not be verified');
  }
  if (
    status.agentdev_error ||
    !agentdev ||
    agentdev.uuid !== AGENTDEV_UUID ||
    agentdev.mount !== '/Volumes/AgentDev' ||
    String(agentdev.filesystem).toLowerCase() !== 'apfs' ||
    path.resolve(agentdev.image) !== agentDevImage ||
    !Number.isFinite(agentdev.free_bytes) ||
    agentdev.free_bytes < 20 * GIB
  ) {
    throw new Error('AgentDev identity or 20 GiB headroom could not be verified');
  }
}

function readPngSize(file) {
  const header = Buffer.alloc(24);
  const descriptor = fs.openSync(file, 'r');
  try {
    fs.readSync(descriptor, header, 0, header.length, 0);
  } finally {
    fs.closeSync(descriptor);
  }
  if (header.toString('ascii', 1, 4) !== 'PNG') throw new Error(`Expected a PNG output: ${file}`);
  return { width: header.readUInt32BE(16), height: header.readUInt32BE(20) };
}

requireVolumePreflight();

if (!fs.existsSync(chrome)) throw new Error(`Configured Chrome executable is missing: ${chrome}`);
for (const cover of covers) {
  const input = path.join(publicDir, cover.background);
  if (!fs.existsSync(input)) throw new Error(`Required extracted frame is missing: ${input}`);
  const inputSize = readPngSize(input);
  if (inputSize.width !== 2160 || inputSize.height !== 3840) {
    throw new Error(`Extracted frame ${cover.background} is ${inputSize.width}x${inputSize.height}, expected 2160x3840`);
  }
  const output = path.join(outputDir, cover.output);
  if (fs.existsSync(output)) throw new Error(`Refusing to overwrite existing cover: ${output}`);
}

fs.mkdirSync(outputDir, { recursive: true });
const temp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'ep19-cover-bundle-'));
let browser;

try {
  const serveUrl = await bundle({
    entryPoint: path.join(root, 'src/Covers.tsx'),
    publicDir,
    outDir: temp,
    onProgress: () => {},
  });
  browser = await openBrowser('chrome', { browserExecutable: chrome, logLevel: 'error' });
  const stagedDir = path.join(temp, 'staged');
  fs.mkdirSync(stagedDir);

  const staged = [];
  for (const cover of covers) {
    const inputProps = { kind: cover.kind };
    const common = {
      serveUrl,
      browserExecutable: chrome,
      puppeteerInstance: browser,
      logLevel: 'error',
      inputProps,
    };
    const composition = await selectComposition({ ...common, id: 'CoverVertical' });
    if (
      composition.width !== 2160 ||
      composition.height !== 3840 ||
      composition.fps !== 60 ||
      composition.durationInFrames !== 1
    ) {
      throw new Error('Cover composition must be native 2160x3840, 60fps, one frame');
    }

    const stagedPath = path.join(stagedDir, cover.output);
    await renderStill({ ...common, composition, frame: 0, output: stagedPath, imageFormat: 'png', scale: 1 });
    const size = readPngSize(stagedPath);
    if (size.width !== 2160 || size.height !== 3840) {
      throw new Error(`Cover ${cover.kind} rendered at ${size.width}x${size.height}, expected 2160x3840`);
    }
    staged.push({ cover, stagedPath });
  }

  for (const { cover } of staged) {
    const output = path.join(outputDir, cover.output);
    if (fs.existsSync(output)) throw new Error(`Refusing to overwrite existing cover: ${output}`);
  }
  for (const { cover, stagedPath } of staged) {
    const output = path.join(outputDir, cover.output);
    fs.copyFileSync(stagedPath, output, fs.constants.COPYFILE_EXCL);
    console.log(`cover ${cover.kind}: ${output}`);
  }
} finally {
  try {
    if (browser) await browser.close({ silent: true });
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
}
