import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFile, execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {promisify} from 'node:util';

const exec = promisify(execFile);
const root = process.cwd();
const planPath = path.resolve(root, 'public/madman/voice-v5/plan.json');
const manifestPath = path.resolve(root, 'public/madman/voice-v5/manifest.json');
const sourcePath = path.resolve(root, 'public/madman/audio/suspense-v5-voice.wav');
const outputPath = path.resolve(root, 'out/madman/voice-v5-asr-check.json');
const cliPath = path.resolve(root, 'out/tools/bailian-cli/node_modules/.bin/bl');
const ffprobePath = '/opt/homebrew/bin/ffprobe';
const expectedCharacterCount = 553;
const timeoutMs = 240_000;

const hash = value => createHash('sha256').update(value).digest('hex');
const hashFile = file => hash(fs.readFileSync(file));

function normalizedText(value) {
  return Array.from(value).filter(character => !/[\p{P}\p{White_Space}]/u.test(character)).join('');
}

function redact(value) {
  return String(value ?? '')
    .replace(/https?:\/\/[^\s"'<>]+/gi, '[redacted-url]')
    .replace(/\bBearer\s+\S+/gi, 'Bearer [redacted]')
    .replace(/\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}\b/gi, '[redacted-secret]')
    .replace(/(api[_ -]?key|authorization|access[_ -]?token|secret|credential)\s*[:=]\s*[^\s,;]+/gi, '$1=[redacted]')
    .replace(/[\r\n\t]+/g, ' ')
    .slice(0, 240);
}

function containsSensitiveText(value) {
  return /https?:\/\/|\bBearer\s+\S+|\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}\b|(api[_ -]?key|authorization|access[_ -]?token|secret|credential)\s*[:=]/i.test(value);
}

function probeAudio(file) {
  const stdout = execFileSync(ffprobePath, [
    '-v', 'error', '-select_streams', 'a:0',
    '-show_entries', 'stream=codec_name,codec_type,sample_rate,channels,bits_per_sample,duration',
    '-show_entries', 'format=format_name,duration', '-of', 'json', file,
  ], {encoding: 'utf8', maxBuffer: 128 * 1024});
  const info = JSON.parse(stdout);
  const audio = info.streams?.find(stream => stream.codec_type === 'audio');
  assert(audio, 'The v5 voice track has no audio stream.');
  assert(String(info.format?.format_name ?? '').split(',').includes('wav'), 'The v5 voice track is not a WAV.');
  const durationSeconds = Number(audio.duration ?? info.format.duration);
  assert(Number.isFinite(durationSeconds) && durationSeconds > 0, 'The v5 voice track duration is invalid.');
  return {
    codec: audio.codec_name ?? null,
    sampleRate: Number(audio.sample_rate) || null,
    channels: Number(audio.channels) || null,
    bitsPerSample: Number(audio.bits_per_sample) || null,
    durationSeconds,
    sha256: hashFile(file),
  };
}

function validateInputs() {
  assert(fs.existsSync(planPath), 'Missing v5 speech plan.');
  assert(fs.existsSync(manifestPath), 'Missing v5 speech manifest.');
  assert(fs.existsSync(sourcePath), 'The v5 voice track is not available yet.');
  assert(fs.existsSync(cliPath), 'Prepared local Bailian CLI is unavailable.');
  assert(fs.existsSync(ffprobePath), 'ffprobe is unavailable.');
  assert(!fs.existsSync(outputPath), 'ASR check output already exists; refusing to make a duplicate recognition call.');

  const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  assert.equal(plan.provider, 'Bailian');
  assert.equal(plan.expectedModel, 'cosyvoice-v3-flash');
  assert.equal(plan.voice, 'longsanshu_v3');
  assert.equal(plan.cues.length, 23);
  assert.equal(manifest.provider, plan.provider);
  assert.equal(manifest.model, plan.expectedModel);
  assert.equal(manifest.voice, plan.voice);
  assert.equal(manifest.rate, plan.rate);
  assert.equal(manifest.complete, true);
  assert.equal(manifest.cueCount, plan.cues.length);
  assert.equal(manifest.totalCueCount, plan.cues.length);
  assert.equal(manifest.cues.length, plan.cues.length);

  const expectedText = plan.cues.map(cue => cue.text).join('');
  assert.equal(expectedText.length, expectedCharacterCount, 'The approved v5 narration text length changed.');
  for (let index = 0; index < plan.cues.length; index += 1) {
    const cue = plan.cues[index];
    const entry = manifest.cues[index];
    assert.equal(entry.id, cue.id, `Manifest cue order differs at ${index}.`);
    assert.equal(entry.text, cue.text, `Manifest text differs for ${cue.id}.`);
    assert.equal(entry.path, cue.audioFile, `Manifest audio path differs for ${cue.id}.`);
    assert.equal(entry.model, plan.expectedModel, `Manifest model differs for ${cue.id}.`);
    assert.equal(entry.voice, plan.voice, `Manifest voice differs for ${cue.id}.`);
    const cuePath = path.resolve(root, entry.path);
    assert(cuePath.startsWith(`${path.resolve(root, 'public/madman/voice-v5')}${path.sep}`), `Cue path escapes voice-v5: ${cue.id}.`);
    assert(fs.existsSync(cuePath), `Manifest audio is missing for ${cue.id}.`);
    assert.equal(hashFile(cuePath), entry.sha256, `Manifest audio hash differs for ${cue.id}.`);
  }

  return {
    plan,
    manifest,
    expectedText,
    audio: probeAudio(sourcePath),
  };
}

