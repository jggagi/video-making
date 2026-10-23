import React, {useLayoutEffect, useRef} from 'react';
import {cancelRender, continueRender, delayRender} from 'remotion';

export const WIDTH = 1080;
export const HEIGHT = 1920;
export const NATIVE_WIDTH = 2160;
export const NATIVE_HEIGHT = 3840;

const DURATION = 5400;
const NODE = {x: 790, y: 905};
const FLOOR = 1244;
const TAU = Math.PI * 2;

type Point = {x: number; y: number};
type Palette = {fill: string; rim: string; seam: string; alpha: number};
type FigureOptions = {
	x: number;
	baseline?: number;
	scale?: number;
	alpha?: number;
	sit?: number;
	raise?: number;
	typing?: number;
	heart?: number;
	reach?: number;
	reachWorldX?: number;
	reachWorldY?: number;
	walk?: number;
	walkPhase?: number;
	palette: Palette;
	eye?: number;
	armRim?: string;
};

const clamp = (v: number, lo = 0, hi = 1): number => Math.min(hi, Math.max(lo, v));
const smooth = (from: number, to: number, value: number): number => {
	const t = clamp((value - from) / (to - from));
	return t * t * (3 - 2 * t);
};
const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
const mixHex = (from: string, to: string, amount: number): string => {
	const a = Number.parseInt(from.slice(1), 16);
	const b = Number.parseInt(to.slice(1), 16);
	const channel = (shift: number): number => Math.round(lerp((a >> shift) & 255, (b >> shift) & 255, amount));
	return '#' + [channel(16), channel(8), channel(0)].map(v => v.toString(16).padStart(2, '0')).join('');
};

const PAPER: Palette = {fill: '#55402D', rim: '#D4A163', seam: '#F4C77D', alpha: 1};
const SHADOW: Palette = {fill: '#0B2830', rim: '#36A1AC', seam: '#70D1D4', alpha: 0.94};
const GOLD: Palette = {fill: '#5A4829', rim: '#E3B54E', seam: '#FFE09A', alpha: 1};
const DEEP_SHADOW: Palette = {fill: '#101C20', rim: '#315A5E', seam: '#4D7778', alpha: 0.8};
const learnedPalette = (frame: number): Palette => {
 const p = smooth(840, 2580, frame);
 return {fill:mixHex(SHADOW.fill,PAPER.fill,p*.85),rim:mixHex(SHADOW.rim,GOLD.rim,p),seam:mixHex(SHADOW.seam,GOLD.seam,p),alpha:.94};
};

const hash = (n: number): number => {
	const v = Math.sin(n * 127.1 + 311.7) * 43758.5453123;
	return v - Math.floor(v);
};

const strokePath = (
	context: CanvasRenderingContext2D,
	path: (ctx: CanvasRenderingContext2D) => void,
	color: string,
	width: number,
): void => {
	context.beginPath();
	path(context);
	context.strokeStyle = color;
	context.lineWidth = width;
	context.lineCap = 'round';
	context.lineJoin = 'round';
	context.stroke();
};

const drawBackground = (context: CanvasRenderingContext2D, frame: number): void => {
	context.fillStyle = '#111211';
	context.fillRect(0, 0, WIDTH, HEIGHT);

	// A localized, slow side-light keeps the stage legible without making a screen-wide band.
	const lightX = 315 + 7 * Math.sin(frame * 0.0022);
	const lightY = 870 + 5 * Math.sin(frame * 0.0017 + 0.8);
	const light = context.createRadialGradient(lightX, lightY, 35, lightX, lightY, 570);
	light.addColorStop(0, 'rgba(142,111,75,0.095)');
	light.addColorStop(0.56, 'rgba(68,75,69,0.045)');
	light.addColorStop(1, 'rgba(17,18,17,0)');
	context.fillStyle = light;
	context.fillRect(90, 430, 900, 850);

	// Fine paper grain is spatially fixed and drifts by at most a few pixels.
	context.save();
	for (let i = 0; i < 190; i += 1) {
		const x = 96 + hash(i + 4) * 888;
		const y = 438 + hash(i + 791) * 826;
		const drift = Math.sin(frame * 0.003 + i * 0.7) * 1.1;
		context.globalAlpha = 0.025 + hash(i + 1409) * 0.035;
		context.fillStyle = i % 4 === 0 ? '#C5B393' : '#82928A';
		context.fillRect(x + drift, y, 0.55 + hash(i + 82) * 0.65, 0.55);
	}
	context.restore();

	context.save();
	context.globalAlpha = 0.24;
	context.strokeStyle = '#9F9A89';
	context.lineWidth = 0.65;
	context.beginPath();
	context.moveTo(93, FLOOR + 1.5 * Math.sin(frame * 0.004));
	context.bezierCurveTo(330, FLOOR - 1, 690, FLOOR + 2, 988, FLOOR + 0.8 * Math.sin(frame * 0.003));
	context.stroke();
	context.restore();
};

