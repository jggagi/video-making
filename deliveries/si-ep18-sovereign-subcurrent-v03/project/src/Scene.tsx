import React, {useLayoutEffect, useRef} from 'react';
import {cancelRender, continueRender, delayRender} from 'remotion';

export const WIDTH = 1080;
export const HEIGHT = 1920;
export const NATIVE_WIDTH = 2160;
export const NATIVE_HEIGHT = 3840;
export const WATERLINE = 844.8;
export const HERO = {x: 490, y: 625};

const BACKGROUND = '#06070A';
const CYAN = '#06B6D4';
const AXIS = '#38BDF8';
const AMBER = '#F59E0B';
const GOLD = '#FACC15';
const VERMILION = '#E11D48';
const TAU = Math.PI * 2;
const DURATION = 5400;
const CONTOUR_SAMPLES = 112;
const CONTOUR_LAYERS = 16;

type Point = {x: number; y: number};
type Geometry = 'organic' | 'lattice';

const clamp = (value: number, min = 0, max = 1): number => Math.min(max, Math.max(min, value));
const smooth = (from: number, to: number, value: number): number => {
	const t = clamp((value - from) / (to - from));
	return t * t * (3 - 2 * t);
};
const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;

const mixColor = (from: string, to: string, amount: number): string => {
	const a = Number.parseInt(from.slice(1), 16);
	const b = Number.parseInt(to.slice(1), 16);
	const channel = (shift: number): number => Math.round(lerp((a >> shift) & 255, (b >> shift) & 255, amount));
	return `rgb(${channel(16)},${channel(8)},${channel(0)})`;
};

const contourRadius = (
	angle: number,
	layer: number,
	frame: number,
	radius: number,
	geometry: Geometry,
	organicAmount: number,
	irisAmount: number,
): number => {
	const step = TAU / 22;
	const facetedAngle = Math.round(angle / step) * step;
	const a = lerp(facetedAngle, angle, organicAmount);
	const layerScale = 1 - layer * 0.048;
	const phase = frame * 0.0017;
	const fingerprint = 1
		+ 0.085 * Math.sin(3 * a + 0.43 + phase * 0.38)
		+ 0.052 * Math.sin(5 * a - 0.91 + phase * 0.26)
		+ 0.027 * Math.sin(9 * a + 1.42 - phase * 0.31)
		+ 0.015 * Math.sin(14 * a - 0.28 + layer * 0.17)
		+ 0.011 * Math.cos(19 * a + phase * 0.16 + layer * 0.23);
	const iris = 1
		+ (0.065 + layerScale * 0.026) * Math.cos(8 * a + phase * 0.58 + layer * 0.075)
		+ 0.022 * Math.sin(5 * a - phase * 0.37)
		+ 0.012 * Math.cos(13 * a + layer * 0.19);
	const breathing = 1 + 0.009 * Math.sin(frame * 0.021 + layer * 0.11);
	return radius * layerScale * lerp(fingerprint, iris, irisAmount) * breathing;
};

const contourPoint = (
	center: Point,
	angle: number,
	layer: number,
	frame: number,
	radius: number,
	geometry: Geometry,
	organicAmount: number,
	irisAmount: number,
): Point => {
	const r = contourRadius(angle, layer, frame, radius, geometry, organicAmount, irisAmount);
	const xScale = 1.035 + 0.014 * Math.sin(frame * 0.009);
	const yScale = 0.965 + 0.012 * Math.cos(frame * 0.011);
	const driftX = 1.6 * Math.sin(frame * 0.018 + layer * 0.16);
	const driftY = 1.8 * Math.sin(frame * 0.016 + layer * 0.09);
	return {
		x: center.x + driftX + Math.cos(angle) * r * xScale,
		y: center.y + driftY + Math.sin(angle) * r * yScale,
	};
};

