import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const timelinePath = path.join(root, 'timeline.json');
const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
const sampleRate = timeline.sampleRate;
const fps = timeline.fps;
const samplesPerFrame = sampleRate / fps;
const totalFrames = timeline.durationInFrames;
const totalSamples = totalFrames * samplesPerFrame;
const TAU = Math.PI * 2;

function invariant(condition, message) {
  if (!condition) throw new Error(message);
}

invariant(Number.isInteger(samplesPerFrame), 'Timeline frame rate must divide the sample rate exactly.');
invariant(fps === 60 && sampleRate === 48_000, 'EP02 audio requires a 60 fps, 48 kHz timeline.');
invariant(totalFrames === 10_800, 'EP02 soundtrack must be exactly 180 seconds.');
invariant(Array.isArray(timeline.harmonicsHz) && timeline.harmonicsHz.length === 9,
  'Timeline must provide the nine overload harmonics.');

const frameSample = frame => frame * samplesPerFrame;
const overloadFrame = timeline.overloadFrame;
const overloadStart = frameSample(overloadFrame);
const overloadEndFrame = overloadFrame + timeline.noiseDurationFrames;
const overloadEnd = frameSample(overloadEndFrame);
const silenceStart = frameSample(overloadEndFrame);
const silenceEnd = frameSample(timeline.silenceUntilFrame);
const titleStart = timeline.silenceUntilFrame;
const manifoldFrame = timeline.manifoldFrame;
const oracleFrame = timeline.oracleFrame;
const endingFrame = totalFrames;

invariant(timeline.overloadFrame === 1_200, 'Unexpected overload boundary.');
invariant(timeline.noiseDurationFrames === 12, 'Overload noise must last exactly 12 frames.');
invariant(timeline.silenceUntilFrame === 1_800, 'Unexpected silence boundary.');
invariant(timeline.manifoldFrame === 6_700 && timeline.oracleFrame === 8_400,
  'Unexpected score transition boundaries.');

const tracks = {
  overload: {left: new Float32Array(totalSamples), right: new Float32Array(totalSamples)},
  order: {left: new Float32Array(totalSamples), right: new Float32Array(totalSamples)},
  atmosphere: {left: new Float32Array(totalSamples), right: new Float32Array(totalSamples)},
};
const scoreEvents = [];
let eventSequence = 0;

function smoothstep(value) {
  const x = Math.max(0, Math.min(1, value));
  return x * x * (3 - 2 * x);
}

function frequencyFromSemitones(rootHz, semitones) {
  return rootHz * (2 ** (semitones / 12));
}

