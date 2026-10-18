import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {BundlerInternals} from '@remotion/bundler';

const run = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const edition = process.argv[3] ?? 'audio-v3';
if (!['audio-v2', 'audio-v3'].includes(edition)) throw new Error('Edition must be audio-v2 or audio-v3.');
const directory = path.join(root, 'public', edition);
const rawDirectory = path.join(directory, 'raw');
const records = path.join(root, edition);
const mode = process.argv[2] ?? 'plan';
if (!['plan', 'sample', 'all'].includes(mode)) throw new Error('Use plan, sample, or all.');
const cli = process.env.BAILIAN_CLI ?? '/Users/guoq/.local/n/bin/bl';
const settings = {provider: 'Bailian', expectedModel: 'cosyvoice-v3-flash', voice: 'longtian_v3', rate: 0.96, format: 'wav', sampleRate: 24000};
fs.mkdirSync(directory, {recursive: true});
fs.mkdirSync(rawDirectory, {recursive: true});
fs.mkdirSync(records, {recursive: true});
const source = await BundlerInternals.esbuild.build({stdin: {contents: "export {SUBTITLES} from './src/lib/timeline';", resolveDir: root, loader: 'ts'}, write: false, bundle: true, platform: 'node', format: 'cjs', logLevel: 'silent'});
const mod = {exports: {}};
vm.runInNewContext(source.outputFiles[0].text, {module: mod, exports: mod.exports, require: createRequire(path.join(root, 'package.json'))});
const cues = mod.exports.SUBTITLES.slice(0, 19).map((c, i) => ({
  id: `voice-${String(i).padStart(2, '0')}`, text: c.zh,
  spokenText: i === 6 ? '热失控，结构坍塌，能量发散。失败先发生在模拟之中。' : c.zh.replace('300', '三百'),
  subtitleFrom: c.from, subtitleTo: c.to,
  startSeconds: i === 0 ? 0.9 : i === 18 ? 159.1 : c.from / 60 + 0.24,
  deadlineSeconds: c.to / 60 - 0.18,
}));
cues.push(
  {id: 'voice-19', text: '人类在现实中试错千次；', spokenText: '人类在现实中试错千次。', subtitleFrom: 9780, subtitleTo: 10080, startSeconds: 163.25, deadlineSeconds: 167.85},
  {id: 'voice-20', text: '超级智能在瞬间穷尽千万个宇宙，', spokenText: '超级智能在瞬间穷尽千万个宇宙，', subtitleFrom: 10080, subtitleTo: 10500, startSeconds: 168.15, deadlineSeconds: 174.8},
  {id: 'voice-21', text: '人类眨眼一瞬，硅基已历万年。', spokenText: '人类眨眼一瞬，硅基已历万年。', subtitleFrom: 10500, subtitleTo: 10800, startSeconds: 175.1, deadlineSeconds: 179.65},
);
const legacy = JSON.parse(fs.readFileSync(path.join(root, 'audio-v2/voice-manifest.json'), 'utf8'));
for (const [key, value] of Object.entries(settings)) if (legacy[key] !== value) throw new Error(`V2 cache setting mismatch: ${key}`);
const reusable = new Map(legacy.cues.map((c) => [c.id, c]));
for (const cue of cues) {
  const cached = reusable.get(cue.id);
  cue.file = edition === 'audio-v3' && cached?.spokenText === cue.spokenText
    ? cached.file
    : `public/${edition}/${cue.id}${cue.id === 'voice-06' ? '-r2' : ''}.wav`;
}
const plan = {version: edition === 'audio-v3' ? 3 : 2, ...settings, fps: 60, durationSeconds: 180, source: 'One Blink, Ten Millennia captions and final title quote', note: 'V3 changes voice-01 to ten millennia and voice-21 to the new final quote. The other 20 verified v2 clips and original score/SFX are reused by hash.', cues};
fs.writeFileSync(path.join(records, 'voice-plan.json'), JSON.stringify(plan, null, 2) + '\n');
const manifestPath = path.join(records, 'voice-manifest.json');
const previous = fs.existsSync(manifestPath) ? JSON.parse(fs.readFileSync(manifestPath, 'utf8')) : (edition === 'audio-v3' ? legacy : {cues: []});
const results = new Map(previous.cues.map((c) => [c.id, c]));
const sha = (data) => createHash('sha256').update(data).digest('hex');
const keyFor = (cue) => sha(JSON.stringify({...settings, spokenText: cue.spokenText}));
const safeError = (value) => String(value).replace(/https?:\/\/[^\s"'<>]+/g, '[redacted-url]').replace(/\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}/g, '[redacted-secret]').replace(/[\r\n]+/g, ' ').slice(0, 350);
const canonicalWave = (rawFile, target) => {
  const input = fs.readFileSync(rawFile);
  if (input.toString('ascii', 0, 4) !== 'RIFF' || input.toString('ascii', 8, 12) !== 'WAVE') throw new Error('Unsupported speech container.');
  let p = 12, format, dataOffset, dataHeader;
  while (p + 8 <= input.length) {
    const type = input.toString('ascii', p, p + 4), size = input.readUInt32LE(p + 4);
    if (type === 'fmt ') format = {tag: input.readUInt16LE(p + 8), channels: input.readUInt16LE(p + 10), rate: input.readUInt32LE(p + 12), byteRate: input.readUInt32LE(p + 16), align: input.readUInt16LE(p + 20), bits: input.readUInt16LE(p + 22)};
    if (type === 'data') {dataOffset = p + 8; dataHeader = p + 4; break;}
    if (p + size + 8 > input.length) throw new Error('Truncated non-audio WAV chunk.');
    p += 8 + size + size % 2;
  }
  if (!format || format.tag !== 1 || format.channels !== 1 || format.rate !== 24000 || format.byteRate !== 48000 || format.align !== 2 || format.bits !== 16 || dataOffset === undefined) throw new Error('WAV normalization supports only validated mono 24 kHz PCM16.');
  const declared = input.readUInt32LE(dataHeader), available = input.length - dataOffset;
  const bytes = Math.min(declared, available);
  if (!bytes || bytes % format.align) throw new Error('WAV payload is not sample-aligned.');
  const output = Buffer.from(input.subarray(0, dataOffset + bytes));
  output.writeUInt32LE(output.length - 8, 4);
  output.writeUInt32LE(bytes, dataHeader);
  if (sha(input.subarray(dataOffset, dataOffset + bytes)) !== sha(output.subarray(dataOffset))) throw new Error('PCM changed during container normalization.');
  fs.writeFileSync(target, output);
  return {rawSha256: sha(input), pcmSha256: sha(output.subarray(dataOffset)), headerNormalized: declared !== bytes || input.readUInt32LE(4) !== input.length - 8, declaredDataBytes: declared, actualDataBytes: bytes};
};
const audioInfo = async (filename) => {
  const {stdout} = await run('ffmpeg', ['-hide_banner', '-v', 'error', '-xerror', '-i', filename, '-ac', '1', '-ar', String(settings.sampleRate), '-f', 's16le', 'pipe:1'], {encoding: 'buffer', maxBuffer: 12 * 1024 * 1024});
  if (!stdout.length || stdout.length % 2) throw new Error('Invalid decoded speech samples.');
  return {durationSeconds: stdout.length / 2 / settings.sampleRate, decodedSamples: stdout.length / 2, sha256: sha(fs.readFileSync(filename))};
};
const save = () => fs.writeFileSync(manifestPath, JSON.stringify({...settings, cliVersion: '2.3.0', providerUsageReported: false, actualBill: null, cues: cues.filter((c) => results.has(c.id)).map((c) => results.get(c.id))}, null, 2) + '\n');
if (mode === 'plan') {
  console.log(JSON.stringify({cues: cues.length, characters: cues.map((c) => c.spokenText).join('').length, ...settings, cloudCallsMade: 0}, null, 2));
} else {
  const selected = mode === 'sample' ? [cues[1]] : cues;
  for (const cue of selected) {
    const file = path.join(root, cue.file);
    const rawFile = path.join(rawDirectory, path.basename(cue.file));
    const contentHash = keyFor(cue);
    const old = results.get(cue.id);
    if (fs.existsSync(file)) {
      const info = await audioInfo(file);
      if (!old || old.contentHash !== contentHash || old.sha256 !== info.sha256) throw new Error(`Unmatched existing audio: ${cue.id}.`);
      results.set(cue.id, {...old, ...cue, reusedFrom: cue.file.startsWith('public/audio-v2/') ? 'audio-v2' : null});
      save();
      console.log(`Cached ${cue.id}: ${info.durationSeconds.toFixed(3)} s`);
      continue;
    }
    // Root's live preflight sample used this exact text, voice and rate in this session.
    const sample = path.join(directory, 'sample.wav');
    let reported;
    if (cue.id === 'voice-01' && fs.existsSync(sample)) {
      const receiptPath = path.join(records, 'sample-receipt.json');
      const receipt = fs.existsSync(receiptPath) ? JSON.parse(fs.readFileSync(receiptPath, 'utf8')) : null;
      if (!receipt || receipt.contentHash !== contentHash || receipt.sha256 !== sha(fs.readFileSync(sample))) throw new Error('Existing sample does not match the current voice/text/settings; review before reuse.');
      fs.copyFileSync(sample, rawFile);
      reported = receipt.reportedByCli;
    } else {
      const textFile = path.join(records, `${cue.id}.txt`);
      fs.writeFileSync(textFile, cue.spokenText + '\n');
      try {
        const {stdout} = await run(cli, ['speech', 'synthesize', '--text-file', textFile, '--voice', settings.voice, '--rate', String(settings.rate), '--format', settings.format, '--sample-rate', String(settings.sampleRate), '--out', rawFile, '--concurrent', '1', '--output', 'json'], {timeout: 180000, maxBuffer: 1024 * 1024});
        const response = JSON.parse(stdout);
        reported = {model: response.model ?? null, voice: response.voice ?? null};
      } catch (error) {
        throw new Error(`Synthesis stopped at ${cue.id}: ${safeError(error.stderr || error.message)}. Existing clips retained.`);
      }
    }
    if (reported.model !== settings.expectedModel || reported.voice !== settings.voice) throw new Error(`Unexpected or missing CLI model/voice report for ${cue.id}; preserve audio for review.`);
    const container = canonicalWave(rawFile, file);
    const info = await audioInfo(file);
    results.set(cue.id, {...cue, contentHash, modelReportedByCli: reported.model, voiceReportedByCli: reported.voice, modelReportedByProvider: null, voiceReportedByProvider: null, ...container, ...info});
    save();
    console.log(`Ready ${cue.id}: ${info.durationSeconds.toFixed(3)} s`);
  }
  console.log(`${selected.length} requested cues ready; no provider/model/voice fallback.`);
}
