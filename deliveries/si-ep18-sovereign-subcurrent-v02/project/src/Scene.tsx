import React, {useLayoutEffect, useRef} from 'react';
import {cancelRender, continueRender, delayRender} from 'remotion';

export const WIDTH = 1080;
export const HEIGHT = 1920;
export const NATIVE_WIDTH = 2160;
export const NATIVE_HEIGHT = 3840;
export const WATERLINE = 729.6;
export const HERO = {x: 485, y: 1060};

const SURFACE = '#081420';
const DEEP = '#060709';
const INK = '#1E293B';
const ICE = '#E0F2FE';
const CYAN = '#0284C7';
const GOLD = '#F59E0B';
const GOLD_LIGHT = '#FACC15';
const VERMILION = '#E11D48';
const TAU = Math.PI * 2;

type Point = {x: number; y: number};

const clamp = (value: number, min = 0, max = 1): number => Math.min(max, Math.max(min, value));
const smooth = (from: number, to: number, value: number): number => {
	const t = clamp((value - from) / (to - from));
	return t * t * (3 - 2 * t);
};
const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;

const tracePoints = (context: CanvasRenderingContext2D, points: Point[], close = false): void => {
	if (points.length < 2) return;
	context.beginPath();
	context.moveTo(points[0].x, points[0].y);
	for (let index = 1; index < points.length; index += 1) context.lineTo(points[index].x, points[index].y);
	if (close) context.closePath();
};

const contourPoints = (scale = 1): Point[] => {
	const base: Point[] = [
		// Exposed crown: a broken, asymmetric ridge with a high left peak and lower right shoulder.
		{x: 338, y: 730}, {x: 354, y: 688}, {x: 378, y: 659}, {x: 389, y: 630},
		{x: 420, y: 604}, {x: 436, y: 565}, {x: 464, y: 539}, {x: 480, y: 495},
		{x: 501, y: 494}, {x: 522, y: 555}, {x: 547, y: 585}, {x: 566, y: 610},
		{x: 609, y: 560}, {x: 630, y: 628}, {x: 650, y: 678}, {x: 658, y: 730},
		// The submerged mass is broad, stepped and fractured, with a heavier right shoulder.
		{x: 711, y: 757}, {x: 776, y: 791}, {x: 839, y: 833}, {x: 872, y: 887},
		{x: 856, y: 934}, {x: 874, y: 979}, {x: 842, y: 1025}, {x: 858, y: 1080},
		{x: 825, y: 1127}, {x: 838, y: 1186}, {x: 799, y: 1231}, {x: 810, y: 1287},
		{x: 768, y: 1338}, {x: 758, y: 1395}, {x: 718, y: 1443}, {x: 700, y: 1508},
		{x: 654, y: 1557}, {x: 638, y: 1611}, {x: 596, y: 1659}, {x: 579, y: 1701},
		{x: 530, y: 1740}, {x: 480, y: 1708}, {x: 428, y: 1681}, {x: 403, y: 1638},
		{x: 358, y: 1607}, {x: 343, y: 1554}, {x: 306, y: 1525}, {x: 292, y: 1471},
		{x: 263, y: 1434}, {x: 253, y: 1377}, {x: 222, y: 1340}, {x: 211, y: 1280},
		{x: 181, y: 1240}, {x: 173, y: 1176}, {x: 149, y: 1137}, {x: 128, y: 1076},
		{x: 121, y: 1028}, {x: 139, y: 977}, {x: 160, y: 930}, {x: 198, y: 891},
		{x: 228, y: 855}, {x: 276, y: 829}, {x: 313, y: 796},
	];
	const center = {x: 500, y: 1097};
	return base.map(({x, y}) => ({
		x: center.x + (x - center.x) * scale,
		y: center.y + (y - center.y) * scale,
	}));
};

const drawClosedPolygon = (context: CanvasRenderingContext2D, points: Point[]): void => {
	// Keep the existing helper name, but preserve the hard geological edges with straight segments.
	tracePoints(context, points, true);
};

const drawBackground = (context: CanvasRenderingContext2D, frame: number): void => {
	context.fillStyle = SURFACE;
	context.fillRect(0, 0, WIDTH, WATERLINE);
	context.fillStyle = DEEP;
	context.fillRect(0, WATERLINE, WIDTH, HEIGHT - WATERLINE);

	const gridOpacity = 1 - smooth(4860, 5040, frame);
	if (gridOpacity > 0.001) {
		context.save();
		context.lineWidth = 0.7;
		context.strokeStyle = CYAN;
		context.globalAlpha = 0.19 * gridOpacity;
		context.beginPath();
		for (let x = 20; x <= WIDTH; x += 50) {
			context.moveTo(x, 0);
			context.lineTo(x, WATERLINE);
		}
		for (let y = 16; y < WATERLINE; y += 50) {
			context.moveTo(0, y);
			context.lineTo(WIDTH, y);
		}
		context.stroke();
		context.strokeStyle = INK;
		context.globalAlpha = 0.42 * gridOpacity;
		context.beginPath();
		for (let x = 20; x <= WIDTH; x += 50) {
			context.moveTo(x, WATERLINE);
			context.lineTo(x, HEIGHT);
		}
		for (let y = WATERLINE + 16; y < HEIGHT; y += 50) {
			context.moveTo(0, y);
			context.lineTo(WIDTH, y);
		}
		context.stroke();
		context.strokeStyle = ICE;
		context.globalAlpha = 0.035 * gridOpacity;
		context.lineWidth = 0.45;
		context.beginPath();
		for (let x = 45; x <= WIDTH; x += 100) {
			context.moveTo(x, 0);
			context.lineTo(x, WATERLINE);
		}
		for (let y = 41; y < WATERLINE; y += 100) {
			context.moveTo(0, y);
			context.lineTo(WIDTH, y);
		}
		context.stroke();
		context.restore();
	}

	const surfaceGlow = context.createLinearGradient(0, WATERLINE - 38, 0, WATERLINE + 75);
	surfaceGlow.addColorStop(0, 'rgba(2,132,199,0)');
	surfaceGlow.addColorStop(0.48, `rgba(224,242,254,${0.13 + 0.025 * Math.sin(frame / 31)})`);
	surfaceGlow.addColorStop(1, 'rgba(2,132,199,0)');
	context.fillStyle = surfaceGlow;
	context.fillRect(0, WATERLINE - 38, WIDTH, 113);

	context.save();
	context.lineWidth = 1;
	context.strokeStyle = ICE;
	context.globalAlpha = 0.66;
	context.beginPath();
	context.moveTo(0, WATERLINE + 0.5 * Math.sin(frame / 29));
	for (let x = 0; x <= WIDTH; x += 12) {
		const wave = 1.7 * Math.sin(x * 0.017 + frame * 0.021) + 0.65 * Math.sin(x * 0.047 - frame * 0.013);
		context.lineTo(x, WATERLINE + wave);
	}
	context.stroke();
	context.globalAlpha = 0.18;
	context.strokeStyle = CYAN;
	context.lineWidth = 5;
	context.stroke();
	context.restore();
};