function addNote(trackName, note) {
  const track = tracks[trackName];
  invariant(track, `Unknown audio track ${trackName}.`);

  const startFrame = note.frame;
  const stopFrame = Math.min(note.stopFrame ?? totalFrames, totalFrames);
  const endFrame = Math.min(startFrame + note.durationFrames, stopFrame);
  const start = frameSample(startFrame);
  const end = frameSample(endFrame);
  const count = end - start;
  if (count <= 0) return;

  const attackSamples = Math.max(1, Math.min(
    Math.round((note.attackSeconds ?? 0.025) * sampleRate),
    Math.floor(count / 2),
  ));
  const releaseSamples = Math.max(1, Math.min(
    Math.round((note.releaseSeconds ?? 0.07) * sampleRate),
    Math.floor(count / 2),
  ));
  const partials = note.partials ?? [1];
  const pan = Math.max(-0.85, Math.min(0.85, note.pan ?? 0));
  const leftGain = Math.sqrt((1 - pan) * 0.5);
  const rightGain = Math.sqrt((1 + pan) * 0.5);
  const echoDelay = note.echoDelayFrames ? frameSample(note.echoDelayFrames) : 0;
  const echoGain = note.echoGain ?? 0;
  const echoLimit = frameSample(stopFrame);
  const phaseRate = TAU * note.frequency / sampleRate;

  for (let local = 0; local < count; local++) {
    const attack = smoothstep((local + 1) / attackSamples);
    const release = smoothstep((count - 1 - local) / releaseSamples);
    const envelope = Math.min(attack, release);
    let wave = 0;
    for (let partial = 0; partial < partials.length; partial++) {
      wave += partials[partial] * Math.sin(phaseRate * local * (partial + 1));
    }
    const value = wave * note.amplitude * envelope;
    const sample = start + local;
    track.left[sample] += value * leftGain;
    track.right[sample] += value * rightGain;

    if (echoDelay && echoGain) {
      const echoSample = sample + echoDelay;
      if (echoSample < echoLimit && echoSample < totalSamples) {
        // A single cross-channel reflection gives the score space without a recursive tail.
        track.left[echoSample] += value * rightGain * echoGain;
        track.right[echoSample] += value * leftGain * echoGain;
      }
    }
  }

  scoreEvents.push({
    id: `note-${String(++eventSequence).padStart(4, '0')}`,
    track: trackName,
    part: note.part,
    frame: startFrame,
    sample: start,
    timeSeconds: startFrame / fps,
    durationFrames: endFrame - startFrame,
    durationSeconds: (endFrame - startFrame) / fps,
    frequencyHz: Number(note.frequency.toFixed(4)),
    amplitude: note.amplitude,
    pan,
    waveform: note.waveform ?? 'sine',
    partials,
    ...(echoDelay && echoGain ? {
      echoDelayFrames: note.echoDelayFrames,
      echoGain,
    } : {}),
  });
}

function addChord(frame, durationFrames, frequencies, amplitude, part, pan = 0) {
  for (const [index, frequency] of frequencies.entries()) {
    addNote('order', {
      frame,
      durationFrames,
      stopFrame: oracleFrame,
      frequency,
      amplitude: amplitude * (index === 0 ? 1.08 : 1),
      pan: pan + (index - (frequencies.length - 1) / 2) * 0.045,
      part,
      waveform: 'soft-sine-pad',
      attackSeconds: 0.6,
      releaseSeconds: 0.7,
    });
  }
}

// The nine timeline-provided tones accumulate from their exact chunk frames.
const overloadLayers = timeline.harmonicsHz.map((frequency, index) => ({
  index,
  frame: timeline.chunkFrames[index],
  sample: frameSample(timeline.chunkFrames[index]),
  frequencyHz: frequency,
  amplitude: 0.025 / Math.sqrt(index + 1),
  pan: Math.sin(index * 1.11) * 0.12,
}));
let activeLayers = 0;
for (let sample = 0; sample < overloadStart; sample++) {
  while (activeLayers < overloadLayers.length && overloadLayers[activeLayers].sample <= sample) activeLayers++;
  let left = 0;
  let right = 0;
  for (let index = 0; index < activeLayers; index++) {
    const layer = overloadLayers[index];
    const local = sample - layer.sample;
    const attack = smoothstep((local + 1) / Math.round(0.035 * sampleRate));
    const value = Math.sin(TAU * layer.frequencyHz * local / sampleRate)
      * layer.amplitude * attack;
    left += value * Math.sqrt((1 - layer.pan) * 0.5);
    right += value * Math.sqrt((1 + layer.pan) * 0.5);
  }
  tracks.overload.left[sample] = left;
  tracks.overload.right[sample] = right;
}

// Seeded xorshift32, lightly brightened and saturated, with a 0.5 ms edge fade.
let randomState = 0x7a31c5e9;
function randomSigned() {
  randomState ^= randomState << 13;
  randomState ^= randomState >>> 17;
  randomState ^= randomState << 5;
  return ((randomState >>> 0) / 0x1_0000_0000) * 2 - 1;
}
let priorLeft = 0;
let priorRight = 0;
const noiseEdgeSamples = Math.round(0.0005 * sampleRate);
for (let local = 0; local < overloadEnd - overloadStart; local++) {
  const rawLeft = randomSigned();
  const rawRight = randomSigned();
  const brightLeft = rawLeft + 0.32 * (rawLeft - priorLeft);
  const brightRight = rawRight + 0.32 * (rawRight - priorRight);
  priorLeft = rawLeft;
  priorRight = rawRight;
  const edge = Math.min(
    smoothstep((local + 1) / noiseEdgeSamples),
    smoothstep((overloadEnd - overloadStart - 1 - local) / noiseEdgeSamples),
  );
  tracks.overload.left[overloadStart + local] = Math.tanh(1.8 * brightLeft) / Math.tanh(1.8) * 0.34 * edge;
  tracks.overload.right[overloadStart + local] = Math.tanh(1.8 * brightRight) / Math.tanh(1.8) * 0.34 * edge;
}

