import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = fs.readFileSync(path.join(root, 'src/lib/captions.ts'), 'utf8');
const {outputText} = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022}});
const {captions: baseCaptions} = await import('data:text/javascript;base64,' + Buffer.from(outputText).toString('base64'));
const voiced = process.argv.includes('--voiced');
const chinese = process.argv.includes('--chinese');
const captions = [...baseCaptions];
if (voiced) {
  const plan = JSON.parse(fs.readFileSync(path.join(root, 'audio-voiced-v2/voice-plan.json'), 'utf8'));
  const quote = plan.cues.find((c) => c.id === 'voice-quote');
  captions.push({from: quote.subtitleFrom, to: quote.subtitleTo, zh: quote.text, en: 'It is not unwilling to explain. A vessel of 7±2 cannot contain a universe of a hundred thousand dimensions.'});
  captions.sort((a, b) => a.from - b.from);
}
const {fps, durationInFrames} = JSON.parse(fs.readFileSync(path.join(root, 'timeline.json'), 'utf8'));
const timestamp = (frame) => {
  const ms = Math.round(frame * 1000 / fps);
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
};
let end = 0;
for (const cue of captions) {
  if (cue.from < end || cue.to <= cue.from || cue.to > durationInFrames) throw new Error('Caption overlap or invalid bounds.');
  end = cue.to;
}
fs.mkdirSync(path.join(root, 'out'), {recursive: true});
fs.writeFileSync(path.join(root, chinese ? 'out/cage-of-seven-plus-two-uhd-v3-zh.srt' : voiced ? 'out/cage-of-seven-plus-two-voiced-v2-bilingual.srt' : 'out/cage-of-seven-plus-two-bilingual.srt'), captions.map((cue, i) => `${i + 1}\n${timestamp(cue.from)} --> ${timestamp(cue.to)}\n${cue.zh}\n${chinese ? '' : cue.en + '\n'}`).join('\n'));
console.log(`Exported ${captions.length} ${chinese ? 'Chinese' : 'bilingual'} subtitle cues.`);
