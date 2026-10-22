import React from "react";

type TraceGroup = "amber" | "bone" | "rust";
type Trace = { d: string; group: TraceGroup };

const TAU = Math.PI * 2;
const LEFT = 140;
const RIGHT = 840;
const PLOT_TOP = 710;
const PLOT_BOTTOM = 1095;
const CENTER_X = 490;
const CENTER_Y = 875;
const AMBER = "#FF9E00";
const SEPIA = "#78350F";
const BONE = "#FEF3C7";
const BLOOM = "#F59E0B";
const RUST = "#DC2626";

const clamp = (value: number, low = 0, high = 1) => Math.max(low, Math.min(high, value));
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (start: number, end: number, value: number) => {
	const t = clamp((value - start) / (end - start));
	return t * t * (3 - 2 * t);
};
const fixed = (value: number) => value.toFixed(1);

function makeCurvePath(lift = 0, beamProgress = 0) {
	const pieces: string[] = [];
	for (let i = 0; i <= 96; i++) {
		const u = i / 96;
		const retention = Math.exp(-u / 0.29);
		const naturalY = PLOT_BOTTOM - retention * 375;
		const sweptLift = beamProgress <= 0 ? 0 : smooth(0, 1, clamp((beamProgress - u) / 0.08));
		const localLift = Math.max(lift, sweptLift);
		const y = mix(naturalY, PLOT_TOP + 10, localLift);
		pieces.push(`${i === 0 ? "M" : "L"}${fixed(mix(LEFT, RIGHT, u))} ${fixed(y)}`);
	}
	return pieces.join("");
}

function traumaSignalPath(frame: number, x0 = LEFT, x1 = RIGHT, centerY = 805, scale = 1) {
	const healing = clamp(frame / 1320);
	const sigma = 0.012 + healing * 0.31;
	const pain = 1 - 0.958 * smooth(0, 1320, frame);
	const points: string[] = [];
	for (let i = 0; i <= 112; i++) {
		const u = i / 112;
		let signal = 0;
		let weight = 0;
		for (let harmonic = 1; harmonic <= 18; harmonic++) {
			const base = 1 / Math.pow(harmonic, 0.72);
			const filter = Math.exp(-0.5 * Math.pow(harmonic * sigma, 2));
			const phase = TAU * harmonic * u + harmonic * 0.57;
			signal += base * filter * Math.sin(phase);
			weight += base * filter;
		}
		const normalized = weight > 0 ? signal / weight : 0;
		const pulse = Math.exp(-Math.pow((u - 0.12) / 0.035, 2));
		const y = centerY - scale * (pain * (normalized * 55 + pulse * 48));
		points.push(`${i === 0 ? "M" : "L"}${fixed(mix(x0, x1, u))} ${fixed(y)}`);
	}
	return points.join("");
}

const EBBINGHAUS_CURVE = makeCurvePath();
const ORIGINAL_TRAUMA_WAVE = traumaSignalPath(1319, LEFT, RIGHT, 850, 0.75);

function gridPath() {
	const paths: string[] = [
		`M96 550H884V1240H96Z`,
		`M96 550H126V580M854 550H884V580M96 1210V1240H126M854 1240H884V1210`,
	];
	for (let i = 0; i <= 8; i++) {
		const x = LEFT + ((RIGHT - LEFT) * i) / 8;
		paths.push(`M${fixed(x)} 570V1220`);
	}
	for (let i = 0; i <= 8; i++) {
		const y = 590 + i * 75;
		paths.push(`M112 ${fixed(y)}H868`);
	}
	for (let i = 0; i <= 32; i++) {
		const x = LEFT + ((RIGHT - LEFT) * i) / 32;
		const length = i % 4 === 0 ? 11 : 5;
		paths.push(`M${fixed(x)} 1238V${fixed(1238 - length)}`);
	}
	for (let i = 0; i <= 24; i++) {
		const y = 570 + i * 27;
		const length = i % 4 === 0 ? 11 : 5;
		paths.push(`M96 ${fixed(y)}H${fixed(96 + length)}`);
		paths.push(`M884 ${fixed(y)}H${fixed(884 - length)}`);
	}
	return paths.join("");
}

const GRATICULE = gridPath();

