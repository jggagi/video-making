import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {BundlerInternals} from '@remotion/bundler';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourceFiles = fs.readdirSync(path.join(root, 'src'), {recursive: true}).filter((p) => /\.tsx?$/.test(p));
const bannedCalls = new Set(['Math.random', 'Date.now', 'requestAnimationFrame', 'setTimeout', 'setInterval', 'fetch']);
for (const name of sourceFiles) {
  const source = fs.readFileSync(path.join(root, 'src', name), 'utf8');
  const parsed = ts.createSourceFile(name, source, ts.ScriptTarget.Latest, true, name.endsWith('tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const inspect = (node) => {
    if (ts.isCallExpression(node)) assert(!bannedCalls.has(node.expression.getText(parsed)), `${name}: prohibited call ${node.expression.getText(parsed)}`);
    if (ts.isNewExpression(node)) assert.notEqual(node.expression.getText(parsed), 'Date', `${name}: wall-clock constructor`);
    ts.forEachChild(node, inspect);
  };
  inspect(parsed);
  assert(!/https?:\/\//.test(source), `${name}: external asset URL`);
  assert(!/\bTODO\b|\.\.\.\s*omitted/i.test(source), `${name}: incomplete implementation`);
}
console.log(`PASS: ${sourceFiles.length} complete TypeScript files; no prohibited runtime calls or asset URLs`);

// Execute the actual scene exports, rather than duplicating their generation code.
const result = await BundlerInternals.esbuild.build({
  stdin: {
    contents: [
      "export * from './src/components/Act2BreadthMCTS';",
      "export * from './src/components/Act3DepthManifold';",
      "export * from './src/components/Act4SplitWorld';",
      "export * from './src/lib/math';",
      "export * from './src/lib/theme';",
      "export * from './src/lib/timeline';",
      "export * from './src/lib/voiced-subtitles';",
      "export * from './src/portrait/captions';",
    ].join('\n'),
    resolveDir: root, sourcefile: 'model-check.ts', loader: 'ts',
  },
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', logLevel: 'silent',
});
const mod = {exports: {}};
vm.runInNewContext(result.outputFiles[0].text, {module: mod, exports: mod.exports, require: createRequire(path.join(root, 'package.json')), console});
const m = mod.exports;
assert.equal(m.ACT_DURATIONS.reduce((a, b) => a + b), m.TOTAL_FRAMES);
assert.equal(m.TOTAL_FRAMES / m.FPS, 180);
assert.equal(m.WIDTH, 1920);
assert.equal(m.HEIGHT, 1080);
for (const [frame, milliseconds, altitudeMm, step, years] of [[0, 0, 120, 1, 0], [10200, 500, 0, 1e10, 10000], [10799, 500, 0, 1e10, 10000]]) {
  const state = m.anchorState(frame);
  assert(Math.abs(state.milliseconds - milliseconds) < 1e-9);
  assert(Math.abs(state.altitudeMm - altitudeMm) < 1e-9);
  assert.equal(state.step, step);
  assert.equal(state.years, years);
  assert.equal(state.centuries, years / 100);
}
assert.equal(m.anchorState(10200).years.toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1}), '10,000.0');
let end = 0;
for (const cue of m.SUBTITLES) {
  assert.equal(cue.from, end, 'subtitle gap or overlap');
  assert(cue.to > cue.from && cue.zh && cue.en);
  end = cue.to;
}
assert.equal(end, 10500);
console.log('PASS: 180 s timeline, normalized HUD formula/clamps, complete bilingual subtitle coverage');
let voicedEnd = 0;
for (const cue of m.VOICED_SUBTITLES) {
  assert(cue.from >= voicedEnd && cue.to > cue.from && cue.to <= 10500, 'voiced subtitle overlap or range error');
  voicedEnd = cue.to;
}
assert.equal(voicedEnd, 10500);
assert.equal(JSON.stringify(m.VOICED_SUBTITLES.slice(0, 19)), JSON.stringify(m.SUBTITLES.slice(0, 19)));
assert.equal(m.VOICED_SUBTITLES[19].from, 9780);
assert.equal(m.VOICED_SUBTITLES[20].zh, '超级智能在瞬间穷尽千万个宇宙，');
console.log('PASS: voiced edition preserves the first 19 captions and gives the complete final quote a readable closing sequence');
for (const cue of m.VOICED_SUBTITLES) {
  const caption = m.portraitCaption(cue.zh);
  assert.equal(caption.replaceAll('\n', ''), cue.zh, 'portrait reflow changed subtitle copy');
  assert(caption.split('\n').length <= 2, 'portrait caption needs more than two lines');
  assert(caption.split('\n').every((line) => Array.from(line).length <= 18), 'portrait caption exceeds its mobile line measure');
}
console.log('PASS: portrait captions preserve every character and cue, within two readable lines');