const traceContour = (
	context: CanvasRenderingContext2D,
	center: Point,
	layer: number,
	frame: number,
	radius: number,
	geometry: Geometry,
	organicAmount: number,
	irisAmount: number,
): void => {
	context.beginPath();
	for (let index = 0; index < CONTOUR_SAMPLES; index += 1) {
		const point = contourPoint(
			center,
			(index / CONTOUR_SAMPLES) * TAU,
			layer,
			frame,
			radius,
			geometry,
			organicAmount,
			irisAmount,
		);
		if (index === 0) context.moveTo(point.x, point.y);
		else context.lineTo(point.x, point.y);
	}
	context.closePath();
};

const drawSoulprint = (
	context: CanvasRenderingContext2D,
	frame: number,
	center: Point,
	radius: number,
	options: {
		geometry?: Geometry;
		organicAmount?: number;
		irisAmount?: number;
		color?: string;
		secondaryColor?: string;
		alpha?: number;
		latticeAlpha?: number;
		warmth?: number;
	},
): void => {
	const geometry = options.geometry ?? 'organic';
	const organicAmount = options.organicAmount ?? 1;
	const irisAmount = options.irisAmount ?? 0;
	const color = options.color ?? AMBER;
	const alpha = options.alpha ?? 1;
	const warmth = clamp(options.warmth ?? (color === GOLD ? 1 : 0));
	context.save();
	context.lineCap = 'round';
	context.lineJoin = 'round';
	if (color === AMBER || color === GOLD || warmth > 0.45) {
		traceContour(context, center, 0, frame, radius * 0.995, geometry, organicAmount, irisAmount);
		context.fillStyle = 'rgba(245,158,11,0.045)';
		context.globalAlpha = alpha;
		context.fill();
	}
	for (let layer = 0; layer < CONTOUR_LAYERS; layer += 1) {
		traceContour(context, center, layer, frame, radius, geometry, organicAmount, irisAmount);
		const isVein = options.secondaryColor === VERMILION && layer % 5 === 3;
		const layerColor = options.secondaryColor && (isVein || (options.secondaryColor !== VERMILION && layer % 4 === 2))
			? options.secondaryColor
			: color;
		context.strokeStyle = layerColor;
		context.lineWidth = isVein ? 0.82 : layer === 0 ? 3 : layer < 4 ? 2.2 : 1.1;
		const contourAlpha = lerp(0.72 + 0.12 * (1 - layer / CONTOUR_LAYERS), 0.98, warmth);
		context.globalAlpha = alpha * contourAlpha * (isVein ? 0.56 : 1);
		if (layer === 0 || layer === 6) {
			context.shadowColor = layerColor;
			context.shadowBlur = layer === 0 ? 7 : 3;
		}
		context.stroke();
		context.shadowBlur = 0;
	}

	// A small off-centre spiral makes the contour field read as a remembered fingerprint.
	context.lineWidth = 1.05;
	context.strokeStyle = options.secondaryColor === VERMILION ? AMBER : options.secondaryColor ?? color;
	context.globalAlpha = alpha * 0.8;
	for (let strand = 0; strand < 3; strand += 1) {
		context.beginPath();
		for (let index = 0; index <= 68; index += 1) {
			const p = index / 68;
			const angle = p * TAU * 1.65 + strand * TAU / 3 + frame * 0.002;
			const r = radius * (0.045 + p * (0.27 + strand * 0.016));
			const x = center.x - radius * 0.11 + Math.cos(angle) * r;
			const y = center.y + radius * 0.08 + Math.sin(angle) * r * 0.88;
			if (index === 0) context.moveTo(x, y);
			else context.lineTo(x, y);
		}
		context.stroke();
	}

	const latticeAlpha = (options.latticeAlpha ?? 0) * alpha;
	if (latticeAlpha > 0.001) {
		context.save();
		traceContour(context, center, 0, frame, radius * 0.99, geometry, organicAmount, irisAmount);
		context.clip();
		context.strokeStyle = options.secondaryColor ?? color;
		context.lineWidth = 0.65;
		context.globalAlpha = latticeAlpha * 0.45;
		context.beginPath();
		for (let x = center.x - radius; x <= center.x + radius; x += 24) {
			context.moveTo(x + 0.2 * Math.sin(frame * 0.009 + x), center.y - radius);
			context.lineTo(x - 0.2 * Math.sin(frame * 0.009 + x), center.y + radius);
		}
		for (let y = center.y - radius; y <= center.y + radius; y += 24) {
			context.moveTo(center.x - radius, y + 0.2 * Math.sin(frame * 0.008 + y));
			context.lineTo(center.x + radius, y - 0.2 * Math.sin(frame * 0.008 + y));
		}
		context.stroke();
		context.restore();
	}
	context.restore();
};

