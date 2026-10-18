import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const run = promisify(execFile);
const input = path.resolve(root, process.argv[2] ?? 'audio-v2/asr-input.wav');
const target = path.resolve(root, process.argv[3] ?? 'audio-v2/asr-review.json');
if (fs.existsSync(target)) throw new Error('ASR review already exists; inspect it before making another paid request.');
try {
  const {stdout} = await run(process.env.BAILIAN_CLI ?? '/Users/guoq/.local/n/bin/bl', ['speech', 'recognize', '--url', input, '--language', 'zh', '--output', 'json'], {timeout: 180000, maxBuffer: 4 * 1024 * 1024});
  let response;
  try { response = JSON.parse(stdout); }
  catch {
    if (!stdout.trim() || /https?:\/\//.test(stdout)) throw new Error('Unexpected ASR output; no transcript cached.');
    response = {text: stdout.trim(), outputFormat: 'plain-text-despite-json-flag'};
  }
  const texts = [];
  const visit = (value, keyPath = '') => {
    if (!value || typeof value !== 'object') return;
    if (typeof value.text === 'string') texts.push({path: keyPath, text: value.text});
    for (const [key, v] of Object.entries(value)) if (v && typeof v === 'object') visit(v, `${keyPath}.${key}`);
  };
  visit(response);
  if (!texts.length) throw new Error('No transcript text in CLI response.');
  const plan = JSON.parse(fs.readFileSync(path.join(root, 'audio-v3/voice-plan.json'), 'utf8'));
  const expectedText = process.argv[4] ? fs.readFileSync(path.resolve(root, process.argv[4]), 'utf8').trim() : plan.cues.map((c) => c.spokenText).join('');
  const result = {provider: 'Bailian', requestedModel: 'active Profile ASR default', reportedModel: response.model ?? null, expectedText, transcripts: texts};
  fs.writeFileSync(target, JSON.stringify(result, null, 2) + '\n');
  console.log(`Saved safe ASR text to ${target}; no signed URLs or raw responses retained.`);
} catch (error) {
  const message = String(error.stderr || error.message).replace(/https?:\/\/[^\s"'<>]+/g, '[redacted-url]').replace(/\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}/g, '[redacted-secret]').slice(0, 400);
  throw new Error(`ASR stopped: ${message}`);
}
