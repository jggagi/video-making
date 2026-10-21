import React from "react";

type Point = { x: number; y: number };
type Rect = { left: number; top: number; width: number; height: number };

const INK = "#18181B";
const SLATE = "#52525B";
const VERMILION = "#E11D48";
const GOLD = "#D97706";
const DEEP_GOLD = "#B45309";
const TAU = Math.PI * 2;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
// Sampled every integer frame 0..1319 and 301 curve points per frame: maximum
// circle/trace radius is 237.07 before this scale, leaving margin inside r=260.
const EPICYCLE_INTERNAL_SCALE = 1.07;

const clamp = (value: number, low = 0, high = 1) => Math.max(low, Math.min(high, value));
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (start: number, end: number, value: number) => {
	const t = clamp((value - start) / (end - start));
	return t * t * (3 - 2 * t);
};
const point = (x: number, y: number): Point => ({ x, y });
const fixed = (value: number) => value.toFixed(2);
const polar = (radius: number, angle: number): Point => ({
	x: radius * Math.cos(angle),
	y: radius * Math.sin(angle),
});

const EPICYCLE = Array.from({ length: 28 }, (_, index) => ({
	radius:
		index === 0
			? 125
			: 1.5 + 20 * Math.exp(-0.1 * (index - 1)),
	omega: (index % 2 === 0 ? 1 : -1) * (0.34 + index * 0.29),
	phase: index * GOLDEN_ANGLE + (index % 3) * 0.17,
}));

function epicycleAt(frame: number) {
	const time = frame * 0.0018;
	let x = 0;
	let y = 0;
	const circles: Array<{ x: number; y: number; r: number; i: number }> = [];
	const arms: string[] = [];
	for (let i = 0; i < EPICYCLE.length; i++) {
		const spec = EPICYCLE[i];
		const cx = x;
		const cy = y;
		circles.push({ x: cx, y: cy, r: spec.radius, i });
		const angle = spec.phase + spec.omega * time;
		x += spec.radius * Math.cos(angle);
		y += spec.radius * Math.sin(angle);
		arms.push(`M${fixed(cx)} ${fixed(cy)}L${fixed(x)} ${fixed(y)}`);
	}
	return { circles, arms: arms.join(""), tip: point(x, y), time };
}

function epicycleTrace(frame: number) {
	const steps = 300;
	const now = frame * 0.0018;
	const pieces: string[] = [];
	for (let step = 0; step <= steps; step++) {
		const age = -TAU + (TAU * step) / steps;
		let x = 0;
		let y = 0;
		for (const spec of EPICYCLE) {
			const angle = spec.phase + spec.omega * (now + age * 0.52);
			x += spec.radius * Math.cos(angle);
			y += spec.radius * Math.sin(angle);
		}
		pieces.push(`${step === 0 ? "M" : "L"}${fixed(x)} ${fixed(y)}`);
	}
	return pieces.join("");
}

const CORNER_MOTIFS = [
	{ x: -342, y: -246, kind: 0 },
	{ x: 342, y: -246, kind: 1 },
	{ x: -342, y: 246, kind: 2 },
	{ x: 342, y: 246, kind: 3 },
];

function cornerMotifPath(kind: number) {
	if (kind === 0) {
		return "M-21 12A25 25 0 0 1 19 -16M-16 -18L-5 -5L-21 0M-12 15L0 4L12 17M-25 0H25";
	}
	if (kind === 1) {
		return "M-24 0A24 12 0 1 0 24 0A24 12 0 1 0 -24 0M0 -25V25M-18 -18L18 18M-18 18L18 -18";
	}
	if (kind === 2) {
		return "M-25 15C-12 -14 8 -14 25 12M-22 -4C-6 14 7 14 23 -5M-24 22H24M-15 18L-15 23M0 18L0 23M15 18L15 23";
	}
	return "M0 23V-8M0 -8L-18 -24M0 -8L18 -24M-12 2L-25 -10M12 2L25 -10M-18 -24L-17 -12M18 -24L17 -12";
}