const drawBackground = (context: CanvasRenderingContext2D, frame: number): void => {
	const motionFrame = Math.min(frame, 4860);
	context.fillStyle = BACKGROUND;
	context.fillRect(0, 0, WIDTH, HEIGHT);

	context.save();
	context.strokeStyle = '#1A2630';
	context.lineWidth = 0.45;
	context.globalAlpha = 0.25;
	context.beginPath();
	for (let x = 34; x < WIDTH; x += 58) {
		const drift = 1.1 * Math.sin(motionFrame * 0.004 + x * 0.013);
		context.moveTo(x + drift, 0);
		context.lineTo(x - drift, HEIGHT);
	}
	for (let y = 22; y < HEIGHT; y += 58) {
		const drift = 0.8 * Math.sin(motionFrame * 0.003 + y * 0.012);
		context.moveTo(0, y + drift);
		context.lineTo(WIDTH, y - drift);
	}
	context.stroke();
	context.restore();

	const axisAlpha = 0.88 * (1 - smooth(4380, 4590, frame));
	if (axisAlpha > 0.001) {
		context.save();
		context.fillStyle = AXIS;
		context.globalAlpha = axisAlpha;
		context.fillRect(0, WATERLINE - 0.25, WIDTH, 0.5);
		context.restore();
	}
};

const drawAbyssStreamlines = (context: CanvasRenderingContext2D, frame: number, assimilation: number): void => {
	const center = {x: HERO.x, y: 2 * WATERLINE - HERO.y};
	const pointAt = (strand: number, progress: number): Point => {
		const phase = frame * 0.00135 + strand * TAU / 8;
		const angle = phase + progress * TAU * 0.94;
		const radius = 174 + strand * 16.5 + 13 * Math.sin(progress * TAU + strand * 0.74 + frame * 0.0018);
		return {
			x: center.x + Math.cos(angle) * radius + 7 * Math.sin(2 * angle + strand),
			y: center.y + Math.sin(angle) * radius * 0.58 + 6 * Math.cos(3 * angle - strand * 0.4),
		};
	};
	const currentColor = mixColor(CYAN, GOLD, assimilation);
	context.save();
	context.lineCap = 'round';
	for (let strand = 0; strand < 8; strand += 1) {
		context.beginPath();
		for (let sample = 0; sample <= 68; sample += 1) {
			const point = pointAt(strand, sample / 68);
			if (sample === 0) context.moveTo(point.x, point.y);
			else context.lineTo(point.x, point.y);
		}
		context.strokeStyle = currentColor;
		context.lineWidth = 1.35;
		context.globalAlpha = 0.15 + 0.06 * (0.5 + 0.5 * Math.sin(frame * 0.022 + strand * 1.3));
		context.stroke();

		const tracer = ((frame * 0.0018 + strand * 0.137) % 1 + 1) % 1;
		const head = pointAt(strand, tracer);
		const tail = pointAt(strand, Math.max(0, tracer - 0.045));
		const tracerColor = strand % 3 === 0 ? GOLD : '#A5F3FC';
		context.strokeStyle = tracerColor;
		context.lineWidth = 2.1;
		context.globalAlpha = 0.74;
		context.beginPath();
		context.moveTo(tail.x, tail.y);
		context.lineTo(head.x, head.y);
		context.stroke();
		context.fillStyle = tracerColor;
		context.globalAlpha = 0.85;
		context.beginPath();
		context.arc(head.x, head.y, 2.1, 0, TAU);
		context.fill();
	}
	context.restore();
};

