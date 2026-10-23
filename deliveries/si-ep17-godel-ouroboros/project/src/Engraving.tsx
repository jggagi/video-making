import React, {useLayoutEffect, useRef} from 'react';
import {cancelRender, continueRender, delayRender} from 'remotion';
import {
	appendPoincareGeodesic,
	buildPoincareTiling,
	mobiusDiskPoint,
	type DiskPoint,
	type PoincareTiling,
} from './hyperbolic';

type EngravingProps = {frame: number};

const WIDTH = 1080;
const HEIGHT = 1920;
const NATIVE_WIDTH = 2160;
const NATIVE_HEIGHT = 3840;
const CX = 485;
const CY = 900;
const DISK_RADIUS = 355;
const BG = '#09090B';
const IVORY = '#FAFAFA';
const SILVER = '#A1A1AA';
const HATCH = '#27272A';
const GOLD = '#FACC15';
const CRIMSON = '#E11D48';
const AMBER = '#F59E0B';
const TAU = Math.PI * 2;
const POINCARE: PoincareTiling = buildPoincareTiling({maxTriangles: 2200, maxRadius: 0.998});

const clamp = (value: number, min = 0, max = 1): number => Math.min(max, Math.max(min, value));
const smooth = (from: number, to: number, value: number): number => {
	const t = clamp((value - from) / (to - from));
	return t * t * (3 - 2 * t);
};
const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
const point = (x: number, y: number): DiskPoint => ({x, y});

const tracePolyline = (context: CanvasRenderingContext2D, points: DiskPoint[], close = false): void => {
	if (points.length < 2) return;
	context.beginPath();
	context.moveTo(points[0].x, points[0].y);
	for (let index = 1; index < points.length; index += 1) context.lineTo(points[index].x, points[index].y);
	if (close) context.closePath();
};

const diskPoint = (radius: number, angle: number): DiskPoint => ({x: radius * Math.cos(angle), y: radius * Math.sin(angle)});

const drawMedallion = (context: CanvasRenderingContext2D, frame: number): void => {
	context.save();
	context.fillStyle = BG;
	context.beginPath();
	context.arc(CX, CY, DISK_RADIUS + 1, 0, TAU);
	context.fill();

	for (const [radius, color, width] of [
		[DISK_RADIUS, IVORY, 1.15],
		[DISK_RADIUS + 5, SILVER, 0.6],
		[DISK_RADIUS + 13, HATCH, 1.1],
	] as const) {
		context.beginPath();
		context.arc(CX, CY, radius, 0, TAU);
		context.strokeStyle = color;
		context.lineWidth = width;
		context.globalAlpha = radius === DISK_RADIUS ? 0.82 : 0.88;
		context.stroke();
	}

	context.globalAlpha = 0.72;
	context.strokeStyle = SILVER;
	context.lineWidth = 0.62;
	context.beginPath();
	for (let index = 0; index < 144; index += 1) {
		const angle = (index / 144) * TAU;
		const longTick = index % 12 === 0;
		const middleTick = index % 3 === 0;
		const inner = DISK_RADIUS + 7;
		const outer = inner + (longTick ? 12 : middleTick ? 7 : 3.4);
		context.moveTo(CX + inner * Math.cos(angle), CY + inner * Math.sin(angle));
		context.lineTo(CX + outer * Math.cos(angle), CY + outer * Math.sin(angle));
	}
	context.stroke();

	context.globalAlpha = 0.4;
	context.strokeStyle = HATCH;
	context.lineWidth = 0.75;
	context.beginPath();
	for (let index = 0; index < 96; index += 1) {
		const angle = (index / 96) * TAU;
		const inner = DISK_RADIUS - 18 - (index % 4) * 2.1;
		const outer = DISK_RADIUS - 8;
		context.moveTo(CX + inner * Math.cos(angle), CY + inner * Math.sin(angle));
		context.lineTo(CX + outer * Math.cos(angle), CY + outer * Math.sin(angle));
	}
	context.stroke();

	context.globalAlpha = 0.65;
	context.strokeStyle = SILVER;
	context.lineWidth = 0.7;
	for (const y of [CY - DISK_RADIUS - 20, CY + DISK_RADIUS + 20]) {
		context.beginPath();
		context.moveTo(CX - 20, y);
		context.lineTo(CX - 5, y);
		context.moveTo(CX + 5, y);
		context.lineTo(CX + 20, y);
		context.moveTo(CX, y - 8);
		context.lineTo(CX, y + 8);
		context.stroke();
		context.beginPath();
		context.arc(CX, y, 3.2, 0, TAU);
		context.stroke();
	}
	context.restore();
};