function CornerDrafting({ opacity = 1 }: { opacity?: number }) {
 const panels=[{x:-414,y:-310,label:'GENERAL RELATIVITY',sub:'SMOOTH METRIC'},
  {x:74,y:-310,label:'QUANTUM FIELD',sub:'UV DIVERGENCE'},
  {x:-414,y:255,label:'NAVIER–STOKES',sub:'TURBULENCE / UNSOLVED'},
  {x:74,y:255,label:'14,820 PATCHES',sub:'REDUNDANCY: 99.94%'}];
 return <g opacity={opacity} strokeLinejoin="round">
  {panels.map(({x,y,label,sub},i)=><g key={label} transform={`translate(${x} ${y})`}>
   <rect width={340} height={130} fill="#F4F1EA" stroke="#CFC9BD" strokeWidth={.8}/>
   <path d="M0 42H340M12 70H328M12 92H328M12 114H328M68 52V122M136 52V122M204 52V122M272 52V122" fill="none" stroke="#E5E0D5" strokeWidth={.65}/>
   <text x={12} y={29} fill={INK} stroke="none" fontSize={30} fontFamily="Menlo,monospace">{label}</text>
   <text x={12} y={66} fill={i===0?SLATE:VERMILION} stroke="none" fontSize={21} fontFamily="Menlo,monospace">{sub}</text>
   {i===0&&<><path d="M12 115Q85 73 170 109T328 89M12 120Q82 88 170 115T328 101" fill="none" stroke={INK} strokeWidth={1.2}/><path d="M171 82L170 119M142 102H197" stroke={GOLD} strokeWidth={1.2}/></>}
   {i===1&&<><path d="M12 105H90L110 86L125 121L139 70L149 121L159 89L171 107H328" fill="none" stroke={INK} strokeWidth={1.15}/><path d="M145 75L161 91M161 75L145 91" stroke={VERMILION} strokeWidth={1.8}/></>}
   {i===2&&Array.from({length:4},(_,j)=><path key={j} d={`M12 ${84+j*9}C70 ${66+j*9} 90 ${125+j*2} 155 ${87+j*6}S250 ${74+j*8} 328 ${94+j*7}`} fill="none" stroke={j===2?VERMILION:INK} strokeWidth={1.05} strokeOpacity={.7}/>)}
   {i===3&&Array.from({length:8},(_,j)=><g key={j}><rect x={14+j*39} y={83} width={27} height={28} fill="none" stroke={j%3===0?VERMILION:SLATE} strokeWidth={1}/><path d={`M${18+j*39} 97h19m-12-9v18`} stroke={j%3===0?VERMILION:INK} strokeWidth={1}/></g>)}
  </g>)}
  <text x={0} y={-228} textAnchor="middle" fill={VERMILION} fontSize={42} stroke="none">≠</text>
 </g>;
}

function ActOne({ frame }: { frame: number }) {
	const machine = epicycleAt(frame);
	const trace = epicycleTrace(frame);
	const ticks: string[] = [];
	for (let i = 0; i < 96; i++) {
		const angle = (TAU * i) / 96;
		const inner = i % 8 === 0 ? 244 : i % 4 === 0 ? 249 : 253;
		const outer = 260;
		const a = polar(inner, angle);
		const b = polar(outer, angle);
		ticks.push(`M${fixed(a.x)} ${fixed(a.y)}L${fixed(b.x)} ${fixed(b.y)}`);
	}
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<CornerDrafting />
			<circle r={260} stroke={SLATE} strokeOpacity={0.2} strokeWidth={0.65} />
			<path d={ticks.join("")} stroke={SLATE} strokeOpacity={0.42} strokeWidth={0.65} />
			<g transform={`scale(${EPICYCLE_INTERNAL_SCALE})`}>
				<path d={trace} stroke={INK} strokeWidth={1.8} strokeOpacity={0.94} />
				<path d={machine.arms} stroke={VERMILION} strokeWidth={1} strokeOpacity={0.68} />
				{machine.circles.map(({ x, y, r, i }) => (
					<circle
						key={i}
						cx={x}
						cy={y}
						r={r}
						stroke={i % 7 === 6 ? VERMILION : INK}
						strokeOpacity={i === 0 ? 0.92 : Math.max(0.55, 0.72 - 0.4 * (i / 28))}
						strokeWidth={i === 0 ? 1.45 : 1.1}
					/>
				))}
				<circle cx={machine.tip.x} cy={machine.tip.y} r={3.8} fill={GOLD} stroke={INK} strokeWidth={0.9} />
				<circle r={5} fill={INK} stroke="none" />
			</g>
			<path d="M-278 0H-264M264 0H278M0 -278V-264M0 264V278" stroke={INK} strokeWidth={1.1} />
		</g>
	);
}