const drawShadowLink = (context: CanvasRenderingContext2D, heroX: number, shadowX: number, alpha: number): void => {
	if (alpha <= 0.002) return;
	const near = heroX + 3;
	const far = shadowX - 7;
	const middle = (near + far) / 2;
	context.save();
	context.globalAlpha = 0.42 * alpha;
	context.fillStyle = 'rgba(9,48,53,0.78)';
	context.beginPath();
	context.moveTo(near, FLOOR - 1);
	context.bezierCurveTo(middle - 18, FLOOR - 10, middle + 16, FLOOR - 16, far, FLOOR - 1);
	context.lineTo(far, FLOOR + 8);
	context.bezierCurveTo(middle + 12, FLOOR + 2, middle - 13, FLOOR + 5, near, FLOOR + 7);
	context.closePath();
	context.fill();
	context.globalAlpha = 0.28 * alpha;
	context.strokeStyle = '#52AAB0';
	context.lineWidth = 1.2;
	context.beginPath();
	context.moveTo(near, FLOOR + 2);
	context.quadraticCurveTo(middle, FLOOR - 5, far, FLOOR + 2);
	context.stroke();
	context.restore();
};

const drawFloorPool = (context: CanvasRenderingContext2D, x: number, width: number, color: string, alpha: number): void => {
	context.save();
	context.globalAlpha = alpha;
	context.fillStyle = color;
	context.beginPath();
	context.ellipse(x, FLOOR + 1, width, 7, 0, 0, TAU);
	context.fill();
	context.restore();
};

const drawDesk = (context: CanvasRenderingContext2D, x: number, alpha: number, frame: number): void => {
	if (alpha <= 0.002) return;
	context.save();
	context.globalAlpha = alpha;
	context.lineJoin = 'round';
	context.fillStyle = '#292A27';
	context.strokeStyle = '#8B795E';
	context.lineWidth = 1.35;
	context.beginPath();
	context.moveTo(x - 92, 992);
	context.quadraticCurveTo(x + 32, 986, x + 164, 991);
	context.lineTo(x + 164, 1007);
	context.quadraticCurveTo(x + 26, 1003, x - 92, 1008);
	context.closePath();
	context.fill();
	context.stroke();
	context.beginPath();
	context.moveTo(x - 70, 1005);
	context.lineTo(x - 75, 1222);
	context.moveTo(x + 138, 1005);
	context.lineTo(x + 147, 1222);
	context.stroke();

	// A small chair and laptop establish the desk scene with simple silhouettes.
	context.strokeStyle = '#8C806C';
	context.globalAlpha = alpha * 0.78;
	context.beginPath();
	context.moveTo(x - 48, 1021);
	context.lineTo(x - 49, 1111);
	context.quadraticCurveTo(x - 46, 1120, x - 28, 1120);
	context.lineTo(x + 26, 1120);
	context.moveTo(x - 37, 1119);
	context.lineTo(x - 50, 1219);
	context.moveTo(x + 14, 1119);
	context.lineTo(x + 30, 1219);
	context.stroke();

	context.globalAlpha = alpha;
	context.fillStyle = '#181E1D';
	context.strokeStyle = '#A39272';
	context.lineWidth = 1.2;
	context.beginPath();
	context.moveTo(x + 24, 989);
	context.lineTo(x + 30, 912);
	context.quadraticCurveTo(x + 32, 906, x + 39, 906);
	context.lineTo(x + 112, 908);
	context.quadraticCurveTo(x + 117, 909, x + 117, 915);
	context.lineTo(x + 119, 989);
	context.closePath();
	context.fill();
	context.stroke();
	context.fillStyle = '#203338';
	context.fillRect(x + 37, 916, 73, 59);
	context.globalAlpha = alpha * (0.18 + 0.04 * Math.sin(frame * 0.025));
	context.fillStyle = '#75A6A1';
	context.fillRect(x + 45, 925, 50, 1.1);
	context.fillRect(x + 45, 931, 38, 0.8);
	context.restore();
};

const drawDeletedFragments = (context: CanvasRenderingContext2D, frame: number, heroX: number, shadowX: number, alpha: number): void => {
	if (alpha <= 0.005) return;
	context.save();
	context.lineCap = 'round';
	for (let i = 0; i < 6; i += 1) {
		const age = ((frame - 610 + i * 101) % 585 + 585) % 585 / 585;
		const x = lerp(heroX + 124, shadowX - 34, age);
		const y = 1000 - 114 * age + 10 * Math.sin(frame * 0.013 + i * 1.7);
		context.globalAlpha = alpha * Math.sin(Math.PI * age) * 0.48;
		context.strokeStyle = i % 2 === 0 ? '#E8A641' : '#D9B66E';
		context.lineWidth = 1.4;
		context.beginPath();
		context.moveTo(x, y);
		context.lineTo(x + 5 + i % 3 * 2, y - 2);
		context.stroke();
	}
	context.restore();
};