const drawPoincareDisk = (context: CanvasRenderingContext2D, frame: number, opacity: number): void => {
	if (opacity <= 0.001) return;
	const shift = {x: 0.075 * Math.sin(frame / 239), y: 0.058 * Math.cos(frame / 317)};
	const rotation = frame * 0.00072;
	const transformed = new Map<string, DiskPoint>();
	const map = (source: DiskPoint): DiskPoint => {
		const key = `${source.x.toFixed(7)},${source.y.toFixed(7)}`;
		const cached = transformed.get(key);
		if (cached) return cached;
		const result = mobiusDiskPoint(source, shift, rotation);
		transformed.set(key, result);
		return result;
	};
	const groups: DiskPoint[][] = [[], [], []];
	for (const edge of POINCARE.edges) {
		const a = map(edge.a);
		const b = map(edge.b);
		const middleRadius = Math.hypot((a.x + b.x) / 2, (a.y + b.y) / 2);
		groups[middleRadius < 0.42 ? 0 : middleRadius < 0.78 ? 1 : 2].push(a, b);
	}

	context.save();
	context.beginPath();
	context.arc(CX, CY, DISK_RADIUS - 0.5, 0, TAU);
	context.clip();
	context.translate(CX, CY);
	context.scale(DISK_RADIUS, DISK_RADIUS);
	const colors = [IVORY, SILVER, SILVER];
	const alphas = [0.72, 0.55, 0.38];
	for (let groupIndex = 0; groupIndex < groups.length; groupIndex += 1) {
		const edges = groups[groupIndex];
		context.beginPath();
		for (let index = 0; index < edges.length; index += 2) {
			appendPoincareGeodesic(context, edges[index], edges[index + 1]);
		}
		context.strokeStyle = colors[groupIndex];
		context.lineWidth = (groupIndex === 0 ? 0.82 : 0.62) / DISK_RADIUS;
		context.globalAlpha = opacity * alphas[groupIndex];
		context.stroke();
	}
	context.restore();
	context.globalAlpha = 1;

	const arrowFade = opacity * (1 - smooth(1240, 1320, frame));
	if (arrowFade > 0.001) drawBoundaryArrows(context, frame, arrowFade);
};

const drawBoundaryArrows = (context: CanvasRenderingContext2D, frame: number, opacity: number): void => {
	const inwardMix = smooth(630, 690, frame);
	context.save();
	context.translate(CX, CY);
	context.globalAlpha = opacity * 0.9;
	context.strokeStyle = GOLD;
	context.fillStyle = GOLD;
	context.lineWidth = 1.05;
	for (let index = 0; index < 28; index += 1) {
		const angle = (index / 28) * TAU;
		const radial = {x: Math.cos(angle), y: Math.sin(angle)};
		const tangent = {x: -radial.y, y: radial.x};
		const base = diskPoint(DISK_RADIUS - 22, angle);
		const length = 11;
		const outerEnd = {x: base.x + radial.x * length, y: base.y + radial.y * length};
		const innerEnd = {x: base.x - radial.x * length, y: base.y - radial.y * length};
		const tip = {
			x: lerp(outerEnd.x, innerEnd.x, inwardMix),
			y: lerp(outerEnd.y, innerEnd.y, inwardMix),
		};
		const shoulder = {
			x: lerp(innerEnd.x, outerEnd.x, inwardMix),
			y: lerp(innerEnd.y, outerEnd.y, inwardMix),
		};
		const wing = 3.2;
		context.beginPath();
		context.moveTo(base.x, base.y);
		context.lineTo(tip.x, tip.y);
		context.moveTo(tip.x, tip.y);
		context.lineTo(shoulder.x + tangent.x * wing, shoulder.y + tangent.y * wing);
		context.moveTo(tip.x, tip.y);
		context.lineTo(shoulder.x - tangent.x * wing, shoulder.y - tangent.y * wing);
		context.stroke();
	}
	context.restore();
};

const drawHatchBand = (
	context: CanvasRenderingContext2D,
	start: DiskPoint,
	end: DiskPoint,
	width: number,
	phase: number,
): void => {
	const dx = end.x - start.x;
	const dy = end.y - start.y;
	const length = Math.hypot(dx, dy);
	const normal = {x: -dy / length, y: dx / length};
	context.save();
	context.lineWidth = 0.72;
	context.strokeStyle = SILVER;
	context.globalAlpha = 0.8;
	context.beginPath();
	for (let position = 9; position < length - 7; position += 10) {
		const shift = (Math.sin(position * 0.031 + phase) * 0.9);
		const ratio = position / length;
		const center = {x: start.x + dx * ratio, y: start.y + dy * ratio};
		context.moveTo(center.x - normal.x * width * 0.43 + shift, center.y - normal.y * width * 0.43);
		context.lineTo(center.x + normal.x * width * 0.43 + shift, center.y + normal.y * width * 0.43);
	}
	context.stroke();
	context.restore();
};