function ringsForActTwo(count: number, phase: number) {
	const paths: Array<{ r: number; opacity: number; color: string; index: number }> = [];
	for (let i = 0; i < 28; i++) {
		const visibility = clamp(count - i);
		if (visibility < 0.015) continue;
		const ringRadius = 18 + 152 * (1 - i / Math.max(count, 1));
		const evaporate = 1 - visibility;
		paths.push({
			r: ringRadius * (1 - 0.28 * evaporate),
			opacity: visibility * (0.72 + 0.18 * Math.sin(phase * 0.025 + i * 0.41)),
			color: i === 0 ? GOLD : i % 7 === 6 ? VERMILION : INK,
			index: i,
		});
	}
	return paths;
}

function ActTwo({ frame }: { frame: number }) {
	const p = clamp((frame - 1320) / 1500);
	let count = 28;
	if (p < 0.25) count = mix(28, 12, smooth(0.02, 0.24, p));
	else if (p < 0.44) count = 12;
	else if (p < 0.65) count = mix(12, 4, smooth(0.45, 0.64, p));
	else if (p < 0.77) count = 4;
	else count = mix(4, 1, smooth(0.78, 0.95, p));
	const caliperY = mix(-300, 300, smooth(0.02, 0.94, p));
	const caliperTicks: string[] = [];
	for (let i = 0; i <= 60; i++) {
		const x = -330 + i * 11;
		const length = i % 5 === 0 ? 13 : 6;
		caliperTicks.push(`M${x} ${fixed(caliperY - length / 2)}V${fixed(caliperY + length / 2)}`);
	}
	const ringTicks: string[] = [];
	for (let i = 0; i < 72; i++) {
		const a = (TAU * i) / 72 + frame * 0.00025;
		const inner = i % 6 === 0 ? 177 : 183;
		const outer = 190;
		const p1 = polar(inner, a);
		const p2 = polar(outer, a);
		ringTicks.push(`M${fixed(p1.x)} ${fixed(p1.y - 12)}L${fixed(p2.x)} ${fixed(p2.y - 12)}`);
	}
	const spiral: string[] = [];
	for (let i = 0; i <= 360; i++) {
		const theta = mix(-8.1, 8.1, i / 360);
		const r = 14 * Math.exp((2 * Math.log((1 + Math.sqrt(5)) / 2) / Math.PI) * theta);
		const a = theta;
		const x = r * Math.cos(a);
		const y = r * Math.sin(a) - 12;
		spiral.push(`${i === 0 ? "M" : "L"}${fixed(x)} ${fixed(y)}`);
	}
	const spiralRotation = (frame - 1320) * 0.018;
	const finalEquationOpacity = smooth(0.78, 1, p);
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<g transform="scale(0.9259259259)"><CornerDrafting opacity={1 - smooth(0.12, 0.55, p)} /></g>
			<g transform={`translate(0 -12)`}>
				<circle r={190} stroke={SLATE} strokeWidth={0.8} strokeOpacity={0.58} />
				<path d={ringTicks.join("")} stroke={SLATE} strokeWidth={0.75} strokeOpacity={0.68} />
				{ringsForActTwo(count, frame).map(({ r, opacity, color, index }) => (
					<circle
						key={index}
						r={r}
						stroke={color}
						strokeOpacity={opacity}
						strokeWidth={index === 0 ? 1.55 : 0.82}
					/>
				))}
				<g transform={`rotate(${spiralRotation})`}>
				<path d={spiral.join("")} stroke={DEEP_GOLD} strokeWidth={1.45} strokeOpacity={smooth(0.18, 0.88, p)} />
				</g>
				<circle r={3.6} fill={INK} stroke="none" />
			</g>
			<g stroke={VERMILION}>
				<path d={`M-360 ${fixed(caliperY)}H360`} strokeWidth={1.55} />
				<path d={`M-360 ${fixed(caliperY - 6)}H360`} strokeWidth={0.75} strokeOpacity={0.62} />
				<path d={caliperTicks.join("")} strokeWidth={0.9} strokeOpacity={0.82} />
				<path d={`M-360 ${fixed(caliperY - 14)}V${fixed(caliperY + 14)}M360 ${fixed(caliperY - 14)}V${fixed(caliperY + 14)}`} strokeWidth={1.2} />
				<path d={`M-8 ${fixed(caliperY - 19)}L0 ${fixed(caliperY - 9)}L8 ${fixed(caliperY - 19)}M-8 ${fixed(caliperY + 19)}L0 ${fixed(caliperY + 9)}L8 ${fixed(caliperY + 19)}`} strokeWidth={1} />
			</g>
			<path d="M-215 324H215M-215 316V332M215 316V332" stroke={GOLD} strokeWidth={0.9} strokeOpacity={0.76 * finalEquationOpacity} />
			<text
				x={0}
				y={330}
				textAnchor="middle"
				fill={INK}
				stroke="none"
				fontFamily="Georgia, 'Times New Roman', serif"
				fontSize={30}
				letterSpacing={0.45}
				opacity={finalEquationOpacity}
			>
				δS = δ∫L(φ, ∂μφ)d⁴x = 0
			</text>
		</g>
	);
}