const drawDroplets = (context: CanvasRenderingContext2D, frame: number): void => {
	if (frame >= 1320) return;
	const offsets = [-116, -72, -28, 24, 70, 112];
	context.save();
	for (let index = 0; index < offsets.length; index += 1) {
		const start = 104 + index * 37;
		const elapsed = frame - start;
		const cycle = ((elapsed % 238) + 238) % 238;
		const hasStarted = elapsed >= 0;
		const progress = clamp(cycle / 96);
		const x = 490 + offsets[index] + 8 * Math.sin(progress * Math.PI + index * 0.8);
		const y = 783 + 171 * progress;
		if (hasStarted && cycle < 112) {
			context.strokeStyle = index % 2 === 0 ? VERMILION : AMBER;
			context.lineWidth = 1.2;
			context.globalAlpha = (1 - progress * 0.38) * 0.74;
			context.beginPath();
			context.moveTo(x - 1.5 * Math.sin(progress * 4), y - 17 - 11 * progress);
			context.quadraticCurveTo(x + 3, y - 8, x, y);
			context.stroke();
			context.fillStyle = index % 2 === 0 ? VERMILION : GOLD;
			context.globalAlpha = 0.92;
			context.beginPath();
			context.arc(x, y, 2.5 + 0.5 * Math.sin(frame * 0.11 + index), 0, TAU);
			context.fill();
		}

		if (hasStarted && cycle >= 92 && cycle < 139) {
			const impact = clamp((cycle - 92) / 47);
			context.strokeStyle = GOLD;
			context.lineWidth = 1;
			context.globalAlpha = (1 - impact) * 0.78;
			for (let ring = 0; ring < 2; ring += 1) {
				context.beginPath();
				context.ellipse(x, 951 + index * 1.3, 5 + impact * (14 + ring * 9), 2.8 + impact * (6 + ring * 3), 0, 0, TAU);
				context.stroke();
			}
		}

		if (hasStarted && elapsed >= 96) {
			const angle = -Math.PI / 2 + offsets[index] * 0.004;
			const segmentRadius = 91 + (index % 5) * 11;
			context.strokeStyle = GOLD;
			context.lineWidth = 2.1;
			context.globalAlpha = 0.7;
			context.beginPath();
			context.ellipse(490, 1064.6, segmentRadius, segmentRadius * 0.93, 0, angle - 0.16, angle + 0.16);
			context.stroke();
		}
	}
	context.restore();
};