const drawPenroseRibbon = (context: CanvasRenderingContext2D, frame: number, opacity: number): void => {
	if (opacity <= 0.001) return;
	const dx = 3.6 * Math.sin(frame / 83);
	const dy = 2.8 * Math.cos(frame / 109);
	const vertices = [point(0, -220), point(194, 116), point(-194, 116)];
	const goldToCrimson = smooth(1830, 2350, frame);
	const pulsePhase = (((frame - 1320) / 840) % 1 + 1) % 1;

	context.save();
	context.translate(CX + dx, CY + dy);
	context.scale(1.28, 1.28);
	context.globalAlpha = opacity;
	context.lineJoin = 'miter';
	context.lineCap = 'square';
	context.beginPath();
	context.moveTo(vertices[0].x, vertices[0].y);
	context.lineTo(vertices[1].x, vertices[1].y);
	context.lineTo(vertices[2].x, vertices[2].y);
	context.closePath();
	context.strokeStyle = IVORY;
	context.lineWidth = 49;
	context.stroke();
	context.strokeStyle = HATCH;
	context.lineWidth = 43;
	context.stroke();
	context.strokeStyle = SILVER;
	context.lineWidth = 1.1;
	context.stroke();

	for (let side = 0; side < 3; side += 1) {
		const start = vertices[side];
		const end = vertices[(side + 1) % 3];
		drawHatchBand(context, start, end, 44, side * 1.7 + frame * 0.003);
		const normal = {x: -(end.y - start.y) / Math.hypot(end.x - start.x, end.y - start.y), y: (end.x - start.x) / Math.hypot(end.x - start.x, end.y - start.y)};
		context.beginPath();
		context.moveTo(start.x + normal.x * 14, start.y + normal.y * 14);
		context.lineTo(end.x + normal.x * 14, end.y + normal.y * 14);
		context.strokeStyle = SILVER;
		context.lineWidth = 0.8;
		context.globalAlpha = opacity * 0.58;
		context.stroke();
		context.globalAlpha = opacity;
	}

	const faultAlpha = frame < 1500 ? 0 : 0.25 + 0.75 * smooth(1500, 1540, frame);
	context.beginPath();
	for (let side = 0; side < 3; side += 1) {
		const start = vertices[side];
		const end = vertices[(side + 1) % 3];
		const length = Math.hypot(end.x - start.x, end.y - start.y);
		const normal = {x: -(end.y - start.y) / length, y: (end.x - start.x) / length};
		for (let sample = 0; sample <= 36; sample += 1) {
			const t = 0.18 + (sample / 36) * 0.64;
			const ripple = Math.sin(t * 74 + side * 2.1) * 1.8 + Math.sin(t * 131 - side) * 0.75;
			const offset = (side === 0 ? -1 : 1) * (18 + ripple);
			const x = lerp(start.x, end.x, t) + normal.x * offset;
			const y = lerp(start.y, end.y, t) + normal.y * offset;
			if (sample === 0) context.moveTo(x, y);
			else context.lineTo(x, y);
		}
	}
	context.strokeStyle = CRIMSON;
	context.lineWidth = 0.9;
	context.globalAlpha = opacity * faultAlpha * 0.82;
	context.stroke();

	// Three flat splice cuts form a cyclic over-under order: each band appears to pass
	// over the next at one joint and under the previous at another.
	for (let corner = 0; corner < 3; corner += 1) {
		const vertex = vertices[corner];
		const towardCenter = {x: -vertex.x / Math.hypot(vertex.x, vertex.y), y: -vertex.y / Math.hypot(vertex.x, vertex.y)};
		const tangent = {x: -towardCenter.y, y: towardCenter.x};
		const seamCenter = {x: vertex.x + towardCenter.x * 25, y: vertex.y + towardCenter.y * 25};
		context.beginPath();
		context.moveTo(seamCenter.x - tangent.x * 25, seamCenter.y - tangent.y * 25);
		context.lineTo(seamCenter.x + tangent.x * 25, seamCenter.y + tangent.y * 25);
		context.strokeStyle = BG;
		context.lineWidth = corner === 1 ? 4.2 : 6.5;
		context.globalAlpha = opacity;
		context.stroke();
		context.beginPath();
		context.moveTo(seamCenter.x - tangent.x * 19, seamCenter.y - tangent.y * 19);
		context.lineTo(seamCenter.x + tangent.x * 19, seamCenter.y + tangent.y * 19);
		context.strokeStyle = corner === 1 ? IVORY : SILVER;
		context.lineWidth = 1.2;
		context.globalAlpha = opacity * 0.9;
		context.stroke();
	}

	const sideIndex = Math.min(2, Math.floor(pulsePhase * 3));
	const localPhase = pulsePhase * 3 - sideIndex;
	const pulseStart = vertices[sideIndex];
	const pulseEnd = vertices[(sideIndex + 1) % 3];
	const pulsePoint = {
		x: lerp(pulseStart.x, pulseEnd.x, localPhase),
		y: lerp(pulseStart.y, pulseEnd.y, localPhase),
	};
	for (const [color, weight] of [[GOLD, 1 - goldToCrimson], [CRIMSON, goldToCrimson]] as const) {
		context.globalAlpha = opacity * weight;
		context.fillStyle = color;
		context.beginPath();
		context.arc(pulsePoint.x, pulsePoint.y, 4.4, 0, TAU);
		context.fill();
		context.strokeStyle = color;
		context.lineWidth = 1.4;
		context.beginPath();
		context.moveTo(vertices[0].x, vertices[0].y);
		context.lineTo(vertices[1].x, vertices[1].y);
		context.stroke();
	}
	context.restore();
};