const drawLimb = (context: CanvasRenderingContext2D, from: Point, through: Point, to: Point, palette: Palette, width: number): void => {
	const path = (ctx: CanvasRenderingContext2D): void => {
		ctx.moveTo(from.x, from.y);
		ctx.quadraticCurveTo(through.x, through.y, to.x, to.y);
	};
	strokePath(context, path, palette.rim, width + 2.2);
	strokePath(context, path, palette.fill, width);
	// A restrained highlight gives the limb a shaped edge without adding skin or facial detail.
	context.save();
	context.globalAlpha *= 0.36;
	strokePath(context, path, palette.seam, 0.8);
	context.restore();
};

const drawFinger = (context: CanvasRenderingContext2D, points: Point[], palette: Palette, width = 4): void => {
	const path = (ctx: CanvasRenderingContext2D): void => {
		ctx.moveTo(points[0].x, points[0].y);
		for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i].x, points[i].y);
	};
	strokePath(context, path, palette.rim, width + 1.2);
	strokePath(context, path, palette.fill, width);
};

const drawHand = (context: CanvasRenderingContext2D, x: number, y: number, mode: 'rest' | 'raise' | 'heart' | 'reach' | 'type', palette: Palette, wave: number): void => {
	context.save();
	context.fillStyle = palette.fill;
	context.strokeStyle = palette.rim;
	context.lineWidth = 1;
	context.beginPath();
	if (mode === 'raise') {
		context.ellipse(x, y + 1, 8.5, 10, 0, 0, TAU);
	} else if (mode === 'reach') {
		context.ellipse(x + 1, y, 10, 8, 0, 0, TAU);
	} else if (mode === 'heart') {
		context.ellipse(x, y + 1, 8.2, 7.2, 0, 0, TAU);
	} else if (mode === 'type') {
		context.ellipse(x + 1, y, 8.4, 5.8, 0, 0, TAU);
	} else {
		context.ellipse(x, y + 2, 7.2, 9, 0, 0, TAU);
	}
	context.fill();
	context.stroke();
	context.restore();

	if (mode === 'raise') {
		for (let i = 0; i < 4; i += 1) {
			const spread = (i - 1.5) * 4.1;
			const tipY = y - 19 - (i === 1 ? 4 : i === 2 ? 2 : 0) + (i === 0 ? wave * 2 : 0);
			drawFinger(context, [{x: x + spread * 0.45, y: y - 3}, {x: x + spread, y: y - 10}, {x: x + spread * 1.12, y: tipY}], palette, 3.8);
		}
		drawFinger(context, [{x: x - 6, y: y + 2}, {x: x - 13, y: y - 1}, {x: x - 16, y: y - 7}], palette, 3.6);
	} else if (mode === 'reach') {
		drawFinger(context, [{x: x + 5, y: y - 4}, {x: x + 15, y: y - 4}, {x: x + 21, y}], palette, 3.7);
		drawFinger(context, [{x: x + 6, y: y - 1}, {x: x + 15, y: y + 1}, {x: x + 18, y: y + 4}], palette, 3.4);
		drawFinger(context, [{x: x + 4, y: y + 2}, {x: x + 11, y: y + 6}, {x: x + 13, y: y + 8}], palette, 3.1);
		drawFinger(context, [{x: x - 4, y: y + 5}, {x: x + 1, y: y + 11}, {x: x + 8, y: y + 11}], palette, 3.2);
		drawFinger(context, [{x: x - 4, y: y - 3}, {x: x - 10, y: y - 6}, {x: x - 13, y: y - 2}], palette, 3.6);
	} else if (mode === 'heart') {
		drawFinger(context, [{x: x - 5, y: y - 2}, {x: x - 3, y: y - 12}, {x: x + 2, y: y - 15}], palette, 3.4);
		drawFinger(context, [{x: x + 1, y: y - 4}, {x: x + 7, y: y - 11}, {x: x + 11, y: y - 9}], palette, 3.4);
		drawFinger(context, [{x: x - 5, y: y + 1}, {x: x - 12, y: y + 5}, {x: x - 15, y: y + 10}], palette, 3.2);
		drawFinger(context, [{x: x + 3, y: y + 3}, {x: x + 9, y: y + 7}, {x: x + 11, y: y + 12}], palette, 3.2);
	} else if (mode === 'type') {
		for (let i = 0; i < 4; i += 1) {
			const baseX = x + 1 + i * 3.2;
			drawFinger(context, [{x: baseX, y: y + 1}, {x: baseX + 3, y: y + 5}, {x: baseX + 5, y: y + 7 + 1.2 * Math.sin(wave + i)}], palette, 2.8);
		}
	} else {
		drawFinger(context, [{x: x - 3, y: y - 4}, {x: x - 5, y: y - 13}], palette, 3.2);
		drawFinger(context, [{x: x + 1, y: y - 4}, {x: x + 1, y: y - 15}], palette, 3.2);
		drawFinger(context, [{x: x + 5, y: y - 2}, {x: x + 8, y: y - 11}], palette, 3.1);
		drawFinger(context, [{x: x - 5, y: y + 3}, {x: x - 11, y: y + 7}], palette, 3.1);
	}
};