function marchingSquares(field: (x: number, y: number) => number, bounds: Rect, columns: number, rows: number, levelCount: number) {
	const values: number[][] = [];
	let minimum = Number.POSITIVE_INFINITY;
	let maximum = Number.NEGATIVE_INFINITY;
	for (let row = 0; row <= rows; row++) {
		const line: number[] = [];
		for (let col = 0; col <= columns; col++) {
			const x = bounds.left + (bounds.width * col) / columns;
			const y = bounds.top + (bounds.height * row) / rows;
			const value = field(x, y);
			line.push(value);
			minimum = Math.min(minimum, value);
			maximum = Math.max(maximum, value);
		}
		values.push(line);
	}
	const paths: Array<{ level: number; d: string }> = [];
	for (let levelIndex = 1; levelIndex <= levelCount; levelIndex++) {
		const level = mix(minimum, maximum, levelIndex / (levelCount + 1));
		const segments: string[] = [];
		for (let row = 0; row < rows; row++) {
			for (let col = 0; col < columns; col++) {
				const x0 = bounds.left + (bounds.width * col) / columns;
				const x1 = bounds.left + (bounds.width * (col + 1)) / columns;
				const y0 = bounds.top + (bounds.height * row) / rows;
				const y1 = bounds.top + (bounds.height * (row + 1)) / rows;
				const corners = [
					{ x: x0, y: y0, value: values[row][col] },
					{ x: x1, y: y0, value: values[row][col + 1] },
					{ x: x1, y: y1, value: values[row + 1][col + 1] },
					{ x: x0, y: y1, value: values[row + 1][col] },
				];
				const edges = [[0, 1], [1, 2], [2, 3], [3, 0]] as const;
				const crossings: Point[] = [];
				for (const [aIndex, bIndex] of edges) {
					const a = corners[aIndex];
					const b = corners[bIndex];
					if ((a.value < level) === (b.value < level)) continue;
					const t = clamp((level - a.value) / (b.value - a.value));
					crossings.push(point(mix(a.x, b.x, t), mix(a.y, b.y, t)));
				}
				const append = (a: Point, b: Point) => segments.push(`M${fixed(a.x)} ${fixed(a.y)}L${fixed(b.x)} ${fixed(b.y)}`);
				if (crossings.length === 2) append(crossings[0], crossings[1]);
				else if (crossings.length === 4) {
					const centerValue = (corners[0].value + corners[1].value + corners[2].value + corners[3].value) / 4;
					if (centerValue >= level) {
						append(crossings[0], crossings[3]);
						append(crossings[1], crossings[2]);
					} else {
						append(crossings[0], crossings[1]);
						append(crossings[2], crossings[3]);
					}
				}
			}
		}
		paths.push({ level: levelIndex, d: segments.join("") });
	}
	return paths;
}

const GRAVITY_CONTOURS = marchingSquares(
	(x, y) => {
		const masses = [
			{ x: -49, y: -24, mass: 1.15 },
			{ x: 43, y: 25, mass: 0.8 },
			{ x: 4, y: -51, mass: 0.45 },
		];
		return masses.reduce((sum, m) => sum + m.mass / Math.sqrt((x - m.x) ** 2 + (y - m.y) ** 2 + 100), 0);
	},
	{ left: -96, top: -78, width: 192, height: 156 },
	25,
	20,
	8,
);

