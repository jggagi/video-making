import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mode = process.argv[2];
const file = {score: 'compose-score.py', mix: 'mix-audio.py'}[mode];
if (!file) throw new Error('Use score or mix.');
const bundled = '/Users/guoq/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const python = process.env.SI_PYTHON || (fs.existsSync(bundled) ? bundled : 'python3');
const result = spawnSync(python, [path.join(root, 'scripts', file), ...process.argv.slice(3)], {cwd: root, stdio: 'inherit'});
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