const drawHead = (context: CanvasRenderingContext2D, palette: Palette, xShift: number, yShift: number): void => {
	context.save();
	context.translate(xShift, yShift - 435);
	context.scale(1, 0.65);
	context.translate(0, 435);
	context.beginPath();
	// Side profile with a clear forehead, nose, chin, neck and back of skull.
	context.moveTo(5, -577);
	context.bezierCurveTo(-19, -577, -39, -559, -42, -536);
	context.bezierCurveTo(-46, -513, -37, -489, -23, -474);
	context.lineTo(-20, -456);
	context.quadraticCurveTo(-18, -443, -6, -438);
	context.lineTo(15, -435);
	context.lineTo(19, -450);
	context.lineTo(31, -456);
	context.quadraticCurveTo(35, -459, 29, -464);
	context.lineTo(23, -468);
	context.quadraticCurveTo(29, -484, 22, -500);
	context.quadraticCurveTo(17, -514, 20, -530);
	context.bezierCurveTo(23, -551, 18, -568, 5, -577);
	context.closePath();
	context.fillStyle = palette.fill;
	context.fill();
	context.strokeStyle = palette.rim;
	context.lineWidth = 1.55;
	context.stroke();
	context.restore();
};

const drawTorso = (context: CanvasRenderingContext2D, palette: Palette, xShift: number, yShift: number, frame: number): void => {
	context.save();
	context.translate(xShift, yShift);
	context.beginPath();
	context.moveTo(-17, -432);
	context.quadraticCurveTo(-46, -428, -61, -405);
	context.quadraticCurveTo(-72, -388, -77, -355);
	context.lineTo(-83, -288);
	context.quadraticCurveTo(-84, -268, -68, -258);
	context.quadraticCurveTo(-54, -250, -37, -247);
	context.lineTo(-33, -218);
	context.quadraticCurveTo(-25, -204, 1, -203);
	context.quadraticCurveTo(29, -202, 43, -215);
	context.lineTo(47, -250);
	context.quadraticCurveTo(67, -259, 73, -274);
	context.lineTo(62, -360);
	context.quadraticCurveTo(59, -403, 39, -420);
	context.quadraticCurveTo(26, -431, 14, -432);
	context.closePath();
	context.fillStyle = palette.fill;
	context.fill();
	context.strokeStyle = palette.rim;
	context.lineWidth = 1.65;
	context.stroke();

	// Quiet shirt and trouser seams help the shape read as a clothed adult.
	context.save();
	context.globalAlpha *= 0.34;
	context.strokeStyle = palette.seam;
	context.lineWidth = 1.05;
	context.beginPath();
	context.moveTo(-47, -398);
	context.quadraticCurveTo(-27, -377, -8, -373);
	context.moveTo(35, -390);
	context.quadraticCurveTo(40, -333, 40, -276);
	context.moveTo(-39, -248);
	context.quadraticCurveTo(0, -240, 43, -251);
	context.stroke();
	context.globalAlpha *= 0.55 + 0.08 * Math.sin(frame * 0.019);
	context.restore();
	context.restore();
};

const drawLeg = (context: CanvasRenderingContext2D, hip: Point, knee: Point, ankle: Point, palette: Palette, width: number): void => {
	const upper = (ctx: CanvasRenderingContext2D): void => {
		ctx.moveTo(hip.x, hip.y);
		ctx.quadraticCurveTo((hip.x + knee.x) / 2 - 1, (hip.y + knee.y) / 2 + 3, knee.x, knee.y);
	};
	const lower = (ctx: CanvasRenderingContext2D): void => {
		ctx.moveTo(knee.x, knee.y);
		ctx.quadraticCurveTo(knee.x + (ankle.x - knee.x) * 0.55, knee.y + (ankle.y - knee.y) * 0.48, ankle.x, ankle.y);
	};
	strokePath(context, upper, palette.rim, width + 2);
	strokePath(context, upper, palette.fill, width);
	strokePath(context, lower, palette.rim, width * 0.79 + 2);
	strokePath(context, lower, palette.fill, width * 0.79);
	context.save();
	context.globalAlpha *= 0.32;
	strokePath(context, lower, palette.seam, 0.9);
	context.restore();
};

const drawShoe = (context: CanvasRenderingContext2D, ankle: Point, palette: Palette, length: number): void => {
	context.beginPath();
	context.moveTo(ankle.x - 11, ankle.y - 8);
	context.quadraticCurveTo(ankle.x - 5, ankle.y - 15, ankle.x + 3, ankle.y - 12);
	context.lineTo(ankle.x + length * 0.48, ankle.y - 5);
	context.quadraticCurveTo(ankle.x + length, ankle.y - 3, ankle.x + length, ankle.y + 3);
	context.quadraticCurveTo(ankle.x + length * 0.9, ankle.y + 8, ankle.x + 8, ankle.y + 7);
	context.quadraticCurveTo(ankle.x - 10, ankle.y + 6, ankle.x - 11, ankle.y - 8);
	context.closePath();
	context.fillStyle = palette.fill;
	context.fill();
	context.strokeStyle = palette.rim;
	context.lineWidth = 1.15;
	context.stroke();
};