function Grid({ opacity = 1, radial = false }: { opacity?: number; radial?: boolean }) {
	return (
		<g fill="none" strokeLinecap="square" opacity={opacity}>
			<path d={GRATICULE} stroke={AMBER} strokeWidth={0.8} strokeOpacity={0.25} />
			{radial && (
				<g stroke={SEPIA} strokeOpacity={0.72} strokeWidth={0.7}>
					<ellipse cx={CENTER_X} cy={CENTER_Y} rx={142} ry={90} />
					<ellipse cx={CENTER_X} cy={CENTER_Y} rx={232} ry={151} />
					<ellipse cx={CENTER_X} cy={CENTER_Y} rx={322} ry={211} />
					<path d={`M158 ${CENTER_Y}H822M${CENTER_X} 620V1130`} strokeDasharray="2 12" />
				</g>
			)}
		</g>
	);
}

function FilmStrip({ frame }: { frame: number }) {
	const drift = frame * 0.11;
	const holes: string[] = [];
	for (let i = 0; i < 20; i++) {
		const x = 156 + i * 35;
		holes.push(`M${fixed(x)} 1160h17v14h-17z`, `M${fixed(x)} 1190h17v14h-17z`);
	}
	const scratches: string[] = [];
	for (let i = 0; i < 12; i++) {
		const x = 162 + ((i * 53 + drift) % 692);
		const y = 1178 + (i % 3) * 5;
		scratches.push(`M${fixed(x)} ${fixed(y)}l${i % 2 ? 9 : -7} ${i % 3 ? -4 : 4}`);
	}
	return (
		<g fill="none" strokeLinecap="round">
			<path d="M140 1152H840V1210H140Z" stroke={AMBER} strokeOpacity={0.46} strokeWidth={0.8} />
			<path d={holes.join("")} stroke={SEPIA} strokeOpacity={0.88} strokeWidth={1} />
			<path d={scratches.join("")} stroke={BONE} strokeOpacity={0.33} strokeWidth={0.7} />
		</g>
	);
}

function ActOne({ frame }: { frame: number }) {
	const progress = clamp(frame / 1319);
	const playheadX = mix(LEFT, RIGHT, progress);
	const retention = Math.exp(-progress / 0.29);
	const playheadY = PLOT_BOTTOM - retention * 375;
	const healing = smooth(0, 1320, frame);
	const waveColor = healing > 0.58 ? AMBER : RUST;
	const trauma = traumaSignalPath(frame);
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<Grid />
			<path d="M140 1124H840M140 642V1124" stroke={AMBER} strokeOpacity={0.62} strokeWidth={1} />
			<path d={EBBINGHAUS_CURVE} stroke={AMBER} strokeOpacity={0.18} strokeWidth={8} />
			<path d={EBBINGHAUS_CURVE} stroke={AMBER} strokeWidth={2.5} />
			<path d={trauma} stroke={waveColor} strokeOpacity={0.2} strokeWidth={8} />
			<path d={trauma} stroke={waveColor} strokeOpacity={mix(0.94, 0.56, healing)} strokeWidth={1.65} />
			<path d={traumaSignalPath(frame, LEFT, RIGHT, 874, 0.26)} stroke={BLOOM} strokeOpacity={0.43} strokeWidth={1.1} />
			<path d={`M${fixed(playheadX)} 635V1126`} stroke={BONE} strokeOpacity={0.45} strokeWidth={0.9} strokeDasharray="4 9" />
			<circle cx={playheadX} cy={playheadY} r={6} fill={BONE} stroke={AMBER} strokeWidth={2} />
			<circle cx={playheadX} cy={playheadY} r={14} stroke={BLOOM} strokeOpacity={0.5} strokeWidth={1.2} />
			<FilmStrip frame={frame} />
		</g>
	);
}

function quantizedStems(frame: number) {
	const lock = smooth(1680, 2440, frame);
	const stems: string[] = [];
	const tops: string[] = [];
	for (let i = 0; i <= 56; i++) {
		const u = i / 56;
		const x = mix(LEFT + 8, RIGHT - 8, u);
		const raw = Math.sin(i * 2.23) * 0.55 + Math.sin(i * 5.71 + 0.6) * 0.34 + Math.sin(i * 9.13) * 0.11;
		const steps = Math.round(raw * 7) / 7;
		const height = 28 + Math.abs(mix(raw, steps, lock)) * 144;
		stems.push(`M${fixed(x)} 1015V${fixed(1015 - height)}M${fixed(x - 4)} ${fixed(1015 - height)}H${fixed(x + 4)}`);
		if (i % 4 === 0) tops.push(`M${fixed(x - 2.2)} ${fixed(1015 - height + 7)}L${fixed(x + 2.2)} ${fixed(1015 - height - 7)}`);
	}
	return { stems: stems.join(""), tops: tops.join(""), lock };
}