// Sparse title bed. It begins at frame 1800 and yields to the matrix arpeggio at 3800.
const titleNotes = [130.8128, 196, 164.8138, 261.6256, 196, 130.8128, 164.8138, 196, 261.6256];
for (let index = 0, frame = titleStart; frame < timeline.matrixFrame; index++, frame += 240) {
  addNote('order', {
    frame,
    durationFrames: 180,
    stopFrame: timeline.matrixFrame,
    frequency: titleNotes[index % titleNotes.length],
    amplitude: 0.027,
    pan: Math.sin(index * 0.8) * 0.12,
    part: 'soft-sparse-title-bed',
    waveform: 'sine',
    attackSeconds: 0.28,
    releaseSeconds: 0.35,
  });
}

// A cyan-like regular arpeggio starts at the timeline's exact matrix frame.
const matrixNotes = [261.6256, 392, 523.2511, 659.2551, 523.2511, 392, 329.6276, 392];
for (let index = 0, frame = timeline.matrixFrame; frame < timeline.actStarts[2]; index++, frame += 30) {
  addNote('order', {
    frame,
    durationFrames: 24,
    stopFrame: timeline.actStarts[2],
    frequency: matrixNotes[index % matrixNotes.length],
    amplitude: 0.032,
    pan: Math.sin(index * 0.63) * 0.18,
    part: 'matrix-cyan-shimmer-arpeggio',
    waveform: 'soft-organ-sine',
    partials: [0.82, 0.14, 0.04],
    attackSeconds: 0.045,
    releaseSeconds: 0.11,
  });
}

// A spare ascending motif occupies the tunnel section and is gated at frame 6700.
const tunnelMotif = [261.6256, 293.6648, 329.6276, 392, 440];
for (let cycle = 0, base = timeline.actStarts[2]; base < manifoldFrame; cycle++, base += 300) {
  for (let index = 0; index < tunnelMotif.length; index++) {
    const frame = base + index * 60;
    if (frame >= manifoldFrame) break;
    addNote('order', {
      frame,
      durationFrames: 50,
      stopFrame: manifoldFrame,
      frequency: tunnelMotif[index] * (cycle >= 2 ? 2 : 1),
      amplitude: 0.039,
      pan: Math.sin((cycle * 5 + index) * 0.51) * 0.16,
      part: 'tunnel-minimal-rising-motif',
      waveform: 'sine',
      attackSeconds: 0.09,
      releaseSeconds: 0.18,
    });
  }
}