const drawHuman = (context: CanvasRenderingContext2D, frame: number, options: FigureOptions): void => {
	const baseline = options.baseline ?? FLOOR;
	const scale = (options.scale ?? 1) * 1.2; // Larger mobile-readable human silhouette; targets remain in world coordinates.
	const palette = options.palette;
	const sit = clamp(options.sit ?? 0);
	const walk = clamp(options.walk ?? 0);
	const wave = Math.sin(frame * 0.075);
	const breathing = 1.4 * Math.sin(frame * 0.026) + walk * 1.3 * Math.sin((options.walkPhase ?? frame * 0.035) * 2);
	const sx = 13 * sit + 1.7 * Math.sin(frame * 0.015);
	const sy = 24 * sit - breathing;

	context.save();
	context.translate(options.x, baseline);
	context.scale(scale, scale);
	context.globalAlpha *= (options.alpha ?? 1) * palette.alpha;
	context.lineCap = 'round';
	context.lineJoin = 'round';

	const walkPhase = options.walkPhase ?? frame * 0.035;
	const leftSwing = Math.sin(walkPhase);
	const rightSwing = Math.sin(walkPhase + Math.PI);
	const hipY = -211 + sy * 0.24;
	const leftHip = {x: -22 + sx, y: hipY};
	const rightHip = {x: 23 + sx, y: hipY + 1};
	const standLeftKnee = {x: -34 + sx + leftSwing * walk * 10, y: -116 + sy * 0.1};
	const standRightKnee = {x: 31 + sx + rightSwing * walk * 10, y: -117 + sy * 0.1};
	const sitLeftKnee = {x: -92 + sx, y: -184 + sy * 0.35};
	const sitRightKnee = {x: 103 + sx, y: -181 + sy * 0.35};
	const leftKnee = {x: lerp(standLeftKnee.x, sitLeftKnee.x, sit), y: lerp(standLeftKnee.y, sitLeftKnee.y, sit)};
	const rightKnee = {x: lerp(standRightKnee.x, sitRightKnee.x, sit), y: lerp(standRightKnee.y, sitRightKnee.y, sit)};
	const leftAnkle = {
		x: lerp(-38 + sx + leftSwing * walk * 16, -92 + sx, sit),
		y: lerp(-12 - Math.max(0, Math.cos(walkPhase)) * walk * 13, -10, sit),
	};
	const rightAnkle = {
		x: lerp(23 + sx + rightSwing * walk * 16, 126 + sx, sit),
		y: lerp(-12 - Math.max(0, Math.cos(walkPhase + Math.PI)) * walk * 13, -10, sit),
	};

	// Legs are drawn first so the torso overlaps them naturally at the hips.
	drawLeg(context, leftHip, leftKnee, leftAnkle, palette, 34);
	drawLeg(context, rightHip, rightKnee, rightAnkle, palette, 35);
	drawShoe(context, leftAnkle, palette, 28);
	drawShoe(context, rightAnkle, palette, 30);

	const leftShoulder = {x: -51 + sx, y: -391 + sy};
	const rightShoulder = {x: 45 + sx, y: -389 + sy};
	const typeAmt = clamp(options.typing ?? 0);
	const raiseAmt = clamp(options.raise ?? 0);
	const heartAmt = clamp(options.heart ?? 0);
	const reachAmt = clamp(options.reach ?? 0);
	const rawWeights = [1 - typeAmt - raiseAmt - heartAmt - reachAmt, typeAmt, raiseAmt, heartAmt, reachAmt].map((v) => Math.max(0, v));
	const weightSum = rawWeights.reduce((a, b) => a + b, 0) || 1;
	const [restW, typeW, raiseW, heartW, reachW] = rawWeights.map((v) => v / weightSum);
	const targetLocalX = ((options.reachWorldX ?? options.x + 118) - options.x) / scale;
	const targetLocalY = ((options.reachWorldY ?? baseline - 320) - baseline) / scale;
	const reachElbow = {x: targetLocalX - 66, y: targetLocalY - 31 + sy};
	const armPos = (part: 'elbow' | 'wrist'): Point => {
		const choices = part === 'elbow'
			? [
				{x: 72 + sx, y: -289 + sy},
				{x: 86 + sx, y: -250 + sy},
				{x: 80 + sx, y: -444 + sy + 18 * (1 - raiseAmt)},
				{x: 57 + sx, y: -326 + sy},
				reachElbow,
			]
			: [
				{x: 76 + sx, y: -211 + sy},
				{x: 139 + sx + 2 * Math.sin(frame * 0.11), y: -226 + sy + 2 * Math.sin(frame * 0.12)},
				{x: 94 + sx + 4 * wave, y: -505 + sy + 15 * (1 - raiseAmt)},
				{x: 12 + sx, y: -344 + sy},
				{x: targetLocalX, y: targetLocalY},
			];
		return choices.reduce((sum, point, index) => ({x: sum.x + point.x * [restW, typeW, raiseW, heartW, reachW][index], y: sum.y + point.y * [restW, typeW, raiseW, heartW, reachW][index]}), {x: 0, y: 0});
	};
	const rightElbow = armPos('elbow');
	const rightWrist = armPos('wrist');
	const limbPalette = options.armRim && reachW > 0 ? {...palette, rim: options.armRim} : palette;
	const leftChoices = [
		{elbow: {x: -72 + sx, y: -278 + sy}, wrist: {x: -72 + sx, y: -210 + sy}},
		{elbow: {x: 12 + sx, y: -257 + sy}, wrist: {x: 87 + sx + Math.sin(frame * 0.12), y: -227 + sy}},
		{elbow: {x: -73 + sx, y: -280 + sy}, wrist: {x: -69 + sx, y: -211 + sy}},
		{elbow: {x: -30 + sx, y: -327 + sy}, wrist: {x: -7 + sx, y: -344 + sy}},
		{elbow: {x: -73 + sx, y: -280 + sy}, wrist: {x: -69 + sx, y: -211 + sy}},
	];
	const leftElbow = leftChoices.reduce((sum, pose, i) => ({x: sum.x + pose.elbow.x * [restW, typeW, raiseW, heartW, reachW][i], y: sum.y + pose.elbow.y * [restW, typeW, raiseW, heartW, reachW][i]}), {x: 0, y: 0});
	const leftWrist = leftChoices.reduce((sum, pose, i) => ({x: sum.x + pose.wrist.x * [restW, typeW, raiseW, heartW, reachW][i], y: sum.y + pose.wrist.y * [restW, typeW, raiseW, heartW, reachW][i]}), {x: 0, y: 0});

	// Far arm, torso, head, then near arm create a single clothed human silhouette.
	drawLimb(context, leftShoulder, leftElbow, leftWrist, palette, 25);
	drawHand(context, leftWrist.x, leftWrist.y, heartW > 0.48 ? 'heart' : typeW > 0.45 ? 'type' : 'rest', palette, wave);
	drawTorso(context, palette, sx, sy, frame);
	context.save();
	context.fillStyle = palette.fill;
	context.strokeStyle = palette.rim;
	context.lineWidth = 1.1;
	context.beginPath();
	context.moveTo(-16 + sx, -445 + sy);
	context.lineTo(-15 + sx, -419 + sy);
	context.quadraticCurveTo(0 + sx, -405 + sy, 22 + sx, -420 + sy);
	context.lineTo(17 + sx, -451 + sy);
	context.closePath();
	context.fill();
	context.stroke();
	context.restore();
	drawHead(context, palette, sx, sy);
	if (raiseW > 0.12 || typeW > 0.4 || heartW > 0.35 || reachW > 0.25) {
		const mode = raiseW > 0.38 ? 'raise' : heartW > 0.38 ? 'heart' : reachW > 0.25 ? 'reach' : typeW > 0.4 ? 'type' : 'rest';
		drawLimb(context, rightShoulder, rightElbow, rightWrist, limbPalette, 26);
		drawHand(context, rightWrist.x, rightWrist.y, mode, limbPalette, wave);
	} else {
		drawLimb(context, rightShoulder, rightElbow, rightWrist, limbPalette, 26);
		drawHand(context, rightWrist.x, rightWrist.y, 'rest', limbPalette, wave);
	}

	if ((options.eye ?? 0) > 0.001) {
		const eyeAlpha = clamp(options.eye ?? 0);
		context.save();
		context.globalAlpha *= eyeAlpha;
		context.fillStyle = 'rgba(31,221,228,0.22)';
		context.beginPath();
		context.arc(10 + sx, -490 + sy, 7.5, 0, TAU);
		context.fill();
		context.fillStyle = '#38E2E7';
		context.beginPath();
		context.arc(10 + sx, -490 + sy, 3, 0, TAU);
		context.fill();
		context.restore();
	}
	context.restore();
};