const QUANTUM_DOTS: Array<{ x: number; y: number; r: number; opacity: number }> = [];
for (let iy = -8; iy <= 8; iy++) {
	for (let ix = -8; ix <= 8; ix++) {
		const x = ix * 10.5;
		const y = iy * 9.5;
		const radius = Math.hypot(x, y);
		if (radius > 82) continue;
		const theta = Math.atan2(y, x);
		const radial = (radius / 70) ** 2 * Math.exp(2 - radius / 35);
		const density = radial ** 2 * Math.cos(4 * theta) ** 2;
		if (density < 0.018) continue;
		QUANTUM_DOTS.push({ x, y, r: 0.65 + 1.15 * Math.sqrt(density), opacity: 0.14 + 0.66 * density });
	}
}

function quantumRosePath() {
	const path: string[] = [];
	for (let i = 0; i <= 360; i++) {
		const theta = (TAU * i) / 360;
		const radius = 78 * Math.abs(Math.cos(4 * theta));
		const p = polar(radius, theta);
		path.push(`${i === 0 ? "M" : "L"}${fixed(p.x)} ${fixed(p.y)}`);
	}
	return `${path.join("")}Z`;
}
const QUANTUM_ROSE = quantumRosePath();

function integrateStreamline(startY: number) {
	const points: Point[] = [];
	let x = -91;
	let y = startY;
	const vector = (px: number, py: number) => ({
	x: 0.94 + 0.0011 * py - 0.0007 * px,
	y: -0.12 + 0.17 * Math.sin(px / 52) + 0.0008 * py,
	});
	for (let step = 0; step < 112; step++) {
		points.push(point(x, y));
		const v = vector(x, y);
		const magnitude = Math.hypot(v.x, v.y) || 1;
		x += (v.x / magnitude) * 2.7;
		y += (v.y / magnitude) * 2.7;
		if (x > 94 || y < -78 || y > 78) break;
	}
	return points;
}

const STREAMLINES = Array.from({ length: 9 }, (_, i) => integrateStreamline(-66 + i * 16.5));

function streamlineArtwork(frame: number) {
	const pathParts: string[] = [];
	const arrows: string[] = [];
	const markers: Point[] = [];
	STREAMLINES.forEach((line, lineIndex) => {
		if (line.length < 4) return;
		pathParts.push(`M${fixed(line[0].x)} ${fixed(line[0].y)}${line.slice(1).map((p) => `L${fixed(p.x)} ${fixed(p.y)}`).join("")}`);
		const arrowIndex = Math.min(line.length - 2, 30 + (lineIndex % 3) * 5);
		const tip = line[arrowIndex + 1];
		const before = line[arrowIndex];
		const angle = Math.atan2(tip.y - before.y, tip.x - before.x);
		const back = point(tip.x - 7 * Math.cos(angle), tip.y - 7 * Math.sin(angle));
		const left = point(back.x + 3.1 * Math.cos(angle + Math.PI / 2), back.y + 3.1 * Math.sin(angle + Math.PI / 2));
		const right = point(back.x + 3.1 * Math.cos(angle - Math.PI / 2), back.y + 3.1 * Math.sin(angle - Math.PI / 2));
		arrows.push(`M${fixed(left.x)} ${fixed(left.y)}L${fixed(tip.x)} ${fixed(tip.y)}L${fixed(right.x)} ${fixed(right.y)}`);
		const markerIndex = (Math.floor(frame * 0.21 + lineIndex * 13) % (line.length - 1)) + 1;
		markers.push(line[markerIndex]);
	});
	return { lines: pathParts.join(""), arrows: arrows.join(""), markers };
}

function bifurcationTree(frame: number) {
	const segments: string[] = [];
	const leaves: Point[] = [];
	const sway = 0.035 * Math.sin(frame * 0.0045);
	const branch = (x: number, y: number, angle: number, length: number, depth: number) => {
		if (depth === 0) {
			leaves.push(point(x, y));
			return;
		}
		const nx = x + Math.sin(angle) * length;
		const ny = y - Math.cos(angle) * length;
		segments.push(`M${fixed(x)} ${fixed(y)}L${fixed(nx)} ${fixed(ny)}`);
		const spread = 0.39 + sway + 0.035 * Math.sin(depth * 1.7);
		branch(nx, ny, angle - spread, length * 0.72, depth - 1);
		branch(nx, ny, angle + spread, length * 0.72, depth - 1);
	};
	branch(0, 74, 0, 31, 7);
	return { branches: segments.join(""), leaves };
}