function ActTwo({ frame }: { frame: number }) {
	const age = frame - 1320;
	const beamProgress = clamp(age / 360);
	const finalized = smooth(180, 420, age);
	const beamX = mix(LEFT, RIGHT, beamProgress);
	const weldedCurve = makeCurvePath(finalized, beamProgress);
	const sweepProgress = Math.max(0, age - 360);
	const sweepX = 190 + (1 - Math.cos((TAU * sweepProgress) / 360)) * 300;
	const sweepOpacity = smooth(360, 420, age);
	const { stems, tops, lock } = quantizedStems(frame);
	const brackets = [
		"M188 730h40M188 730v285M188 1015h40",
		"M792 730h-40M792 730v285M792 1015h-40",
		"M323 779h24M323 779v188M323 967h24",
		"M657 779h-24M657 779v188M657 967h-24",
	].join("");
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<Grid opacity={0.9 - 0.32 * finalized} />
			<path d="M140 1124H840M140 642V1124" stroke={AMBER} strokeOpacity={0.48} strokeWidth={0.9} />
			<path d={EBBINGHAUS_CURVE} stroke={SEPIA} strokeOpacity={0.42 * (1 - finalized)} strokeWidth={1.2} />
			<path d={weldedCurve} stroke={AMBER} strokeOpacity={0.27} strokeWidth={10} />
			<path d={weldedCurve} stroke={AMBER} strokeOpacity={0.76} strokeWidth={2.5} />
			<path d={weldedCurve} stroke={BONE} strokeOpacity={finalized} strokeWidth={1.5} />
			<path d={`M${fixed(LEFT)} ${PLOT_TOP + 10}H${fixed(beamX)}`} stroke={BLOOM} strokeOpacity={0.48} strokeWidth={14} />
			<path d={`M${fixed(LEFT)} ${PLOT_TOP + 10}H${fixed(beamX)}`} stroke={BONE} strokeOpacity={0.95} strokeWidth={2.7} />
			<path d={`M${fixed(beamX)} 615V1125`} stroke={BONE} strokeOpacity={0.86} strokeWidth={2.1} />
			<path d={`M${fixed(beamX - 9)} 615H${fixed(beamX + 9)}M${fixed(beamX - 9)} 1125H${fixed(beamX + 9)}`} stroke={BLOOM} strokeWidth={1.2} />
			<path d={`M${fixed(sweepX)} 720V1050`} stroke={BLOOM} strokeOpacity={0.32 * sweepOpacity} strokeWidth={10} />
			<path d={`M${fixed(sweepX)} 720V1050M${fixed(sweepX - 7)} 856H${fixed(sweepX + 7)}`} stroke={BONE} strokeOpacity={0.92 * sweepOpacity} strokeWidth={1.6} />
			<path d={ORIGINAL_TRAUMA_WAVE} stroke={RUST} strokeOpacity={0.21 * (1 - lock)} strokeWidth={5} />
			<path d={stems} stroke={AMBER} strokeOpacity={0.76} strokeWidth={1.1} />
			<path d={tops} stroke={BONE} strokeOpacity={0.8} strokeWidth={0.9} />
			<path d={brackets} stroke={RUST} strokeOpacity={0.8} strokeWidth={1.8} />
			<path d="M210 1041H770M210 1034V1048M770 1034V1048" stroke={AMBER} strokeOpacity={0.58} strokeWidth={0.8} />
			<FilmStrip frame={frame} />
		</g>
	);
}

function makeTrace(index: number): Trace {
	const a = 2 + (index % 5);
	const b = 3 + ((index * 7) % 8);
	const phase = ((index * 0.618033988749895) % 1) * TAU;
	const rx = 238 + (index % 9) * 8.1;
	const ry = 154 + (index % 7) * 7.4;
	const cx = CENTER_X + Math.sin(index * 2.17) * 29;
	const cy = CENTER_Y + Math.cos(index * 1.73) * 20;
	const pieces: string[] = [];
	for (let step = 0; step <= 104; step++) {
		const theta = (TAU * step) / 104;
		const x = cx + rx * Math.sin(a * theta + phase) + 18 * Math.sin((a + 2) * theta + phase * 0.61);
		const y = cy + ry * Math.sin(b * theta) + 12 * Math.sin((b + 1) * theta + phase * 0.73);
		pieces.push(`${step === 0 ? "M" : "L"}${fixed(x)} ${fixed(y)}`);
	}
	const group: TraceGroup = index % 17 === 8 ? "rust" : index % 4 === 0 ? "bone" : "amber";
	return { d: pieces.join(""), group };
}