const drawDecisionNode = (context: CanvasRenderingContext2D, frame: number): void => {
 if(frame<2700 || frame>=4260) return;
 const alpha=clamp((frame-2700)/90)*(1-clamp((frame-4140)/120));
 context.save();context.globalAlpha=alpha;
 context.beginPath();context.roundRect(735,862,165,80,8);
 context.fillStyle=frame<3900?'#182124':'#E8BB70';context.fill();
 context.strokeStyle=frame<3900?'#63AAB4':'#E8BB70';context.lineWidth=2;context.stroke();
 context.font='600 39px EPSerif';context.textAlign='center';context.textBaseline='alphabetic';
 context.fillStyle=frame<3900?'#F4E7D0':'#151718';context.fillText(frame<3900?'确认':'已生效',817.5,915);
 context.restore();
};

const drawDecisionImpulse = (context: CanvasRenderingContext2D, frame: number): void => {
	if (frame < 3900 || frame > 4180) return;
	const age = frame - 3900;
	const fade = 1 - smooth(0, 150, age);
	context.save();
	context.globalAlpha = 0.82 * fade;
	context.strokeStyle = '#E4C169';
	context.lineWidth = 1.6;
	context.beginPath();
	context.arc(NODE.x, NODE.y, 13 + 46 * smooth(0, 110, age), 0, TAU);
	context.stroke();
	context.globalAlpha *= 0.65;
	context.lineWidth = 1;
	context.beginPath();
	context.arc(NODE.x, NODE.y, 3 + 28 * smooth(0, 76, age), 0, TAU);
	context.stroke();
	context.restore();
};

