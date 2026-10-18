import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFile, execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {promisify} from 'node:util';

const exec = promisify(execFile);
const root = process.cwd();
const outputDirectory = path.resolve(root, 'public/madman/voice-v5');
const planPath = path.join(outputDirectory, 'plan.json');
const manifestPath = path.join(outputDirectory, 'manifest.json');
const sourceDirectory = path.resolve(root, 'public/madman/voice-v2');
const sourceManifestPath = path.join(sourceDirectory, 'manifest.json');
const cliPath = path.resolve(root, 'out/tools/bailian-cli/node_modules/.bin/bl');
const ffmpegPath = '/opt/homebrew/bin/ffmpeg';
const ffprobePath = '/opt/homebrew/bin/ffprobe';
const mode = process.argv[2] ?? 'plan';
if (!['plan', 'all'].includes(mode)) throw new Error('Choose plan or all.');

const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const sourceManifest = JSON.parse(fs.readFileSync(sourceManifestPath, 'utf8'));
const hash = value => createHash('sha256').update(value).digest('hex');
const hashFile = file => hash(fs.readFileSync(file));
const contentHash = cue => hash(JSON.stringify({
  text: cue.text,
  expectedModel: plan.expectedModel,
  voice: plan.voice,
  rate: plan.rate,
  format: plan.format,
  sampleRate: plan.sampleRate,
}));