const TRACE_DATA: Trace[] = Array.from({ length: 190 }, (_, index) => makeTrace(index));
const TRACE_CUMULATIVE: Record<TraceGroup, string[]> = { amber: [], bone: [], rust: [] };
for (const trace of TRACE_DATA) {
	TRACE_CUMULATIVE[trace.group].push(trace.d);
}
for (const group of ["amber", "bone", "rust"] as const) {
	let combined = "";
	const paths = TRACE_CUMULATIVE[group];
	for (let index = 0; index < TRACE_DATA.length; index++) {
		const trace = TRACE_DATA[index];
		if (trace.group === group) combined += trace.d;
		paths[index] = combined;
	}
}

function spikePath(frame: number) {
	const pieces: string[] = [];
	const phase = frame * 0.008;
	for (let i = 0; i < 42; i++) {
		const angle = (TAU * i) / 42 + phase;
		const wobble = 12 * Math.sin(i * 1.71 + phase * 2);
		const innerX = CENTER_X + (292 + wobble) * Math.cos(angle);
		const innerY = CENTER_Y + (192 + wobble * 0.54) * Math.sin(angle);
		const length = 14 + (i % 6) * 7 + 8 * Math.sin(i * 0.93 + phase);
		const outerX = CENTER_X + (292 + length + wobble) * Math.cos(angle);
		const outerY = CENTER_Y + (192 + (length + wobble) * 0.54) * Math.sin(angle);
		pieces.push(`M${fixed(innerX)} ${fixed(innerY)}L${fixed(outerX)} ${fixed(outerY)}`);
	}
	return pieces.join("");
}

function scratchPath(frame: number) {
	const pieces: string[] = [];
	for (let i = 0; i < 26; i++) {
		const x = 190 + ((i * 137 + frame * (0.09 + (i % 3) * 0.025)) % 600);
		const y = 625 + ((i * 83) % 500);
		const length = 8 + (i % 5) * 3;
		pieces.push(`M${fixed(x)} ${fixed(y)}l${fixed(length * 0.58)} ${fixed(length)}`);
	}
	return pieces.join("");
}

function traceCount(frame: number) {
	if (frame <= 3900) return Math.floor(mix(5, 172, smooth(2820, 3900, frame)));
	return Math.floor(mix(172, 190, smooth(3900, 4380, frame)));
}

function TraceTangle({ frame, scale = 1, opacity = 1 }: { frame: number; scale?: number; opacity?: number }) {
	const count = traceCount(frame);
	const index = Math.max(0, count - 1);
	const amber = TRACE_CUMULATIVE.amber[index];
	const bone = TRACE_CUMULATIVE.bone[index];
	const rust = TRACE_CUMULATIVE.rust[index];
	const countMix = smooth(2820, 3900, frame);
	return (
		<g transform={`translate(${CENTER_X} ${CENTER_Y}) scale(${scale}) translate(${-CENTER_X} ${-CENTER_Y})`} opacity={opacity} fill="none" strokeLinecap="round" strokeLinejoin="round">
			<path d={amber} stroke={BLOOM} strokeOpacity={0.19} strokeWidth={4.2 + countMix * 1.8} />
			<path d={bone} stroke={BONE} strokeOpacity={0.31 + countMix * 0.24} strokeWidth={2.3 + countMix * 0.7} />
			<path d={rust} stroke={RUST} strokeOpacity={0.72} strokeWidth={1.35 + countMix * 0.45} />
			<path d={amber} stroke={AMBER} strokeOpacity={0.95} strokeWidth={0.85} />
			<path d={bone} stroke={BONE} strokeOpacity={1} strokeWidth={0.62} />
			<path d={rust} stroke={RUST} strokeOpacity={0.97} strokeWidth={0.82} />
			<path d={spikePath(frame)} stroke={RUST} strokeOpacity={0.82} strokeWidth={1.25} />
			<path d={scratchPath(frame)} stroke={BONE} strokeOpacity={0.24} strokeWidth={0.75} />
		</g>
	);
}