const drawIceberg = (context: CanvasRenderingContext2D, frame: number): void => {
	const bob = 1.5 * Math.sin(frame / 113);
	const mass = contourPoints();
	context.save();
	context.translate(0, bob);
	drawClosedPolygon(context, mass);
	const underseaFill = context.createLinearGradient(0, WATERLINE, 0, 1740);
	underseaFill.addColorStop(0, 'rgba(24,69,90,0.66)');
	underseaFill.addColorStop(0.22, 'rgba(13,48,68,0.53)');
	underseaFill.addColorStop(0.58, 'rgba(7,27,43,0.37)');
	underseaFill.addColorStop(0.88, 'rgba(5,14,23,0.24)');
	underseaFill.addColorStop(1, 'rgba(6,7,9,0.035)');
	context.fillStyle = underseaFill;
	context.fill();

	// All geology sits inside one angular boundary; the central shadow keeps the seal clear.
	context.save();
	drawClosedPolygon(context, mass);
	context.clip();
	const centerShadow = context.createRadialGradient(HERO.x, HERO.y, 135, HERO.x, HERO.y, 430);
	centerShadow.addColorStop(0, 'rgba(3,9,15,0.35)');
	centerShadow.addColorStop(0.54, 'rgba(4,14,23,0.22)');
	centerShadow.addColorStop(1, 'rgba(5,16,26,0)');
	context.fillStyle = centerShadow;
	context.fillRect(110, WATERLINE, 770, 1040);

	// Cold planar faces flank the seal, leaving a dark window through the center.
	const face = (points: Point[], color: string | CanvasGradient, edgeAlpha: number): void => {
		drawClosedPolygon(context, points);
		context.fillStyle = color;
		context.fill();
		context.strokeStyle = `rgba(145,211,233,${edgeAlpha})`;
		context.lineWidth = 1.05;
		context.stroke();
	};

	// Crown shadow on the text-facing left slope.
	face([
		{x: 480, y: 495}, {x: 464, y: 539}, {x: 436, y: 565}, {x: 420, y: 604},
		{x: 389, y: 630}, {x: 378, y: 659}, {x: 354, y: 688}, {x: 338, y: 730},
		{x: 430, y: 730}, {x: 455, y: 672}, {x: 478, y: 617}, {x: 495, y: 566},
	], 'rgba(8,38,57,0.62)', 0.23);
	// Pale cyan crown face begins to the right of the opening hook text.
	const crownFace = context.createLinearGradient(480, 495, 650, 730);
	crownFace.addColorStop(0, 'rgba(211,237,247,0.66)');
	crownFace.addColorStop(0.34, 'rgba(151,205,224,0.43)');
	crownFace.addColorStop(1, 'rgba(16,87,119,0.31)');
	face([
		{x: 522, y: 555}, {x: 547, y: 585},
		{x: 566, y: 610}, {x: 609, y: 560}, {x: 630, y: 628}, {x: 650, y: 678},
		{x: 658, y: 730}, {x: 548, y: 730}, {x: 529, y: 684}, {x: 510, y: 625},
		{x: 493, y: 568}, {x: 522, y: 555},
	], crownFace, 0.36);
	// A sharper light plane catches the right side of the ridge without washing it out.
	face([
		{x: 522, y: 555}, {x: 547, y: 585}, {x: 566, y: 610},
		{x: 609, y: 560}, {x: 630, y: 628}, {x: 612, y: 648}, {x: 578, y: 632},
		{x: 548, y: 599}, {x: 522, y: 571},
	], 'rgba(203,232,243,0.22)', 0.32);

	// Angular underwater planes follow the fractured shoulders and fade toward depth.
	face([
		{x: 338, y: 730}, {x: 411, y: 751}, {x: 454, y: 779}, {x: 404, y: 850},
		{x: 331, y: 898}, {x: 263, y: 922}, {x: 198, y: 891}, {x: 228, y: 855},
		{x: 276, y: 829}, {x: 313, y: 796},
	], 'rgba(24,92,121,0.29)', 0.2);
	face([
		{x: 198, y: 891}, {x: 263, y: 922}, {x: 331, y: 898}, {x: 353, y: 962},
		{x: 306, y: 1005}, {x: 245, y: 1035}, {x: 171, y: 1016}, {x: 139, y: 977},
		{x: 160, y: 930},
	], 'rgba(10,61,84,0.24)', 0.16);
	face([
		{x: 658, y: 730}, {x: 711, y: 757}, {x: 776, y: 791}, {x: 839, y: 833},
		{x: 872, y: 887}, {x: 856, y: 934}, {x: 798, y: 955}, {x: 735, y: 914},
		{x: 686, y: 850},
	], 'rgba(25,98,127,0.34)', 0.22);
	face([
		{x: 798, y: 955}, {x: 856, y: 934}, {x: 874, y: 979}, {x: 842, y: 1025},
		{x: 858, y: 1080}, {x: 825, y: 1127}, {x: 785, y: 1087}, {x: 749, y: 1038},
	], 'rgba(11,62,85,0.27)', 0.17);
	face([
		{x: 128, y: 1076}, {x: 149, y: 1033}, {x: 181, y: 1016}, {x: 222, y: 1052},
		{x: 236, y: 1112}, {x: 207, y: 1170}, {x: 173, y: 1176}, {x: 149, y: 1137},
	], 'rgba(8,48,68,0.22)', 0.14);
	face([
		{x: 825, y: 1127}, {x: 838, y: 1186}, {x: 799, y: 1231}, {x: 810, y: 1287},
		{x: 768, y: 1338}, {x: 724, y: 1281}, {x: 742, y: 1215}, {x: 785, y: 1165},
	], 'rgba(7,38,56,0.22)', 0.13);
	face([
		{x: 181, y: 1240}, {x: 211, y: 1280}, {x: 222, y: 1340}, {x: 263, y: 1377},
		{x: 292, y: 1471}, {x: 253, y: 1434}, {x: 222, y: 1340},
	], 'rgba(7,31,46,0.15)', 0.1);
	face([
		{x: 718, y: 1443}, {x: 700, y: 1508}, {x: 654, y: 1557}, {x: 638, y: 1611},
		{x: 596, y: 1659}, {x: 579, y: 1701}, {x: 560, y: 1641}, {x: 609, y: 1584},
		{x: 659, y: 1519},
	], 'rgba(7,30,45,0.17)', 0.1);

	// Fine fractures stay at the crown and outer shoulders, clear of the gold center.
	context.lineJoin = 'miter';
	context.lineCap = 'round';
	context.strokeStyle = 'rgba(224,242,254,0.57)';
	context.lineWidth = 1.05;
	const cracks: Point[][] = [
		[{x: 506, y: 516}, {x: 524, y: 545}, {x: 519, y: 570}, {x: 540, y: 593}],
		[{x: 524, y: 545}, {x: 549, y: 550}, {x: 563, y: 568}],
		[{x: 600, y: 614}, {x: 589, y: 642}, {x: 609, y: 660}, {x: 602, y: 687}],
		[{x: 402, y: 662}, {x: 416, y: 682}, {x: 407, y: 706}],
		[{x: 219, y: 925}, {x: 244, y: 950}, {x: 231, y: 978}, {x: 250, y: 998}],
		[{x: 803, y: 930}, {x: 779, y: 962}, {x: 791, y: 990}, {x: 767, y: 1016}],
	];
	for (const crack of cracks) {
		tracePoints(context, crack);
		context.stroke();
	}

	// Broken, nearly horizontal geological layers replace the old nested contour rings.
	context.strokeStyle = 'rgba(186,224,239,0.23)';
	context.lineWidth = 0.85;
	const strata: Point[][] = [
		[{x: 205, y: 818}, {x: 259, y: 825}, {x: 306, y: 817}, {x: 349, y: 829}],
		[{x: 648, y: 813}, {x: 696, y: 824}, {x: 742, y: 817}, {x: 790, y: 836}],
		[{x: 160, y: 925}, {x: 199, y: 934}, {x: 236, y: 925}, {x: 270, y: 939}],
		[{x: 716, y: 925}, {x: 754, y: 932}, {x: 790, y: 923}, {x: 829, y: 943}],
		[{x: 136, y: 1042}, {x: 169, y: 1050}, {x: 203, y: 1044}, {x: 225, y: 1056}],
		[{x: 758, y: 1048}, {x: 790, y: 1058}, {x: 822, y: 1047}, {x: 845, y: 1063}],
		[{x: 171, y: 1162}, {x: 207, y: 1170}, {x: 239, y: 1163}, {x: 265, y: 1176}],
		[{x: 748, y: 1171}, {x: 779, y: 1180}, {x: 810, y: 1171}, {x: 829, y: 1187}],
	];
	for (const layer of strata) {
		tracePoints(context, layer);
		context.stroke();
	}
	context.restore();

	// A crisp polygon edge makes the floating cross-section read at thumbnail size.
	drawClosedPolygon(context, mass);
	context.strokeStyle = ICE;
	context.lineWidth = 1.35;
	context.globalAlpha = 0.72;
	context.stroke();
	context.restore();
};