// Original C-major imitative counterpoint: four entries, two seconds apart.
// The tune and its harmonies are newly composed procedural material.
const subjectSemitones = [0, 2, 4, 7, 5, 4, 2, 7, 12, 11, 12, 14];
const cMajorScale = [0, 2, 4, 5, 7, 9, 11];
function diatonicFifth(semitones) {
  const octave = Math.floor(semitones / 12);
  const pitchClass = semitones % 12;
  const degree = cMajorScale.indexOf(pitchClass);
  invariant(degree >= 0, `Subject pitch ${semitones} is outside C major.`);
  const targetDegree = octave * 7 + degree + 4;
  const targetOctave = Math.floor(targetDegree / 7);
  return targetOctave * 12 + cMajorScale[targetDegree % 7];
}
const dominantAnswer = subjectSemitones.map(diatonicFifth);
const closingVariation = [0, 2, 4, 7, 5, 7, 9, 12, 7, 5, 4, 0];
const subjectDevelopment = [
  subjectSemitones,
  dominantAnswer,
  subjectSemitones.map(semitones => semitones + 12),
  closingVariation,
].flat();
const dominantDevelopment = subjectDevelopment.map(diatonicFifth);
const voices = [
  {name: 'bass-subject', root: 130.8128, subject: subjectDevelopment, offset: 0, amplitude: 0.052, pan: -0.22},
  {name: 'tenor-dominant-answer', root: 130.8128, subject: dominantDevelopment, offset: 120, amplitude: 0.048, pan: 0.18},
  {name: 'alto-subject-octave', root: 261.6256, subject: subjectDevelopment, offset: 240, amplitude: 0.044, pan: -0.08},
  {name: 'soprano-dominant-answer', root: 261.6256, subject: dominantDevelopment, offset: 360, amplitude: 0.04, pan: 0.12},
];
for (const voice of voices) {
  for (let index = 0; index < subjectDevelopment.length; index++) {
    addNote('order', {
      frame: manifoldFrame + voice.offset + index * 30,
      durationFrames: 28,
      stopFrame: oracleFrame,
      frequency: frequencyFromSemitones(voice.root, voice.subject[index]),
      amplitude: voice.amplitude,
      pan: voice.pan,
      part: `c-major-imitative-${voice.name}`,
      waveform: 'soft-organ-sine',
      partials: [0.78, 0.17, 0.05],
      attackSeconds: 0.035,
      releaseSeconds: 0.08,
      echoDelayFrames: 54,
      echoGain: 0.16,
    });
  }
}

// Slow C-major-family chords sit below the four imitative lines.
addChord(manifoldFrame, 480, [130.8128, 164.8138, 196, 261.6256], 0.013, 'counterpoint-underlay-c-major', -0.08);
addChord(manifoldFrame + 480, 480, [174.6141, 220, 261.6256, 349.2282], 0.012, 'counterpoint-underlay-f-major', 0.08);
addChord(manifoldFrame + 960, 480, [196, 246.9417, 293.6648, 392], 0.012, 'counterpoint-underlay-g-major', -0.04);
addChord(manifoldFrame + 1_440, oracleFrame - (manifoldFrame + 1_440), [130.8128, 164.8138, 196, 261.6256], 0.013, 'counterpoint-underlay-c-major-return', 0.04);

// At frame 8400 the bed opens into a slower golden resolution and a final phrase.
const resolutionChords = [
  {frame: oracleFrame, notes: [130.8128, 164.8138, 196, 261.6256]},
  {frame: oracleFrame + 600, notes: [174.6141, 220, 261.6256, 349.2282]},
  {frame: oracleFrame + 1_200, notes: [196, 246.9417, 293.6648, 392]},
  {frame: oracleFrame + 1_800, notes: [130.8128, 164.8138, 196, 261.6256]},
];
for (const [index, chord] of resolutionChords.entries()) {
  const nextFrame = resolutionChords[index + 1]?.frame ?? endingFrame;
  for (const [noteIndex, frequency] of chord.notes.entries()) {
    addNote('order', {
      frame: chord.frame,
      durationFrames: nextFrame - chord.frame,
      stopFrame: endingFrame,
      frequency,
      amplitude: 0.012,
      pan: (noteIndex - 1.5) * 0.055,
      part: 'golden-sustained-resolution-chord',
      waveform: 'soft-sine-pad',
      attackSeconds: 0.9,
      releaseSeconds: 1.2,
    });
  }
}
const closingPhrase = [
  {offset: 0, frequency: 392},
  {offset: 300, frequency: 440},
  {offset: 600, frequency: 392},
  {offset: 900, frequency: 329.6276},
  {offset: 1_200, frequency: 293.6648},
  {offset: 1_500, frequency: 261.6256},
  {offset: 1_800, frequency: 261.6256},
];
for (const [index, note] of closingPhrase.entries()) {
  addNote('order', {
    frame: oracleFrame + note.offset,
    durationFrames: Math.min(index === closingPhrase.length - 1 ? 360 : 210, endingFrame - (oracleFrame + note.offset)),
    stopFrame: endingFrame,
    frequency: note.frequency,
    amplitude: index === closingPhrase.length - 1 ? 0.033 : 0.027,
    pan: Math.sin(index * 0.72) * 0.12,
    part: 'final-resolution-phrase',
    waveform: 'sine',
    attackSeconds: 0.14,
    releaseSeconds: 0.55,
  });
}
const hookFrame = timeline.hookFrame;
addNote('order', {
  frame: hookFrame,
  durationFrames: 84,
  stopFrame: endingFrame,
  frequency: 523.2511,
  amplitude: 0.026,
  pan: -0.48,
  part: 'final-hook-stereo-pulse-left',
  waveform: 'soft-organ-sine',
  partials: [0.9, 0.1],
  attackSeconds: 0.018,
  releaseSeconds: 0.3,
});
addNote('order', {
  frame: hookFrame + 30,
  durationFrames: 84,
  stopFrame: endingFrame,
  frequency: 659.2551,
  amplitude: 0.022,
  pan: 0.48,
  part: 'final-hook-stereo-pulse-right',
  waveform: 'soft-organ-sine',
  partials: [0.9, 0.1],
  attackSeconds: 0.018,
  releaseSeconds: 0.3,
});

