import {createHash} from 'node:crypto';
import {readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
import {createRequire} from 'node:module';

const scriptPath = fileURLToPath(import.meta.url);
const projectRoot = resolve(dirname(scriptPath), '..');
const engravingPath = resolve(projectRoot, 'src/Engraving.tsx');
const hyperbolicPath = resolve(projectRoot, 'src/hyperbolic.ts');
const outputPath = resolve(projectRoot, '../review/frame-smoke-check.json');
const require = createRequire(import.meta.url);
const ts = require('typescript');
const frameCount = 5400;

const readSource = (path) => readFileSync(path, 'utf8');
const sha256 = (source) => createHash('sha256').update(source).digest('hex');
const engravingSource = readSource(engravingPath);
const hyperbolicSource = readSource(hyperbolicPath);

const counters = {canvasCalls: 0, pathCalls: 0, numericArguments: 0};
const check = (value) => {
	counters.numericArguments += 1;
	if (!Number.isFinite(value)) throw new RangeError(`Non-finite numeric canvas input: ${String(value)}`);
};

class MockPath2D {
	moveTo(x, y) { counters.pathCalls += 1; check(x); check(y); }
	lineTo(x, y) { counters.pathCalls += 1; check(x); check(y); }
	quadraticCurveTo(cpx, cpy, x, y) { counters.pathCalls += 1; check(cpx); check(cpy); check(x); check(y); }
	bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x, y) {
		counters.pathCalls += 1;
		check(cp1x); check(cp1y); check(cp2x); check(cp2y); check(x); check(y);
	}
	closePath() { counters.pathCalls += 1; }
}

const canvasMethods = {
	setTransform(a, b, c, d, e, f) { counters.canvasCalls += 1; check(a); check(b); check(c); check(d); check(e); check(f); },
	clearRect(x, y, width, height) { counters.canvasCalls += 1; check(x); check(y); check(width); check(height); },
	beginPath() { counters.canvasCalls += 1; },
	closePath() { counters.canvasCalls += 1; },
	moveTo(x, y) { counters.canvasCalls += 1; check(x); check(y); },
	lineTo(x, y) { counters.canvasCalls += 1; check(x); check(y); },
	arc(x, y, radius, start, end) { counters.canvasCalls += 1; check(x); check(y); check(radius); check(start); check(end); },
	ellipse(x, y, radiusX, radiusY, rotation, start, end) {
		counters.canvasCalls += 1;
		check(x); check(y); check(radiusX); check(radiusY); check(rotation); check(start); check(end);
	},
	bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x, y) {
		counters.canvasCalls += 1;
		check(cp1x); check(cp1y); check(cp2x); check(cp2y); check(x); check(y);
	},
	quadraticCurveTo(cpx, cpy, x, y) { counters.canvasCalls += 1; check(cpx); check(cpy); check(x); check(y); },
	translate(x, y) { counters.canvasCalls += 1; check(x); check(y); },
	scale(x, y) { counters.canvasCalls += 1; check(x); check(y); },
	rotate(angle) { counters.canvasCalls += 1; check(angle); },
	strokeRect(x, y, width, height) { counters.canvasCalls += 1; check(x); check(y); check(width); check(height); },
	save() { counters.canvasCalls += 1; },
	restore() { counters.canvasCalls += 1; },
	clip() { counters.canvasCalls += 1; },
	fill() { counters.canvasCalls += 1; },
	stroke() { counters.canvasCalls += 1; },
};

const makeCanvas = () => {
	const context = {...canvasMethods};
	for (const property of ['globalAlpha', 'lineWidth']) {
		let value = 1;
		Object.defineProperty(context, property, {
			get: () => value,
			set: (next) => { check(next); value = next; },
			enumerable: true,
		});
	}
	const canvas = {
		width: 2160,
		height: 3840,
		getContext: (type) => type === '2d' ? context : null,
	};
	return canvas;
};

const transpile = (source, fileName) => {
	const result = ts.transpileModule(source, {
		fileName,
		reportDiagnostics: true,
		compilerOptions: {
			target: ts.ScriptTarget.ES2022,
			module: ts.ModuleKind.CommonJS,
			jsx: ts.JsxEmit.ReactJSX,
			esModuleInterop: true,
		},
	});
	const errors = (result.diagnostics ?? []).filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error);
	if (errors.length > 0) {
		const details = errors.map((diagnostic) => ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n')).join('\n');
		throw new Error(`TypeScript transpilation failed for ${fileName}: ${details}`);
	}
	return result.outputText;
};

const loadCommonJs = (code, filename, customRequire, globals = {}) => {
	const module = {exports: {}};
	const sandbox = {
		module,
		exports: module.exports,
		require: customRequire,
		__filename: filename,
		__dirname: dirname(filename),
		...globals,
	};
	vm.runInNewContext(code, sandbox, {filename, timeout: 120000});
	return module.exports;
};

const reactStub = {useLayoutEffect() {}, useRef: () => ({current: null})};
const jsxRuntimeStub = {jsx: () => null, jsxs: () => null, Fragment: Symbol.for('react.fragment')};
const remotionStub = {cancelRender() {}, continueRender() {}, delayRender: () => 0};
const hyperbolicModule = loadCommonJs(
	transpile(hyperbolicSource, hyperbolicPath),
	hyperbolicPath,
	() => { throw new Error('Unexpected import in hyperbolic.ts'); },
);
const engravingForSmoke = `${engravingSource}\n;module.exports.__drawEngravingForSmoke = drawEngraving;\n`;
const engravingModule = loadCommonJs(
	transpile(engravingForSmoke, engravingPath),
	engravingPath,
	(specifier) => {
		if (specifier === 'react') return reactStub;
		if (specifier === 'react/jsx-runtime') return jsxRuntimeStub;
		if (specifier === 'remotion') return remotionStub;
		if (specifier === './hyperbolic') return hyperbolicModule;
		throw new Error(`Unexpected Engraving.tsx import: ${specifier}`);
	},
	{Path2D: MockPath2D},
);
const drawEngraving = engravingModule.__drawEngravingForSmoke;
if (typeof drawEngraving !== 'function') throw new Error('Could not expose drawEngraving for the smoke check.');

const canvas = makeCanvas();
let framesExecuted = 0;
let failure = null;
const startedAt = process.hrtime.bigint();
for (let frame = 0; frame < frameCount; frame += 1) {
	try {
		drawEngraving(canvas, frame);
		framesExecuted += 1;
	} catch (error) {
		failure = {
			frame,
			name: error instanceof Error ? error.name : 'Error',
			message: error instanceof Error ? error.message : String(error),
		};
		break;
	}
}
const runtimeMs = Number(process.hrtime.bigint() - startedAt) / 1e6;

const report = {
	check: 'EP17 all-frame real drawEngraving runtime smoke',
	status: failure === null && framesExecuted === frameCount ? 'passed' : 'failed',
	frames_expected: frameCount,
	frames_executed: framesExecuted,
	failure,
	runtime_ms: Math.round(runtimeMs * 100) / 100,
	canvas_size: {width: canvas.width, height: canvas.height},
	canvas_calls: counters.canvasCalls,
	path_calls: counters.pathCalls,
	finite_numeric_arguments_checked: counters.numericArguments,
	sources: {
		'project/src/Engraving.tsx': sha256(engravingSource),
		'project/src/hyperbolic.ts': sha256(hyperbolicSource),
	},
};
mkdirSync(dirname(outputPath), {recursive: true});
writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
if (report.status !== 'passed') process.exitCode = 1;
