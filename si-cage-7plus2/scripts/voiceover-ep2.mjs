import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import ts from 'typescript';

const run = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const edition = 'audio-voiced-v2';
const records = path.join(root, edition);
const publicDir = path.join(root, 'public', edition);
const mode = process.argv[2] ?? 'plan';
if (!['plan', 'sample', 'all'].includes(mode)) throw new Error('Use plan, sample, or all.');
const cli = process.env.BAILIAN_CLI ?? '/Users/guoq/.local/n/bin/bl';
const settings = {provider: 'Bailian', expectedModel: 'cosyvoice-v3-flash', voice: 'longtian_v3', rate: 0.96, format: 'wav', sampleRate: 24000};
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
for (const dir of [records, publicDir, path.join(publicDir, 'raw')]) fs.mkdirSync(dir, {recursive: true});
const source = fs.readFileSync(path.join(root, 'src/lib/captions.ts'), 'utf8');
const {outputText} = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022}});
const {captions} = await import('data:text/javascript;base64,' + Buffer.from(outputText).toString('base64'));
const cues = captions.map((c, i) => ({
  id: `voice-${String(i).padStart(2, '0')}`, text: c.zh,
  spokenText: c.zh.replaceAll('7±2', '七加减二').replaceAll('……', '，'),
  subtitleFrom: c.from, subtitleTo: c.to,
  startFrame: i === 3 ? 1242 : i === 11 ? 7200 : c.from + 14,
  deadlineFrame: Math.min(c.to - 11, 10788),
  file: `public/${edition}/voice-${String(i).padStart(2, '0')}.wav`,
}));
cues.splice(cues.length - 1, 0, {
  id: 'voice-quote', text: '不是它不愿向人类解释，而是 7±2 的容器，装不下一座十万维的宇宙。',
  spokenText: '不是它不愿向人类解释，而是七加减二的容器，装不下一座十万维的宇宙。',
  subtitleFrom: 10000, subtitleTo: 10550, startFrame: 10008, deadlineFrame: 10530,
  file: `public/${edition}/voice-quote.wav`,
});
const plan = {version: 2, ...settings, fps: 60, durationInFrames: 10800, sampleRate: 48000, sourceSampleRate: settings.sampleRate, source: 'Current EP02 Chinese subtitles plus the visible closing quote', alignment: 'Sentence-level placement inside existing subtitle intervals; no word timestamps claimed.', pronunciation: {'7±2': '七加减二'}, overloadVoiceEntryFrame: 1242, cues};
fs.writeFileSync(path.join(records, 'voice-plan.json'), JSON.stringify(plan, null, 2) + '\n');
const manifestPath = path.join(records, 'voice-manifest.json');
const previous = fs.existsSync(manifestPath) ? JSON.parse(fs.readFileSync(manifestPath, 'utf8')) : {cues: [], attempts: []};
const results = new Map(previous.cues.map((c) => [c.id, c]));
const attempts = previous.attempts ?? [];
const contentHashFor = (cue) => sha(JSON.stringify({...settings, spokenText: cue.spokenText}));
const save = () => fs.writeFileSync(manifestPath, JSON.stringify({...settings, cliVersion: '2.3.1', providerUsageReported: false, actualBill: null, attempts, cues: cues.filter((c) => results.has(c.id)).map((c) => results.get(c.id))}, null, 2) + '\n');
const safeError = (s) => String(s).replace(/https?:\/\/[^\s"'<>]+/g, '[redacted-url]').replace(/\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}/g, '[redacted-secret]').replace(/[\r\n]+/g, ' ').slice(0, 400);

function canonicalize(rawFile, target) {
  const input = fs.readFileSync(rawFile);
  if (input.toString('ascii', 0, 4) !== 'RIFF' || input.toString('ascii', 8, 12) !== 'WAVE') throw new Error('Unsupported speech container.');
  let pos = 12, fmt, payload, declared;
  while (pos + 8 <= input.length) {
    const type = input.toString('ascii', pos, pos + 4), size = input.readUInt32LE(pos + 4);
    if (type === 'fmt ') fmt = {tag: input.readUInt16LE(pos + 8), channels: input.readUInt16LE(pos + 10), rate: input.readUInt32LE(pos + 12), byteRate: input.readUInt32LE(pos + 16), align: input.readUInt16LE(pos + 20), bits: input.readUInt16LE(pos + 22)};
    if (type === 'data') {declared = size; payload = input.subarray(pos + 8, pos + 8 + Math.min(size, input.length - pos - 8)); break;}
    if (pos + size + 8 > input.length) throw new Error('Truncated WAV metadata.');
    pos += size + 8 + size % 2;
  }
  if (!fmt || fmt.tag !== 1 || fmt.channels !== 1 || fmt.rate !== 24000 || fmt.bits !== 16 || fmt.align !== 2 || fmt.byteRate !== 48000 || !payload?.length || payload.length % 2) throw new Error('Expected sample-aligned mono 24kHz PCM16 WAV.');
  const out = Buffer.alloc(44 + payload.length);
  out.write('RIFF', 0); out.writeUInt32LE(out.length - 8, 4); out.write('WAVEfmt ', 8); out.writeUInt32LE(16, 16);
  out.writeUInt16LE(1, 20); out.writeUInt16LE(1, 22); out.writeUInt32LE(24000, 24); out.writeUInt32LE(48000, 28); out.writeUInt16LE(2, 32); out.writeUInt16LE(16, 34);
  out.write('data', 36); out.writeUInt32LE(payload.length, 40); payload.copy(out, 44);
  fs.writeFileSync(target, out);
  return {rawSha256: sha(input), pcmSha256: sha(payload), declaredDataBytes: declared, actualDataBytes: payload.length, headerNormalized: declared !== payload.length || input.readUInt32LE(4) !== input.length - 8};
}

async function info(file) {
  const {stdout} = await run('ffmpeg', ['-v', 'error', '-xerror', '-i', file, '-ac', '1', '-ar', '24000', '-f', 's16le', '-'], {encoding: 'buffer', maxBuffer: 8 * 1024 * 1024});
  if (!stdout.length || stdout.length % 2) throw new Error('Empty or unaligned decoded audio.');
  return {sha256: sha(fs.readFileSync(file)), decodedSamples: stdout.length / 2, durationSeconds: stdout.length / 48000, decodedPcmSha256: sha(stdout)};
}

if (mode === 'plan') {
  console.log(JSON.stringify({cues: cues.length, characters: cues.map((c) => c.spokenText).join('').length, ...settings, cloudCallsMade: 0}, null, 2));
} else {
  const preflight = JSON.parse(fs.readFileSync(path.join(records, 'preflight.json'), 'utf8'));
  if (preflight.cliVersion !== '2.3.1' || preflight.skillVersion !== '2.3.1' || preflight.effectiveTtsModel !== settings.expectedModel || preflight.voice !== settings.voice) throw new Error('Provider preflight does not match this plan.');
  const selected = mode === 'sample' ? [cues.find((c) => c.id === 'voice-quote')] : cues;
  for (const cue of selected) {
    const target = path.join(root, cue.file), rawFile = path.join(publicDir, 'raw', path.basename(target));
    const contentHash = contentHashFor(cue), old = results.get(cue.id);
    if (fs.existsSync(target)) {
      const measured = await info(target);
      if (!old || old.contentHash !== contentHash || old.sha256 !== measured.sha256) throw new Error(`Unmatched existing cache ${cue.id}; retained for review.`);
      results.set(cue.id, {...old, ...cue}); save();
      console.log(`Cached ${cue.id}: ${measured.durationSeconds.toFixed(3)}s`);
      continue;
    }
    if (fs.existsSync(rawFile)) throw new Error(`Unverified raw cache retained at ${rawFile}; inspect before another call.`);
    const textFile = path.join(records, cue.id + '.txt');
    fs.writeFileSync(textFile, cue.spokenText + '\n');
    const attempt = {id: cue.id, contentHash, status: 'started'}; attempts.push(attempt); save();
    try {
      const {stdout} = await run(cli, ['speech', 'synthesize', '--text-file', textFile, '--voice', settings.voice, '--rate', String(settings.rate), '--format', 'wav', '--sample-rate', '24000', '--out', rawFile, '--concurrent', '1', '--output', 'json'], {timeout: 180000, maxBuffer: 1024 * 1024});
      const reported = JSON.parse(stdout);
      if (reported.model !== settings.expectedModel || reported.voice !== settings.voice) throw new Error('CLI model/voice differs from the selected profile; preserve result for review.');
      const container = canonicalize(rawFile, target), measured = await info(target);
      if (container.pcmSha256 !== measured.decodedPcmSha256) throw new Error('Canonical normalization changed speech PCM.');
      results.set(cue.id, {...cue, contentHash, modelReportedByCli: reported.model, voiceReportedByCli: reported.voice, modelReportedByProvider: null, voiceReportedByProvider: null, ...container, ...measured});
      attempt.status = 'success'; save();
      console.log(`Ready ${cue.id}: ${measured.durationSeconds.toFixed(3)}s (window ${((cue.deadlineFrame - cue.startFrame) / 60).toFixed(3)}s)`);
    } catch (error) {
      attempt.status = 'failed'; attempt.error = safeError(error.stderr || error.message); save();
      throw new Error(`Stopped at ${cue.id}: ${attempt.error}; existing clips preserved.`);
    }
  }
  console.log(`${selected.length} requested cues ready; provider/model/voice unchanged.`);
}