function collectTextCandidates(rootValue) {
  const candidates = [];
  const timedSentences = [];
  const timedWords = [];
  const seen = new WeakSet();
  function visit(value, route = '$', collectionKey = '') {
    if (!value || typeof value !== 'object' || seen.has(value)) return;
    seen.add(value);
    if (Array.isArray(value)) {
      const isSentenceCollection = /^(sentences?|segments?|utterances?)$/i.test(collectionKey);
      const isWordCollection = /^words?$/i.test(collectionKey);
      value.forEach((item, index) => {
        if ((isSentenceCollection || isWordCollection) && item && typeof item === 'object' && !Array.isArray(item) && typeof item.text === 'string') {
          const start = getField(item, ['begin_time', 'start_time', 'startTime', 'start', 'begin', 'offset']);
          const end = getField(item, ['end_time', 'stop_time', 'endTime', 'end', 'stop']);
          if (isSentenceCollection) candidates.push({text: item.text, field: 'text', path: `${route}[${index}].text`, segmentField: true});
          const record = {
            text: item.text,
            timing: start || end ? {start, end, units: 'as reported by ASR response'} : null,
            sourcePath: `${route}[${index}]`,
          };
          (isSentenceCollection ? timedSentences : timedWords).push(record);
        }
        visit(item, `${route}[${index}]`, collectionKey);
      });
      return;
    }
    for (const [key, child] of Object.entries(value)) {
      if (typeof child === 'string' && /^(transcript|recognized_text|recognition_text|text|content)$/i.test(key) && child.trim()) {
        candidates.push({text: child, field: key, path: `${route}.${key}`, segmentField: /\.(sentences?|segments?|utterances?|words?)\[/.test(route)});
      } else if (child && typeof child === 'object') {
        visit(child, `${route}.${key}`, key);
      }
    }
  }
  visit(rootValue);
  return {candidates, timedSentences, timedWords};
}

function getField(object, names) {
  for (const name of names) {
    if (object?.[name] !== undefined && object?.[name] !== null) {
      const value = object[name];
      if (typeof value === 'number' || typeof value === 'string') return {field: name, value};
    }
  }
  return null;
}

function extractReportedModel(value) {
  const models = new Set();
  const seen = new WeakSet();
  function visit(node, depth = 0) {
    if (!node || typeof node !== 'object' || depth > 10 || seen.has(node)) return;
    seen.add(node);
    if (Array.isArray(node)) {
      node.forEach(entry => visit(entry, depth + 1));
      return;
    }
    for (const [key, child] of Object.entries(node)) {
      if (/^model$/i.test(key) && typeof child === 'string') models.add(child);
      if (child && typeof child === 'object') visit(child, depth + 1);
    }
  }
  visit(value);
  return [...models];
}

function parseCliTranscript(stdout, rawResponse) {
  const {candidates, timedSentences, timedWords} = collectTextCandidates(rawResponse);
  const fullCandidates = candidates.filter(candidate => !candidate.segmentField);
  fullCandidates.sort((left, right) => normalizedText(right.text).length - normalizedText(left.text).length);
  let transcript = fullCandidates[0]?.text ?? null;
  let transcriptSource = fullCandidates[0]?.path ?? null;
  let sentences = timedSentences;

  if (!transcript && sentences.length > 0) {
    transcript = sentences.map(sentence => sentence.text).join('');
    transcriptSource = 'ASR response sentence segments joined in response order';
  }

  if (!transcript && stdout.trim()) {
    try {
      const parsedStdout = JSON.parse(stdout);
      const stdoutCandidates = collectTextCandidates(parsedStdout).candidates.filter(candidate => !candidate.segmentField);
      stdoutCandidates.sort((left, right) => normalizedText(right.text).length - normalizedText(left.text).length);
      if (stdoutCandidates[0]) {
        transcript = stdoutCandidates[0].text;
        transcriptSource = `CLI stdout ${stdoutCandidates[0].path}`;
      }
    } catch {
      // The CLI emits sentence text as plain lines for the completed async ASR path.
    }
    if (!transcript) {
      const lines = stdout.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
      const spokenLines = lines.filter(line => !/^\[(Model|FAILED):/i.test(line) && !/^\{/.test(line));
      if (spokenLines.length > 0) {
        transcript = spokenLines.join('');
        transcriptSource = 'CLI stdout sentence lines';
        if (sentences.length === 0) {
          sentences = spokenLines.map((text, index) => ({text, timing: null, sourcePath: `CLI stdout line ${index + 1}`}));
        }
      }
    }
  }

  return {transcript, transcriptSource, sentences, words: timedWords};
}

function calculateCharacterDiffs(expected, actual) {
  const left = Array.from(expected);
  const right = Array.from(actual);
  const rows = left.length + 1;
  const columns = right.length + 1;
  const distance = Array.from({length: rows}, () => new Uint16Array(columns));
  for (let i = 0; i < rows; i += 1) distance[i][0] = i;
  for (let j = 0; j < columns; j += 1) distance[0][j] = j;
  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < columns; j += 1) {
      const substitutionCost = left[i - 1] === right[j - 1] ? 0 : 1;
      distance[i][j] = Math.min(
        distance[i - 1][j] + 1,
        distance[i][j - 1] + 1,
        distance[i - 1][j - 1] + substitutionCost,
      );
    }
  }

  const edits = [];
  let i = left.length;
  let j = right.length;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && left[i - 1] === right[j - 1] && distance[i][j] === distance[i - 1][j - 1]) {
      i -= 1;
      j -= 1;
      continue;
    }
    if (i > 0 && j > 0 && distance[i][j] === distance[i - 1][j - 1] + 1) {
      edits.push({operation: 'replace', expectedIndex: i - 1, actualIndex: j - 1, expectedCharacter: left[i - 1], actualCharacter: right[j - 1]});
      i -= 1;
      j -= 1;
      continue;
    }
    if (i > 0 && distance[i][j] === distance[i - 1][j] + 1) {
      edits.push({operation: 'delete', expectedIndex: i - 1, actualIndex: j, expectedCharacter: left[i - 1], actualCharacter: null});
      i -= 1;
      continue;
    }
    edits.push({operation: 'insert', expectedIndex: i, actualIndex: j - 1, expectedCharacter: null, actualCharacter: right[j - 1]});
    j -= 1;
  }
  return edits.reverse();
}

