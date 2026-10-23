import {createHash} from 'node:crypto';
import {existsSync, readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {dirname, resolve, relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';

const scriptPath = fileURLToPath(import.meta.url);
const projectRoot = resolve(dirname(scriptPath), '..');
const scenePath = resolve(projectRoot, 'src/Scene.tsx');
const outputPath = resolve(projectRoot, '../review/frame-smoke-check.json');
const require = createRequire(resolve(projectRoot, 'package.json'));
const plan = JSON.parse(readFileSync(resolve(projectRoot, 'render-plan.json'), 'utf8'));
const delivery = JSON.parse(readFileSync(resolve(projectRoot, '../delivery.json'), 'utf8'));
const frameCount = delivery.total_frames;
const logicalWidth = plan.composition.logicalCanvas.width;
const logicalHeight = plan.composition.logicalCanvas.height;
const counters = {canvasCalls: 0, numericArguments: 0};

const sha256 = (source) => createHash('sha256').update(source).digest('hex');
const checkNumber = (value) => {
  counters.numericArguments += 1;
  if (!Number.isFinite(value)) throw new RangeError('Non-finite numeric canvas input: ' + String(value));
};
const gradient = () => ({addColorStop(offset) { if (typeof offset === 'number') checkNumber(offset); }});

const makeContext = (canvas) => {
  const state = new Map();
  const methods = new Set([
    'save', 'restore', 'beginPath', 'closePath', 'moveTo', 'lineTo', 'bezierCurveTo',
    'quadraticCurveTo', 'arc', 'ellipse', 'arcTo', 'rect', 'roundRect', 'clearRect',
    'fillRect', 'strokeRect', 'fill', 'stroke', 'clip', 'translate', 'scale', 'rotate',
    'transform', 'setTransform', 'resetTransform', 'setLineDash', 'fillText', 'strokeText',
    'drawImage', 'putImageData', 'createLinearGradient', 'createRadialGradient',
    'createConicGradient', 'createPattern', 'measureText', 'getLineDash', 'getTransform',
    'isPointInPath', 'isPointInStroke', 'getImageData',
  ]);
  const target = {};
  return new Proxy(target, {
    get(_target, property) {
      if (property === 'canvas') return canvas;
      if (state.has(property)) return state.get(property);
      if (property === 'globalAlpha') return state.get(property) ?? 1;
      if (property === 'lineWidth') return state.get(property) ?? 1;
      if (property === 'measureText') return (text) => {
        counters.canvasCalls += 1;
        return {width: String(text).length * 18, actualBoundingBoxAscent: 18, actualBoundingBoxDescent: 4};
      };
      if (property === 'getLineDash') return () => [];
      if (property === 'getTransform') return () => ({a: 1, b: 0, c: 0, d: 1, e: 0, f: 0});
      if (property === 'isPointInPath' || property === 'isPointInStroke') return () => false;
      if (property === 'createLinearGradient' || property === 'createRadialGradient' || property === 'createConicGradient') return (...args) => {
        counters.canvasCalls += 1;
        for (const value of args) if (typeof value === 'number') checkNumber(value);
        return gradient();
      };
      if (property === 'createPattern') return () => ({setTransform() {}});
      if (property === 'getImageData') return (_x, _y, width, height) => ({data: new Uint8ClampedArray(Math.max(0, width * height * 4)), width, height});
      if (typeof property === 'string' && methods.has(property)) return (...args) => {
        counters.canvasCalls += 1;
        for (const value of args) if (typeof value === 'number') checkNumber(value);
        return undefined;
      };
      return undefined;
    },
    set(_target, property, value) {
      if (typeof value === 'number') checkNumber(value);
      state.set(property, value);
      return true;
    },
  });
};

const sourceHashes = {};
let failure = null;
let framesExecuted = 0;
let runtimeMs = 0;
try {
  if (frameCount !== plan.composition.durationInFrames || delivery.fps !== plan.composition.fps) throw new Error('delivery.json frame timing differs from render-plan.json');
  if (!existsSync(scenePath)) throw new Error('Expected project/src/Scene.tsx to export named drawScene(context, frame); Scene.tsx is missing.');
  const sceneSource = readFileSync(scenePath, 'utf8');
  sourceHashes['project/src/Scene.tsx'] = sha256(sceneSource);
  const esbuild = require('esbuild');
  const built = await esbuild.build({
    absWorkingDir: projectRoot,
    entryPoints: [scenePath],
    bundle: true,
    platform: 'node',
    format: 'cjs',
    target: 'node20',
    packages: 'external',
    write: false,
    metafile: true,
    logLevel: 'silent',
  });
  for (const input of Object.keys(built.metafile.inputs)) {
    const absolute = resolve(projectRoot, input);
    if (absolute.startsWith(resolve(projectRoot, 'src') + '/')) {
      sourceHashes['project/' + relative(projectRoot, absolute)] = sha256(readFileSync(absolute));
    }
  }
  const code = built.outputFiles[0].text;
  const module = {exports: {}};
  const execute = new Function('require', 'module', 'exports', code);
  execute(require, module, module.exports);
  const drawScene = module.exports.drawScene;
  if (typeof drawScene !== 'function') throw new Error('Expected project/src/Scene.tsx to export named drawScene(context, frame); export was not found.');
  const canvas = {width: plan.composition.width, height: plan.composition.height};
  const startedAt = process.hrtime.bigint();
  for (let frame = 0; frame < frameCount; frame += 1) {
    try {
      drawScene(makeContext(canvas), frame);
      framesExecuted += 1;
    } catch (error) {
      failure = {frame, name: error instanceof Error ? error.name : 'Error', message: error instanceof Error ? error.message : String(error)};
      break;
    }
  }
  runtimeMs = Number(process.hrtime.bigint() - startedAt) / 1e6;
} catch (error) {
  failure = {frame: framesExecuted, name: error instanceof Error ? error.name : 'Error', message: error instanceof Error ? error.message : String(error)};
}

const report = {
  check: 'EP18 v04 all-frame drawScene runtime smoke',
  contract: 'Named drawScene(context, frame) export from project/src/Scene.tsx; logical canvas dimensions come from render-plan.json.',
  status: failure === null && framesExecuted === frameCount ? 'passed' : 'failed',
  framesExpected: frameCount,
  framesExecuted,
  failure,
  runtimeMs: Math.round(runtimeMs * 100) / 100,
  logicalCanvasSize: {width: logicalWidth, height: logicalHeight},
  backingCanvasSize: {width: plan.composition.width, height: plan.composition.height},
  canvasCalls: counters.canvasCalls,
  finiteNumericArgumentsChecked: counters.numericArguments,
  sourceSha256: sourceHashes,
};
mkdirSync(dirname(outputPath), {recursive: true});
try {
  writeFileSync(outputPath, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
} catch (error) {
  if (error?.code === 'EEXIST') throw new Error('Refusing to overwrite existing frame-smoke-check.json; preserve prior evidence.');
  throw error;
}
process.stdout.write(JSON.stringify(report, null, 2) + '\n');
if (report.status !== 'passed') process.exitCode = 1;
