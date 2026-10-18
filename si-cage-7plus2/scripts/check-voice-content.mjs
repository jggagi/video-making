import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const run = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mode = process.argv[2] ?? 'prepare';
if (!['prepare', 'asr'].includes(mode)) throw new Error('Use prepare (local only), or asr after explicit audio-upload authorization.');
const plan = JSON.parse(fs.readFileSync(path.join(root, 'audio-voiced-v2/voice-plan.json')));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'audio-voiced-v2/voice-manifest.json')));
const input = path.join(root, 'public/audio-voiced-v2/voice-review.wav');
const target = path.join(root, 'audio-voiced-v2/asr-review.json');
const hash = (b) => createHash('sha256').update(b).digest('hex');
const chunks = [];
for (const cue of plan.cues) {
  const record = manifest.cues.find((c) => c.id === cue.id);
  const file = fs.readFileSync(path.join(root, cue.file));
  if (!record || hash(file) !== record.sha256) throw new Error(`Unverified voice ${cue.id}`);
  if (file.readUInt16LE(22) !== 1 || file.readUInt32LE(24) !== 24000 || file.readUInt16LE(34) !== 16) throw new Error('Expected canonical mono 24kHz PCM16.');
  chunks.push(file.subarray(44), Buffer.alloc(7200));
}
const pcm = Buffer.concat(chunks), header = Buffer.alloc(44);
header.write('RIFF', 0); header.writeUInt32LE(36 + pcm.length, 4); header.write('WAVEfmt ', 8); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20); header.writeUInt16LE(1, 22); header.writeUInt32LE(24000, 24); header.writeUInt32LE(48000, 28); header.writeUInt16LE(2, 32); header.writeUInt16LE(16, 34); header.write('data', 36); header.writeUInt32LE(pcm.length, 40);
const audio = Buffer.concat([header, pcm]), inputSha256 = hash(audio);
fs.writeFileSync(input, audio);
if (mode === 'prepare') {
  console.log(JSON.stringify({mode, cloudCallsMade: 0, path: path.relative(root, input), durationSeconds: pcm.length / 48000, inputSha256}, null, 2));
  process.exit(0);
}
if (fs.existsSync(target)) {
  const old = JSON.parse(fs.readFileSync(target));
  if (old.inputSha256 !== inputSha256) throw new Error('Existing ASR result has a different source hash; review before another call.');
  console.log(`Cached ASR: ${old.differences.length} literal character differences.`);
  process.exit(0);
}
const safe = (s) => String(s).replace(/https?:\/\/[^\s"'<>]+/g, '[redacted-url]').replace(/\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}/g, '[redacted-secret]').slice(0, 400);
try {
  const {stdout} = await run(process.env.BAILIAN_CLI ?? '/Users/guoq/.local/n/bin/bl', ['speech', 'recognize', '--url', input, '--language', 'zh', '--output', 'json'], {timeout: 240000, maxBuffer: 4 * 1024 * 1024});
  let response;
  try {response = JSON.parse(stdout);} catch {if (/https?:\/\//.test(stdout)) throw new Error('Unexpected ASR response; no raw output retained.'); response = {text: stdout.trim()};}
  const texts = [];
  const visit = (value, at = '') => {
    if (!value || typeof value !== 'object') return;
    if (typeof value.text === 'string') texts.push({path: at, text: value.text});
    for (const [key, child] of Object.entries(value)) if (child && typeof child === 'object') visit(child, `${at}.${key}`);
  };
  visit(response);
  if (!texts.length) throw new Error('No ASR transcript text in response.');
  const transcript = [...texts].sort((a, b) => b.text.length - a.text.length)[0].text;
  const expectedText = plan.cues.map((c) => c.spokenText).join('');
  const clean = (s) => Array.from(s.replace(/[\p{P}\p{Z}\s]/gu, ''));
  const a = clean(expectedText), b = clean(transcript);
  const d = Array.from({length: a.length + 1}, () => new Uint16Array(b.length + 1));
  for (let i = 0; i <= a.length; i++) d[i][0] = i;
  for (let j = 0; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + Number(a[i - 1] !== b[j - 1]));
  let i = a.length, j = b.length;
  const differences = [];
  while (i || j) {
    if (i && j && d[i][j] === d[i - 1][j - 1] + Number(a[i - 1] !== b[j - 1])) {if (a[i - 1] !== b[j - 1]) differences.push({operation: 'replace', expectedIndex: i - 1, expected: a[i - 1], recognized: b[j - 1]}); i--; j--;}
    else if (i && d[i][j] === d[i - 1][j] + 1) {differences.push({operation: 'delete', expectedIndex: i - 1, expected: a[i - 1]}); i--;}
    else {differences.push({operation: 'insert', expectedIndex: i, recognized: b[j - 1]}); j--;}
  }
  differences.reverse();
  const result = {provider: 'Bailian', requestedModel: 'active Profile ASR default', reportedModel: response.model ?? null, inputSha256, sourceDurationSeconds: pcm.length / 48000, expectedText, transcript, transcripts: texts, differences, comparisonPolicy: 'Ignore punctuation and whitespace only. Digits, symbols, homophones and wording remain literal differences. ASR is not a pronunciation/listening acceptance.'};
  fs.writeFileSync(target, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({sourceDurationSeconds: result.sourceDurationSeconds, differences, reportedModel: result.reportedModel}, null, 2));
} catch (error) {throw new Error('ASR stopped: ' + safe(error.stderr || error.message));}