const drawRoleExchange = (context: CanvasRenderingContext2D, frame: number, heroX: number, shadowX: number, swap: number, approach: number): void => {
	const oldAlpha = lerp(1, 0.82, swap);
	const oldScale = lerp(1, 0.8, swap);
	const oldPalette = {
		fill: mixHex(PAPER.fill, DEEP_SHADOW.fill, swap),
		rim: mixHex(PAPER.rim, DEEP_SHADOW.rim, swap),
		seam: mixHex(PAPER.seam, DEEP_SHADOW.seam, swap),
		alpha: lerp(1, DEEP_SHADOW.alpha, swap),
	};
	drawFloorPool(context, heroX, 96, 'rgba(17,61,67,0.76)', 0.48 + swap * 0.18);
	drawHuman(context, frame, {
		x: lerp(heroX, 420, swap),
		baseline: lerp(FLOOR, FLOOR + 5, swap),
		scale: oldScale,
		alpha: oldAlpha,
		walk: 0.05 * swap,
		walkPhase: frame * 0.018,
		reach: 1 - smooth(3960, 4140, frame),
		reachWorldX: heroX + 205,
		reachWorldY: NODE.y,
		palette: oldPalette,
	});

	const arrive = smooth(3920, 4300, frame);
	const finalX = lerp(shadowX, 620, arrive);
	const finalScale = lerp(1.15 + approach * 0.05, 1.025, arrive);
	const goldAmount = smooth(3960, 4470, frame);
	const palette = {
		fill: mixHex(learnedPalette(frame).fill, GOLD.fill, goldAmount),
		rim: mixHex(learnedPalette(frame).rim, GOLD.rim, goldAmount),
		seam: mixHex(learnedPalette(frame).seam, GOLD.seam, goldAmount),
		alpha: 1,
	};
	drawFloorPool(context, finalX, 104 * finalScale, 'rgba(39,54,43,0.85)', 0.38);
	drawHuman(context, frame, {
		x: finalX,
		baseline: FLOOR,
		scale: finalScale,
		alpha: lerp(0.97 * SHADOW.alpha, 1, goldAmount),
		heart: 0.14 * (1 - arrive),
		reach: 1 - smooth(3990, 4180, frame),
		reachWorldX: NODE.x - 21 * finalScale,
		reachWorldY: NODE.y,
		walk: 0.12 + 0.56 * smooth(4530, 4740, frame),
		walkPhase: frame * 0.033,
		palette,
		eye: smooth(5010, 5160, frame),
	});
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
	drawDecisionNode(context, f); // Panel is behind the hands, so contact is visible.

	const sit = smooth(520, 690, f) * (1 - smooth(1370, 1590, f));
	const deskAlpha = smooth(535, 675, f) * (1 - smooth(1370, 1530, f));
	const approach = smooth(2500, 3240, f);
	const heroX = lerp(330, 450, approach);
	const projectedOffset = lerp(240, 205, smooth(500, 760, f));
	const nearOffset = lerp(projectedOffset, 150, smooth(2500, 2800, f));
	const detach = smooth(3300, 3900, f);
	const shadowX = heroX + nearOffset + 22 * detach;
	const transition = smooth(3960, 4500, f);
	const finalMovement = smooth(4530, 5400, f);
	const postHeroX = lerp(shadowX, 620 + 92 * finalMovement, smooth(4300, 4530, f));
	const echoLead = 18 * (1 - smooth(2280, 2580, f));
	const echoFrame = f + echoLead;
	const typing = deskAlpha;
	const raised = smooth(180, 330, f) * (1 - smooth(570, 690, f)) * (0.94 + 0.035 * Math.sin(f * 0.018));
	const heart = smooth(1570, 1840, f) * (1 - smooth(2420, 2610, f));
	const echoHeart = smooth(1570, 1840, echoFrame) * (1 - smooth(2420, 2610, echoFrame));
	const humanReach = smooth(3220, 3600, f) * (1 - smooth(3970, 4140, f));
	const shadowReach = smooth(3660, 3900, f) * (1 - smooth(3990, 4180, f));
	const stageReach = clamp(shadowReach);
	const projectionAlpha = 1 - smooth(3310, 3780, f);

	if (deskAlpha > 0.002) drawDesk(context, heroX, deskAlpha, f);
	if (f < 3960) drawShadowLink(context, heroX, shadowX, projectionAlpha * (1 - transition));
	if (f >= 3960) drawFloorPool(context, heroX, 92, 'rgba(20,61,66,0.86)', 0.53);

	if (f < 3960) {
		const shadowSit = smooth(520, 690, echoFrame) * (1 - smooth(1370, 1590, echoFrame));
		const shadowTyping = smooth(535, 675, echoFrame) * (1 - smooth(1370, 1530, echoFrame));
		const shadowHeartAmt = echoHeart * (1 - approach * 0.9);
		const shadowRaise = smooth(120, 270, f) * (1 - smooth(570, 690, echoFrame)) * (0.94 + 0.035 * Math.sin(echoFrame * 0.018));
		const shadowScale = lerp(1.12, 1.2, approach);
		drawFloorPool(context, shadowX, 89 * shadowScale, 'rgba(6,42,47,0.86)', 0.74);
		drawHuman(context, echoFrame, {
			x: shadowX,
			baseline: FLOOR - 1,
			scale: shadowScale,
			alpha: 0.97,
			sit: shadowSit,
			raise: shadowRaise,
			typing: shadowTyping,
			heart: shadowHeartAmt,
			reach: stageReach,
			reachWorldX: NODE.x - 21 * shadowScale,
			reachWorldY: NODE.y,
			walk: 0.08 + detach * 0.36,
			walkPhase: echoFrame * 0.036,
			palette: learnedPalette(f),
			armRim: f >= 3660 ? '#63BDC8' : undefined,
		});
	}

	if (f < 3960) {
		drawHuman(context, f, {
			x: heroX,
			baseline: FLOOR,
			scale: 1,
			sit,
			raise: raised,
			typing,
			heart: heart * (1 - approach),
			reach: humanReach,
			reachWorldX: Math.min(678, heroX + 205),
			reachWorldY: NODE.y,
			walk: approach * 0.16,
			walkPhase: f * 0.022,
			palette: PAPER,
		});
	}

	if (deskAlpha > 0.002) drawDeletedFragments(context, f, heroX, shadowX, deskAlpha);

	if (f >= 3960 && f < 4500) {
		drawRoleExchange(context, f, heroX, postHeroX, transition, approach);
	} else if (f < 3960) {
		drawFloorPool(context, heroX, 86, 'rgba(94,70,43,0.75)', 0.3);
	}

	// After the exchange the warm figure keeps moving while the former person stays as a cool shadow.
	if (f >= 4500) {
		const forwardX = 620 + 92 * finalMovement;
		drawFloorPool(context, 420 + 8 * smooth(4530, 5400, f), 80, 'rgba(9,43,48,0.85)', 0.72);
		drawHuman(context, f, {
			x: 420 + 8 * smooth(4530, 5400, f),
			baseline: FLOOR + 5,
			scale: 0.8,
			alpha: 0.82,
			walk: 0.05,
			walkPhase: f * 0.018,
			palette: DEEP_SHADOW,
		});
		drawFloorPool(context, forwardX, 106, 'rgba(39,54,43,0.86)', 0.45);
		drawHuman(context, f, {
			x: forwardX,
			baseline: FLOOR,
			scale: 1.025 + 0.015 * finalMovement,
			alpha: 1,
			walk: 0.12 + 0.58 * finalMovement,
			walkPhase: f * 0.033,
			palette: GOLD,
			eye: smooth(5010, 5160, f),
		});
	}

	drawDecisionImpulse(context, f);

	const fade = 1 - smooth(5320, 5400, f);
	if (fade < 0.999) {
		context.save();
		context.globalAlpha = fade;
		context.fillStyle = '#111211';
		context.globalCompositeOperation = 'destination-over';
		context.fillRect(0, 0, WIDTH, HEIGHT);
		context.restore();
		// A foreground veil fades the complete painted scene, including its paper texture.
		context.save();
		context.globalAlpha = 1 - fade;
		context.globalCompositeOperation = 'source-over';
		context.fillStyle = '#111211';
		context.fillRect(0, 0, WIDTH, HEIGHT);
		context.restore();
	}
};

export const Scene: React.FC<{frame: number}> = ({frame}) => {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useLayoutEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const handle = delayRender(`EP18 v04 human-shadow scene frame ${frame}`);
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
				if (!context) throw new Error('Could not acquire the EP18 v04 2D canvas context.');
				drawScene(context, frame);
				// Canvas drawing is synchronous; release only after every scene primitive is painted.
				release();
			})
			.catch(fail);

		return () => {
			cancelled = true;
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