// Quiet, deterministic low-frequency air supports the score from the title onward.
const atmosphereStart = frameSample(titleStart);
const atmosphereEnd = totalSamples;
const ambienceVoices = [
  {frequency: 55, amplitude: 0.0065, pan: -0.12, phase: 0.2},
  {frequency: 82.4069, amplitude: 0.0042, pan: 0.1, phase: 1.3},
  {frequency: 110, amplitude: 0.0028, pan: 0.2, phase: 2.2},
];
for (let sample = atmosphereStart; sample < atmosphereEnd; sample++) {
  const elapsed = (sample - atmosphereStart) / sampleRate;
  const fadeIn = smoothstep(elapsed / 1.6);
  const fadeOut = smoothstep((atmosphereEnd - 1 - sample) / (10 * sampleRate));
  const breathing = 0.76 + 0.24 * Math.sin(TAU * elapsed * 0.045);
  for (const voice of ambienceVoices) {
    const carrier = Math.sin(TAU * voice.frequency * elapsed + voice.phase);
    const softOctave = Math.sin(TAU * voice.frequency * 2 * elapsed + voice.phase * 0.7) * 0.12;
    const value = (carrier + softOctave) * voice.amplitude * fadeIn * fadeOut * breathing;
    const leftGain = Math.sqrt((1 - voice.pan) * 0.5);
    const rightGain = Math.sqrt((1 + voice.pan) * 0.5);
    tracks.atmosphere.left[sample] += value * leftGain;
    tracks.atmosphere.right[sample] += value * rightGain;
  }
}

// Apply a smooth final ten-second fade to every musical and atmospheric component.
const finalFadeStart = frameSample(endingFrame - 600);
for (const trackName of ['order', 'atmosphere']) {
  const track = tracks[trackName];
  for (let sample = finalFadeStart; sample < totalSamples; sample++) {
    const fade = smoothstep((totalSamples - 1 - sample) / (totalSamples - finalFadeStart));
    track.left[sample] *= fade;
    track.right[sample] *= fade;
  }
}

// The silence interval is a hard sample gate across all stems.
for (const [name, track] of Object.entries(tracks)) {
  for (let sample = silenceStart; sample < silenceEnd; sample++) {
    invariant(track.left[sample] === 0 && track.right[sample] === 0,
      `${name} contains a non-zero sample during the required silence.`);
  }
}
invariant(tracks.overload.left[overloadStart] !== 0 && tracks.overload.right[overloadStart] !== 0,
  'The overload noise did not begin at frame 1200.');
