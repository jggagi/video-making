#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(scriptDir, '..');
const proofDir = path.resolve(projectDir, '..');
const repoDir = path.resolve(projectDir, '../../..');
const entryPoint = path.join(projectDir, 'src', 'index.ts');
const reviewDir = path.join(proofDir, 'review');

const stills = new Map([
  ['CoffeeStill', 'coffee-4k.png'],
  ['ChoiceStill', 'choice-4k.png'],
  ['CrystalStill', 'crystal-4k.png'],
]);
const expectedStill = {width: 3840, height: 2160};
const expectedVideo = {
  id: 'CrystalProof',
  width: 1920,
  height: 1080,
  fps: 60,
  durationInFrames: 720,
};
const chromiumOptions = {gl: 'angle', headless: true};

function usage() {
  return [
    'Usage:',
    '  node scripts/render-proof.mjs stills',
    '  node scripts/render-proof.mjs single <CoffeeStill|ChoiceStill|CrystalStill>',
    '  node scripts/render-proof.mjs video',
    '',
    'Outputs are written to the sibling review/ directory.',
  ].join('\n');
}

function resolveBrowserExecutable() {
  const configured = process.env.REMOTION_CHROME_EXECUTABLE;
  if (configured) {
    if (!fs.existsSync(configured)) {
      throw new Error(`REMOTION_CHROME_EXECUTABLE does not exist: ${configured}`);
    }
    return path.resolve(configured);
  }

  const platformArch = `${process.platform}-${process.arch}`;
  const candidates = [
    path.join(repoDir, 'node_modules', '.remotion', 'chrome-headless-shell', platformArch, 'chrome-headless-shell'),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ];
  const executable = candidates.find((candidate) => fs.existsSync(candidate));
  if (!executable) {
    throw new Error(
      `No Chrome executable found. Checked:\n${candidates.join('\n')}\n` +
        'Set REMOTION_CHROME_EXECUTABLE to an installed Chrome or Chromium binary.',
    );
  }
  return executable;
}

function assertComposition(composition, expected) {
  const mismatches = Object.entries(expected)
    .filter(([key, value]) => composition[key] !== value)
    .map(([key, value]) => `${key}: expected ${value}, got ${composition[key]}`);
  if (mismatches.length) {
    throw new Error(`Composition ${composition.id} does not match the proof spec: ${mismatches.join('; ')}`);
  }
}

function ensureFreshOutputs(paths) {
  const existing = paths.filter((output) => fs.existsSync(output));
  if (existing.length) {
    throw new Error(`Refusing to overwrite existing proof output(s):\n${existing.join('\n')}`);
  }
}

async function main() {
  const [mode, compositionId, ...extraArgs] = process.argv.slice(2);
  if (mode === '--help' || mode === '-h' || !mode) {
    console.log(usage());
    return;
  }

  let selectedMode;
  let outputPaths;
  if (mode === 'stills' && !compositionId && extraArgs.length === 0) {
    selectedMode = 'stills';
    outputPaths = [...stills.values()].map((name) => path.join(reviewDir, name));
  } else if (mode === 'single' && stills.has(compositionId) && extraArgs.length === 0) {
    selectedMode = 'single';
    outputPaths = [path.join(reviewDir, stills.get(compositionId))];
  } else if (mode === 'video' && !compositionId && extraArgs.length === 0) {
    selectedMode = 'video';
    outputPaths = [path.join(reviewDir, 'crystal-proof-12s-1080p.mp4')];
  } else {
    throw new Error(usage());
  }

  if (!fs.existsSync(entryPoint)) {
    throw new Error(`Remotion entry point not found: ${entryPoint}`);
  }
  fs.mkdirSync(reviewDir, {recursive: true});
  ensureFreshOutputs(outputPaths);

  if (process.platform === 'darwin' && fs.existsSync('/Users/guoq/Developer/agent-workstation') && !process.env.TMPDIR?.startsWith('/Volumes/AgentDev/')) {
    throw new Error('On Q’s Mac, run rendering through agent-dev run after a successful current volume preflight.');
  }

  const browserExecutable = resolveBrowserExecutable();
  const bundleDir = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'ep06-v02-proof-bundle-'));
  let browser;
  try {
    const publicDir = path.join(projectDir, 'public');
    const serveUrl = await bundle({
      entryPoint,
      publicDir: fs.existsSync(publicDir) ? publicDir : null,
      outDir: bundleDir,
      onProgress: () => {},
    });
    browser = await openBrowser('chrome', {
      browserExecutable,
      chromiumOptions,
      logLevel: 'error',
    });

    const common = {
      serveUrl,
      browserExecutable,
      chromiumOptions,
      puppeteerInstance: browser,
      logLevel: 'error',
    };

    if (selectedMode === 'video') {
      const composition = await selectComposition({...common, id: expectedVideo.id});
      assertComposition(composition, expectedVideo);
      let lastLoggedPercent = -10;
      await renderMedia({
        ...common,
        composition,
        outputLocation: outputPaths[0],
        codec: 'h264',
        pixelFormat: 'yuv420p',
        audioCodec: 'aac',
        audioBitrate: '320k',
        sampleRate: 48000,
        colorSpace: 'bt709',
        crf: 18,
        x264Preset: 'veryfast',
        imageFormat: 'jpeg',
        scale: 1,
        concurrency: 1,
        onProgress: ({progress, renderedFrames}) => {
          const percent = Math.floor(progress * 100 / 10) * 10;
          if (percent >= lastLoggedPercent + 10) {
            lastLoggedPercent = percent;
            console.log(`CrystalProof ${percent}% (${renderedFrames}/720 frames)`);
          }
        },
      });
      console.log(`Rendered ${outputPaths[0]}`);
      return;
    }

    const ids = selectedMode === 'stills' ? [...stills.keys()] : [compositionId];
    for (const id of ids) {
      const composition = await selectComposition({...common, id});
      assertComposition(composition, {id, ...expectedStill});
      const output = path.join(reviewDir, stills.get(id));
      await renderStill({
        ...common,
        composition,
        frame: 0,
        output,
        imageFormat: 'png',
      });
      console.log(`Rendered ${output}`);
    }
  } finally {
    if (browser) {
      await browser.close({silent: true});
    }
    fs.rmSync(bundleDir, {recursive: true, force: true});
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