assert.equal(m.SEARCH_NODES.length, 600);
assert.equal(m.SEARCH_NODES.filter((n) => !n.survives).length, 576);
assert.equal(new Set(m.GOLDEN_PATH).size, m.GOLDEN_PATH.length);
assert.equal(m.GOLDEN_PATH[0], 0);
for (let i = 1; i < m.GOLDEN_PATH.length; i++) assert.equal(m.SEARCH_NODES[m.GOLDEN_PATH[i]].parentId, m.GOLDEN_PATH[i - 1]);
for (const node of m.SEARCH_NODES) {
  assert(Number.isFinite(node.x) && Number.isFinite(node.y));
  if (node.parentId !== null) {
    assert(node.parentId < node.id);
    assert(m.SEARCH_NODES[node.parentId].spawnFrame <= node.spawnFrame);
    if (node.survives) assert(m.SEARCH_NODES[node.parentId].survives, 'disconnected surviving branch');
  }
  if (!node.survives) assert.equal(node.pruneFrame - node.spawnFrame, 45);
}
console.log('PASS: 600-node connected tree; 576 pruned exactly 45 frames after spawn; single connected golden chain');

assert.equal(m.ACT3_MANIFOLD_VERTICES.length, 64);
assert.equal(m.ACT3_MANIFOLD_EDGES.length, 160);
assert.equal(new Set(m.ACT3_MANIFOLD_VERTICES.map((v) => v.join(','))).size, 64);
for (const [a, b, axis] of m.ACT3_MANIFOLD_EDGES) {
  const changes = m.ACT3_MANIFOLD_VERTICES[a].map((v, i) => v !== m.ACT3_MANIFOLD_VERTICES[b][i] ? i : -1).filter((i) => i >= 0);
  assert.equal(changes.length, 1);
  assert.equal(changes[0], axis);
}
const projectionBounds = [Infinity, -Infinity, Infinity, -Infinity];
for (let frame = 0; frame < 2700; frame++) for (const vertex of m.ACT3_MANIFOLD_VERTICES) {
  const p = m.projectAct3Vertex(vertex, frame);
  assert(Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.depth));
  assert(p.x >= 700 && p.x <= 1840 && p.y >= 390 && p.y <= 865, 'manifold exceeds its visual viewport');
  projectionBounds[0] = Math.min(projectionBounds[0], p.x); projectionBounds[1] = Math.max(projectionBounds[1], p.x);
  projectionBounds[2] = Math.min(projectionBounds[2], p.y); projectionBounds[3] = Math.max(projectionBounds[3], p.y);
}
for (const vertex of m.ACT3_MANIFOLD_VERTICES) {
  assert.equal(JSON.stringify(m.projectAct3Vertex(vertex, 2580)), JSON.stringify(m.projectAct3Vertex(vertex, 2699)));
  const rotated = m.rotate4(vertex, 0, 3, 1.34);
  assert(Math.abs(rotated.reduce((s, x) => s + x * x, 0) - vertex.reduce((s, x) => s + x * x, 0)) < 1e-10);
}
console.log(`PASS: 64 distinct 4D vertices / 160 adjacent edges; all 2700 frames finite and in bounds [${projectionBounds.map(Math.round).join(', ')}]; rotation norm and final lock`);

assert.equal(m.DIGITAL_NODE_COUNT, 500);
assert.equal(m.ICOSAHEDRON_VERTICES.length, 12);
assert.equal(m.ICOSAHEDRON_EDGES.length, 30);
assert.equal(m.ICOSAHEDRON_FACES.length, 20);
assert.equal(12 - 30 + 20, 2);
for (let vertex = 0; vertex < 12; vertex++) assert.equal(m.ICOSAHEDRON_EDGES.filter(([a, b]) => a === vertex || b === vertex).length, 5);
for (const [a, b] of m.ICOSAHEDRON_EDGES) assert.equal(m.ICOSAHEDRON_FACES.filter((face) => face.includes(a) && face.includes(b)).length, 2);
assert.equal(m.IMPACT_LOCAL_FRAME + 7200, m.IMPACT_FRAME);
assert.equal(m.laboratoryState(2399).impacted, false);
assert.equal(m.laboratoryState(2400).impacted, true);
assert.equal(m.gearState(2000).rotation, 4);
for (let f = 0; f < 2100; f += 7) assert(Math.abs(m.gearState(f).jitter) <= 0.8);
for (const v of m.ICOSAHEDRON_VERTICES) assert(Math.abs(m.rotateIcosahedronVertex(v, 901).reduce((s, x) => s + x * x, 0) - 1) < 1e-10);
console.log('PASS: 500 digital nodes; regular 12/30/20 crystal; exact impact boundary; 0.002°/frame gear and bounded micro-jitter');
console.log('All source/model checks passed. Real render and visual inspection are separate checks.');