const flowField = (x: number, y: number, frame: number): Point => {
	const dx = x - HERO.x;
	const dy = (y - HERO.y) * 1.14;
	const radius = Math.max(80, Math.hypot(dx, dy));
	const phaseA = frame * 0.006;
	const phaseB = frame * 0.0037;
	const curlX = 20 * Math.cos(dy * 0.013 + phaseA) * Math.sin(dx * 0.009 - phaseB);
	const curlY = -18 * Math.sin(dy * 0.013 + phaseA) * Math.cos(dx * 0.009 - phaseB);
	return {
		x: -dy / radius + curlX / (radius + 120),
		y: (dx / radius + curlY / (radius + 120)) / 1.14,
	};
};

const drawInkEddies = (context: CanvasRenderingContext2D, frame: number, intensity: number): void => {
	if (intensity < 0.01) return;
	context.save();
	context.lineCap = 'round';
	for (let line = 0; line < 22; line += 1) {
		const angle = (line / 22) * TAU + 0.09 * Math.sin(frame / 167 + line);
		const radius = 285 + (line % 6) * 39;
		let x = HERO.x + radius * Math.cos(angle);
		let y = HERO.y + radius * 0.86 * Math.sin(angle);
		const points: Point[] = [{x, y}];
		for (let step = 0; step < 118; step += 1) {
			const v = flowField(x, y, frame);
			const stepSize = 4.4 + 0.4 * Math.sin(step * 0.09 + line);
			x += v.x * stepSize;
			y += v.y * stepSize;
			if (x < 18 || x > 1062 || y < WATERLINE + 20 || y > 1890) break;
			points.push({x, y});
		}
		tracePoints(context, points);
		context.strokeStyle = INK;
		context.lineWidth = 0.75 + (line % 4) * 0.16;
		context.globalAlpha = intensity * (0.22 + (line % 5) * 0.035);
		context.stroke();
	}
	context.restore();
};