const QUADRANTS = [
	{ x: -101, y: -88, rotation: -0.18, type: "gravity" },
	{ x: 101, y: -88, rotation: 0.14, type: "quantum" },
	{ x: -101, y: 88, rotation: -0.1, type: "flow" },
	{ x: 101, y: 88, rotation: 0.2, type: "tree" },
] as const;

function QuadrantContent({ type, frame, labelOpacity }: { type: (typeof QUADRANTS)[number]["type"]; frame: number; labelOpacity: number }) {
	const title = type === "gravity" ? "GRAVITY" : type === "quantum" ? "QUANTUM" : type === "flow" ? "THERMO" : "LIFE";
	const label = (
		<text
			x={0}
			y={-91}
			textAnchor="middle"
			fill={INK}
			stroke="none"
			fontFamily="Arial, Helvetica, sans-serif"
			fontSize={24}
			fontWeight={600}
			letterSpacing={1.6}
			opacity={labelOpacity}
		>
			{title}
		</text>
	);
	if (type === "gravity") {
		return (
			<g fill="none" strokeLinecap="round" strokeLinejoin="round">
				<rect x={-97} y={-79} width={194} height={158} stroke={SLATE} strokeWidth={0.65} strokeOpacity={0.45} />
				<path d="M-96 0H96M0 -78V78" stroke={SLATE} strokeWidth={0.55} strokeOpacity={0.3} />
				{GRAVITY_CONTOURS.map(({ level, d }) => (
					<path key={level} d={d} stroke={level % 3 === 0 ? GOLD : INK} strokeWidth={level % 3 === 0 ? 1.2 : 1} strokeOpacity={level % 3 === 0 ? 0.78 : 0.62} />
				))}
				<circle cx={-49} cy={-24} r={2.8} fill={GOLD} stroke="none" />
				<circle cx={43} cy={25} r={2.5} fill={INK} stroke="none" />
				{label}
			</g>
		);
	}
	if (type === "quantum") {
		const rotation = frame * 0.018;
		return (
			<g fill="none" strokeLinecap="round" strokeLinejoin="round">
				<circle r={82} stroke={SLATE} strokeWidth={1} strokeOpacity={0.62} />
				<g transform={`rotate(${rotation})`}>
					<path d={QUANTUM_ROSE} stroke={DEEP_GOLD} strokeWidth={1.15} strokeOpacity={0.9} />
					<path d="M-84 0H84M0 -84V84" stroke={SLATE} strokeWidth={0.8} strokeOpacity={0.55} />
					{QUANTUM_DOTS.map(({ x, y, r, opacity }, index) => (
						<circle key={index} cx={x} cy={y} r={r} fill={INK} fillOpacity={opacity} stroke="none" />
					))}
				</g>
				<circle r={2.4} fill={VERMILION} stroke="none" />
				{label}
			</g>
		);
	}
	if (type === "flow") {
		const art = streamlineArtwork(frame);
		return (
			<g fill="none" strokeLinecap="round" strokeLinejoin="round">
				<rect x={-97} y={-79} width={194} height={158} stroke={SLATE} strokeWidth={0.8} strokeOpacity={0.58} />
				<path d={art.lines} stroke={SLATE} strokeWidth={1.05} strokeOpacity={0.86} />
				<path d={art.arrows} stroke={GOLD} strokeWidth={1.35} />
				{art.markers.map((p, index) => <circle key={index} cx={p.x} cy={p.y} r={2.3} fill={VERMILION} stroke={INK} strokeWidth={0.55} />)}
				{label}
			</g>
		);
	}
	const tree = bifurcationTree(frame);
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<path d="M-96 78H96M0 -82V78" stroke={SLATE} strokeWidth={0.8} strokeOpacity={0.46} />
			<path d={tree.branches} stroke={INK} strokeWidth={1.05} strokeOpacity={0.9} />
			{tree.leaves.map((p, index) => <circle key={index} cx={p.x} cy={p.y} r={1.25} fill={index % 4 === 0 ? GOLD : SLATE} stroke="none" />)}
			<circle cy={74} r={3} fill={VERMILION} stroke="none" />
			{label}
		</g>
	);
}

function polygonPoints(sides: number, radius: number, rotation = -Math.PI / 2) {
	return Array.from({ length: sides }, (_, i) => polar(radius, rotation + (TAU * i) / sides));
}

function pointList(points: Point[]) {
	return points.map((p) => `${fixed(p.x)},${fixed(p.y)}`).join(" ");
}