const drawBranchPaths = (context: CanvasRenderingContext2D, frame: number): void => {
	if (frame < 2820 || frame >= 4380) return;
	const hesitation = 2.2 * Math.sin((frame - 2820) * 0.11) * (1 - smooth(3660, 3840, frame));
	const orbit = Math.PI * smooth(3660, 3840, frame);
	const upperStart = {x: 632 - 164 * Math.sin(orbit) + hesitation, y: WATERLINE - 219.8 * Math.cos(orbit) + 38 - hesitation * 0.6};
	const node = {x: 800, y: WATERLINE};
	const upperReach = smooth(2820, 3270, frame);
	const upperEnd = {x: 769, y: WATERLINE - 22 + hesitation};
	context.save();
	context.lineCap = 'round';
	context.strokeStyle = AMBER;
	context.globalAlpha = 0.82 * (1 - smooth(3760, 3950, frame));
	context.lineWidth = 1.7;
	context.shadowColor = AMBER;
	context.shadowBlur = 5;
	context.beginPath();
	context.moveTo(upperStart.x, upperStart.y);
	context.bezierCurveTo(703, 693, 730, 778, lerp(760, upperEnd.x, upperReach), lerp(709, upperEnd.y, upperReach));
	context.stroke();
	context.shadowBlur = 0;

	const surge = smooth(3660, 3900, frame);
	const risePath = smooth(3660, 3840, frame);
	const lowerStart = {x: 632 + 164 * Math.sin(orbit), y: WATERLINE + 219.8 * Math.cos(orbit) + 12};
	const lowerEnd = {x: lerp(747, node.x, surge), y: lerp(WATERLINE + 92, node.y, surge)};
	context.strokeStyle = GOLD;
	context.globalAlpha = 0.32 + 0.62 * smooth(3660, 3780, frame);
	context.lineWidth = 1.8 + surge * 0.8;
	context.shadowColor = GOLD;
	context.shadowBlur = 7;
	context.beginPath();
	context.moveTo(lowerStart.x, lowerStart.y);
	context.bezierCurveTo(693, 1037, 715, 942, lowerEnd.x, lowerEnd.y);
	context.stroke();
	context.shadowBlur = 0;

	const nodePulse = 0.5 + 0.5 * Math.sin(frame * 0.07);
	context.fillStyle = frame >= 3900 ? GOLD : AXIS;
	context.globalAlpha = frame >= 3900 ? 0.95 : 0.68 + 0.25 * nodePulse;
	context.beginPath();
	context.arc(node.x, node.y, 12, 0, TAU);
	context.strokeStyle = frame >= 3900 ? GOLD : AXIS;
	context.lineWidth = 1.8;
	context.stroke();
	context.beginPath();
	context.arc(node.x, node.y, 4.2 + nodePulse, 0, TAU);
	context.fill();
	context.restore();
};

const drawExchange = (context: CanvasRenderingContext2D, frame: number): void => {
	if (frame < 3660 || frame >= 3900) return;
	const rise = smooth(3660, 3840, frame);
	// The pair travels through a half-turn in the flat picture plane.
	// An elliptical path exchanges the two vertical positions without perspective.
	const angle = Math.PI * rise;
	const goldCenter = {
		x: 490 + 164 * Math.sin(angle),
		y: WATERLINE + 219.8 * Math.cos(angle),
	};
	const amberCenter = {
		x: 490 - 164 * Math.sin(angle),
		y: WATERLINE - 219.8 * Math.cos(angle),
	};
	const amberFade = 1 - smooth(3840, 3900, frame);
	drawSoulprint(context, frame, amberCenter, 164, {
		color: AMBER,
		secondaryColor: VERMILION,
		alpha: 0.86 * amberFade,
	});
	drawSoulprint(context, frame, goldCenter, 166, {
		color: GOLD,
		secondaryColor: AMBER,
		alpha: 0.72 + 0.25 * rise,
	});
};

const drawImpactRings = (context: CanvasRenderingContext2D, frame: number): void => {
	if (frame < 3900 || frame >= 4380) return;
	context.save();
	context.lineWidth = 1.25;
	context.strokeStyle = GOLD;
	for (let ring = 0; ring < 7; ring += 1) {
		const rawAge = (frame - 3900 - ring * 31) / 480;
		if (rawAge < 0 || rawAge >= 1) continue;
		const age = clamp(rawAge);
		const radius = 14 + 390 * age;
		context.globalAlpha = (1 - age) * 0.62;
		context.beginPath();
		context.ellipse(800, WATERLINE, radius, radius * 0.27, 0, 0, TAU);
		context.stroke();
	}
	context.fillStyle = GOLD;
	context.globalAlpha = 0.95 * (1 - smooth(3900, 3948, frame));
	context.beginPath();
	context.arc(800, WATERLINE, 12, 0, TAU);
	context.strokeStyle = GOLD;
	context.lineWidth = 2.2;
	context.stroke();
	context.beginPath();
	context.arc(800, WATERLINE, 4.5, 0, TAU);
	context.fill();
	context.restore();
};

