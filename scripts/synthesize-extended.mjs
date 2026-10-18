import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {pathToFileURL} from 'node:url';

const execFileAsync = promisify(execFile);
export const MODEL = 'cosyvoice-v3-flash';
export const VOICE = 'longsanshu_v3';
export const FORMAT = 'wav';
export const SAMPLE_RATE = 24000;
const CLI = path.resolve('out/tools/bailian-cli/node_modules/.bin/bl');
const TIMELINE_FILE = path.resolve('src/museum/timeline.json');
const OUTPUT_ROOT = path.resolve('out/extended');
const SPEECH_ROOT = path.join(OUTPUT_ROOT, 'speech');
const INPUT_ROOT = path.join(OUTPUT_ROOT, 'scripts');
const MANIFEST_FILE = path.join(OUTPUT_ROOT, 'manifest.json');
const EXPECTED_CUE_COUNT = 26;
const EXPECTED_SCENE_COUNT = 17;

const pronunciations = [
  ['会稽', 'kuai4 ji1'],
  ['修禊', 'xiu1 xi4'],
  ['少长', 'shao4 zhang3'],
  ['夫人', 'fu2 ren2'],
  ['悟言', 'wu4 yan2'],
  ['趣舍', 'qu3 she3'],
  ['悲夫', 'bei1 fu2'],
  ['骋怀', 'cheng3 huai2'],
  ['彭殇', 'peng2 shang1'],
  ['系之', 'xi4 zhi1'],
];

const sha256 = (value) => createHash('sha256').update(value).digest('hex');
const xmlEscape = (value) => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&apos;');

export function buildSsml(text, rate) {
  let inner = xmlEscape(text);
  for (const [word, phonemes] of pronunciations) {
    const escapedWord = xmlEscape(word);
    inner = inner.replaceAll(escapedWord, `<phoneme alphabet="py" ph="${phonemes}">${escapedWord}</phoneme>`);
  }
  return `<speak rate="${rate.toFixed(2)}">${inner}</speak>`;
}

export function buildPlan(timeline = JSON.parse(fs.readFileSync(TIMELINE_FILE, 'utf8'))) {
  const scenes = timeline.shots.filter((shot) => shot.kind === 'scene');
  if (scenes.length !== EXPECTED_SCENE_COUNT) {
    throw new Error(`Expected ${EXPECTED_SCENE_COUNT} scene passages; found ${scenes.length}.`);
  }
  const cues = [];
  for (const scene of scenes) {
    for (const [index, cue] of scene.cues.entries()) {
      const rate = scene.mood === 'reflect' ? 0.78 : 0.82;
      const ssml = buildSsml(cue.text, rate);
      const contentHash = sha256(JSON.stringify({ssml, model: MODEL, voice: VOICE, format: FORMAT}));
      const file = `cue-${contentHash}.wav`;
      cues.push({
        sceneId: scene.id,
        cueIndex: index + 1,
        originalText: cue.text,
        rate,
        ssml,
        contentHash,
        textPath: path.join(INPUT_ROOT, `cue-${contentHash}.txt`),
        ssmlPath: path.join(INPUT_ROOT, `cue-${contentHash}.ssml`),
        outputPath: path.join(SPEECH_ROOT, file),
        relativePath: path.posix.join('out/extended/speech', file),
      });
    }
  }
  if (cues.length !== EXPECTED_CUE_COUNT) {
    throw new Error(`Expected ${EXPECTED_CUE_COUNT} narration cues; found ${cues.length}.`);
  }
  for (const scene of scenes) {
    const sourceText = scene.cues.map((cue) => cue.text).join('');
    if (sourceText !== scene.text) throw new Error(`Source cue text does not exactly cover passage ${scene.id}.`);
  }
  return cues;
}

function wavInfo(file) {
  const buffer = fs.readFileSync(file);
  if (buffer.length < 44 || buffer.toString('ascii', 0, 4) !== 'RIFF' || buffer.toString('ascii', 8, 12) !== 'WAVE') return null;
  if (buffer.readUInt16LE(20) !== 1 || buffer.readUInt16LE(22) !== 1 || buffer.readUInt32LE(24) !== SAMPLE_RATE) return null;
  const blockAlign = buffer.readUInt16LE(32);
  const declaredDataBytes = buffer.readUInt32LE(40);
  const availableDataBytes = buffer.length - 44;
  const isStreamingLength = declaredDataBytes > availableDataBytes && declaredDataBytes >= 0x7fff0000;
  const dataBytes = isStreamingLength ? availableDataBytes : declaredDataBytes;
  if (blockAlign !== 2 || dataBytes <= 0 || dataBytes % blockAlign !== 0 || dataBytes > availableDataBytes) return null;
  const samples = dataBytes / blockAlign;
  return {samples, durationSeconds: samples / SAMPLE_RATE, sha256: sha256(buffer)};
}

