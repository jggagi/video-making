import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const work = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const deliveryPath = path.join(work, 'delivery.json');
const reviewDir = path.join(work, 'review');
const sdk = '/Users/guoq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const expectedLayouts = [
  {layout: 'landscape', key: 'bilibili', button: 'B站 · 4K 横屏', width: 3840, height: 2160},
  {layout: 'portrait', key: 'xiaohongshu', button: '小红书 · 4K 竖屏', width: 2160, height: 3840},
];

function mimeType(file) {
  return ({
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.mp4': 'video/mp4',
    '.srt': 'text/plain; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.wav': 'audio/wav',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
  })[path.extname(file).toLowerCase()] ?? 'application/octet-stream';
}

function makeLocalServer(root) {
  const realRoot = fs.realpathSync(root);
  const requests = [];
  const server = http.createServer((request, response) => {
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://127.0.0.1').pathname);
    } catch {
      response.writeHead(400).end('Bad request');
      return;
    }
    if (pathname === '/') pathname = '/watch.html';
    const file = path.resolve(realRoot, `.${pathname}`);
    if (file !== realRoot && !file.startsWith(`${realRoot}${path.sep}`)) {
      response.writeHead(403).end('Forbidden');
      return;
    }
    if (!['GET', 'HEAD'].includes(request.method ?? '')) {
      response.writeHead(405, {Allow: 'GET, HEAD'}).end('Method not allowed');
      return;
    }
    let info;
    let realFile;
    try {
      realFile = fs.realpathSync(file);
      if (realFile !== realRoot && !realFile.startsWith(`${realRoot}${path.sep}`)) {
        response.writeHead(403).end('Forbidden');
        return;
      }
      info = fs.statSync(realFile);
    } catch {
      requests.push({method: request.method, path: pathname, status: 404});
      response.writeHead(404).end('Not found');
      return;
    }
    if (!info.isFile()) {
      requests.push({method: request.method, path: pathname, status: 404});
      response.writeHead(404).end('Not found');
      return;
    }

    const headers = {
      'Accept-Ranges': 'bytes',
      'Content-Type': mimeType(realFile),
      'Cross-Origin-Resource-Policy': 'same-origin',
    };
    const range = request.headers.range;
    let start = 0;
    let end = info.size - 1;
    let status = 200;
    if (range) {
      const match = /^bytes=(\d*)-(\d*)$/.exec(range);
      if (!match || (!match[1] && !match[2])) {
        response.writeHead(416, {'Content-Range': `bytes */${info.size}`}).end();
        requests.push({method: request.method, path: pathname, status: 416});
        return;
      }
      if (!match[1]) {
        const suffixLength = Number(match[2]);
        start = Math.max(0, info.size - suffixLength);
      } else {
        start = Number(match[1]);
        if (match[2]) end = Math.min(Number(match[2]), end);
      }
      if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start > end || start >= info.size) {
        response.writeHead(416, {'Content-Range': `bytes */${info.size}`}).end();
        requests.push({method: request.method, path: pathname, status: 416});
        return;
      }
      status = 206;
      headers['Content-Range'] = `bytes ${start}-${end}/${info.size}`;
    }
    headers['Content-Length'] = end - start + 1;
    requests.push({method: request.method, path: pathname, status, range: range ?? null});
    response.writeHead(status, headers);
    if (request.method === 'HEAD') {
      response.end();
      return;
    }
    fs.createReadStream(realFile, {start, end}).pipe(response);
  });
  return {server, requests};
}

function loadDelivery() {
  let delivery;
  try {
    delivery = JSON.parse(fs.readFileSync(deliveryPath, 'utf8'));
  } catch (error) {
    throw new Error(`Cannot read delivery.json: ${error.message}`);
  }
  if (delivery.slug !== path.basename(work)
      || delivery.duration_seconds !== 120 || delivery.fps !== 60 || delivery.total_frames !== 7200) {
    throw new Error('delivery.json does not describe this 120-second, 60-fps, 7200-frame delivery');
  }
  for (const layout of expectedLayouts) {
    const output = delivery.outputs?.[layout.key];
    if (!output || output.width !== layout.width || output.height !== layout.height || typeof output.path !== 'string') {
      throw new Error(`delivery.json outputs.${layout.key} has unexpected dimensions or path`);
    }
    const media = path.resolve(work, output.path);
    const realWork = fs.realpathSync(work);
    if (!fs.existsSync(media)) throw new Error(`Final ${layout.layout} MP4 is missing: ${output.path}`);
    const realMedia = fs.realpathSync(media);
    if (realMedia !== realWork && !realMedia.startsWith(`${realWork}${path.sep}`)) {
      throw new Error(`delivery.json outputs.${layout.key} escapes the delivery folder`);
    }
    if (!fs.statSync(realMedia).isFile()) throw new Error(`Final ${layout.layout} MP4 is missing: ${output.path}`);
    layout.mediaPath = `/${path.relative(realWork, realMedia).split(path.sep).map(encodeURIComponent).join('/')}`;
    layout.mediaRequestPath = `/${path.relative(realWork, realMedia).split(path.sep).join('/')}`;
  }
  return delivery;
}