const drawGoldenSubcurrents = (
	context: CanvasRenderingContext2D,
	frame: number,
	intensity: number,
	coreRadius: number,
): void => {
	if (intensity < 0.01) return;
	context.save();
	context.beginPath();
	context.rect(0, WATERLINE, WIDTH, 1332 - WATERLINE);
	context.arc(HERO.x, HERO.y, coreRadius + 14, 0, TAU, true);
	context.clip('evenodd');
	context.lineCap = 'round';
	context.lineJoin = 'round';
	const phase = frame * 0.0034;
	for (let line = 0; line < 12; line += 1) {
		const initialAngle = (line / 12) * TAU + 0.055 * Math.sin(frame / 107 + line);
		const initialRadius = coreRadius + 48 + (line % 3) * 28;
		const points: Point[] = [];
		for (let sample = 0; sample <= 120; sample += 1) {
			const t = sample / 120;
			const angle = initialAngle + t * 1.15 + 0.12 * Math.sin(t * 4.4 + phase + line * 0.7);
			const radius = initialRadius + 13 * Math.sin(t * 5.1 + phase + line) + 7 * Math.sin(t * 10.3 - phase * 0.8);
			points.push({x: HERO.x + radius * Math.cos(angle), y: HERO.y + radius * 0.78 * Math.sin(angle)});
		}
		tracePoints(context, points);
		context.shadowColor = 'rgba(245,158,11,0.7)';
		context.shadowBlur = 5.5;
		context.strokeStyle = GOLD;
		context.lineWidth = 1.75;
		context.globalAlpha = intensity * (0.58 + 0.08 * Math.sin(phase + line));
		context.stroke();
		context.shadowBlur = 0;
		context.strokeStyle = GOLD_LIGHT;
		context.lineWidth = 0.72;
		context.globalAlpha = intensity * 0.74;
		context.stroke();

		// Each current forks once, like a warm ink vein following a changing pressure field.
		const forkIndex = 64;
		const forkT = forkIndex / 120;
		const forkAngle = initialAngle + forkT * 1.15 + 0.12 * Math.sin(forkT * 4.4 + phase + line * 0.7);
		const forkRadius = initialRadius + 13 * Math.sin(forkT * 5.1 + phase + line) + 7 * Math.sin(forkT * 10.3 - phase * 0.8);
		const branchSide = line % 2 === 0 ? 1 : -1;
		const branch: Point[] = [];
		for (let sample = 0; sample <= 34; sample += 1) {
			const t = sample / 34;
			const angle = forkAngle + t * (0.45 + branchSide * 0.17);
			const radius = forkRadius + t * 51 + 4 * Math.sin(t * 7 + phase + line);
			branch.push({x: HERO.x + radius * Math.cos(angle), y: HERO.y + radius * 0.78 * Math.sin(angle)});
		}
		tracePoints(context, branch);
		context.shadowColor = 'rgba(245,158,11,0.56)';
		context.shadowBlur = 4.5;
		context.strokeStyle = GOLD;
		context.lineWidth = 1.18;
		context.globalAlpha = intensity * 0.68;
		context.stroke();
		context.shadowBlur = 0;
	}
	context.restore();
};

const makeNodalSegments = (): Array<[number, number, number, number]> => {
	const count = 84;
	const min = -0.98;
	const step = (1.96 / count);
	const field = (x: number, y: number): number =>
		Math.cos(3 * Math.PI * x) * Math.cos(5 * Math.PI * y) - Math.cos(5 * Math.PI * x) * Math.cos(3 * Math.PI * y);
	const segments: Array<[number, number, number, number]> = [];
	for (let row = 0; row < count; row += 1) {
		for (let column = 0; column < count; column += 1) {
			const x0 = min + column * step;
			const x1 = x0 + step;
			const y0 = min + row * step;
			const y1 = y0 + step;
			const corners: Point[] = [{x: x0, y: y0}, {x: x1, y: y0}, {x: x1, y: y1}, {x: x0, y: y1}];
			const values = corners.map(({x, y}) => field(x, y));
			const hits: Point[] = [];
			for (let edge = 0; edge < 4; edge += 1) {
				const next = (edge + 1) % 4;
				const a = values[edge];
				const b = values[next];
				if ((a < 0 && b >= 0) || (a >= 0 && b < 0)) {
					const t = a / (a - b);
					hits.push({
						x: lerp(corners[edge].x, corners[next].x, t),
						y: lerp(corners[edge].y, corners[next].y, t),
					});
				}
			}
			if (hits.length === 2) segments.push([hits[0].x, hits[0].y, hits[1].x, hits[1].y]);
			else if (hits.length === 4) {
				segments.push([hits[0].x, hits[0].y, hits[1].x, hits[1].y]);
				segments.push([hits[2].x, hits[2].y, hits[3].x, hits[3].y]);
			}
		}
	}
	return segments;
};

