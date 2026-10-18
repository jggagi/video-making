import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const timeline = JSON.parse(fs.readFileSync(path.join(root, 'timeline.json')));
assert.deepEqual([timeline.width, timeline.height, timeline.fps], [3840, 2160, 60]);
assert.equal(timeline.renderScale, 2);
assert.equal(timeline.logicalWidth * timeline.renderScale, timeline.width);
assert.equal(timeline.logicalHeight * timeline.renderScale, timeline.height);
assert.equal(timeline.actDurations.reduce((a, b) => a + b, 0), 10800);
assert.equal(timeline.sampleRate / timeline.fps, 800);
assert.equal(timeline.chunkFrames.length, 9);
assert.equal(timeline.overloadFrame, 1200);
assert.equal(timeline.actStarts[2] + 1300, timeline.manifoldFrame);
assert.deepEqual(timeline.chunkFrames.map((frame) => frame * 800), [0, 96000, 192000, 288000, 384000, 480000, 576000, 672000, 768000]);
function sourceFiles(dir) {return fs.readdirSync(dir, {withFileTypes: true}).flatMap((e) => e.isDirectory() ? sourceFiles(path.join(dir, e.name)) : /\.tsx?$/.test(e.name) ? [path.join(dir, e.name)] : []);}
for (const file of sourceFiles(path.join(root, 'src'))) {
  const source = fs.readFileSync(file, 'utf8');
  assert(!/Math\.random\s*\(|Date\.now\s*\(|requestAnimationFrame\s*\(|https?:\/\//.test(source), `Nondeterministic or remote content in ${file}`);
  assert(!/TODO|\.\.\.\s*omitted/.test(source), `Incomplete source ${file}`);
}
const hud = fs.readFileSync(path.join(root, 'src/components/GlobalHUD.tsx'), 'utf8');
assert(!hud.includes('cue?.en'), 'Narrative subtitle must remain Chinese-only.');
for (const name of ['Act1BiologicalOverload', 'Act2LinearVsMatrix', 'Act3DeepCoTManifold', 'Act4OracleProjection']) {
  const source = fs.readFileSync(path.join(root, `src/components/${name}.tsx`), 'utf8');
  assert(!/title="[A-Za-z]/.test(source), `Main title is not Chinese in ${name}`);
}
const wav = fs.readFileSync(path.join(root, 'public/audio/soundtrack.wav'));
assert.equal(wav.toString('ascii', 0, 4), 'RIFF');
assert.equal(wav.readUInt16LE(22), 2);
assert.equal(wav.readUInt32LE(24), 48000);
assert.equal(wav.readUInt16LE(34), 16);
assert.equal(wav.readUInt32LE(40), 180 * 48000 * 4);
for (let n = (1200 + 12) * 800 * 4 + 44; n < 1800 * 800 * 4 + 44; n += 2) assert.equal(wav.readInt16LE(n), 0, `Nonzero crash silence at byte ${n}`);
console.log('PASS: native UHD canvas, uniform 2x vector scale, Chinese narrative titles, deterministic sources, four-act timing, exact PCM and original post-snap silence.');