const drawSquareWindow = (context: CanvasRenderingContext2D, size: number, logScale: number, opacity: number): void => {
	context.save();
	const rotation = logScale * Math.PI / 11 + Math.sin(logScale * 2.3) * 0.012;
	context.rotate(rotation);
	const half = size / 2;
	context.globalAlpha = opacity * 0.87;
	context.strokeStyle = IVORY;
	context.lineWidth = 0.92 + 0.53 * smooth(150, 800, size);
	context.strokeRect(-half, -half, size, size);
	context.globalAlpha = opacity * 0.62;
	context.strokeStyle = IVORY;
	context.lineWidth = 0.9;
	context.strokeRect(-half + 5, -half + 5, size - 10, size - 10);

	context.beginPath();
	context.arc(0, 0, size * 0.235, 0, TAU);
	context.strokeStyle = SILVER;
	context.lineWidth = 0.85;
	context.globalAlpha = opacity * 0.64;
	context.stroke();
	context.beginPath();
	context.moveTo(-size * 0.3, 0);
	context.lineTo(size * 0.3, 0);
	context.moveTo(0, -size * 0.3);
	context.lineTo(0, size * 0.3);
	context.strokeStyle = SILVER;
	context.lineWidth = 0.65;
	context.stroke();

	const partitions = 24;
	context.beginPath();
	for (let side = 0; side < 4; side += 1) {
		for (let index = 0; index < partitions; index += 1) {
			if ((index + side) % 3 === 1) continue;
			const along = -half + (size * (index + 0.5)) / partitions;
			const edge: DiskPoint[] = [
				point(along, -half),
				point(half, along),
				point(-along, half),
				point(-half, -along),
			];
			const p = edge[side];
			const fraction = (index % 4) * 0.07 + 0.08;
			let target: DiskPoint;
			if (side === 0) target = point(p.x, p.y + size * fraction);
			else if (side === 1) target = point(p.x - size * fraction, p.y);
			else if (side === 2) target = point(p.x, p.y - size * fraction);
			else target = point(p.x + size * fraction, p.y);
			context.moveTo(p.x, p.y);
			context.lineTo(target.x, target.y);
			context.arc(target.x, target.y, Math.max(1, size * 0.006), 0, TAU);
		}
	}
	context.strokeStyle = SILVER;
	context.lineWidth = 0.78;
	context.globalAlpha = opacity * 0.7;
	context.stroke();
	context.restore();
};