const NODAL_SEGMENTS = makeNodalSegments();

const drawKintsugiCracks = (context: CanvasRenderingContext2D): void => {
	const seams: Point[][] = [
		[
			{x: 90, y: -216}, {x: 75, y: -184}, {x: 48, y: -164}, {x: 62, y: -137},
			{x: 32, y: -112}, {x: 42, y: -86}, {x: 17, y: -60}, {x: -6, y: -38},
			{x: 7, y: -13}, {x: -12, y: 18}, {x: -27, y: 46}, {x: -12, y: 69},
			{x: -42, y: 99}, {x: -37, y: 128}, {x: -62, y: 153}, {x: -50, y: 179}, {x: -71, y: 205},
		],
		[{x: 62, y: -137}, {x: 94, y: -141}, {x: 115, y: -159}, {x: 145, y: -170}],
		[{x: 17, y: -60}, {x: 48, y: -72}, {x: 65, y: -96}, {x: 95, y: -108}],
		[{x: -27, y: 46}, {x: -59, y: 50}, {x: -82, y: 74}, {x: -111, y: 83}],
		[{x: -42, y: 99}, {x: -73, y: 111}, {x: -97, y: 133}, {x: -127, y: 141}],
		[{x: -62, y: 153}, {x: -91, y: 164}, {x: -111, y: 186}, {x: -135, y: 194}],
	];
	context.lineCap = 'round';
	context.lineJoin = 'round';
	context.shadowColor = 'rgba(245,158,11,0.72)';
	context.shadowBlur = 8;
	for (const [index, seam] of seams.entries()) {
		tracePoints(context, seam);
		context.strokeStyle = index === 0 ? GOLD_LIGHT : GOLD;
		context.lineWidth = index === 0 ? 2.25 : 1.5;
		context.globalAlpha = index === 0 ? 0.95 : 0.78;
		context.stroke();
	}
	context.shadowBlur = 0;
};

const drawChladniSeal = (context: CanvasRenderingContext2D, frame: number, scale: number): void => {
	const breathing = frame >= 4860 ? 1 + 0.028 * Math.sin((frame - 4860) * TAU / 60) : 1 + 0.011 * Math.sin(frame / 73);
	const driftX = frame >= 4860 ? 4.5 * Math.sin((frame - 4860) / 47) : 2.2 * Math.sin(frame / 131);
	const driftY = frame >= 4860 ? 3.8 * Math.cos((frame - 4860) / 59) : 1.8 * Math.cos(frame / 149);
	context.save();
	context.translate(HERO.x + driftX, HERO.y + driftY);
	context.scale(scale * breathing, scale * breathing);
	context.rotate(0.018 * Math.sin(frame / 181) + (frame >= 4860 ? 0.013 * Math.sin((frame - 4860) / 83) : 0));

	const halo = context.createRadialGradient(0, 0, 18, 0, 0, 254);
	halo.addColorStop(0, 'rgba(250,204,21,0.095)');
	halo.addColorStop(0.68, 'rgba(245,158,11,0.045)');
	halo.addColorStop(1, 'rgba(245,158,11,0)');
	context.fillStyle = halo;
	context.beginPath();
	context.arc(0, 0, 254, 0, TAU);
	context.fill();

	const core = context.createRadialGradient(-58, -83, 12, 0, 0, 240);
	core.addColorStop(0, '#16130D');
	core.addColorStop(0.62, '#0B0C0D');
	core.addColorStop(1, '#070809');
	context.fillStyle = core;
	context.beginPath();
	context.arc(0, 0, 239, 0, TAU);
	context.fill();
	context.save();
	context.beginPath();
	context.arc(0, 0, 233, 0, TAU);
	context.clip();
	context.lineCap = 'round';
	context.lineWidth = 1.7;
	context.strokeStyle = GOLD_LIGHT;
	context.globalAlpha = 0.93;
	context.shadowColor = 'rgba(245,158,11,0.62)';
	context.shadowBlur = 8;
	context.beginPath();
	for (const [x1, y1, x2, y2] of NODAL_SEGMENTS) {
		context.moveTo(x1 * 225, y1 * 225);
		context.lineTo(x2 * 225, y2 * 225);
	}
	context.stroke();
	context.shadowBlur = 0;
	context.lineWidth = 1.1;
	context.strokeStyle = GOLD;
	context.globalAlpha = 0.79;
	context.beginPath();
	for (const [x1, y1, x2, y2] of NODAL_SEGMENTS) {
		context.moveTo(x1 * 217 + 1.3 * Math.sin(frame / 97), y1 * 217);
		context.lineTo(x2 * 217 + 1.3 * Math.sin(frame / 97), y2 * 217);
	}
	context.stroke();
	drawKintsugiCracks(context);
	context.restore();

	for (const [radius, color, width, alpha] of [
		[239, GOLD, 2.5, 0.99], [228, GOLD_LIGHT, 1.05, 0.9], [215, GOLD, 0.82, 0.58],
	] as const) {
		context.beginPath();
		context.arc(0, 0, radius, 0, TAU);
		context.strokeStyle = color;
		context.lineWidth = width;
		context.globalAlpha = alpha;
		context.shadowColor = 'rgba(245,158,11,0.58)';
		context.shadowBlur = radius === 239 ? 8 : 0;
		context.stroke();
	}
	context.shadowBlur = 0;
	context.strokeStyle = GOLD_LIGHT;
	context.lineWidth = 0.7;
	context.globalAlpha = 0.48;
	context.beginPath();
	for (let index = 0; index < 72; index += 1) {
		const angle = (index / 72) * TAU + frame * 0.0007;
		const inner = 222;
		const outer = inner + (index % 6 === 0 ? 13 : index % 3 === 0 ? 7 : 3);
		context.moveTo(inner * Math.cos(angle), inner * Math.sin(angle));
		context.lineTo(outer * Math.cos(angle), outer * Math.sin(angle));
	}
	context.stroke();
	context.fillStyle = GOLD_LIGHT;
	context.globalAlpha = 0.76;
	context.beginPath();
	context.arc(0, 0, 2.4, 0, TAU);
	context.fill();
	context.restore();
};

