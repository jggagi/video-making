import React, { useLayoutEffect, useRef } from 'react';
import {
  CHOICE_BRANCH_COUNT,
  CHOSEN_BRANCH,
  GEODESIC_MESH,
  authoredChoicePath,
  clamp,
  clamp01,
  choicePotential,
  computeShieldRay,
  integrateChoicePath,
  lorenzTracePoint,
  laplaceQuantile,
  lorenzDelayCoordinates,
  mix,
  readinessPotentialMicrovolts,
  rotatePoint3,
  seededUnit,
  smoothstep,
  syntheticReconstructionCoordinates,
  syntheticTrajectoryResidualPercent,
  type Vec2,
  type Vec3,
} from './math';

type Props = { frame: number; portrait: boolean; width: number; height: number };
type Ctx = CanvasRenderingContext2D;
type Box = { x: number; y: number; w: number; h: number };

const VOID = '#050811';
const AMBER = '#f59e0b';
const CYAN = '#06b6d4';
const MAGENTA = '#d946ef';
const RED = '#ef4444';
const GOLD = '#facc15';
const WHITE = '#ffffff';
const MUTED = '#9aaabd';
const GRID = '#102031';

const CONTENT_LANDSCAPE: Box = { x: 74, y: 280, w: 1772, h: 590 };
const CONTENT_PORTRAIT: Box = { x: 64, y: 480, w: 838, h: 780 };

function setFont(ctx: Ctx, size: number, bold = false): void {
  ctx.font = `${bold ? '600' : '400'} ${size}px Arial, "PingFang SC", "Noto Sans CJK SC", sans-serif`;
}

function label(
  ctx: Ctx,
  value: string,
  x: number,
  y: number,
  size: number,
  color = WHITE,
  align: CanvasTextAlign = 'left',
  bold = false,
): void {
  ctx.save();
  setFont(ctx, size, bold);
  ctx.textAlign = align;
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = color;
  ctx.fillText(value, x, y);
  ctx.restore();
}

