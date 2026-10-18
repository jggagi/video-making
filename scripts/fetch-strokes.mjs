import fs from 'node:fs';
import path from 'node:path';

const chars = [...new Set('蘭亭集序一觴詠錄其所述')];
const dir = 'public/museum/strokes';
fs.mkdirSync(dir, {recursive: true});
const data = {};
await Promise.all(chars.map(async char => {
  const url = `https://raw.githubusercontent.com/chanind/hanzi-writer-data/master/data/${encodeURIComponent(char)}.json`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${char}: HTTP ${response.status}`);
  const json = await response.json();
  if (!json.strokes?.length || json.strokes.length !== json.medians.length) throw new Error(`Invalid stroke data for ${char}`);
  fs.writeFileSync(path.join(dir, `${char}.json`), JSON.stringify(json));
  data[char] = json;
  console.log(`${char}: ${json.strokes.length} strokes`);
}));
const license = await fetch('https://raw.githubusercontent.com/chanind/hanzi-writer-data/master/ARPHICPL.TXT');
if (!license.ok) throw new Error(`License HTTP ${license.status}`);
fs.writeFileSync(path.join(dir, 'ARPHICPL.TXT'), await license.text());
fs.writeFileSync('src/museum/strokes.json', JSON.stringify(data));
fs.writeFileSync(path.join(dir, 'SOURCE.md'), '# Stroke source\n\nUnmodified glyph outlines and medians from Hanzi Writer Data, derived from Make Me a Hanzi and Arphic fonts.\n\nhttps://github.com/chanind/hanzi-writer-data\n\nLicensed under Arphic Public License; accompanying ARPHICPL.TXT is retained.\n\nThe animation is a typeset writing visualization. It does not reproduce or claim to be Wang Xizhi\'s handwriting.\n');