const drawRecursiveBlueprint = (context: CanvasRenderingContext2D, frame: number, opacity: number): void => {
	if (opacity <= 0.001) return;
	const fractionalPhase = (((frame - 2820) / 120) % 1 + 1) % 1;
	const dx = 2.4 * Math.sin(frame / 79);
	const dy = 2.1 * Math.cos(frame / 97);
	context.save();
	context.translate(CX + dx, CY + dy);
	for (let level = -2; level <= 10; level += 1) {
		const logScale = fractionalPhase - level;
		const size = 264 * 2 ** logScale;
		if (size < 8 || size > 1100) continue;
		drawSquareWindow(context, size, logScale, opacity);
	}
	context.globalAlpha = opacity * 0.58;
	context.strokeStyle = SILVER;
	context.lineWidth = 0.8;
	for (let index = 0; index < 12; index += 1) {
		const angle = (index / 12) * TAU;
		const inner = 103 + (index % 3) * 8;
		const outer = 166 + (index % 4) * 9;
		context.beginPath();
		context.moveTo(inner * Math.cos(angle), inner * Math.sin(angle));
		context.lineTo(outer * Math.cos(angle), outer * Math.sin(angle));
		context.lineTo((outer + 8) * Math.cos(angle + 0.045), (outer + 8) * Math.sin(angle + 0.045));
		context.stroke();
	}
	context.restore();
};

const ringPoint = (radius: number, angle: number, frame: number): DiskPoint => {
	const modulation = 3.4 * Math.sin(angle * 7 + frame * 0.008) + 1.35 * Math.sin(angle * 17 - frame * 0.004);
	const adjustedRadius = radius + modulation;
	return {x: adjustedRadius * Math.cos(angle), y: adjustedRadius * Math.sin(angle)};
};

const traceSerpentBody = (context: CanvasRenderingContext2D, frame: number): void => {
	const gap = 0.18;
	const start = -Math.PI / 2 + gap;
	const end = (3 * Math.PI) / 2 - gap;
	const points: DiskPoint[] = [];
	for (let index = 0; index <= 720; index += 1) {
		const angle = lerp(start, end, index / 720);
		points.push(ringPoint(218, angle, frame));
	}
	tracePolyline(context, points);
};

const cantorDigit = (value: number, place: number): number => Math.floor(value / 3 ** place) % 3;

const drawCantorScales = (context: CanvasRenderingContext2D, frame: number, redCoverage: number, opacity: number): void => {
	context.save();
	const gap = 0.18;
	const start = -Math.PI / 2 + gap;
	const span = TAU - gap * 2;
	const ivoryPath = new Path2D();
	const silverPath = new Path2D();
	const crimsonPath = new Path2D();
	for (let index = 0; index < 729; index += 1) {
		const fraction = (index + 0.5) / 729;
		const angle = start + span * fraction;
		const radial = {x: Math.cos(angle), y: Math.sin(angle)};
		const tangent = {x: -radial.y, y: radial.x};
		const center = ringPoint(218, angle, frame);
		const nearHead = fraction < 0.055 || fraction > 0.945;
		for (let lane = 0; lane < 5; lane += 1) {
			if (cantorDigit(index, lane % 3) === 1 || nearHead) continue;
			const tangentOffset = (lane - 2) * 7;
			const inward = (lane - 2) * 0.8;
			const cx = center.x + tangent.x * tangentOffset + radial.x * inward;
			const cy = center.y + tangent.y * tangentOffset + radial.y * inward;
			const from = {x: cx - radial.x * 20, y: cy - radial.y * 20};
			const to = {x: cx + radial.x * 20, y: cy + radial.y * 20};
			const bow = 2.1 * Math.sin(frame * 0.006 + index * 0.18 + lane);
			const control = {x: cx + tangent.x * bow, y: cy + tangent.y * bow};
			const redArcPosition = ((fraction + frame * 0.000055) % 1 + 1) % 1;
			const path = redArcPosition < redCoverage ? crimsonPath : (index + lane) % 4 === 0 ? ivoryPath : silverPath;
			path.moveTo(from.x, from.y);
			path.quadraticCurveTo(control.x, control.y, to.x, to.y);
		}
	}
	context.lineWidth = 0.82;
	context.strokeStyle = SILVER;
	context.globalAlpha = opacity * 0.88;
	context.stroke(silverPath);
	context.strokeStyle = IVORY;
	context.lineWidth = 0.95;
	context.globalAlpha = opacity * 0.82;
	context.stroke(ivoryPath);
	context.strokeStyle = CRIMSON;
	context.lineWidth = 1.18;
	context.globalAlpha = opacity * 0.92;
	context.stroke(crimsonPath);
	context.restore();
};

const drawTail = (context: CanvasRenderingContext2D, frame: number): void => {
	context.save();
	context.beginPath();
	context.moveTo(35, -188);
	context.quadraticCurveTo(51, -199, 55, -219);
	context.lineTo(50, -239);
	context.lineTo(9, -223);
	context.lineTo(26, -218);
	context.lineTo(10, -211);
	context.quadraticCurveTo(26, -202, 35, -188);
	context.closePath();
	context.fillStyle = BG;
	context.fill();
	context.strokeStyle = IVORY;
	context.lineWidth = 2.2;
	context.stroke();

	context.strokeStyle = frame >= 3900 ? CRIMSON : SILVER;
	context.lineWidth = 0.8;
	context.globalAlpha = 0.8;
	context.beginPath();
	context.moveTo(43, -203);
	context.lineTo(31, -214);
	context.lineTo(47, -224);
	context.moveTo(48, -212);
	context.lineTo(34, -222);
	context.stroke();
	context.restore();
};