function loadPreviousManifest() {
  try {
    return JSON.parse(fs.readFileSync(MANIFEST_FILE, 'utf8'));
  } catch {
    return null;
  }
}

function findReusable(cue, prior) {
  if (!prior || prior.model !== MODEL || prior.voice !== VOICE || prior.format !== FORMAT || prior.sampleRate !== SAMPLE_RATE) return null;
  const old = prior.cues?.find((item) => item.sceneId === cue.sceneId && item.cueIndex === cue.cueIndex);
  if (!old || old.contentHash !== cue.contentHash || old.text !== cue.originalText || old.path !== cue.relativePath) return null;
  if (old.model !== MODEL || old.voice !== VOICE || old.rate !== cue.rate || old.format !== FORMAT || old.sampleRate !== SAMPLE_RATE) return null;
  if (!fs.existsSync(cue.outputPath)) return null;
  const info = wavInfo(cue.outputPath);
  if (!info || old.sha256 !== info.sha256 || Math.abs(Number(old.durationSeconds) - info.durationSeconds) > 1 / SAMPLE_RATE) return null;
  return {...old, durationSeconds: info.durationSeconds, sha256: info.sha256};
}

function safeCliError(value) {
  return String(value ?? '')
    .replace(/https?:\/\/[^\s"'<>]+/gi, '[redacted-url]')
    .replace(/\bBearer\s+[^\s,;]+/gi, 'Bearer [redacted]')
    .replace(/\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}\b/gi, '[redacted-secret]')
    .replace(/(api[_ -]?key|authorization|access[_ -]?token|secret|credential)\s*[:=]\s*[^\s,;]+/gi, '$1=[redacted]')
    .replace(/\b[0-9a-f]{32,}\b/gi, '[redacted-id]')
    .replace(/[\r\n\t]+/g, ' ')
    .trim()
    .slice(0, 240);
}

function safeResultFields(stdout, expectedPath) {
  let parsed;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw new Error('CLI returned no valid JSON result.');
  }
  const objects = [];
  const visit = (value, depth = 0) => {
    if (!value || typeof value !== 'object' || depth > 4) return;
    if (Array.isArray(value)) {
      for (const child of value) visit(child, depth + 1);
      return;
    }
    objects.push(value);
    for (const child of Object.values(value)) visit(child, depth + 1);
  };
  visit(parsed);
  const reported = {};
  for (const object of objects) {
    if (!reported.model && typeof object.model === 'string') reported.model = object.model;
    if (!reported.voice && typeof object.voice === 'string') reported.voice = object.voice;
    for (const field of ['saved', 'path', 'output']) {
      if (!reported.saved && typeof object[field] === 'string') reported.saved = object[field];
    }
  }
  if (reported.model && reported.model !== MODEL) throw new Error('CLI reported a different model.');
  if (reported.voice && reported.voice !== VOICE) throw new Error('CLI reported a different voice.');
  if (reported.saved) {
    if (/^https?:\/\//i.test(reported.saved) || path.resolve(reported.saved) !== expectedPath) {
      throw new Error('CLI reported an unexpected saved-file location.');
    }
  }
  return {saved: expectedPath, model: reported.model ?? MODEL, voice: reported.voice ?? VOICE};
}

function entryFor(cue, info, cliResult) {
  return {
    sceneId: cue.sceneId,
    cueIndex: cue.cueIndex,
    contentHash: cue.contentHash,
    model: cliResult.model,
    voice: cliResult.voice,
    rate: cue.rate,
    format: FORMAT,
    sampleRate: SAMPLE_RATE,
    text: cue.originalText,
    path: cue.relativePath,
    sha256: info.sha256,
    durationSeconds: info.durationSeconds,
  };
}