function redact(value) {
  return String(value ?? '')
    .replace(/https?:\/\/[^\s"'<>]+/g, '[redacted-url]')
    .replace(/\bBearer\s+\S+/gi, 'Bearer [redacted]')
    .replace(/\b(?:sk|key|token)[-_][A-Za-z0-9._-]{8,}\b/g, '[redacted-secret]')
    .replace(/(api[_ -]?key|authorization|token|secret|credential)\s*[:=]\s*[^\s,;]+/gi, '$1=[redacted]')
    .replace(/[\r\n\t]+/g, ' ')
    .slice(0, 240);
}

function audioInfo(file) {
  const stdout = execFileSync(ffprobePath, [
    '-v', 'error', '-select_streams', 'a:0',
    '-show_entries', 'stream=codec_name,codec_type,sample_rate,channels,bits_per_sample,duration',
    '-show_entries', 'format=format_name,duration', '-of', 'json', file,
  ], {encoding: 'utf8', maxBuffer: 128 * 1024});
  const info = JSON.parse(stdout);
  const audio = info.streams?.find(stream => stream.codec_type === 'audio');
  assert(audio, `No audio stream in ${path.basename(file)}.`);
  assert(String(info.format?.format_name ?? '').split(',').includes('wav'), `${path.basename(file)} is not a WAV.`);
  assert.equal(audio.codec_name, 'pcm_s16le', `${path.basename(file)} must be 16-bit PCM.`);
  assert.equal(Number(audio.sample_rate), plan.sampleRate, `${path.basename(file)} must be ${plan.sampleRate} Hz.`);
  assert.equal(Number(audio.channels), 1, `${path.basename(file)} must be mono.`);
  const durationSeconds = Number(audio.duration ?? info.format.duration);
  assert(Number.isFinite(durationSeconds) && durationSeconds > 0, `${path.basename(file)} has an invalid duration.`);
  return {
    codec: audio.codec_name,
    sampleRate: Number(audio.sample_rate),
    channels: Number(audio.channels),
    bitsPerSample: Number(audio.bits_per_sample),
    durationSeconds,
    sha256: hashFile(file),
  };
}

function safeMetadata(stdout) {
  let parsed;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw new Error('Bailian CLI did not return valid JSON metadata.');
  }
  const found = {};
  function visit(value, depth = 0) {
    if (!value || typeof value !== 'object' || depth > 6) return;
    if (Array.isArray(value)) {
      value.forEach(entry => visit(entry, depth + 1));
      return;
    }
    for (const key of ['model', 'voice', 'saved', 'path']) {
      if (typeof value[key] === 'string') found[key] = value[key];
    }
    Object.values(value).forEach(entry => visit(entry, depth + 1));
  }
  visit(parsed);
  if (!found.model) throw new Error('Bailian CLI did not report the effective model.');
  if (!found.voice) throw new Error('Bailian CLI did not report the effective voice.');
  if (found.model !== plan.expectedModel) throw new Error('Bailian CLI reported a different model; stop and review provider selection.');
  if (found.voice !== plan.voice) throw new Error('Bailian CLI reported a different voice.');
  return found;
}

function audioPathFor(cue) {
  const file = path.resolve(root, cue.audioFile);
  assert(file.startsWith(`${outputDirectory}${path.sep}`), `Audio path escapes voice-v5: ${cue.id}.`);
  return file;
}

function validatePlan() {
  assert.equal(plan.provider, 'Bailian');
  assert.equal(plan.expectedModel, 'cosyvoice-v3-flash');
  assert.equal(plan.voice, 'longsanshu_v3');
  assert.equal(plan.rate, 0.92);
  assert.equal(plan.format, 'wav');
  assert.equal(plan.sampleRate, 24_000);
  assert.equal(sourceManifest.provider, 'Bailian');
  assert.equal(sourceManifest.model, plan.expectedModel);
  assert.equal(sourceManifest.voice, plan.voice);
  assert.equal(sourceManifest.rate, plan.rate);
  assert.equal(sourceManifest.format, plan.format);
  assert.equal(sourceManifest.sampleRate, plan.sampleRate);
  assert.equal(plan.cues.length, 23);
  assert.equal(new Set(plan.cues.map(cue => cue.id)).size, plan.cues.length, 'Plan cue IDs must be unique.');
  for (const cue of plan.cues) {
    assert.equal(typeof cue.text, 'string');
    assert(cue.text.trim(), `Cue ${cue.id} has empty text.`);
    assert(cue.shotId && cue.section, `Cue ${cue.id} is missing its source section.`);
    audioPathFor(cue);
  }
}

function validateReuse(cue) {
  const key = contentHash(cue);
  const source = sourceManifest.cues.find(entry => entry.id === cue.reuseId);
  assert(source, `Missing v2 source cue for reuseId ${cue.reuseId}.`);
  assert.equal(source.text, cue.text, `Reused source text differs for ${cue.id}.`);
  assert.equal(source.model, plan.expectedModel, `Reused source model differs for ${cue.id}.`);
  assert.equal(source.voice, plan.voice, `Reused source voice differs for ${cue.id}.`);
  assert.equal(source.rate, plan.rate, `Reused source rate differs for ${cue.id}.`);
  assert.equal(source.sampleRate, plan.sampleRate, `Reused source sample rate differs for ${cue.id}.`);
  assert.equal(source.contentHash, key, `Reused cache key differs for ${cue.id}.`);
  assert.equal(source.modelReportedByCli, true, `v2 did not record a reported model for ${cue.id}.`);
  assert.equal(source.voiceReportedByCli, true, `v2 did not record a reported voice for ${cue.id}.`);
  const sourceFile = path.resolve(root, source.path);
  assert(sourceFile.startsWith(`${sourceDirectory}${path.sep}`), `Reused source path escapes voice-v2: ${cue.id}.`);
  const sourceInfo = audioInfo(sourceFile);
  assert.equal(sourceInfo.sha256, source.sha256, `Reused source hash differs for ${cue.id}.`);
  return {source, sourceFile, sourceInfo, key};
}

validatePlan();
assert(fs.existsSync(cliPath), `Missing prepared local Bailian CLI: ${cliPath}`);
assert(fs.existsSync(ffprobePath), `Missing ffprobe: ${ffprobePath}`);
assert(fs.existsSync(ffmpegPath), `Missing ffmpeg: ${ffmpegPath}`);

const reuseCues = plan.cues.filter(cue => cue.reuseId);
const newCues = plan.cues.filter(cue => !cue.reuseId);
if (mode === 'plan') {
  for (const cue of reuseCues) validateReuse(cue);
  console.log(JSON.stringify({
    providerSelected: true,
    intendedModel: plan.expectedModel,
    voice: plan.voice,
    rate: plan.rate,
    cues: plan.cues.length,
    reuseCues: reuseCues.length,
    synthesizeCues: newCues.length,
    plannedSynthesisCalls: newCues.length,
    providerCallsMade: 0,
  }, null, 2));
} else {
  const planSha256 = hashFile(planPath);
  const sourceManifestSha256 = hashFile(sourceManifestPath);
  const previous = fs.existsSync(manifestPath)
    ? JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
    : null;
  if (previous) {
    assert.equal(previous.planSha256, planSha256, 'Existing v5 manifest belongs to a different plan.');
    assert.equal(previous.provider, plan.provider);
    assert.equal(previous.model, plan.expectedModel);
    assert.equal(previous.voice, plan.voice);
    assert.equal(previous.rate, plan.rate);
  }
  const priorCues = new Map((previous?.cues ?? []).map(entry => [entry.id, entry]));
  assert.equal(priorCues.size, previous?.cues.length ?? 0, 'Existing manifest has duplicate cue records.');
  for (const entry of priorCues.values()) {
    const cue = plan.cues.find(item => item.id === entry.id);
    assert(cue, `Existing manifest contains an unexpected cue ${entry.id}.`);
    assert.equal(entry.contentHash, contentHash(cue), `Existing cache key differs for ${entry.id}.`);
    const file = audioPathFor(cue);
    assert(fs.existsSync(file), `Existing manifest audio is missing: ${entry.id}.`);
    const info = audioInfo(file);
    assert.equal(info.sha256, entry.sha256, `Existing audio hash differs for ${entry.id}.`);
    assert.equal(info.durationSeconds, entry.durationSeconds, `Existing duration differs for ${entry.id}.`);
    assert.equal(entry.model, plan.expectedModel);
    assert.equal(entry.voice, plan.voice);
    assert.equal(entry.modelReportedByCli, true);
    assert.equal(entry.voiceReportedByCli, true);
  }

  const resultById = new Map(priorCues);
  let cloudCallsAttempted = previous?.cloudCallsAttempted ?? previous?.cloudCalls ?? 0;
  let successfulSynthesisCalls = previous?.successfulSynthesisCalls ?? previous?.synthesizedCueCount ?? 0;
  const saveManifest = () => {
    const cues = plan.cues.filter(cue => resultById.has(cue.id)).map(cue => resultById.get(cue.id));
    const complete = cues.length === plan.cues.length;
    const output = {
      edition: plan.edition,
      provider: plan.provider,
      model: plan.expectedModel,
      voice: plan.voice,
      rate: plan.rate,
      format: plan.format,
      sampleRate: plan.sampleRate,
      spokenTextSource: plan.source,
      planPath: path.relative(root, planPath),
      planSha256,
      reuseSourceManifest: {
        path: path.relative(root, sourceManifestPath),
        sha256: sourceManifestSha256,
      },
      complete,
      cueCount: cues.length,
      totalCueCount: plan.cues.length,
      reuseCueCount: cues.filter(entry => entry.origin === 'v2-cache-copy').length,
      synthesizedCueCount: cues.filter(entry => entry.origin === 'bailian-synthesis').length,
      cloudCalls: successfulSynthesisCalls,
      cloudCallsAttempted,
      cliInvocationAttempts: cloudCallsAttempted,
      successfulSynthesisCalls,
      totalDurationSeconds: cues.reduce((sum, entry) => sum + entry.durationSeconds, 0),
      cues,
    };
    fs.writeFileSync(manifestPath, `${JSON.stringify(output, null, 2)}\n`, 'utf8');
  };

  for (const cue of plan.cues) {
    const file = audioPathFor(cue);
    const old = resultById.get(cue.id);
    const key = contentHash(cue);
    if (old) {
      console.log(`Verified cached ${cue.id}: ${old.durationSeconds.toFixed(3)}s`);
      continue;
    }
    if (fs.existsSync(file)) {
      throw new Error(`Unmatched existing audio ${cue.id}; retain it and review before replacing.`);
    }

    if (cue.reuseId) {
      const {source, sourceFile, sourceInfo} = validateReuse(cue);
      fs.copyFileSync(sourceFile, file, fs.constants.COPYFILE_EXCL);
      const copiedInfo = audioInfo(file);
      assert.equal(copiedInfo.sha256, source.sha256, `Copied audio changed for ${cue.id}.`);
      resultById.set(cue.id, {
        id: cue.id,
        shotId: cue.shotId,
        section: cue.section,
        text: cue.text,
        path: cue.audioFile,
        contentHash: key,
        model: source.model,
        modelReportedByCli: source.modelReportedByCli,
        voice: source.voice,
        voiceReportedByCli: source.voiceReportedByCli,
        rate: source.rate,
        format: plan.format,
        sampleRate: plan.sampleRate,
        channels: copiedInfo.channels,
        codec: copiedInfo.codec,
        bitsPerSample: copiedInfo.bitsPerSample,
        durationSeconds: copiedInfo.durationSeconds,
        sha256: copiedInfo.sha256,
        origin: 'v2-cache-copy',
        reusedFromId: cue.reuseId,
        reusedFromPath: source.path,
        reusedFromManifestSha256: sourceManifestSha256,
        sourceDurationSeconds: sourceInfo.durationSeconds,
      });
      saveManifest();
      console.log(`Copied ${cue.id} from ${cue.reuseId}: ${copiedInfo.durationSeconds.toFixed(3)}s`);
      continue;
    }

    const textPath = path.join(outputDirectory, `${cue.id}.txt`);
    const expectedTextFile = `${cue.text}\n`;
    if (fs.existsSync(textPath)) {
      assert.equal(fs.readFileSync(textPath, 'utf8'), expectedTextFile, `Existing text file differs for ${cue.id}.`);
    } else {
      fs.writeFileSync(textPath, expectedTextFile, {encoding: 'utf8', flag: 'wx'});
    }

    let output;
    try {
      cloudCallsAttempted++;
      saveManifest();
      // Deliberately omit --model: use the preflighted Profile default, then require it in CLI metadata.
      output = await exec(cliPath, [
        'speech', 'synthesize',
        '--text-file', textPath,
        '--voice', plan.voice,
        '--rate', String(plan.rate),
        '--format', plan.format,
        '--sample-rate', String(plan.sampleRate),
        '--out', file,
        '--concurrent', '1',
        '--output', 'json',
      ], {timeout: 180_000, maxBuffer: 2 * 1024 * 1024});
    } catch (error) {
      throw new Error(`Synthesis stopped at ${cue.id}: ${redact(error.stderr || error.message)}. Existing files were retained.`);
    }

    const reported = safeMetadata(output.stdout);
    assert(fs.existsSync(file), `CLI reported success but did not write ${cue.id}.`);
    const info = audioInfo(file);
    successfulSynthesisCalls++;
    resultById.set(cue.id, {
      id: cue.id,
      shotId: cue.shotId,
      section: cue.section,
      text: cue.text,
      path: cue.audioFile,
      contentHash: key,
      model: reported.model,
      modelReportedByCli: true,
      voice: reported.voice,
      voiceReportedByCli: true,
      rate: plan.rate,
      format: plan.format,
      sampleRate: plan.sampleRate,
      channels: info.channels,
      codec: info.codec,
      bitsPerSample: info.bitsPerSample,
      durationSeconds: info.durationSeconds,
      sha256: info.sha256,
      origin: 'bailian-synthesis',
      providerMetadata: Object.fromEntries(Object.entries(reported).filter(([keyName]) => ['model', 'voice', 'saved', 'path'].includes(keyName))),
    });
    saveManifest();
    console.log(`Synthesized ${cue.id}: ${info.durationSeconds.toFixed(3)}s (reported ${reported.model}, ${reported.voice})`);
  }

  assert.equal(resultById.size, plan.cues.length);
  const finalCues = plan.cues.map(cue => resultById.get(cue.id));
  assert.deepEqual(finalCues.map(cue => cue.id), plan.cues.map(cue => cue.id));
  assert.deepEqual(finalCues.map(cue => cue.text), plan.cues.map(cue => cue.text));
  assert(finalCues.every(cue => cue.sha256 && cue.model === plan.expectedModel && cue.voice === plan.voice && cue.modelReportedByCli && cue.voiceReportedByCli));
  saveManifest();
  console.log(`Prepared ${finalCues.length} cues in plan order; ${successfulSynthesisCalls} successful Bailian calls across ${cloudCallsAttempted} CLI invocation attempts; total narration ${finalCues.reduce((sum, cue) => sum + cue.durationSeconds, 0).toFixed(3)}s.`);
}