const drawIrisDetails = (
	context: CanvasRenderingContext2D,
	frame: number,
	center: Point,
	radius: number,
	reveal: number,
): void => {
	const amount = clamp(reveal);
	if (amount <= 0) return;
	context.save();
	context.lineCap = 'round';
	context.lineJoin = 'round';
	for (let filament = 0; filament < 32; filament += 1) {
		const phase = (frame - 4380) * 0.00055;
		const angle = filament * TAU / 32 + phase + 0.035 * Math.sin(filament * 1.71);
		const startRadius = 38 + 2.5 * Math.sin(filament * 2.13);
		const endRadius = radius * lerp(0.7, 0.9, amount) * (0.96 + 0.035 * Math.sin(filament * 1.37));
		const bend = 0.075 * Math.sin(filament * 1.29 + phase * 2);
		const point = (r: number, a: number): Point => ({
			x: center.x + Math.cos(a) * r,
			y: center.y + Math.sin(a) * r * 0.96,
		});
		const start = point(startRadius, angle);
		const control1 = point(lerp(startRadius, endRadius, 0.34), angle + bend);
		const control2 = point(lerp(startRadius, endRadius, 0.72), angle - bend * 0.7);
		const end = point(endRadius, angle + bend * 0.32);
		context.beginPath();
		context.moveTo(start.x, start.y);
		context.bezierCurveTo(control1.x, control1.y, control2.x, control2.y, end.x, end.y);
		context.strokeStyle = filament % 5 === 0 ? AMBER : GOLD;
		context.lineWidth = filament % 4 === 0 ? 1.45 : 1.05;
		context.globalAlpha = amount * (0.44 + 0.18 * (0.5 + 0.5 * Math.sin(filament * 2.4)));
		context.stroke();
	}

	context.fillStyle = BACKGROUND;
	context.globalAlpha = amount;
	context.beginPath();
	context.arc(center.x, center.y, 32, 0, TAU);
	context.fill();
	context.strokeStyle = GOLD;
	context.lineWidth = 1.35;
	context.globalAlpha = 0.92 * amount;
	context.beginPath();
	context.arc(center.x, center.y, 36, 0, TAU);
	context.stroke();
	context.restore();
};

const drawIris = (context: CanvasRenderingContext2D, frame: number, fade: number): void => {
	const afterSilence = Math.max(0, frame - 4860);
	const evolution = frame < 4860 ? frame : 4860 + afterSilence * 0.24;
	const breath = 1 + 0.013 * Math.sin((evolution - 4380) * 0.018);
	const center = {
		x: 490 + 2.4 * Math.sin((evolution - 4380) * 0.006),
		y: 885 + 2.8 * Math.sin((evolution - 4380) * 0.007),
	};
	drawSoulprint(context, evolution, center, 250 * breath, {
		color: GOLD,
		secondaryColor: AMBER,
		alpha: fade,
		irisAmount: 1,
	});
	drawIrisDetails(context, evolution, center, 250 * breath, fade);

	const glintOn = frame >= 4890 && frame <= 4904;
	if (glintOn) {
		const pixelX = Math.floor(center.x * 2) / 2;
		const pixelY = Math.floor(center.y * 2) / 2;
		context.save();
		context.setTransform(2, 0, 0, 2, 0, 0);
		context.globalAlpha = 1;
		context.shadowBlur = 0;
		context.fillStyle = CYAN;
		context.fillRect(pixelX, pixelY, 0.5, 0.5);
		context.restore();
	}
};