function ActThree({ frame }: { frame: number }) {
	const buildup = smooth(2820, 3360, frame);
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<Grid opacity={0.66 - buildup * 0.28} radial />
			<path d="M172 875H808M490 635V1115" stroke={AMBER} strokeOpacity={0.2} strokeWidth={0.8} strokeDasharray="3 11" />
			<TraceTangle frame={frame} opacity={0.72 + buildup * 0.28} />
			<path d={`M216 ${CENTER_Y}H764`} stroke={BONE} strokeOpacity={0.08 + buildup * 0.12} strokeWidth={0.8} />
		</g>
	);
}

type Dust = { x: number; start: number; cycle: number; speed: number; radius: number; phase: number };
const DUST: Dust[] = Array.from({ length: 38 }, (_, i) => ({
	x: CENTER_X + Math.sin(i * 2.399) * (74 + (i % 9) * 19),
	start: (i * 47) % 91,
	cycle: 170 + (i % 7) * 29,
	speed: 0.7 + (i % 5) * 0.11,
	radius: 0.9 + (i % 4) * 0.36,
	phase: i * 1.41,
}));

function closingWave(frame: number, collapse = false) {
	const age = Math.max(0, frame - 4890);
	const decay = Math.exp(-age / 235);
	const amplitude = collapse ? 0 : (3.5 + 19 * decay) * decay;
	const pieces: string[] = [];
	for (let i = 0; i <= 112; i++) {
		const u = i / 112;
		const envelope = Math.sin(Math.PI * u);
		const y = CENTER_Y + amplitude * envelope * Math.sin(u * TAU * 2.25 + age * 0.025);
		pieces.push(`${i === 0 ? "M" : "L"}${fixed(mix(220, 760, u))} ${fixed(y)}`);
	}
	return pieces.join("");
}

function DustField({ frame }: { frame: number }) {
	const age = Math.max(0, frame - 4890);
	return (
		<g fill={BLOOM} stroke="none">
			{DUST.map((dust, index) => {
				const phase = (age + dust.start) % dust.cycle;
				const t = phase / dust.cycle;
				const x = dust.x + Math.sin(age * 0.009 + dust.phase) * 9;
				const y = 1100 - phase * dust.speed;
				const opacity = Math.sin(Math.PI * t) * (0.3 + 0.5 * (index % 3) / 2);
				return <circle key={index} cx={x} cy={y} r={dust.radius} opacity={opacity} />;
			})}
		</g>
	);
}

function ActFour({ frame }: { frame: number }) {
	if (frame < 4860) {
		return (
			<g fill="none" strokeLinecap="round" strokeLinejoin="round">
				<Grid opacity={0.34} radial />
				<TraceTangle frame={frame} />
			</g>
		);
	}
	if (frame < 4890) {
		const snapAge = frame - 4860;
		const y = CENTER_Y + 1.6 * Math.sin(snapAge * 0.16);
		const breath = 0.8 + 0.2 * Math.sin(snapAge * 0.22);
		return (
			<g fill="none" strokeLinecap="round">
				<path d={`M214 ${fixed(y)}H766`} stroke={BLOOM} strokeOpacity={0.48 * breath} strokeWidth={11} />
				<path d={`M214 ${fixed(y)}H766`} stroke={AMBER} strokeOpacity={0.96 * breath} strokeWidth={1.8} />
			</g>
		);
	}
	const age = frame - 4890;
	const lineOpacity = Math.exp(-age / 280);
	const wave = closingWave(frame);
	return (
		<g fill="none" strokeLinecap="round" strokeLinejoin="round">
			<path d={wave} stroke={BLOOM} strokeOpacity={0.42 * lineOpacity} strokeWidth={5} />
			<path d={wave} stroke={AMBER} strokeOpacity={0.96 * lineOpacity} strokeWidth={1.7} />
			<DustField frame={frame} />
		</g>
	);
}

export const Geometry: React.FC<{ frame: number }> = ({ frame: rawFrame }) => {
	const frame = Number.isFinite(rawFrame) ? clamp(rawFrame, 0, 5400) : 0;
	if (frame < 1320) return <ActOne frame={frame} />;
	if (frame < 2820) return <ActTwo frame={frame} />;
	if (frame < 4380) return <ActThree frame={frame} />;
	return <ActFour frame={frame} />;
};