const drawOuroboros = (context: CanvasRenderingContext2D, frame: number, visibility: number): Point => {
	const cx = 720 + 4.4 * Math.sin(frame / 173);
	const cy = 530 + 2.8 * Math.cos(frame / 197);
	const rx = 168;
	const ry = 72;
	const fracture = smooth(3900, 3960, frame);
	const gap = lerp(0.13, 0.43, fracture);
	const start = -Math.PI / 2 + gap;
	const end = (3 * Math.PI) / 2 - gap;
	const points: Point[] = [];
	for (let index = 0; index <= 360; index += 1) {
		const angle = lerp(start, end, index / 360);
		const ripple = 2.2 * Math.sin(angle * 7 + frame * 0.009) + 1.1 * Math.sin(angle * 13 - frame * 0.006);
		points.push({x: cx + (rx + ripple) * Math.cos(angle), y: cy + (ry + ripple * 0.46) * Math.sin(angle)});
	}
	const opacity = visibility * (1 - 0.68 * smooth(3960, 4320, frame));
	context.save();
	context.lineCap = 'round';
	context.lineJoin = 'round';
	tracePoints(context, points);
	context.strokeStyle = ICE;
	context.lineWidth = 29;
	context.globalAlpha = opacity * 0.72;
	context.stroke();
	context.strokeStyle = '#0B1119';
	context.lineWidth = 23;
	context.globalAlpha = opacity;
	context.stroke();
	context.strokeStyle = CYAN;
	context.lineWidth = 1.15;
	context.globalAlpha = opacity * 0.82;
	context.stroke();

	// A small scale rhythm gives the loop its serpent body without turning it into a diagram.
	context.strokeStyle = ICE;
	context.lineWidth = 0.82;
	context.globalAlpha = opacity * 0.35;
	context.beginPath();
	for (let index = 0; index < 54; index += 1) {
		const fraction = (index + 0.5) / 54;
		const angle = start + (end - start) * fraction;
		const x = cx + rx * Math.cos(angle);
		const y = cy + ry * Math.sin(angle);
		const nx = Math.cos(angle);
		const ny = Math.sin(angle);
		context.moveTo(x - nx * 5, y - ny * 4);
		context.lineTo(x + nx * 5, y + ny * 4);
	}
	context.stroke();

	const top = cy - ry;
	// Left end: a distinct head, eye and open jaw directed toward its own tail.
	context.beginPath();
	context.moveTo(cx - 40, top + 10);
	context.quadraticCurveTo(cx - 47, top - 11, cx - 22, top - 18);
	context.quadraticCurveTo(cx - 4, top - 20, cx + 9, top - 6);
	context.lineTo(cx - 8, top + 1);
	context.quadraticCurveTo(cx - 23, top - 3, cx - 40, top + 10);
	context.closePath();
	context.fillStyle = '#0B1119';
	context.globalAlpha = opacity;
	context.fill();
	context.strokeStyle = ICE;
	context.lineWidth = 1.7;
	context.stroke();
	context.fillStyle = GOLD_LIGHT;
	context.beginPath();
	context.arc(cx - 19, top - 10, 2.25, 0, TAU);
	context.fill();
	context.strokeStyle = ICE;
	context.lineWidth = 1.1;
	context.beginPath();
	context.moveTo(cx - 1, top - 5);
	context.lineTo(cx + 8, top - 1);
	context.stroke();

	// Right end: a tapered tail with two small fin cuts.
	context.beginPath();
	context.moveTo(cx + 27, top + 1);
	context.lineTo(cx + 48, top - 13);
	context.lineTo(cx + 42, top + 3);
	context.lineTo(cx + 55, top + 11);
	context.lineTo(cx + 34, top + 10);
	context.closePath();
	context.fillStyle = '#0B1119';
	context.fill();
	context.strokeStyle = ICE;
	context.lineWidth = 1.35;
	context.stroke();
	context.strokeStyle = ICE;
	context.lineWidth = 0.75;
	context.beginPath();
	context.moveTo(cx + 36, top + 3);
	context.lineTo(cx + 46, top - 6);
	context.moveTo(cx + 39, top + 7);
	context.lineTo(cx + 49, top + 7);
	context.stroke();
	context.restore();
	return {x: cx + 4, y: top - 1};
};

const cubicPoint = (p0: Point, p1: Point, p2: Point, p3: Point, t: number): Point => {
	const u = 1 - t;
	return {
		x: u ** 3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t ** 3 * p3.x,
		y: u ** 3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t ** 3 * p3.y,
	};
};

