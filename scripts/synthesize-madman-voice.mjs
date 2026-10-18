import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const exec = promisify(execFile);
const root = path.resolve('public/madman/voice-v2');
const plan = JSON.parse(fs.readFileSync(path.join(root, 'plan.json'), 'utf8'));
const manifestPath = path.join(root, 'manifest.json');
const cli = path.resolve('out/tools/bailian-cli/node_modules/.bin/bl');
const probe = '/opt/homebrew/bin/ffprobe';
const mode = process.argv[2] ?? 'plan';
if (!['plan', 'sample', 'all'].includes(mode)) throw new Error('Choose plan, sample, or all.');
if (mode !== 'plan' && plan.provider !== 'Bailian') throw new Error('The provider has not been selected; no cloud call was made.');
let previous = {cues: []};
if (fs.existsSync(manifestPath)) previous = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const hash = value => createHash('sha256').update(value).digest('hex');
const contentHash = cue => hash(JSON.stringify({text: cue.text, expectedModel: plan.expectedModel, voice: plan.voice, rate: plan.rate, format: plan.format, sampleRate: plan.sampleRate}));
const redact = value => String(value ?? '').replace(/https?:\/\/[^\s"'<>]+/g, '[redacted-url]').replace(/\bBearer\s+\S+/gi, 'Bearer [redacted]').replace(/\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}\b/g, '[redacted-secret]').replace(/(api[_ -]?key|authorization|token|secret|credential)\s*[:=]\s*[^\s,;]+/gi, '$1=[redacted]').replace(/[\r\n\t]+/g, ' ').slice(0, 200);

async function audioInfo(file) {
  const result = await exec(probe, ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', file]);
  const info = JSON.parse(result.stdout);
  const audio = info.streams.find(s => s.codec_type === 'audio');
  if (!audio || audio.codec_name !== 'pcm_s16le' || audio.channels !== 1 || Number(audio.sample_rate) !== plan.sampleRate || Number(info.format.duration) <= 0) throw new Error('Expected valid mono 24 kHz PCM WAV.');
  return {durationSeconds: Number(info.format.duration), sha256: hash(fs.readFileSync(file)), sampleRate: Number(audio.sample_rate), channels: audio.channels};
}

function safeMetadata(stdout) {
  const data = JSON.parse(stdout);
  const result = {};
  function visit(value, depth = 0) {
    if (!value || typeof value !== 'object' || depth > 5) return;
    if (Array.isArray(value)) {value.forEach(v => visit(v, depth + 1)); return;}
    for (const key of ['model', 'voice', 'saved', 'path']) if (typeof value[key] === 'string') result[key] = value[key];
    Object.values(value).forEach(v => visit(v, depth + 1));
  }
  visit(data);
  if (result.model && result.model !== plan.expectedModel) throw new Error('CLI returned a different model; retain the file and review the provider selection.');
  if (result.voice && result.voice !== plan.voice) throw new Error('CLI returned a different voice.');
  return result;
}

if (mode === 'plan') {
  console.log(JSON.stringify({providerSelected: plan.provider === 'Bailian', intendedModel: plan.expectedModel, voice: plan.voice, rate: plan.rate, characters: plan.cues.map(c => c.text).join('').length, cues: plan.cues.length, providerCallsMade: 0}, null, 2));
} else {
  const results = new Map(previous.cues.map(c => [c.id, c]));
  const manifest = {provider: 'Bailian', model: plan.expectedModel, voice: plan.voice, rate: plan.rate, sampleRate: plan.sampleRate, format: plan.format, spokenTextSource: plan.source, cues: []};
  const selected = mode === 'sample' ? plan.cues.slice(0, 1) : plan.cues;
  for (const cue of selected) {
    const file = path.resolve(cue.audioFile);
    const old = results.get(cue.id);
    const key = contentHash(cue);
    if (fs.existsSync(file)) {
      const info = await audioInfo(file);
      if (!old || old.contentHash !== key || old.sha256 !== info.sha256) throw new Error(`Unmatched existing audio ${cue.id}; review before replacing it.`);
      console.log(`Cached ${cue.id}: ${info.durationSeconds}s`);
      continue;
    }
    const textFile = path.join(root, `${cue.id}.txt`);
    fs.writeFileSync(textFile, cue.text + '\n');
    try {
      // No --model override: use the active Profile TTS model, preflighted by root.
      const output = await exec(cli, ['speech', 'synthesize', '--text-file', textFile, '--voice', plan.voice, '--rate', String(plan.rate), '--format', 'wav', '--sample-rate', String(plan.sampleRate), '--out', file, '--concurrent', '1', '--output', 'json'], {timeout: 180000, maxBuffer: 2 * 1024 * 1024});
      const reported = safeMetadata(output.stdout);
      const info = await audioInfo(file);
      results.set(cue.id, {id: cue.id, shotId: cue.shotId, cueIndex: cue.cueIndex, text: cue.text, path: cue.audioFile, contentHash: key, model: reported.model ?? plan.expectedModel, modelReportedByCli: Boolean(reported.model), voice: reported.voice ?? plan.voice, voiceReportedByCli: Boolean(reported.voice), rate: plan.rate, ...info});
      manifest.cues = plan.cues.filter(c => results.has(c.id)).map(c => results.get(c.id));
      fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
      console.log(`Generated ${cue.id}: ${info.durationSeconds}s`);
    } catch (error) {
      throw new Error(`Synthesis stopped at ${cue.id}: ${redact(error.stderr || error.message)}. Existing files were retained.`);
    }
  }
  console.log(`${selected.length} requested cues ready; no model or voice fallback.`);
}