const drawSerpentHead = (context: CanvasRenderingContext2D, frame: number): void => {
	context.save();
	context.beginPath();
	context.moveTo(-48, -188);
	context.quadraticCurveTo(-48, -214, -31, -231);
	context.quadraticCurveTo(-11, -250, 10, -240);
	context.lineTo(31, -228);
	context.lineTo(37, -222);
	context.lineTo(17, -217);
	context.lineTo(33, -210);
	context.quadraticCurveTo(12, -199, -7, -207);
	context.quadraticCurveTo(-28, -207, -48, -188);
	context.closePath();
	context.fillStyle = BG;
	context.fill();
	context.strokeStyle = IVORY;
	context.lineWidth = 2.6;
	context.stroke();

	context.beginPath();
	context.moveTo(10, -219);
	context.quadraticCurveTo(22, -216, 33, -210);
	context.strokeStyle = SILVER;
	context.lineWidth = 1.05;
	context.stroke();

	context.fillStyle = IVORY;
	context.beginPath();
	context.arc(-7, -232, 5.1, 0, TAU);
	context.fill();
	context.fillStyle = BG;
	context.beginPath();
	context.arc(-5.5, -232, 2.25, 0, TAU);
	context.fill();
	context.fillStyle = GOLD;
	context.beginPath();
	context.arc(-4.7, -233, 0.8, 0, TAU);
	context.fill();

	context.fillStyle = IVORY;
	for (const x of [15, 23]) {
		context.beginPath();
		context.moveTo(x - 1.9, -218.2);
		context.lineTo(x, -211.9);
		context.lineTo(x + 1.6, -217.2);
		context.closePath();
		context.fill();
	}
	context.beginPath();
	context.moveTo(16, -211.8);
	context.lineTo(18, -206.6);
	context.lineTo(20.1, -211.3);
	context.moveTo(23, -211.3);
	context.lineTo(25, -206.5);
	context.lineTo(27, -210.2);
	context.strokeStyle = IVORY;
	context.lineWidth = 1;
	context.stroke();

	context.strokeStyle = CRIMSON;
	context.lineWidth = 1.4;
	context.beginPath();
	context.moveTo(31, -211);
	context.quadraticCurveTo(40, -210, 46, -213);
	context.moveTo(40, -211.5);
	context.lineTo(44, -216);
	context.moveTo(41, -211.5);
	context.lineTo(47, -209);
	context.stroke();

	context.fillStyle = frame >= 3900 ? CRIMSON : SILVER;
	context.beginPath();
	context.arc(24, -229, 1.1, 0, TAU);
	context.fill();
	context.restore();
};

const drawSerpentOutline = (context: CanvasRenderingContext2D, frame: number, alpha: number, offset: DiskPoint, rotationExtra = 0): void => {
	if (alpha <= 0.001) return;
	context.save();
	context.translate(offset.x, offset.y);
	context.scale(1.25, 1.25);
	context.rotate(rotationExtra);
	traceSerpentBody(context, frame);
	context.strokeStyle = IVORY;
	context.lineWidth = 64;
	context.globalAlpha = alpha * 0.82;
	context.lineCap = 'round';
	context.lineJoin = 'round';
	context.stroke();
	context.strokeStyle = HATCH;
	context.lineWidth = 56;
	context.globalAlpha = alpha;
	context.stroke();
	context.strokeStyle = SILVER;
	context.lineWidth = 47;
	context.globalAlpha = alpha * 0.72;
	context.stroke();
	context.restore();
};