const filamentPoint = (t: number, target: Point): Point => cubicPoint(
	{x: HERO.x, y: HERO.y - 238},
	{x: HERO.x + 7, y: WATERLINE + 42},
	{x: target.x - 25, y: target.y + 112},
	{x: target.x, y: target.y},
	t,
);

const drawFilament = (context: CanvasRenderingContext2D, frame: number, target: Point): void => {
	if (frame < 3660) return;
	const rise = smooth(3660, 3900, frame);
	const points: Point[] = [];
	const samples = Math.max(1, Math.ceil(200 * rise));
	for (let index = 0; index <= samples; index += 1) {
		const t = rise * index / samples;
		const point = filamentPoint(t, target);
		const taper = Math.sin(Math.PI * t);
		points.push({
			x: point.x + taper * 1.8 * Math.sin(t * 53 + frame * 0.021),
			y: point.y + taper * 1.15 * Math.sin(t * 37 - frame * 0.017),
		});
	}
	context.save();
	tracePoints(context, points);
	context.strokeStyle = GOLD;
	context.lineWidth = 10;
	context.globalAlpha = 0.2;
	context.shadowColor = 'rgba(245,158,11,0.75)';
	context.shadowBlur = 6;
	context.stroke();
	context.shadowBlur = 0;
	context.strokeStyle = GOLD_LIGHT;
	context.lineWidth = 3.5;
	context.globalAlpha = 0.96;
	context.stroke();
	context.strokeStyle = '#FFF0A6';
	context.lineWidth = 1.1;
	context.globalAlpha = 0.82;
	context.stroke();
	const tip = points[points.length - 1];
	context.fillStyle = GOLD_LIGHT;
	context.globalAlpha = 0.92;
	context.beginPath();
	context.arc(tip.x, tip.y, 3.1 + 0.75 * Math.sin(frame / 8), 0, TAU);
	context.fill();
	const fork = smooth(3900, 3960, frame) * (1 - smooth(4040, 4100, frame));
	if (fork > 0.001) {
		context.strokeStyle = GOLD_LIGHT;
		context.lineWidth = 1.5;
		context.globalAlpha = 0.88 * fork;
		context.shadowColor = 'rgba(245,158,11,0.72)';
		context.shadowBlur = 4;
		const length = 27 * smooth(3900, 3960, frame);
		for (const side of [-1, 1]) {
			context.beginPath();
			context.moveTo(tip.x, tip.y);
			context.quadraticCurveTo(tip.x + side * length * 0.38, tip.y - length * 0.14, tip.x + side * length, tip.y - length * 0.52);
			context.stroke();
		}
		context.shadowBlur = 0;
	}
	context.restore();
};

const drawFracture = (context: CanvasRenderingContext2D, frame: number, target: Point): void => {
	if (frame < 3900) return;
	const breakOpen = smooth(3900, 3960, frame);
	const settled = 1 - 0.45 * smooth(3960, 4320, frame);
	context.save();
	context.lineCap = 'round';
	context.strokeStyle = ICE;
	context.lineWidth = 1.3;
	context.globalAlpha = 0.9 * settled;
	const cracks: Point[][] = [
		[target, {x: target.x - 19, y: target.y - 18}, {x: target.x - 44, y: target.y - 48}, {x: target.x - 63, y: target.y - 79}, {x: target.x - 95, y: target.y - 101}],
		[target, {x: target.x + 20, y: target.y - 16}, {x: target.x + 42, y: target.y - 43}, {x: target.x + 68, y: target.y - 56}, {x: target.x + 99, y: target.y - 88}],
		[target, {x: target.x + 13, y: target.y + 22}, {x: target.x + 38, y: target.y + 47}, {x: target.x + 59, y: target.y + 73}, {x: target.x + 91, y: target.y + 91}],
		[target, {x: target.x - 18, y: target.y + 24}, {x: target.x - 43, y: target.y + 49}, {x: target.x - 66, y: target.y + 66}, {x: target.x - 87, y: target.y + 97}],
		[target, {x: target.x + 31, y: target.y + 5}, {x: target.x + 54, y: target.y + 7}, {x: target.x + 76, y: target.y + 20}, {x: target.x + 103, y: target.y + 34}],
	];
	for (const points of cracks) {
		const scaled = points.map((point, index) => ({
			x: target.x + (point.x - target.x) * breakOpen * settled,
			y: target.y + (point.y - target.y) * (index === 0 ? 1 : breakOpen * settled),
		}));
		tracePoints(context, scaled);
		context.stroke();
	}
	context.strokeStyle = VERMILION;
	context.lineWidth = 1.05;
	context.globalAlpha = 0.58 * breakOpen * settled;
	context.beginPath();
	context.moveTo(target.x - 30 * breakOpen, target.y + 9);
	context.lineTo(target.x - 47 * breakOpen, target.y + 22);
	context.lineTo(target.x - 53 * breakOpen, target.y + 36);
	context.stroke();

	const shardFade = smooth(3895, 3930, frame) * (1 - smooth(4040, 4100, frame));
	const shardTravel = smooth(3900, 4100, frame);
	for (let index = 0; index < 4; index += 1) {
		const side = index % 2 === 0 ? -1 : 1;
		const startX = target.x + side * (13 + (index % 3) * 8);
		const startY = target.y + (index < 2 ? -10 : 12);
		const x = startX + side * (12 + index * 5) * shardTravel;
		const y = startY + (index < 2 ? -1 : 1) * (15 + index * 3) * shardTravel;
		context.save();
		context.translate(x, y);
		context.rotate(frame * 0.012 + index * 1.7);
		context.globalAlpha = shardFade * 0.76;
		context.fillStyle = '#BFEAFF';
		context.strokeStyle = ICE;
		context.lineWidth = 0.85;
		context.beginPath();
		context.moveTo(-3.5, -8 - index);
		context.lineTo(4 + index * 0.5, -1.5);
		context.lineTo(-2, 6 + index);
		context.closePath();
		context.fill();
		context.stroke();
		context.restore();
	}
	context.restore();
};

