import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderStill, renderMedia} from '@remotion/renderer';

const mode = process.argv[2] ?? 'video';
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const output = path.resolve('out');
fs.mkdirSync(output, {recursive: true});
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), outDir: path.join(output, 'bundle'), onProgress: () => {}});
const browser = await openBrowser('chrome', {browserExecutable, chromiumOptions: {disableWebSecurity: false}, logLevel: 'error'});
try {
  const composition = await selectComposition({serveUrl, id: 'Lanting', browserExecutable, puppeteerInstance: browser, logLevel: 'error'});
  if (mode === 'stills') {
    const timeline = JSON.parse(fs.readFileSync('src/timeline.json', 'utf8'));
    const selected = ['title', 'grove', 'water', 'cups', 'joy', 'life', 'mortality', 'judgment', 'future', 'end'];
    for (const id of selected) {
      const shot = timeline.shots.find(s => s.id === id);
      const frame = shot.from + Math.min(Math.round(shot.duration / 2), 72);
      await renderStill({serveUrl, composition, output: path.join(output, `still-${id}.png`), frame, browserExecutable, puppeteerInstance: browser, imageFormat: 'png', logLevel: 'error'});
      console.log(`Still ${id} @ ${frame}`);
    }
  } else {
    let last = -1;
    await renderMedia({
      serveUrl, composition, outputLocation: path.join(output, '兰亭集序.mp4'),
      codec: 'h264', audioCodec: 'aac', audioBitrate: '192k', pixelFormat: 'yuv420p',
      crf: 18, concurrency: 2, browserExecutable, puppeteerInstance: browser,
      metadata: {title: '兰亭集序', artist: '原文：王羲之', comment: 'Remotion · 原文朗读水墨短片'},
      logLevel: 'error',
      onProgress: ({progress}) => {
        const p = Math.floor(progress * 100 / 5) * 5;
        if (p !== last) {console.log(`Rendering ${p}%`); last = p;}
      },
    });
    console.log(`Final MP4: ${path.join(output, '兰亭集序.mp4')}`);
  }
} finally {await browser.close({silent: true});}