async function main() {
  const delivery = loadDelivery();
  const {chromium} = await import(pathToFileURL(sdk).href);
  const {server, requests} = makeLocalServer(work);
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Local review server did not bind an ephemeral TCP port');
  const baseUrl = `http://127.0.0.1:${address.port}`;
  let browser;
  const errors = [];
  const expectedMediaCancellations = [];
  const results = [];
  let failure = null;
  try {
    browser = await chromium.launch({
      headless: true,
      executablePath: chrome,
      args: ['--autoplay-policy=no-user-gesture-required'],
    });
    const page = await browser.newPage({viewport: {width: 1280, height: 1000}});
    const localOrigin = new URL(baseUrl).origin;
    await page.route('**/*', route => {
      if (new URL(route.request().url()).origin === localOrigin) return route.continue();
      return route.abort();
    });
    page.on('pageerror', error => errors.push(error.message));
    page.on('requestfailed', request => {
      const reason=request.failure()?.errorText ?? 'request failed';
      const isMedia=expectedLayouts.some(layout=>layout.mediaPath===new URL(request.url()).pathname);
      // A seek or source switch intentionally cancels the preceding media Range.
      // Real element errors, failed HTTP responses and failed seeks stay fatal.
      if(reason==='net::ERR_ABORTED'&&isMedia){expectedMediaCancellations.push({path:new URL(request.url()).pathname,reason});return;}
      errors.push(`${request.method()} ${request.url()}: ${reason}`);
    });
    await page.goto(`${baseUrl}/watch.html`, {waitUntil: 'domcontentloaded'});
    if (!requests.some(item => item.path === '/watch.html' && item.status === 200)) {
      throw new Error('The watch page was not served successfully over local HTTP');
    }
    const snapshot = await page.locator('body').innerText();
    for (const layout of expectedLayouts) {
      if (!snapshot.includes(layout.button)) throw new Error(`Player control missing: ${layout.button}`);
    }

    for (const layout of expectedLayouts) {
      await page.getByRole('button', {name: layout.button, exact: true}).click();
      await page.waitForFunction(
        () => { const video = document.querySelector('#film'); return video?.readyState >= 2 && video.duration > 0; },
        null,
        {timeout: 30000},
      );
      const video = page.locator('#film');
      const meta = await video.evaluate(videoEl => ({
        width: videoEl.videoWidth,
        height: videoEl.videoHeight,
        duration: videoEl.duration,
        currentSrc: new URL(videoEl.currentSrc).pathname,
        error: videoEl.error?.message ?? null,
      }));
      if (meta.width !== layout.width || meta.height !== layout.height
          || Math.abs(meta.duration - delivery.duration_seconds) > 0.05
          || meta.currentSrc !== layout.mediaPath || meta.error) {
        throw new Error(`Metadata or served source mismatch for ${layout.layout}: ${JSON.stringify(meta)}`);
      }

      await video.evaluate(async videoEl => {
        videoEl.muted = true;
        videoEl.currentTime = 0;
        await videoEl.play();
      });
      await page.waitForFunction(() => document.querySelector('#film')?.currentTime > 0.7, null, {timeout: 15000});
      const playback = await video.evaluate(videoEl => ({
        time: videoEl.currentTime,
        paused: videoEl.paused,
        totalFrames: videoEl.getVideoPlaybackQuality().totalVideoFrames,
        droppedFrames: videoEl.getVideoPlaybackQuality().droppedVideoFrames,
      }));
      if (playback.paused || playback.totalFrames < 3) throw new Error(`Playback did not advance for ${layout.layout}`);

      const seeks = [];
      for (const target of [16, 48, 80, 96.5, 118.5]) {
        await video.evaluate(async (videoEl, time) => {
          videoEl.pause();
          await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('seek timed out')), 15000);
            videoEl.addEventListener('seeked', () => { clearTimeout(timeout); resolve(); }, {once: true});
            videoEl.addEventListener('error', () => { clearTimeout(timeout); reject(new Error(videoEl.error?.message ?? 'video seek failed')); }, {once: true});
            videoEl.currentTime = time;
          });
        }, target);
        const value = await video.evaluate(videoEl => ({
          time: videoEl.currentTime,
          readyState: videoEl.readyState,
          error: videoEl.error?.message ?? null,
        }));
        if (Math.abs(value.time - target) > 0.1 || value.readyState < 2 || value.error) {
          throw new Error(`Seek failed for ${layout.layout} at ${target}s: ${JSON.stringify(value)}`);
        }
        seeks.push({target, ...value});
      }
      await fs.promises.mkdir(reviewDir, {recursive: true});
      await page.screenshot({
        path: path.join(reviewDir, `browser-player-${layout.layout}.jpg`),
        fullPage: true,
        type: 'jpeg',
        quality: 90,
      });
      results.push({layout: layout.layout, sourcePath: layout.mediaPath, metadata: meta, playback, seeks});
    }
    if (errors.length) throw new Error(errors.join('\n'));
    for (const layout of expectedLayouts) {
      if (!requests.some(item => item.path === layout.mediaRequestPath && item.status === 206)) {
        throw new Error(`No successful HTTP byte-range response was recorded for ${layout.layout}`);
      }
    }
  } catch (error) {
    failure = error instanceof Error ? error.message : String(error);
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }

  const report = {
    expected_media_range_cancellations: expectedMediaCancellations,
    schema_version: 1,
    status: failure ? 'FAIL' : 'evidence_collected',
    acceptance_status: 'NOT_EVALUATED',
    method: 'Muted playback and seeks in Google Chrome through an ephemeral loopback HTTP server with byte-range support.',
    results,
    local_server: {
      origin: baseUrl,
      served_watch_page: requests.some(item => item.path === '/watch.html' && item.status === 200),
      successful_media_range_requests: requests.filter(item => item.status === 206).map(({path: servedPath, range}) => ({path: servedPath, range})),
      failed_requests: requests.filter(item => item.status >= 400),
    },
    error: failure,
    limitations: [
      'Playback was muted; this check makes no claim about listening, mix quality, or pronunciation.',
      'Automated browser playback does not establish continuous human review, phone playback, or platform App acceptance.',
    ],
  };
  await fs.promises.mkdir(reviewDir, {recursive: true});
  await fs.promises.writeFile(path.join(reviewDir, 'browser-player-qa.json'), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (failure) process.exitCode = 1;
}

await main();