for (let sample = overloadStart; sample < totalSamples; sample++) {
  // The overload harmonics stop at frame 1200; only its 12-frame noise transient follows.
  if (sample >= overloadEnd) {
    invariant(tracks.overload.left[sample] === 0 && tracks.overload.right[sample] === 0,
      'The overload stem has a tail after frame 1212.');
  }
}

fs.mkdirSync(path.join(root, 'public/audio'), {recursive: true});
fs.mkdirSync(path.join(root, 'out'), {recursive: true});

function writeFully(fd, buffer) {
  let offset = 0;
  while (offset < buffer.length) {
    offset += fs.writeSync(fd, buffer, offset, buffer.length - offset);
  }
}

function wavHeader(sampleFrames) {
  const dataBytes = sampleFrames * 4;
  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + dataBytes, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(2, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 4, 28);
  header.writeUInt16LE(4, 32);
  header.writeUInt16LE(16, 34);
  header.write('data', 36);
  header.writeUInt32LE(dataBytes, 40);
  return header;
}

function writeWav(file, sampleFrames, startSample, sourceTracks, label) {
  const fd = fs.openSync(file, 'w');
  const digest = createHash('sha256');
  const header = wavHeader(sampleFrames);
  let samplePeak = 0;
  let sumSquares = 0;
  let writtenFrames = 0;
  const chunkFrames = 24_000;
  try {
    writeFully(fd, header);
    digest.update(header);
    while (writtenFrames < sampleFrames) {
      const count = Math.min(chunkFrames, sampleFrames - writtenFrames);
      const pcm = Buffer.allocUnsafe(count * 4);
      for (let frame = 0; frame < count; frame++) {
        const sourceSample = startSample + writtenFrames + frame;
        let left = 0;
        let right = 0;
        for (const track of sourceTracks) {
          left += track.left[sourceSample];
          right += track.right[sourceSample];
        }
        invariant(Number.isFinite(left) && Number.isFinite(right), `${label} has a non-finite sample.`);
        invariant(Math.abs(left) < 0.8 && Math.abs(right) < 0.8,
          `${label} exceeds the 0.8 peak ceiling; review stem gains instead of clipping.`);
        const leftPcm = Math.round(left * 32_767);
        const rightPcm = Math.round(right * 32_767);
        pcm.writeInt16LE(leftPcm, frame * 4);
        pcm.writeInt16LE(rightPcm, frame * 4 + 2);
        const leftValue = leftPcm / 32_768;
        const rightValue = rightPcm / 32_768;
        samplePeak = Math.max(samplePeak, Math.abs(leftValue), Math.abs(rightValue));
        sumSquares += leftValue * leftValue + rightValue * rightValue;
      }
      writeFully(fd, pcm);
      digest.update(pcm);
      writtenFrames += count;
    }
  } finally {
    fs.closeSync(fd);
  }
  return {
    path: path.relative(root, file),
    format: 'WAV PCM16 stereo',
    sampleRate,
    sampleFrames,
    durationSeconds: sampleFrames / sampleRate,
    samplePeak,
    samplePeakDbfs: samplePeak === 0 ? null : Number((20 * Math.log10(samplePeak)).toFixed(3)),
    rms: Number(Math.sqrt(sumSquares / (sampleFrames * 2)).toFixed(7)),
    sha256: digest.digest('hex'),
  };
}

const fullOutputs = {};
for (const [name, filename] of [
  ['overload', 'overload.wav'],
  ['order', 'order.wav'],
  ['atmosphere', 'atmosphere.wav'],
]) {
  fullOutputs[name] = writeWav(
    path.join(root, 'public/audio', filename),
    totalSamples,
    0,
    [tracks[name]],
    name,
  );
}
fullOutputs.soundtrack = writeWav(
  path.join(root, 'public/audio/soundtrack.wav'),
  totalSamples,
  0,
  Object.values(tracks),
  'soundtrack',
);