function Astrolabe({ frame, opacity = 1, scale = 1 }: { frame: number; opacity?: number; scale?: number }) {
	const ticks: string[] = [];
	for (let i = 0; i < 96; i++) {
		const a = (TAU * i) / 96;
		const r1 = i % 8 === 0 ? 166 : i % 4 === 0 ? 172 : 177;
		const r2 = 184;
		const p1 = polar(r1, a);
		const p2 = polar(r2, a);
		ticks.push(`M${fixed(p1.x)} ${fixed(p1.y)}L${fixed(p2.x)} ${fixed(p2.y)}`);
	}
	const spokes: string[] = [];
	for (let i = 0; i < 16; i++) {
		const a = (TAU * i) / 16 + frame * 0.00035;
		const p1 = polar(i % 2 === 0 ? 48 : 78, a);
		const p2 = polar(i % 2 === 0 ? 163 : 145, a);
		spokes.push(`M${fixed(p1.x)} ${fixed(p1.y)}L${fixed(p2.x)} ${fixed(p2.y)}`);
	}
	const gear: Point[] = [];
	for (let i = 0; i < 192; i++) {
		const angle = (TAU * i) / 192;
		const radius = i % 8 === 0 ? 193 : i % 4 === 0 ? 189 : 185;
		gear.push(polar(radius, angle));
	}
	const petals = Array.from({ length: 12 }, (_, i) => {
		const rotation = (360 * i) / 12 + frame * 0.012;
		return <path key={i} transform={`rotate(${rotation})`} d="M0 -48C22 -72 23 -111 0 -136C-23 -111 -22 -72 0 -48Z" />;
	});
	const polygonA = polygonPoints(12, 128, -Math.PI / 2 + frame * 0.0002);
	const polygonB = polygonPoints(12, 103, -Math.PI / 2 + Math.PI / 12 - frame * 0.00016);
	return (
		<g transform={`scale(${scale}) rotate(${frame * 0.004})`} opacity={opacity} fill="none" strokeLinecap="round" strokeLinejoin="round">
			<circle r={193} stroke={DEEP_GOLD} strokeWidth={1.35} />
			<path d={`M${pointList(gear)}Z`} stroke={INK} strokeWidth={1} />
			<circle r={177} stroke={GOLD} strokeWidth={1.05} strokeDasharray="1 4" />
			<path d={ticks.join("")} stroke={INK} strokeWidth={1} />
			<circle r={164} stroke={SLATE} strokeWidth={1} />
			<circle r={143} stroke={GOLD} strokeWidth={1.05} strokeDasharray="22 5 1 5" />
			<path d={spokes.join("")} stroke={SLATE} strokeWidth={1} />
			<polygon points={pointList(polygonA)} stroke={GOLD} strokeWidth={1.1} />
			<polygon points={pointList(polygonB)} stroke={INK} strokeWidth={1} />
			<g stroke={DEEP_GOLD} strokeWidth={1.15} strokeOpacity={0.9}>{petals}</g>
			<circle r={77} stroke={INK} strokeWidth={1} />
			<circle r={55} stroke={GOLD} strokeWidth={1.05} />
			<path d="M0 -193V-164M193 0H164M0 193V164M-193 0H-164" stroke={VERMILION} strokeWidth={1.35} />
			<circle r={22} stroke={DEEP_GOLD} strokeWidth={1.2} />
			<circle r={5} fill={INK} stroke="none" />
		</g>
	);
}

function ActThree({ frame }: { frame: number }) {
	const isFolding = frame >= 3600;
	const preFoldProgress = smooth(2820, 3600, frame);
	const convergenceProgress = isFolding ? smooth(3600, 4380, frame) : 0;
	const astrolabeOpacity = isFolding
		? 0.38 + 0.62 * smooth(0, 0.82, convergenceProgress)
		: 0.18 + 0.2 * smooth(0.2, 1, preFoldProgress);
	const astrolabeScale = isFolding
		? mix(0.94, 1, smooth(0, 0.25, convergenceProgress))
		: mix(0.88, 0.94, preFoldProgress);
	const labelOpacity = 1 - smooth(0.16, 0.2, convergenceProgress);
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<path d="M0 -210V210M-226 0H226" stroke={INK} strokeWidth={1.1} strokeOpacity={0.62 * (1 - convergenceProgress)} />
			{QUADRANTS.map((quadrant, index) => {
				const scale = isFolding ? mix(1, 0.58, convergenceProgress) : 1;
				const x = isFolding ? quadrant.x * (1 - convergenceProgress) : quadrant.x;
				const y = isFolding ? quadrant.y * (1 - convergenceProgress) : quadrant.y;
				const initialAngle = Math.sin(frame * 0.003 + index) * 0.8;
				const convergedAngle = quadrant.rotation * (180 / Math.PI);
				const angle = isFolding ? mix(initialAngle, convergedAngle, convergenceProgress) : initialAngle;
				return (
					<g key={quadrant.type} transform={`translate(${fixed(x)} ${fixed(y)}) rotate(${fixed(angle)}) scale(${scale})`} opacity={1 - 0.15 * convergenceProgress}>
						<QuadrantContent type={quadrant.type} frame={frame} labelOpacity={labelOpacity} />
					</g>
				);
			})}
			<Astrolabe frame={frame} opacity={astrolabeOpacity} scale={astrolabeScale} />
		</g>
	);
}