const drawOuroboros = (context: CanvasRenderingContext2D, frame: number, opacity: number): void => {
	if (opacity <= 0.001) return;
	const stateFrame = Math.min(frame, 4860);
	const rotation = (stateFrame - 3600) * 0.00055;
	const redCoverage = smooth(3900, 4750, stateFrame);
	const aliasStrength = smooth(4380, 4620, stateFrame) * (1 - smooth(4840, 4860, frame));

	context.save();
	context.translate(CX, CY);
	context.scale(1.25, 1.25);
	context.rotate(rotation);
	context.globalAlpha = opacity;
	context.lineCap = 'round';
	context.lineJoin = 'round';
	traceSerpentBody(context, stateFrame);
	context.strokeStyle = IVORY;
	context.lineWidth = 65;
	context.globalAlpha = opacity * 0.88;
	context.stroke();
	context.strokeStyle = HATCH;
	context.lineWidth = 56;
	context.globalAlpha = opacity;
	context.stroke();
	context.strokeStyle = SILVER;
	context.lineWidth = 45;
	context.globalAlpha = opacity * 0.92;
	context.stroke();

	const outerKeyline: DiskPoint[] = [];
	const innerKeyline: DiskPoint[] = [];
	for (let index = 0; index <= 720; index += 1) {
		const angle = lerp(-Math.PI / 2 + 0.18, (3 * Math.PI) / 2 - 0.18, index / 720);
		outerKeyline.push(ringPoint(247, angle, stateFrame));
		innerKeyline.push(ringPoint(189, angle, stateFrame));
	}
	tracePolyline(context, outerKeyline);
	context.strokeStyle = IVORY;
	context.lineWidth = 0.95;
	context.globalAlpha = opacity * 0.72;
	context.stroke();
	tracePolyline(context, innerKeyline);
	context.strokeStyle = SILVER;
	context.lineWidth = 0.85;
	context.globalAlpha = opacity * 0.62;
	context.stroke();

	context.globalAlpha = opacity;
	drawCantorScales(context, stateFrame, redCoverage, opacity);
	drawTail(context, stateFrame);
	drawSerpentHead(context, stateFrame);

	context.strokeStyle = CRIMSON;
	context.lineWidth = 1.4;
	context.globalAlpha = opacity * redCoverage * 0.82;
	context.beginPath();
	for (let index = 0; index < 144; index += 1) {
		const fraction = 0.25 + (index / 144) * 0.48;
		const angle = -Math.PI / 2 + 0.18 + (TAU - 0.36) * fraction;
		const inner = ringPoint(192 + 2.5 * Math.sin(index * 0.2 + stateFrame * 0.003), angle, stateFrame);
		const outer = ringPoint(200 + 3 * Math.cos(index * 0.31), angle + 0.008, stateFrame);
		context.moveTo(inner.x, inner.y);
		context.lineTo(outer.x, outer.y);
	}
	context.stroke();
	context.restore();

	if (aliasStrength > 0.001) {
		drawSerpentOutline(context, stateFrame, opacity * aliasStrength * 0.13, point(1.15 * Math.sin(frame * 0.21), 0.95 * Math.cos(frame * 0.18)), 0.0018 * Math.sin(frame * 0.19));
		drawSerpentOutline(context, stateFrame, opacity * aliasStrength * 0.11, point(-1.05 * Math.sin(frame * 0.17), -1.15 * Math.cos(frame * 0.23)), -0.0015 * Math.cos(frame * 0.22));
		drawMandalaEngraving(context, frame, opacity * aliasStrength);
	}
};

const drawMandalaEngraving = (context: CanvasRenderingContext2D, frame: number, opacity: number): void => {
	context.save();
	context.translate(CX, CY);
	context.strokeStyle = SILVER;
	context.lineWidth = 0.7;
	context.globalAlpha = Math.min(0.21, opacity * 0.23);
	for (let petal = 0; petal < 12; petal += 1) {
		const angle = (petal / 12) * TAU + frame * 0.00028;
		const r0 = 270;
		const r1 = 309 + 3 * Math.sin(frame * 0.035 + petal);
		const a = {x: r0 * Math.cos(angle), y: r0 * Math.sin(angle)};
		const b = {x: r1 * Math.cos(angle + 0.025), y: r1 * Math.sin(angle + 0.025)};
		const c = {x: r1 * Math.cos(angle - 0.025), y: r1 * Math.sin(angle - 0.025)};
		context.beginPath();
		context.moveTo(a.x, a.y);
		context.quadraticCurveTo(b.x, b.y, c.x, c.y);
		context.stroke();
	}
	context.restore();
};