const drawHarmonicRose = (context: CanvasRenderingContext2D, frame: number, center: Point): void => {
	if (frame < 3960) return;
	const grow = smooth(3960, 4320, frame);
	const radius = 12 + 98 * grow;
	const phase = frame * 0.003;
	context.save();
	context.translate(center.x, center.y);
	context.rotate(phase * 0.45);
	context.lineCap = 'round';
	for (let layer = 0; layer < 3; layer += 1) {
		const points: Point[] = [];
		for (let index = 0; index <= 480; index += 1) {
			const angle = (index / 480) * TAU;
			const petal = 0.58 + 0.42 * Math.cos(6 * angle + phase + layer * 0.38);
			const r = radius * petal * (0.72 + layer * 0.12);
			points.push({x: r * Math.cos(angle), y: r * Math.sin(angle)});
		}
		tracePoints(context, points, true);
		context.strokeStyle = layer === 1 ? CYAN : layer === 2 ? GOLD : GOLD_LIGHT;
		context.lineWidth = layer === 0 ? 2.2 : layer === 1 ? 1.4 : 0.78;
		context.globalAlpha = (0.36 + 0.58 * grow) * (layer === 2 ? 0.58 : 0.88);
		context.stroke();
	}
	context.fillStyle = GOLD_LIGHT;
	context.globalAlpha = 0.5 + 0.45 * grow;
	context.beginPath();
	context.arc(0, 0, 3 + grow * 2, 0, TAU);
	context.fill();
	context.restore();
};

const drawScanningLight = (context: CanvasRenderingContext2D, frame: number): void => {
	if (frame >= 1320) return;
	const active = smooth(40, 120, frame) * (1 - smooth(1190, 1320, frame));
	const progress = smooth(70, 910, frame);
	const y = lerp(305, WATERLINE - 24, progress);
	context.save();
	const ray = context.createLinearGradient(0, y - 14, 0, y + 18);
	ray.addColorStop(0, 'rgba(224,242,254,0)');
	ray.addColorStop(0.5, `rgba(224,242,254,${0.16 * active})`);
	ray.addColorStop(1, 'rgba(2,132,199,0)');
	context.fillStyle = ray;
	context.fillRect(0, y - 14, WIDTH, 32);
	context.strokeStyle = ICE;
	context.lineWidth = 0.8;
	context.globalAlpha = 0.52 * active;
	context.beginPath();
	context.moveTo(55, y);
	context.lineTo(395, y);
	context.lineTo(433, y + 3);
	context.stroke();
	// A visible stop at the boundary reads as an access decision, never a physical refraction claim.
	if (progress > 0.78) {
		const stop = smooth(0.78, 1, progress);
		context.strokeStyle = GOLD_LIGHT;
		context.globalAlpha = active * 0.65 * stop;
		context.lineWidth = 1.1;
		context.beginPath();
		context.moveTo(430, WATERLINE - 12);
		context.lineTo(430, WATERLINE + 13);
		context.stroke();
	}
	context.restore();
};

const sealScaleForFrame = (frame: number): number => {
	if (frame < 1320) return lerp(0.42, 0.72, smooth(0, 1320, frame));
	if (frame < 2820) {
		const close = lerp(0.72, 1.25, smooth(1320, 1510, frame));
		return lerp(close, 1, smooth(2640, 2820, frame));
	}
	return 1;
};

export const drawScene = (context: CanvasRenderingContext2D, frame: number): void => {
	const f = clamp(frame, 0, 5400);
	context.setTransform(2, 0, 0, 2, 0, 0);
	context.clearRect(0, 0, WIDTH, HEIGHT);
	context.globalAlpha = 1;
	context.globalCompositeOperation = 'source-over';
	context.lineCap = 'round';
	context.lineJoin = 'round';
	if (f >= 4860) {
		context.fillStyle = DEEP;
		context.fillRect(0, 0, WIDTH, HEIGHT);
		drawChladniSeal(context, f, lerp(1, 1.15, smooth(4860, 5040, f)));
		return;
	}
	drawBackground(context, f);
	drawIceberg(context, f);
	drawInkEddies(context, f, f >= 1320 && f < 2820 ? 1.24 : 0.86);
	const sealScale = sealScaleForFrame(f);
	const currentIntensity = clamp(
		0.32 + 0.55 * smooth(1100, 1400, f) - 0.2 * smooth(2700, 2940, f) + 0.3 * smooth(4320, 4500, f),
	);
	drawGoldenSubcurrents(context, f, currentIntensity, sealScale * 239);
	drawChladniSeal(context, f, sealScale);
	drawScanningLight(context, f);
	const loopVisibility = smooth(2760, 2860, f) * (1 - 0.18 * smooth(4620, 4860, f));
	const loopTarget = drawOuroboros(context, f, loopVisibility);
	drawFilament(context, f, loopTarget);
	drawFracture(context, f, loopTarget);
	drawHarmonicRose(context, f, loopTarget);
};

export const Scene: React.FC<{frame: number}> = ({frame}) => {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useLayoutEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const handle = delayRender(`EP18 pure 2D scene frame ${frame}`);
		try {
			const context = canvas.getContext('2d', {alpha: false});
			if (!context) throw new Error('Could not acquire the EP18 2D canvas context.');
			drawScene(context, frame);
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
			style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}
		/>
	);
};

export default Scene;
