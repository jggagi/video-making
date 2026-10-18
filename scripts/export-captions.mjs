import fs from 'node:fs';
import assert from 'node:assert/strict';
import {passages} from './text.mjs';

const timeline = JSON.parse(fs.readFileSync('src/timeline.json', 'utf8'));
const scenes = timeline.shots.filter(s => s.kind === 'scene');
assert.equal(scenes.map(s => s.text).join(''), passages.map(s => s.text).join(''));
let previousEnd = 0;
for (const shot of timeline.shots) {
  assert.equal(shot.from, previousEnd, `Timeline gap in ${shot.id}`);
  assert(shot.duration > 0);
  previousEnd += shot.duration;
  if (shot.kind === 'scene') {
    assert.equal(shot.cues.map(c => c.text).join(''), shot.text, `Missing caption in ${shot.id}`);
    for (const cue of shot.cues) assert(cue.from >= 0 && cue.from + cue.duration <= shot.duration);
  }
}
assert.equal(previousEnd, timeline.durationInFrames);
const format = (frame, separator = ',') => {
  const ms = Math.round(frame / timeline.fps * 1000);
  const h = Math.floor(ms / 3600000);
  const m = Math.floor(ms / 60000) % 60;
  const s = Math.floor(ms / 1000) % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}${separator}${String(ms % 1000).padStart(3, '0')}`;
};
const cues = scenes.flatMap(shot => shot.cues.map(cue => ({...cue, from: shot.from + cue.from})));
const srt = cues.map((cue, i) => `${i + 1}\n${format(cue.from)} --> ${format(cue.from + cue.duration)}\n${cue.text}\n`).join('\n');
const vtt = 'WEBVTT\n\n' + cues.map(cue => `${format(cue.from, '.')} --> ${format(cue.from + cue.duration, '.')}\n${cue.text}\n`).join('\n');
fs.writeFileSync('out/兰亭集序.srt', srt);
fs.writeFileSync('out/兰亭集序.vtt', vtt);
console.log(`${scenes.length} scenes, ${cues.length} exact captions, continuous ${timeline.durationInFrames}-frame timeline`);