const drawInkDropAndRipples = (context: CanvasRenderingContext2D, frame: number): void => {
	if (frame < 4890) return;
	const flight = smooth(4890, 4920, frame);
	const x = lerp(CX + DISK_RADIUS, CX + DISK_RADIUS - 24, flight);
	const y = CY + flight * 9;
	const dropOpacity = 1 - smooth(4890, 4938, frame);
	const dropColor = AMBER;
	context.save();
	context.fillStyle = dropColor;
	context.strokeStyle = dropColor;
	context.globalAlpha = dropOpacity * 0.96;
	context.beginPath();
	context.moveTo(x, y - 12);
	context.bezierCurveTo(x - 4, y - 4, x - 10, y + 2, x - 8, y + 7);
	context.bezierCurveTo(x - 7, y + 15, x + 7, y + 15, x + 9, y + 7);
	context.bezierCurveTo(x + 10, y + 2, x + 4, y - 5, x, y - 12);
	context.closePath();
	context.fill();
	context.globalAlpha = 0.58;
	context.beginPath();
	context.moveTo(x - 1.8, y - 6);
	context.lineTo(x - 4.2, y + 3);
	context.strokeStyle = BG;
	context.lineWidth = 1.15;
	context.stroke();

	const impactFrame = 4890;
	if (frame >= impactFrame) {
		const elapsed = frame - impactFrame;
		for (let ripple = 0; ripple < 5; ripple += 1) {
			const age = elapsed - ripple * 115;
			if (age < 0) continue;
			const radius = 10 + age * 2.16;
			const alpha = 0.63 * Math.exp(-age / 315);
			context.beginPath();
			context.ellipse(CX + DISK_RADIUS, CY, radius, radius * 0.78, -0.06, 0, TAU);
			context.strokeStyle = GOLD;
			context.lineWidth = 1.15;
			context.globalAlpha = alpha;
			context.stroke();
		}
		// The locked serpent stays frozen; a visible seam of gold travels through it.
		const front = clamp(elapsed / 470) * TAU;
		context.beginPath();
		context.moveTo(CX + DISK_RADIUS, CY);
		context.lineTo(CX + 278, CY);
		for (let index = 0; index <= 320; index += 1) {
			const angle = -front * index / 320;
			const radius = 278 + 4 * Math.sin(angle * 11) + 2 * Math.sin(angle * 29);
			context.lineTo(CX + radius * Math.cos(angle), CY + radius * Math.sin(angle));
		}
		context.strokeStyle = GOLD;
		context.lineWidth = 2.25;
		context.globalAlpha = 0.82 * smooth(4890, 4920, frame);
		context.stroke();
		const seamRadius = 278 + 4 * Math.sin(-front * 11) + 2 * Math.sin(-front * 29);
		context.beginPath();
		context.arc(CX + seamRadius * Math.cos(-front), CY + seamRadius * Math.sin(-front), 4.2, 0, TAU);
		context.fillStyle = GOLD;
		context.globalAlpha = 0.9;
		context.fill();
		context.beginPath();
		context.arc(CX + DISK_RADIUS, CY, 2.4, 0, TAU);
		context.fillStyle = GOLD;
		context.globalAlpha = 0.9;
		context.fill();
	}
	context.restore();
};

const drawEngraving = (canvas: HTMLCanvasElement, frame: number): void => {
	const context = canvas.getContext('2d', {alpha: true});
	if (!context) throw new Error('Could not acquire the EP17 engraving 2D canvas context.');
	context.setTransform(2, 0, 0, 2, 0, 0);
	context.clearRect(0, 0, WIDTH, HEIGHT);
	context.lineCap = 'round';
	context.lineJoin = 'round';
	drawMedallion(context, frame);

	context.save();
	context.beginPath();
	context.arc(CX, CY, DISK_RADIUS - 1, 0, TAU);
	context.clip();
	const poincareOpacity = (1 - smooth(1260, 1340, frame)) + smooth(3500, 3700, frame) * (1 - smooth(4380, 4490, frame)) * 0.18;
	drawPoincareDisk(context, frame, clamp(poincareOpacity));
	drawPenroseRibbon(context, frame, smooth(1270, 1340, frame) * (1 - smooth(2760, 2860, frame)));
	drawRecursiveBlueprint(context, frame, smooth(2760, 2860, frame) * (1 - smooth(3540, 3660, frame)));
	drawOuroboros(context, frame, smooth(3540, 3660, frame));
	context.restore();
	drawInkDropAndRipples(context, frame);
};

export const Engraving: React.FC<EngravingProps> = ({frame}) => {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useLayoutEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const handle = delayRender(`EP17 engraving frame ${frame}`);
		try {
			drawEngraving(canvas, frame);
			continueRender(handle);
		} catch (error) {
			cancelRender(error instanceof Error ? error : new Error(String(error)));
		}
	}, [frame]);

	return (
		<canvas
			ref={canvasRef}
			width={NATIVE_WIDTH}
			height={NATIVE_HEIGHT}
			aria-hidden="true"
			style={{position: 'absolute', left: 0, top: 0, width: '100%', height: '100%', pointerEvents: 'none'}}
		/>
	);
};

export default Engraving;