function homophoneCandidates(differences) {
  const tentativePairs = new Map([
    ['心|新', 'xīn / xīn'],
    ['的|地', 'de / de (particle reading)'],
    ['叶|页', 'yè / yè'],
    ['罢|吧', 'bà / ba (particle; tone or realization may differ)'],
    ['赴|复', 'fù / fù'],
  ]);
  return differences
    .filter(difference => difference.operation === 'replace')
    .map(difference => {
      const pronunciation = tentativePairs.get(`${difference.expectedCharacter}|${difference.actualCharacter}`);
      return pronunciation ? {
        ...difference,
        pronunciation,
        status: 'plausible, unverified; for root review only',
      } : null;
    })
    .filter(Boolean);
}

function writeReport(report) {
  fs.mkdirSync(path.dirname(outputPath), {recursive: true});
  fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
}

async function main() {
  const {plan, manifest, expectedText, audio} = validateInputs();
  const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'madman-v5-asr-'));
  const temporaryResponsePath = path.join(temporaryDirectory, 'recognition.json');
  let commandInvocations = 0;
  let successfulAsrCalls = 0;
  let stdout = '';
  let stderr = '';
  let rawResponse = null;
  let commandFailure = null;
  try {
    commandInvocations += 1;
    const result = await exec(cliPath, [
      'speech', 'recognize', '--url', sourcePath,
      '--language', 'zh', '--output', 'json', '--out', temporaryResponsePath,
    ], {cwd: root, encoding: 'utf8', timeout: timeoutMs, maxBuffer: 8 * 1024 * 1024});
    stdout = result.stdout ?? '';
    stderr = result.stderr ?? '';
    successfulAsrCalls = 1;
    if (fs.existsSync(temporaryResponsePath)) {
      try {
        rawResponse = JSON.parse(fs.readFileSync(temporaryResponsePath, 'utf8'));
      } catch {
        rawResponse = null;
      }
    }
  } catch (error) {
    stdout = typeof error?.stdout === 'string' ? error.stdout : '';
    stderr = typeof error?.stderr === 'string' ? error.stderr : '';
    commandFailure = redact(stderr || error?.message || 'Bailian ASR command failed.');
  } finally {
    fs.rmSync(temporaryDirectory, {recursive: true, force: true});
  }

  const cliModel = stderr.match(/\[Model:\s*([^\]\s]+)\]/i)?.[1] ?? null;
  const responseModels = extractReportedModel(rawResponse);
  if (commandFailure) {
    writeReport({
      status: 'blocked',
      provider: 'Bailian',
      command: 'speech recognize --language zh --output json (profile-default ASR model)',
      source: {path: path.relative(root, sourcePath), ...audio},
      expected: {cueCount: plan.cues.length, characterCount: expectedText.length, planText: expectedText, planSha256: hashFile(planPath), manifestSha256: hashFile(manifestPath)},
      recognition: {commandInvocations, successfulAsrCalls, modelReportedByCli: cliModel, modelReportedInResponse: responseModels, failure: commandFailure},
      comparison: null,
      possibleHomophonesForRootReview: [],
      humanReviewRequired: true,
      cloudCalls: 0,
    });
    console.log(JSON.stringify({status: 'blocked', commandInvocations, successfulAsrCalls, output: path.relative(root, outputPath)}));
    return;
  }

  const extracted = parseCliTranscript(stdout, rawResponse);
  if ([extracted.transcript ?? '', ...extracted.sentences.map(sentence => sentence.text), ...extracted.words.map(word => word.text)].some(containsSensitiveText)) {
    writeReport({
      status: 'blocked-sensitive-transcript-not-saved',
      provider: 'Bailian',
      source: {path: path.relative(root, sourcePath), ...audio},
      expected: {cueCount: plan.cues.length, characterCount: expectedText.length, planText: expectedText, planSha256: hashFile(planPath), manifestSha256: hashFile(manifestPath)},
      recognition: {commandInvocations, successfulAsrCalls, modelReportedByCli: cliModel, modelReportedInResponse: responseModels},
      transcript: null,
      comparison: null,
      possibleHomophonesForRootReview: [],
      humanReviewRequired: true,
      cloudCalls: successfulAsrCalls,
    });
    console.log(JSON.stringify({status: 'blocked-sensitive-transcript-not-saved', commandInvocations, successfulAsrCalls, output: path.relative(root, outputPath)}));
    return;
  }

  const actualText = extracted.transcript;
  const expectedNormalized = normalizedText(expectedText);
  const actualNormalized = actualText === null ? null : normalizedText(actualText);
  const differences = actualNormalized === null ? [] : calculateCharacterDiffs(expectedNormalized, actualNormalized);
  const comparison = {
    normalization: 'removed Unicode punctuation and whitespace only; no homophone or phonetic normalization',
    matches: actualNormalized === expectedNormalized,
    expectedNormalizedCharacterCount: Array.from(expectedNormalized).length,
    actualNormalizedCharacterCount: actualNormalized === null ? null : Array.from(actualNormalized).length,
    expectedNormalizedText: expectedNormalized,
    actualNormalizedText: actualNormalized,
    characterDiffs: differences,
  };
  const status = actualText === null ? 'response-unparsed' : comparison.matches ? 'completed-exact-base-text-match' : 'completed-with-character-mismatches';
  const possibleHomophones = homophoneCandidates(differences);
  const possibleNumberRendering = expectedNormalized.includes('四千') && actualNormalized?.includes('4000')
    ? [{expectedText: '四千', observedText: '4000', note: 'Possible equivalent spoken quantity rendered with Arabic digits; left unchanged in the character comparison.'}]
    : [];
  const report = {
    status,
    provider: 'Bailian',
    command: 'speech recognize --language zh --output json (profile-default ASR model)',
    source: {path: path.relative(root, sourcePath), ...audio},
    expected: {
      cueCount: plan.cues.length,
      characterCount: expectedText.length,
      planText: expectedText,
      planSha256: hashFile(planPath),
      manifestSha256: hashFile(manifestPath),
      narrationManifestTotalDurationSeconds: manifest.totalDurationSeconds,
    },
    recognition: {
      commandInvocations,
      successfulAsrCalls,
      modelReportedByCli: cliModel,
      modelReportedInResponse: responseModels,
      language: 'zh',
      transcriptSource: extracted.transcriptSource,
      sentenceCount: extracted.sentences.length,
      sentences: extracted.sentences,
      wordCount: extracted.words.length,
      words: extracted.words,
    },
    transcript: actualText,
    comparison,
    possibleHomophonesForRootReview: possibleHomophones,
    possibleNumberRenderingForRootReview: possibleNumberRendering,
    homophoneReviewNote: 'Candidates are tentative. No homophone or number rendering was normalized or accepted.',
    humanReviewRequired: true,
    cloudCalls: successfulAsrCalls,
  };
  writeReport(report);
  console.log(JSON.stringify({status, commandInvocations, successfulAsrCalls, sentenceCount: extracted.sentences.length, differenceCount: differences.length, modelReportedByCli: cliModel, output: path.relative(root, outputPath)}));
}

main().catch(error => {
  const safeMessage = redact(error?.message || 'ASR check stopped during local validation.');
  console.error(`ASR check stopped: ${safeMessage}`);
  process.exitCode = 1;
});