async function synthesize(cue) {
  const args = [
    'speech', 'synthesize',
    '--text-file', cue.ssmlPath,
    '--model', MODEL,
    '--voice', VOICE,
    '--enable-ssml',
    '--format', FORMAT,
    '--sample-rate', String(SAMPLE_RATE),
    '--out', cue.outputPath,
    '--concurrent', '1',
    '--output', 'json',
  ];
  try {
    const result = await execFileAsync(CLI, args, {maxBuffer: 2 * 1024 * 1024, timeout: 180000});
    const cliResult = safeResultFields(result.stdout, cue.outputPath);
    const info = fs.existsSync(cue.outputPath) ? wavInfo(cue.outputPath) : null;
    if (!info) throw new Error('CLI completed without a valid mono 24000 Hz WAV file.');
    return entryFor(cue, info, cliResult);
  } catch (error) {
    const code = Number.isInteger(error?.code) ? ` (exit ${error.code})` : '';
    const detail = safeCliError(error?.stderr || error?.message || 'unknown CLI error');
    throw new Error(`Speech synthesis failed for ${cue.sceneId} cue ${cue.cueIndex}${code}: ${detail || 'provider details suppressed'}`);
  }
}

function writeInputs(cues) {
  fs.mkdirSync(INPUT_ROOT, {recursive: true});
  for (const cue of cues) {
    fs.writeFileSync(cue.textPath, `${cue.originalText}\n`);
    fs.writeFileSync(cue.ssmlPath, `${cue.ssml}\n`);
  }
}

async function run() {
  const planOnly = process.argv.includes('--plan') || process.argv.includes('--check');
  const cues = buildPlan();
  writeInputs(cues);
  const previous = loadPreviousManifest();
  const reusable = new Map(cues.map((cue) => [cue.contentHash, findReusable(cue, previous)]));
  if (planOnly) {
    const plan = {
      model: MODEL,
      voice: VOICE,
      format: FORMAT,
      sampleRate: SAMPLE_RATE,
      requests: cues.length,
      maxParallelRequests: 2,
      providerCallsMade: 0,
      cues: cues.map((cue) => ({sceneId: cue.sceneId, cueIndex: cue.cueIndex, rate: cue.rate, text: cue.originalText, contentHash: cue.contentHash, ssmlPath: path.relative(process.cwd(), cue.ssmlPath), outputPath: cue.relativePath, cached: reusable.get(cue.contentHash) !== null})),
    };
    fs.mkdirSync(OUTPUT_ROOT, {recursive: true});
    fs.writeFileSync(path.join(OUTPUT_ROOT, 'plan.json'), `${JSON.stringify(plan, null, 2)}\n`);
    console.log(`${cues.length} cues planned; 0 provider calls; model ${MODEL}; voice ${VOICE}.`);
    return;
  }

  if (!fs.existsSync(CLI)) throw new Error(`Project-local Bailian CLI is missing: ${path.relative(process.cwd(), CLI)}.`);
  fs.mkdirSync(SPEECH_ROOT, {recursive: true});
  const results = new Map();
  for (const cue of cues) {
    const cached = findReusable(cue, previous);
    if (cached) results.set(`${cue.sceneId}:${cue.cueIndex}`, cached);
  }
  let cursor = 0;
  let failure = null;
  const worker = async () => {
    while (cursor < cues.length && !failure) {
      const cue = cues[cursor++];
      if (results.has(`${cue.sceneId}:${cue.cueIndex}`)) continue;
      try {
        const entry = await synthesize(cue);
        results.set(`${cue.sceneId}:${cue.cueIndex}`, entry);
      } catch (error) {
        failure = error;
      }
    }
  };
  await Promise.all([worker(), worker()]);
  const manifest = {
    model: MODEL,
    voice: VOICE,
    format: FORMAT,
    sampleRate: SAMPLE_RATE,
    channels: 1,
    cues: cues.filter((cue) => results.has(`${cue.sceneId}:${cue.cueIndex}`))
      .map((cue) => results.get(`${cue.sceneId}:${cue.cueIndex}`)),
  };
  fs.mkdirSync(OUTPUT_ROOT, {recursive: true});
  fs.writeFileSync(MANIFEST_FILE, `${JSON.stringify(manifest, null, 2)}\n`);
  if (failure) throw failure;
  if (manifest.cues.length !== EXPECTED_CUE_COUNT) throw new Error(`Only ${manifest.cues.length} of ${EXPECTED_CUE_COUNT} cues are ready.`);
  console.log(`${manifest.cues.length} cues ready; all files are mono ${SAMPLE_RATE} Hz WAV.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  run().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