export const drawScene = (context: CanvasRenderingContext2D, frame: number): void => {
	const f = Number.isFinite(frame) ? clamp(frame, 0, DURATION) : 0;
	context.setTransform(2, 0, 0, 2, 0, 0);
	context.clearRect(0, 0, WIDTH, HEIGHT);
	context.globalAlpha = 1;
	context.globalCompositeOperation = 'source-over';
	context.lineCap = 'round';
	context.lineJoin = 'round';
	drawBackground(context, f);

	if (f < 1320) {
		drawAbyssStreamlines(context, f, 0.08 + 0.16 * smooth(0, 1320, f));
		drawSoulprint(context, f, HERO, 166, {
			color: AMBER,
			secondaryColor: VERMILION,
			alpha: 0.97,
		});
		context.save();
		context.translate(0, WATERLINE * 2);
		context.scale(1, -1);
		drawSoulprint(context, f, HERO, 166, {
			geometry: 'lattice',
			organicAmount: 0,
			color: CYAN,
			secondaryColor: '#67E8F9',
			alpha: 0.94,
			latticeAlpha: 0.78,
		});
		context.restore();
		drawDroplets(context, f);
		return;
	}

	if (f < 2820) {
		const convergence = smooth(1320, 2820, f);
		const echoColor = mixColor(CYAN, GOLD, convergence);
		drawAbyssStreamlines(context, f, convergence);
		drawSoulprint(context, f, HERO, 166, {
			color: AMBER,
			secondaryColor: VERMILION,
			alpha: 0.98,
		});
		context.save();
		context.translate(0, WATERLINE * 2);
		context.scale(1, -1);
		drawSoulprint(context, f, HERO, 166, {
			geometry: 'lattice',
			organicAmount: convergence,
			color: echoColor,
			secondaryColor: mixColor('#67E8F9', AMBER, convergence),
			alpha: 0.95,
			latticeAlpha: 0.74 * (1 - convergence),
			warmth: convergence,
		});
		context.restore();
		return;
	}

	if (f < 3900) {
		const exchange = smooth(3660, 3840, f);
		if (f < 3660) {
			const upperCenter = {x: HERO.x, y: HERO.y + 1.7 * Math.sin(f * 0.075) * (1 - exchange)};
			drawSoulprint(context, f, upperCenter, 166, {
				color: AMBER,
				secondaryColor: VERMILION,
				alpha: 0.98,
			});
			context.save();
			context.translate(0, WATERLINE * 2);
			context.scale(1, -1);
			drawSoulprint(context, f, upperCenter, 166, {
				color: GOLD,
				secondaryColor: AMBER,
				alpha: 0.97,
			});
			context.restore();
		}
		drawBranchPaths(context, f);
		drawExchange(context, f);
		return;
	}

	if (f < 4380) {
		const transition = smooth(3900, 4380, f);
		const center = {x: 490, y: lerp(625, 885, transition)};
		const radius = lerp(166, 250, transition);
		drawSoulprint(context, f, center, radius, {
			color: GOLD,
			secondaryColor: AMBER,
			alpha: 0.96,
			irisAmount: transition,
		});
		drawImpactRings(context, f);
		if (f >= 4320) drawIrisDetails(context, f, center, radius, smooth(4320, 4380, f));
		return;
	}

	const fade = 1 - smooth(5280, 5399, f);
	drawIris(context, f, fade);
};

export const Scene: React.FC<{frame: number}> = ({frame}) => {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useLayoutEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const handle = delayRender(`EP18 v03 pure 2D scene frame ${frame}`);
		let cancelled = false;
		let released = false;
		const release = (): void => {
			if (released) return;
			released = true;
			continueRender(handle);
		};
		const fail = (error: unknown): void => {
			if (cancelled || released) return;
			released = true;
			cancelRender(error instanceof Error ? error : new Error(String(error)));
		};

		void Promise.resolve(document.fonts?.ready)
			.then(() => {
				if (cancelled) return;
				const context = canvas.getContext('2d', {alpha: false});
				if (!context) throw new Error('Could not acquire the EP18 v03 2D canvas context.');
				drawScene(context, frame);
				// drawScene is synchronous on this canvas; the handle is released after its draw calls finish.
				release();
			})
			.catch(fail);

		return () => {
			cancelled = true;
			// A frame superseded during font readiness must not leave Remotion waiting on its handle.
			release();
		};
	}, [frame]);

	return (
		<canvas
			ref={canvasRef}
			width={NATIVE_WIDTH}
			height={NATIVE_HEIGHT}
			aria-hidden="true"
			style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}
		/>
	);
};

export default Scene;