function line(ctx: Ctx, x1: number, y1: number, x2: number, y2: number, color: string, width = 2): void {
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

function glowDot(ctx: Ctx, x: number, y: number, radius: number, color: string, alpha = 1): void {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.shadowColor = color;
  ctx.shadowBlur = radius * 4;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawBackground(ctx: Ctx, width: number, height: number, frame: number): void {
  ctx.fillStyle = VOID;
  ctx.fillRect(0, 0, width, height);
  const glow = ctx.createRadialGradient(width * 0.52, height * 0.46, 10, width * 0.52, height * 0.46, Math.max(width, height) * 0.8);
  glow.addColorStop(0, 'rgba(9, 27, 42, 0.48)');
  glow.addColorStop(0.58, 'rgba(7, 17, 30, 0.18)');
  glow.addColorStop(1, 'rgba(5, 8, 17, 0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.strokeStyle = GRID;
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.32;
  const offsetX = (frame * 0.24) % 72;
  const offsetY = (frame * 0.16) % 64;
  for (let x = -72 + offsetX; x < width + 72; x += 72) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
  }
  for (let y = -64 + offsetY; y < height + 64; y += 64) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
  }
  ctx.restore();
}

function drawContentPlate(ctx: Ctx, width: number, height: number, accent: string): void {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, 'rgba(8, 18, 31, 0.90)');
  gradient.addColorStop(0.52, 'rgba(7, 14, 25, 0.76)');
  gradient.addColorStop(1, 'rgba(5, 10, 20, 0.92)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = 'rgba(89, 126, 151, 0.34)';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(0.75, 0.75, width - 1.5, height - 1.5);
  ctx.fillStyle = accent;
  ctx.globalAlpha = 0.78;
  ctx.fillRect(0, 0, Math.min(width * 0.14, 220), 3);
  ctx.globalAlpha = 1;
}

function cubicPoint(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2, t: number): Vec2 {
  const u = 1 - t;
  return {
    x: u ** 3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t ** 3 * p3.x,
    y: u ** 3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t ** 3 * p3.y,
  };
}

function choicePathPoint(progress: number, width: number, height: number): Vec2 {
  const p0 = { x: width * 0.20, y: height * 0.72 };
  const p1 = { x: width * 0.34, y: height * 0.18 };
  const p2 = { x: width * 0.57, y: height * 0.24 };
  const p3 = { x: width * 0.70, y: height * 0.50 };
  const p4 = { x: width * 0.80, y: height * 0.78 };
  const q = clamp01(progress);
  return q < 0.64
    ? cubicPoint(p0, p1, p2, p3, q / 0.64)
    : cubicPoint(p3, { x: width * 0.77, y: height * 0.58 }, { x: width * 0.82, y: height * 0.60 }, p4, (q - 0.64) / 0.36);
}

function drawCoffeeMug(ctx: Ctx, width: number, height: number, frame: number): void {
  const x = width * 0.80;
  const y = height * 0.51;
  const mugW = Math.min(width * 0.105, height * 0.72);
  const mugH = height * 0.51;
  ctx.save();
  const mugGlow = ctx.createRadialGradient(x, y, 1, x, y, mugW * 1.4);
  mugGlow.addColorStop(0, 'rgba(245, 158, 11, 0.18)');
  mugGlow.addColorStop(1, 'rgba(245, 158, 11, 0)');
  ctx.fillStyle = mugGlow;
  ctx.fillRect(x - mugW * 1.4, y - mugH, mugW * 2.8, mugH * 2.1);
  ctx.fillStyle = 'rgba(242, 231, 209, 0.10)';
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.82)';
  ctx.lineWidth = Math.max(2, height * 0.014);
  ctx.beginPath();
  ctx.moveTo(x - mugW * 0.5, y - mugH * 0.34);
  ctx.lineTo(x - mugW * 0.42, y + mugH * 0.40);
  ctx.quadraticCurveTo(x, y + mugH * 0.53, x + mugW * 0.42, y + mugH * 0.40);
  ctx.lineTo(x + mugW * 0.5, y - mugH * 0.34);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.ellipse(x, y - mugH * 0.34, mugW * 0.5, mugH * 0.12, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.ellipse(x + mugW * 0.48, y + mugH * 0.02, mugW * 0.22, mugH * 0.22, 0, -Math.PI / 2, Math.PI / 2);
  ctx.stroke();
  ctx.strokeStyle = 'rgba(255, 224, 171, 0.6)';
  ctx.lineWidth = 2;
  for (let i = 0; i < 3; i += 1) {
    const steam = (frame * 0.009 + i * 0.31) % 1;
    const sx = x - mugW * 0.18 + i * mugW * 0.18;
    const rise = steam * height * 0.32;
    ctx.beginPath();
    ctx.moveTo(sx, y - mugH * 0.55 - rise);
    ctx.bezierCurveTo(sx - mugW * 0.18, y - mugH * 0.72 - rise, sx + mugW * 0.16, y - mugH * 0.85 - rise, sx, y - mugH - rise);
    ctx.stroke();
  }
  ctx.restore();
}

function drawHand(ctx: Ctx, width: number, height: number): void {
  const x = width * 0.03;
  const y = height * 0.84;
  ctx.save();
  ctx.lineWidth = Math.max(3, height * 0.024);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.76)';
  ctx.fillStyle = 'rgba(245, 158, 11, 0.12)';
  ctx.beginPath();
  ctx.moveTo(x, y + height * 0.14);
  ctx.quadraticCurveTo(x + width * 0.055, y - height * 0.04, x + width * 0.10, y - height * 0.12);
  ctx.lineTo(x + width * 0.16, y - height * 0.30);
  ctx.quadraticCurveTo(x + width * 0.17, y - height * 0.39, x + width * 0.20, y - height * 0.37);
  ctx.quadraticCurveTo(x + width * 0.22, y - height * 0.35, x + width * 0.21, y - height * 0.24);
  ctx.lineTo(x + width * 0.20, y - height * 0.14);
  ctx.lineTo(x + width * 0.22, y - height * 0.32);
  ctx.quadraticCurveTo(x + width * 0.23, y - height * 0.41, x + width * 0.26, y - height * 0.39);
  ctx.quadraticCurveTo(x + width * 0.28, y - height * 0.38, x + width * 0.27, y - height * 0.26);
  ctx.lineTo(x + width * 0.26, y - height * 0.10);
  ctx.quadraticCurveTo(x + width * 0.32, y - height * 0.20, x + width * 0.35, y - height * 0.15);
  ctx.lineTo(x + width * 0.44, y - height * 0.01);
  ctx.quadraticCurveTo(x + width * 0.50, y + height * 0.08, x + width * 0.45, y + height * 0.17);
  ctx.lineTo(x + width * 0.35, y + height * 0.30);
  ctx.quadraticCurveTo(x + width * 0.18, y + height * 0.34, x + width * 0.06, y + height * 0.28);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function drawPreEchoScene(ctx: Ctx, box: Box, frame: number, portrait: boolean): void {
  drawContentPlate(ctx, box.w, box.h, AMBER);
  const upperHeight = portrait ? 294 : 208;
  drawCoffeeMug(ctx, box.w, upperHeight, frame);
  drawHand(ctx, box.w, upperHeight);

  const amberProgress = ((frame % 780) / 780 + 1) % 1;
  const ghostProgress = ((frame + 30) % 780) / 780;
  ctx.save();
  ctx.beginPath();
  for (let i = 0; i <= 80; i += 1) {
    const point = choicePathPoint(i / 80, box.w, upperHeight);
    if (i === 0) ctx.moveTo(point.x, point.y); else ctx.lineTo(point.x, point.y);
  }
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.34)';
  ctx.lineWidth = portrait ? 3 : 2;
  ctx.setLineDash([9, 11]);
  ctx.stroke();
  ctx.setLineDash([]);

  const amber = choicePathPoint(amberProgress, box.w, upperHeight);
  const ghost = choicePathPoint(ghostProgress, box.w, upperHeight);
  ctx.beginPath();
  ctx.moveTo(amber.x, amber.y);
  ctx.quadraticCurveTo((amber.x + ghost.x) / 2, Math.min(amber.y, ghost.y) - upperHeight * 0.12, ghost.x, ghost.y);
  ctx.strokeStyle = 'rgba(6, 182, 212, 0.66)';
  ctx.lineWidth = portrait ? 3 : 2;
  ctx.stroke();
  glowDot(ctx, ghost.x, ghost.y, portrait ? 9 : 7, CYAN, 0.82);
  glowDot(ctx, amber.x, amber.y, portrait ? 11 : 8, AMBER, 1);
  for(const event of [{at:870,p:ghost,c:CYAN},{at:900,p:amber,c:AMBER}]){
    const age=frame-event.at;
    if(age>=0&&age<60){ctx.save();ctx.globalAlpha=1-age/60;ctx.strokeStyle=event.c;ctx.lineWidth=portrait?4:3;ctx.beginPath();ctx.arc(event.p.x,event.p.y,12+age*1.4,0,Math.PI*2);ctx.stroke();ctx.restore();}
  }

  ctx.beginPath();
  ctx.strokeStyle = 'rgba(255, 227, 173, 0.95)';
  ctx.lineWidth = portrait ? 3 : 2;
  ctx.arc(amber.x, amber.y, portrait ? 19 : 15, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();

  const chartY = upperHeight + 12;
  const chartH = box.h - chartY - 12;
  const left = portrait ? 82 : 90;
  const right = box.w - (portrait ? 36 : 48);
  const top = chartY + (portrait ? 67 : 47);
  const bottom = chartY + chartH - (portrait ? 76 : 58);
  const plotW = right - left;
  const plotH = bottom - top;
  const axisFont = portrait ? 30 : 21;
  label(ctx, 'READINESS POTENTIAL · SCHEMATIC SAMPLE', left, chartY + (portrait ? 41 : 34), portrait ? 30 : 22, WHITE, 'left', true);

  const xForMs = (milliseconds: number): number => left + ((milliseconds + 1000) / 1200) * plotW;
  const zeroY = bottom - 10;
  const yForUv = (microvolts: number): number => zeroY + microvolts * (plotH * 0.55 / 1.3);
  ctx.save();
  ctx.beginPath(); ctx.rect(left, top, plotW, plotH); ctx.clip();
  for (const tick of [-1000, -550, -200, 0, 200]) {
    const x = xForMs(tick);
    const special = tick === -550 ? AMBER : tick === -200 ? CYAN : tick === 0 ? RED : '#3a5266';
    ctx.strokeStyle = tick === -1000 || tick === 200 ? 'rgba(58, 82, 102, 0.34)' : `${special}88`;
    ctx.lineWidth = tick === -550 || tick === -200 || tick === 0 ? 2 : 1;
    ctx.setLineDash(tick === -550 || tick === -200 || tick === 0 ? [8, 8] : []);
    ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke();
  }
  ctx.setLineDash([]);
  for (const uv of [0, -0.5, -1.0]) {
    const y = yForUv(uv);
    ctx.strokeStyle = uv === 0 ? 'rgba(194, 211, 225, 0.56)' : 'rgba(80, 105, 126, 0.34)';
    ctx.lineWidth = uv === 0 ? 1.5 : 1;
    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
  }
  ctx.beginPath();
  ctx.lineWidth = portrait ? 5 : 4;
  ctx.strokeStyle = AMBER;
  ctx.shadowColor = AMBER;
  ctx.shadowBlur = 12;
  for (let i = 0; i <= 320; i += 1) {
    const ms = -1000 + (1200 * i) / 320;
    const y = yForUv(readinessPotentialMicrovolts(ms));
    if (i === 0) ctx.moveTo(xForMs(ms), y); else ctx.lineTo(xForMs(ms), y);
  }
  ctx.stroke();
  ctx.restore();

  label(ctx, '−1 μV', left - 8, yForUv(-1) + (portrait ? 10 : 8), axisFont, MUTED, 'right');
  label(ctx, '0', left - 8, zeroY + (portrait ? 10 : 8), axisFont, MUTED, 'right');
  label(ctx, '−1000', xForMs(-1000), bottom + (portrait ? 37 : 30), axisFont, WHITE, 'center');
  label(ctx, '−550', xForMs(-550), bottom + (portrait ? 37 : 30), axisFont, AMBER, 'center', true);
  const wLabelX = xForMs(-200);
  const wLabelY = top + (portrait ? 48 : 42);
  ctx.fillStyle = 'rgba(5, 8, 17, 0.92)';
  ctx.fillRect(wLabelX - (portrait ? 111 : 84), wLabelY - (portrait ? 33 : 26), portrait ? 222 : 168, portrait ? 43 : 34);
  label(ctx, 'W · −200 ms', wLabelX, wLabelY, axisFont, CYAN, 'center', true);
  label(ctx, 'M 0', xForMs(0), bottom + (portrait ? 37 : 30), axisFont, RED, 'center', true);
  label(ctx, '+200', right - 8, bottom + (portrait ? 37 : 30), axisFont, WHITE, 'right');
  label(ctx, 'μV · negative up', left + plotW * 0.25, top + (portrait ? 25 : 21), axisFont, MUTED, 'left');
}

function drawPrismTunnel(ctx: Ctx, width: number, height: number, frame: number): void {
  const cx = width * 0.5;
  const cy = height * 0.48;
  const phase = (frame - 1260) / 540;
  const pulse = 1 + 0.035 * Math.sin(phase * Math.PI * 8);
  const rings = 12;
  ctx.save();
  const haze = ctx.createRadialGradient(cx, cy, 20, cx, cy, Math.max(width, height) * 0.68);
  haze.addColorStop(0, 'rgba(6, 182, 212, 0.13)');
  haze.addColorStop(0.34, 'rgba(6, 182, 212, 0.035)');
  haze.addColorStop(1, 'rgba(5, 8, 17, 0)');
  ctx.fillStyle = haze;
  ctx.fillRect(0, 0, width, height);
  for (let ring = rings - 1; ring >= 0; ring -= 1) {
    const d = (ring + ((phase * 5) % 1)) / rings;
    const scale = (0.05 + d * d * 1.42) * pulse;
    const rx = width * 0.34 * scale;
    const ry = height * 0.31 * scale;
    const rotation = phase * 0.31 + ring * 0.08;
    ctx.beginPath();
    for (let side = 0; side <= 6; side += 1) {
      const angle = (side % 6) * Math.PI / 3 + rotation;
      const x = cx + Math.cos(angle) * rx;
      const y = cy + Math.sin(angle) * ry;
      if (side === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = ring % 3 === 0 ? 'rgba(6, 182, 212, 0.76)' : 'rgba(245, 158, 11, 0.42)';
    ctx.lineWidth = Math.max(1, 3.2 - d * 1.4);
    ctx.globalAlpha = 0.42 + d * 0.48;
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  const beams = 18;
  for (let i = 0; i < beams; i += 1) {
    const angle = (Math.PI * 2 * i) / beams + phase * 0.16;
    const edgeX = cx + Math.cos(angle) * width * 0.56;
    const edgeY = cy + Math.sin(angle) * height * 0.56;
    line(ctx, edgeX, edgeY, cx, cy, i % 3 === 0 ? 'rgba(6, 182, 212, 0.32)' : 'rgba(245, 158, 11, 0.18)', 1.4);
  }
  ctx.restore();
}

function drawPanel(ctx: Ctx, x: number, y: number, width: number, height: number, accent: string): void {
  const gradient = ctx.createLinearGradient(x, y, x + width, y + height);
  gradient.addColorStop(0, 'rgba(9, 21, 35, 0.90)');
  gradient.addColorStop(1, 'rgba(5, 10, 19, 0.88)');
  ctx.fillStyle = gradient;
  ctx.fillRect(x, y, width, height);
  ctx.strokeStyle = 'rgba(103, 137, 159, 0.42)';
  ctx.lineWidth = 1.3;
  ctx.strokeRect(x + 0.65, y + 0.65, width - 1.3, height - 1.3);
  ctx.fillStyle = accent;
  ctx.fillRect(x, y, Math.min(width * 0.18, 170), 3);
}

function normalizedLorenz(point: Vec3, frame: number, delayCoordinates = false): Vec3 {
  return rotatePoint3(
    delayCoordinates
      ? { x: point.x / 25, y: point.y / 25, z: point.z / 25 }
      : { x: point.x / 25, y: point.y / 32, z: (point.z - 25) / 30 },
    frame * 0.0019,
    0.28 + Math.sin(frame * 0.0012) * 0.18,
    frame * 0.0011,
  );
}

function projectAttractor(point: Vec3, cx: number, cy: number, scale: number): Vec2 {
  const perspective = 1.12 / (1.12 + point.z * 0.20);
  return { x: cx + point.x * scale * perspective, y: cy - point.y * scale * perspective };
}

function drawTelemetry(ctx: Ctx, x: number, y: number, width: number, height: number, frame: number, portrait: boolean): void {
  for (let i = 0; i < 14; i += 1) {
    const phase = ((frame * 0.004 + seededUnit(i, 41)) % 1 + 1) % 1;
    const side = i % 4;
    const start: Vec2 = side === 0 ? { x: x + phase * width, y }
      : side === 1 ? { x: x + width, y: y + phase * height }
        : side === 2 ? { x: x + (1 - phase) * width, y: y + height }
          : { x, y: y + (1 - phase) * height };
    const center = { x: x + width * 0.5, y: y + height * 0.48 };
    const t = 0.08 + phase * 0.2;
    ctx.save();
    ctx.globalAlpha = 0.16 + (1 - phase) * 0.34;
    ctx.strokeStyle = i % 5 === 0 ? AMBER : CYAN;
    ctx.lineWidth = portrait ? 2.5 : 1.8;
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.quadraticCurveTo(start.x + (center.x - start.x) * t, start.y + (center.y - start.y) * t, center.x, center.y);
    ctx.stroke();
    glowDot(ctx, start.x + (center.x - start.x) * phase, start.y + (center.y - start.y) * phase, portrait ? 3.8 : 3, i % 5 === 0 ? AMBER : CYAN, 0.86);
    ctx.restore();
  }
}

function drawGlassBox(ctx: Ctx, cx: number, cy: number, scale: number, frame: number, portrait: boolean): void {
  const vertices: Vec3[] = [];
  for (const z of [-0.78, 0.78]) {
    for (const y of [-0.78, 0.78]) {
      for (const x of [-0.78, 0.78]) vertices.push(normalizedLorenz({ x: x * 25, y: y * 32, z: 25 + z * 30 }, frame));
    }
  }
  const edges: [number, number][] = [];
  for (let i = 0; i < 8; i += 1) {
    for (let bit = 0; bit < 3; bit += 1) {
      const other = i ^ (1 << bit);
      if (i < other) edges.push([i, other]);
    }
  }
  ctx.save();
  ctx.strokeStyle = 'rgba(6, 182, 212, 0.34)';
  ctx.lineWidth = portrait ? 2 : 1.5;
  for (const [a, b] of edges) {
    const p1 = projectAttractor(vertices[a], cx, cy, scale * 1.16);
    const p2 = projectAttractor(vertices[b], cx, cy, scale * 1.16);
    line(ctx, p1.x, p1.y, p2.x, p2.y, ctx.strokeStyle, ctx.lineWidth);
  }
  ctx.restore();
}

function drawAttractorPanel(
  ctx: Ctx,
  x: number,
  y: number,
  width: number,
  height: number,
  frame: number,
  portrait: boolean,
  delayCoordinates: boolean,
): void {
  const color = delayCoordinates ? CYAN : AMBER;
  drawPanel(ctx, x, y, width, height, color);
  const font = portrait ? 30 : 22;
  const header = delayCoordinates ? 'DELAY EMBED  ·  τ = 24f' : 'LORENZ STATE  ·  RK4';
  label(ctx, header, x + (portrait ? 18 : 22), y + (portrait ? 39 : 34), font, color, 'left', true);
  if (delayCoordinates) {
    label(ctx, 'AMBER / CYAN', x + width - 18, y + (portrait ? 39 : 34), font, WHITE, 'right');
  }

  const chartTop = y + (portrait ? 58 : 50);
  const chartBottom = y + height - (portrait ? 65 : 52);
  const chartLeft = x + 18;
  const chartRight = x + width - 18;
  const cx = (chartLeft + chartRight) / 2;
  const cy = (chartTop + chartBottom) / 2;
  const scale = Math.min(chartRight - chartLeft, chartBottom - chartTop) * 0.41;
  drawTelemetry(ctx, chartLeft + 6, chartTop + 4, chartRight - chartLeft - 12, chartBottom - chartTop - 8, frame, portrait);
  if (delayCoordinates) drawGlassBox(ctx, cx, cy, scale, frame, portrait);

  const currentFrame = Math.max(LORENZ_MIN_FRAME, Math.floor(frame));
  const trailFrames = portrait ? 190 : 230;
  const start = Math.max(0, currentFrame - trailFrames);
  const drawTrace = (useDelay: boolean, reconstructed: boolean, traceColor: string, widthPx: number, alpha: number): Vec2 => {
    ctx.save();
    ctx.beginPath();
    for (let f = start; f <= currentFrame; f += 2) {
      const raw = useDelay
        ? (reconstructed ? syntheticReconstructionCoordinates(f, currentFrame) : lorenzDelayCoordinates(f))
        : lorenzTracePoint(f, false);
      const point = normalizedLorenz(raw, frame, useDelay);
      const projected = projectAttractor(point, cx, cy, scale);
      if (f === start) ctx.moveTo(projected.x, projected.y); else ctx.lineTo(projected.x, projected.y);
    }
    const finalRaw = useDelay
      ? (reconstructed ? syntheticReconstructionCoordinates(currentFrame, currentFrame) : lorenzDelayCoordinates(currentFrame))
      : lorenzTracePoint(currentFrame, false);
    const finalPoint = projectAttractor(normalizedLorenz(finalRaw, frame, useDelay), cx, cy, scale);
    ctx.strokeStyle = traceColor;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = widthPx;
    ctx.shadowColor = traceColor;
    ctx.shadowBlur = reconstructed ? 11 : 7;
    ctx.stroke();
    glowDot(ctx, finalPoint.x, finalPoint.y, portrait ? 6.5 : 5, traceColor, alpha);
    ctx.restore();
    return finalPoint;
  };

  if (delayCoordinates) {
    drawTrace(true, false, AMBER, portrait ? 4 : 3.2, 0.94);
    drawTrace(true, true, CYAN, portrait ? 3.2 : 2.7, 0.96);
  } else {
    drawTrace(false, false, AMBER, portrait ? 4 : 3.4, 0.97);
  }

  if (delayCoordinates) {
    const residual = syntheticTrajectoryResidualPercent(frame);
    const residualText = residual <= 0.001 ? '0.001%' : residual < 0.01 ? `${residual.toFixed(3)}%` : `${residual.toFixed(2)}%`;
    label(ctx, `SYNTHETIC ERROR  ${residualText}`, x + width - 18, y + height - (portrait ? 20 : 15), font, WHITE, 'right', true);
  } else {
    label(ctx, 'x(t) · y(t) · z(t)', x + width - 18, y + height - (portrait ? 20 : 15), font, MUTED, 'right');
  }
}

const LORENZ_MIN_FRAME = 0;

function drawLorenzScene(ctx: Ctx, box: Box, frame: number, portrait: boolean): void {
  drawContentPlate(ctx, box.w, box.h, CYAN);
  const gap = portrait ? 18 : 24;
  if (portrait) {
    const panelHeight = (box.h - gap) / 2;
    drawAttractorPanel(ctx, 0, 0, box.w, panelHeight, frame, true, false);
    drawAttractorPanel(ctx, 0, panelHeight + gap, box.w, panelHeight, frame, true, true);
  } else {
    const panelWidth = (box.w - gap) / 2;
    drawAttractorPanel(ctx, 0, 0, panelWidth, box.h, frame, false, false);
    drawAttractorPanel(ctx, panelWidth + gap, 0, panelWidth, box.h, frame, false, true);
  }
}

const PERCEIVED_PATHS = Array.from({ length: CHOICE_BRANCH_COUNT }, (_, branch) => authoredChoicePath(branch));
const NUDGED_PATHS = Array.from({ length: CHOICE_BRANCH_COUNT }, (_, branch) => integrateChoicePath(branch, true, 1));

function projectLandscapePoint(point: Vec2, potential: number, width: number, height: number): Vec2 {
  const scaleX = width * 0.071;
  const scaleZ = height * 0.059;
  const centerX = width * 0.5;
  const baseY = height * 0.82;
  return {
    x: centerX + (point.x + point.y * 0.17) * scaleX,
    y: baseY - (point.y + 3.75) * scaleZ - potential * height * 0.17,
  };
}

function blendPaths(a: Vec2[], b: Vec2[], amount: number): Vec2[] {
  const count = Math.min(a.length, b.length);
  return Array.from({ length: count }, (_, index) => ({
    x: mix(a[index].x, b[index].x, amount),
    y: mix(a[index].y, b[index].y, amount),
  }));
}

function drawLandscapeGrid(ctx: Ctx, width: number, height: number, hidden: boolean, nudge: number, portrait: boolean): void {
  const xSamples = 17;
  const zSamples = 9;
  ctx.save();
  ctx.lineWidth = portrait ? 2 : 1.5;
  for (let row = 0; row < zSamples; row += 1) {
    const z = 3.75 - (7.5 * row) / (zSamples - 1);
    ctx.beginPath();
    for (let col = 0; col < xSamples; col += 1) {
      const x = -5 + (10 * col) / (xSamples - 1);
      const point = projectLandscapePoint({ x, y: z }, choicePotential(x, z, hidden, nudge), width, height);
      if (col === 0) ctx.moveTo(point.x, point.y); else ctx.lineTo(point.x, point.y);
    }
    ctx.strokeStyle = hidden ? `rgba(6, 182, 212, ${0.20 + nudge * 0.16})` : 'rgba(6, 182, 212, 0.33)';
    ctx.stroke();
  }
  for (let col = 0; col < xSamples; col += 1) {
    const x = -5 + (10 * col) / (xSamples - 1);
    ctx.beginPath();
    for (let row = 0; row < zSamples; row += 1) {
      const z = 3.75 - (7.5 * row) / (zSamples - 1);
      const point = projectLandscapePoint({ x, y: z }, choicePotential(x, z, hidden, nudge), width, height);
      if (row === 0) ctx.moveTo(point.x, point.y); else ctx.lineTo(point.x, point.y);
    }
    ctx.strokeStyle = hidden ? 'rgba(217, 70, 239, 0.28)' : 'rgba(245, 158, 11, 0.24)';
    ctx.stroke();
  }
  ctx.restore();
}

function drawLandscapePanel(
  ctx: Ctx,
  x: number,
  y: number,
  width: number,
  height: number,
  hidden: boolean,
  nudge: number,
  frame: number,
  portrait: boolean,
): void {
  drawPanel(ctx, x, y, width, height, hidden ? MAGENTA : AMBER);
  const font = portrait ? 30 : 22;
  label(ctx, hidden ? 'HIDDEN FIELD  ·  DRIVEN FLOW' : 'PERCEIVED FIELD  ·  10 AUTHORED ROUTES', x + 18, y + (portrait ? 40 : 34), font, hidden ? MAGENTA : AMBER, 'left', true);
  ctx.save();
  ctx.beginPath();
  ctx.rect(x + 8, y + (portrait ? 54 : 46), width - 16, height - (portrait ? 62 : 54));
  ctx.clip();
  ctx.translate(x, y);
  drawLandscapeGrid(ctx, width, height, hidden, nudge, portrait);

  const reveal = smoothstep(nudge);
  const actProgress = clamp01((frame - 3600) / 1800);
  for (let branch = 0; branch < CHOICE_BRANCH_COUNT; branch += 1) {
    const path = blendPaths(PERCEIVED_PATHS[branch], NUDGED_PATHS[branch], reveal);
    const selected = branch === CHOSEN_BRANCH;
    const potentialColor = selected ? AMBER : hidden ? (branch % 2 === 0 ? RED : MAGENTA) : AMBER;
    ctx.beginPath();
    const animatedCount = Math.max(2, Math.floor(2 + actProgress * (path.length - 1)));
    for (let i = 0; i < animatedCount; i += 1) {
      const scenePoint = path[i];
      const sampledPotential = choicePotential(scenePoint.x, scenePoint.y, hidden, nudge);
      const point = projectLandscapePoint(scenePoint, sampledPotential, width, height);
      if (i === 0) ctx.moveTo(point.x, point.y); else ctx.lineTo(point.x, point.y);
    }
    ctx.globalAlpha = selected ? 0.96 : hidden ? 0.30 + 0.22 * (1 - reveal) : 0.54;
    ctx.strokeStyle = potentialColor;
    ctx.lineWidth = selected ? (portrait ? 5 : 4) : (portrait ? 2.5 : 2);
    if (hidden && !selected) ctx.setLineDash([7, 7]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    const endpoint = path[path.length - 1];
    const endpointP = projectLandscapePoint(endpoint, choicePotential(endpoint.x, endpoint.y, hidden, nudge), width, height);
    glowDot(ctx, endpointP.x, endpointP.y, selected ? (portrait ? 7 : 6) : (portrait ? 4 : 3), potentialColor, selected ? 0.95 : (hidden ? 0.45 : 0.7));

    if (selected) {
      const particleIndex = Math.min(path.length - 1, Math.floor(actProgress * (path.length - 1)));
      const particle = path[particleIndex];
      const projected = projectLandscapePoint(particle, choicePotential(particle.x, particle.y, hidden, nudge), width, height);
      glowDot(ctx, projected.x, projected.y, portrait ? 10 : 8, AMBER, 1);
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
      ctx.lineWidth = 2;
      ctx.arc(projected.x, projected.y, portrait ? 18 : 14, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  if (hidden) {
    const chosen = NUDGED_PATHS[CHOSEN_BRANCH][NUDGED_PATHS[CHOSEN_BRANCH].length - 1];
    const basin = projectLandscapePoint(chosen, choicePotential(chosen.x, chosen.y, true, nudge), width, height);
    ctx.save();
    ctx.globalAlpha = 0.35 + reveal * 0.6;
    const basinGlow = ctx.createRadialGradient(basin.x, basin.y, 2, basin.x, basin.y, portrait ? 62 : 48);
    basinGlow.addColorStop(0, 'rgba(217, 70, 239, 0.40)');
    basinGlow.addColorStop(1, 'rgba(217, 70, 239, 0)');
    ctx.fillStyle = basinGlow;
    ctx.fillRect(basin.x - 64, basin.y - 64, 128, 128);
    ctx.restore();
  }
  ctx.restore();
}

function drawChoiceScene(ctx: Ctx, box: Box, frame: number, portrait: boolean): void {
  drawContentPlate(ctx, box.w, box.h, MAGENTA);
  const nudge = clamp01((frame - 3600) / 1800);
  const gap = portrait ? 18 : 24;
  if (portrait) {
    const panelHeight = (box.h - gap) / 2;
    drawLandscapePanel(ctx, 0, 0, box.w, panelHeight, false, 0, frame, true);
    drawLandscapePanel(ctx, 0, panelHeight + gap, box.w, panelHeight, true, nudge, frame, true);
  } else {
    const panelWidth = (box.w - gap) / 2;
    drawLandscapePanel(ctx, 0, 0, panelWidth, box.h, false, 0, frame, false);
    drawLandscapePanel(ctx, panelWidth + gap, 0, panelWidth, box.h, true, nudge, frame, false);
  }
}

function projectShieldPoint(point: Vec3, cx: number, cy: number, scale: number, frame: number): Vec2 {
  const rotated = rotatePoint3(point, frame * 0.003, 0.30 + Math.sin(frame * 0.0015) * 0.18, frame * 0.0014);
  const perspective = 1.8 / (1.8 + rotated.z * 0.12);
  return { x: cx + rotated.x * scale * perspective, y: cy - rotated.y * scale * perspective };
}

function drawShieldRay(ctx: Ctx, index: number, frame: number, cx: number, cy: number, scale: number, closed: boolean, portrait: boolean): void {
  const ray = computeShieldRay(index);
  if (!ray.hit || !ray.tangent || !ray.exit) return;
  const source = projectShieldPoint(ray.origin, cx, cy, scale, frame);
  const hit = projectShieldPoint(ray.hit, cx, cy, scale, frame);
  const phase = ((frame / 154 + seededUnit(index, 23)) % 1 + 1) % 1;
  ctx.save();
  ctx.globalAlpha = 0.16 + (closed ? 0.1 : 0.17) * Math.sin(frame * 0.025 + index);
  line(ctx, source.x, source.y, hit.x, hit.y, index % 5 === 0 ? RED : CYAN, portrait ? 2 : 1.5);
  ctx.restore();

  let particle: Vec2;
  if (closed) {
    const travel = phase < 0.64 ? phase / 0.64 : (phase - 0.64) / 0.36;
    if (phase < 0.64) {
      particle = { x: mix(source.x, hit.x, travel), y: mix(source.y, hit.y, travel) };
    } else {
      const arcIndex = Math.min(ray.arc.length - 1, Math.floor(travel * (ray.arc.length - 1)));
      particle = projectShieldPoint(ray.arc[arcIndex], cx, cy, scale, frame);
    }
  } else {
    particle = { x: mix(source.x, hit.x, phase), y: mix(source.y, hit.y, phase) };
  }
  glowDot(ctx, particle.x, particle.y, portrait ? 4.2 : 3.4, closed && phase >= 0.64 ? GOLD : CYAN, 0.9);

  if (closed) {
    ctx.save();
    ctx.beginPath();
    for (let i = 0; i < ray.arc.length; i += 1) {
      const point = projectShieldPoint(ray.arc[i], cx, cy, scale, frame);
      if (i === 0) ctx.moveTo(point.x, point.y); else ctx.lineTo(point.x, point.y);
    }
    ctx.strokeStyle = 'rgba(250, 204, 21, 0.72)';
    ctx.lineWidth = portrait ? 2.5 : 2;
    ctx.stroke();
    const arcEnd = projectShieldPoint(ray.arc[ray.arc.length - 1], cx, cy, scale, frame);
    const exit = projectShieldPoint(ray.exit, cx, cy, scale, frame);
    line(ctx, arcEnd.x, arcEnd.y, exit.x, exit.y, 'rgba(250, 204, 21, 0.40)', portrait ? 2 : 1.5);
    ctx.restore();
  }
}

function drawCrystal(ctx: Ctx, cx: number, cy: number, scale: number, frame: number, closed: boolean, portrait: boolean): void {
  const transformed = GEODESIC_MESH.vertices.map((vertex) => projectShieldPoint(vertex, cx, cy, scale, frame));
  const localZ = GEODESIC_MESH.vertices.map((vertex) => rotatePoint3(vertex, frame * 0.003, 0.30 + Math.sin(frame * 0.0015) * 0.18, frame * 0.0014).z);
  ctx.save();
  for (let edgeIndex = 0; edgeIndex < GEODESIC_MESH.edges.length; edgeIndex += 1) {
    const [a, b] = GEODESIC_MESH.edges[edgeIndex];
    const midpointZ = (localZ[a] + localZ[b]) / 2;
    const openSeam = !closed && (edgeIndex % 9 === 0 || (midpointZ > 0.82 && edgeIndex % 2 === 0));
    if (openSeam) continue;
    const p1 = transformed[a];
    const p2 = transformed[b];
    const front = midpointZ > 0;
    ctx.globalAlpha = closed ? (front ? 0.86 : 0.34) : (0.22 + 0.50 * clamp01((frame - 5400) / 360));
    ctx.strokeStyle = edgeIndex % 7 === 0 ? WHITE : GOLD;
    ctx.lineWidth = edgeIndex % 7 === 0 ? (portrait ? 2.8 : 2.2) : (portrait ? 1.8 : 1.35);
    ctx.shadowColor = GOLD;
    ctx.shadowBlur = closed && front ? 7 : 2;
    line(ctx, p1.x, p1.y, p2.x, p2.y, ctx.strokeStyle, ctx.lineWidth);
  }
  ctx.restore();

  const coreRadius = portrait ? 22 : 18;
  const pulse = 1 + 0.12 * Math.sin(frame * 0.08);
  const coreGlow = ctx.createRadialGradient(cx, cy, 1, cx, cy, coreRadius * 4 * pulse);
  coreGlow.addColorStop(0, 'rgba(255, 224, 145, 0.95)');
  coreGlow.addColorStop(0.16, 'rgba(245, 158, 11, 0.74)');
  coreGlow.addColorStop(0.52, 'rgba(245, 158, 11, 0.12)');
  coreGlow.addColorStop(1, 'rgba(245, 158, 11, 0)');
  ctx.fillStyle = coreGlow;
  ctx.fillRect(cx - coreRadius * 4 * pulse, cy - coreRadius * 4 * pulse, coreRadius * 8 * pulse, coreRadius * 8 * pulse);
  glowDot(ctx, cx, cy, coreRadius * pulse, AMBER, 1);
  ctx.beginPath();
  ctx.strokeStyle = 'rgba(255, 240, 205, 0.92)';
  ctx.lineWidth = portrait ? 3 : 2;
  ctx.arc(cx, cy, coreRadius * 1.65 * pulse, 0, Math.PI * 2);
  ctx.stroke();
}

function drawShieldScene(ctx: Ctx, box: Box, frame: number, portrait: boolean): void {
  drawContentPlate(ctx, box.w, box.h, GOLD);
  const closure = clamp01((frame - 5400) / 360);
  const closed = frame >= 5760;
  const pullback = frame >= 6300 ? smoothstep((frame - 6300) / 90) : 0;
  const cx = box.w * 0.5;
  const cy = mix(box.h * 0.50, box.h * 0.62, pullback);
  const scale = Math.min(box.w, box.h) * (portrait ? 0.24 : 0.27) * (1 - 0.12 * pullback);
  for (let ray = 0; ray < 18; ray += 1) drawShieldRay(ctx, ray, frame, cx, cy, scale, closed, portrait);

  if (closed) {
    ctx.save();ctx.beginPath();
    for(let i=0;i<=96;i+=1){
      const angle=i/96*Math.PI*2+frame*0.006;
      const r=scale*(1.12+0.022*laplaceQuantile(seededUnit(i%96,61)));
      const x=cx+Math.cos(angle)*r,y=cy+Math.sin(angle)*r;
      if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
    }
    ctx.strokeStyle='rgba(250,204,21,0.32)';ctx.lineWidth=portrait?2:1.5;ctx.stroke();ctx.restore();
  }
  const shellScale = scale * (0.76 + 0.24 * closure);
  drawCrystal(ctx, cx, cy, shellScale, frame, closed, portrait);

  if (closed && frame < 6300) {
    const ringRadius = scale * (2.25 + 0.09 * Math.sin(frame * 0.025));
    ctx.save();
    ctx.strokeStyle = 'rgba(250, 204, 21, 0.30)';
    ctx.lineWidth = portrait ? 3 : 2;
    ctx.beginPath(); ctx.ellipse(cx, cy, ringRadius, ringRadius * 0.34, frame * 0.001, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(cx, cy, ringRadius * 0.87, ringRadius, -frame * 0.0014, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
  }

  if (frame >= 6300 && frame < 6900) {
    const calm = 0.5 + 0.5 * Math.sin(frame * 0.054);
    const orbit = {
      x: cx + Math.cos(frame * 0.031) * scale * 0.44,
      y: cy + Math.sin(frame * 0.047) * scale * 0.32,
    };
    glowDot(ctx, orbit.x, orbit.y, (portrait ? 6 : 5) + calm * 3, AMBER, 0.95);
    ctx.strokeStyle = 'rgba(250, 204, 21, 0.24)';
    ctx.lineWidth = portrait ? 2 : 1.5;
    ctx.beginPath(); ctx.ellipse(cx, cy, scale * 1.22, scale * 0.44, -frame * 0.001, 0, Math.PI * 2); ctx.stroke();
  }
}

function drawFinalRings(ctx: Ctx, box: Box, frame: number, portrait: boolean): void {
  drawContentPlate(ctx, box.w, box.h, GOLD);
  const progress = clamp01((frame - 6900) / 300);
  const pullback = 1 - 0.62 * smoothstep(progress);
  const cx = box.w * 0.5;
  const cy = box.h * 0.5;
  const maximum = Math.min(box.w, box.h) * (portrait ? 0.42 : 0.47) * pullback;
  ctx.save();
  for (let i = 0; i < 6; i += 1) {
    const phase = frame * (0.0018 + i * 0.00012) + i * 0.22;
    const radius = maximum * (0.34 + i * 0.13);
    ctx.beginPath();
    ctx.ellipse(cx, cy, radius, radius * (0.48 + i * 0.04), phase, 0, Math.PI * 2);
    ctx.strokeStyle = i === 5 ? 'rgba(250, 204, 21, 0.88)' : `rgba(250, 204, 21, ${0.36 + i * 0.065})`;
    ctx.lineWidth = i === 5 ? (portrait ? 5 : 4) : (portrait ? 2.5 : 2);
    ctx.shadowColor = GOLD;
    ctx.shadowBlur = 8 + i * 2;
    ctx.stroke();
    const orbit = { x: cx + Math.cos(phase) * radius, y: cy + Math.sin(phase) * radius * (0.48 + i * 0.04) };
    glowDot(ctx, orbit.x, orbit.y, portrait ? 5 : 4, i % 2 === 0 ? WHITE : GOLD, 0.92);
  }
  const emblem = ctx.createRadialGradient(cx, cy, 1, cx, cy, maximum * 0.23);
  emblem.addColorStop(0, 'rgba(255, 255, 255, 0.84)');
  emblem.addColorStop(0.24, 'rgba(250, 204, 21, 0.72)');
  emblem.addColorStop(1, 'rgba(250, 204, 21, 0)');
  ctx.fillStyle = emblem;
  ctx.fillRect(cx - maximum * 0.23, cy - maximum * 0.23, maximum * 0.46, maximum * 0.46);
  ctx.restore();
}

export const CanvasWorld: React.FC<Props> = ({ frame, portrait, width, height }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const logicalWidth = portrait ? 1080 : 1920;
    const logicalHeight = portrait ? 1920 : 1080;
    ctx.resetTransform();
    ctx.clearRect(0, 0, width, height);
    ctx.setTransform(width / logicalWidth, 0, 0, height / logicalHeight, 0, 0);
    drawBackground(ctx, logicalWidth, logicalHeight, frame);

    if (frame >= 1260 && frame < 1800) {
      drawPrismTunnel(ctx, logicalWidth, logicalHeight, frame);
      return;
    }

    const content = portrait ? CONTENT_PORTRAIT : CONTENT_LANDSCAPE;
    ctx.save();
    ctx.beginPath();
    ctx.rect(content.x, content.y, content.w, content.h);
    ctx.clip();
    ctx.translate(content.x, content.y);
    const box = { x: 0, y: 0, w: content.w, h: content.h };

    if (frame < 1260) drawPreEchoScene(ctx, box, frame, portrait);
    else if (frame < 3600) drawLorenzScene(ctx, box, frame, portrait);
    else if (frame < 5400) drawChoiceScene(ctx, box, frame, portrait);
    else if (frame < 6900) drawShieldScene(ctx, box, frame, portrait);
    else drawFinalRings(ctx, box, frame, portrait);
    ctx.restore();
  }, [frame, portrait, width, height]);

  return <canvas ref={canvasRef} width={width} height={height} style={{ position: 'absolute', inset: 0, width, height }} />;
};