function writeFrameClip(filename, startFrame, endFrame, label) {
  const firstSample = frameSample(startFrame);
  const sampleFrames = frameSample(endFrame) - firstSample;
  return writeWav(
    path.join(root, 'out', filename),
    sampleFrames,
    firstSample,
    Object.values(tracks),
    label,
  );
}

const clips = {
  buildup: writeFrameClip('nine-layer-build-sample.wav', 0, 1_350, 'nine-layer buildup and snap'),
  overload: writeFrameClip('overload-sample.wav', 1_080, 1_350, 'overload sample clip'),
  manifold: writeFrameClip('manifold-sample.wav', 6_580, 7_180, 'manifold sample clip'),
  polyphony: writeFrameClip('four-voice-order-sample.wav', 6_700, 8_400, 'complete manifold counterpoint'),
};

scoreEvents.sort((a, b) => a.frame - b.frame || a.frequencyHz - b.frequencyHz);
const manifest = {
  edition: 'EP02 procedural original score',
  compositionNote: 'Original procedural music. The C-major section uses Bach-inspired four-voice imitation; no Bach composition is used.',
  sourceTimeline: path.relative(root, timelinePath),
  timing: {
    fps,
    sampleRate,
    channels: 2,
    bitsPerSample: 16,
    durationFrames: totalFrames,
    durationSeconds: totalFrames / fps,
    samplesPerFrame,
    totalSampleFrames: totalSamples,
    overloadFrame,
    overloadStartSample: overloadStart,
    overloadNoiseDurationFrames: timeline.noiseDurationFrames,
    overloadEndFrame,
    overloadEndSample: overloadEnd,
    hardSilenceFrames: {start: overloadEndFrame, endExclusive: timeline.silenceUntilFrame},
    hardSilenceSamples: {start: silenceStart, endExclusive: silenceEnd},
    titleBedFrame: titleStart,
    matrixFrame: timeline.matrixFrame,
    tunnelFrame: timeline.actStarts[2],
    manifoldFrame,
    oracleFrame,
    hookFrame,
    timelineEndingFrame: timeline.endingFrame,
    endingFrame,
    finalFadeStartFrame: endingFrame - 600,
  },
  gains: {
    overloadHarmonics: '0.025 / sqrt(layerIndex + 1), added from each timeline chunk frame with subtle per-layer pan; held until the hard gate at sample 960000.',
    overloadLayers,
    overloadNoise: {
      generator: 'seeded xorshift32 white noise, seed 0x7a31c5e9',
      shaping: '0.32 first-difference bright emphasis followed by tanh saturation',
      gain: 0.34,
      edgeFadeMilliseconds: 0.5,
    },
    titleBed: 0.027,
    matrixArpeggio: 0.032,
    tunnelMotif: 0.039,
    counterpointVoices: voices.map(({name, root, offset, amplitude, pan}) => ({name, rootHz: root, entryOffsetFrames: offset, amplitude, pan})),
    counterpointDevelopment: 'A planned 48-note line per voice: the original 12-note subject, its diatonic dominant answer, an octave development, and a closing C-major variation; entries are staggered by 120 frames and each line is gated at frame 8400.',
    counterpointEcho: {delayFrames: 54, delaySeconds: 0.9, gain: 0.16},
    finalHookPulse: {frame: hookFrame, durationFrames: 84, stereo: true},
    atmosphereVoices: ambienceVoices,
    finalFadeSeconds: 10,
    pcmPolicy: 'No mix normalization or blanket clipping; generation stops if any output reaches 0.8 sample peak.',
  },
  outputs: fullOutputs,
  listeningClips: clips,
  scoreNoteEvents: scoreEvents,
};
const manifestPath = path.join(root, 'out/audio-ep2-manifest.json');
fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

console.log(JSON.stringify({
  durationSeconds: manifest.timing.durationSeconds,
  sampleRate,
  samplesPerFrame,
  outputs: fullOutputs,
  listeningClips: clips,
  scoreNoteEvents: scoreEvents.length,
  manifest: path.relative(root, manifestPath),
}, null, 2));