function sectorPath(index: number, count: number, outer: number, inner: number) {
	const angle = (TAU * index) / count - Math.PI / 2;
	const half = Math.PI / count * 0.76;
	const a = polar(outer, angle - half);
	const b = polar(outer, angle + half);
	const c = polar(inner, angle + half * 0.68);
	const d = polar(inner, angle - half * 0.68);
	return `M${fixed(a.x)} ${fixed(a.y)}L${fixed(b.x)} ${fixed(b.y)}L${fixed(c.x)} ${fixed(c.y)}L${fixed(d.x)} ${fixed(d.y)}Z`;
}

function ActFour({ frame }: { frame: number }) {
	const p = clamp((frame - 4380) / 480);
	let count = 20;
	if (p < 0.3) count = mix(20, 10, smooth(0, 0.28, p));
	else if (p < 0.51) count = 10;
	else if (p < 0.69) count = mix(10, 5, smooth(0.52, 0.68, p));
	else count = 5;
	const radius = mix(183, 35, smooth(0.63, 1, p));
	const astrolabeOpacity = 1 - smooth(0.04, 0.36, p);
	const ringOpacity = smooth(0.69, 0.93, p);
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<Astrolabe frame={frame} opacity={astrolabeOpacity} scale={mix(1, 0.78, smooth(0.12, 0.48, p))} />
			{Array.from({ length: 20 }, (_, index) => {
				const visible = clamp(count - index);
				if (visible < 0.015) return null;
				const t = mix(0.14, 0.8, index / 19);
				const outer = radius * t;
				const inner = outer * 0.56;
				return (
					<path
						key={index}
						d={sectorPath(index, Math.max(count, 1), outer, inner)}
						stroke={index % 4 === 0 ? GOLD : INK}
						strokeWidth={index % 4 === 0 ? 1.05 : 0.72}
						strokeOpacity={visible * (index % 4 === 0 ? 0.86 : 0.68)}
						fill={index % 4 === 0 ? GOLD : SLATE}
						fillOpacity={visible * 0.055}
					/>
				);
			})}
			<circle r={radius} stroke={GOLD} strokeWidth={1.3} strokeOpacity={ringOpacity} />
			<circle r={mix(4, 6, smooth(0.88, 1, p))} fill={INK} stroke="none" opacity={smooth(0.92, 1, p)} />
		</g>
	);
}

function QuietEnding({ frame }: { frame: number }) {
	const elapsed = Math.max(0, frame - 4860);
	const radius = 35 + 14 * Math.sin((TAU * elapsed) / 420);
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<circle r={radius} stroke={GOLD} strokeWidth={1.1} opacity={0.86} />
			<circle r={6} fill={INK} stroke="none" />
		</g>
	);
}

export const Geometry: React.FC<{ frame: number }> = ({ frame }) => {
	if (frame >= 4860) {
		return <g transform="translate(490 850)"><QuietEnding frame={frame} /></g>;
	}
	if (frame < 1320) {
		return <g transform="translate(490 850)"><ActOne frame={frame} /></g>;
	}
	if (frame < 2820) {
		return <g transform="translate(490 850) scale(1.08)"><ActTwo frame={frame} /></g>;
	}
	if (frame < 4380) {
		return <g transform="translate(490 850) scale(1.6)"><ActThree frame={frame} /></g>;
	}
	return <g transform="translate(490 850) scale(1.6)"><ActFour frame={frame} /></g>;
};
