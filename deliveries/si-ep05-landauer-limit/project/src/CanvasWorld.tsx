import React, { useLayoutEffect, useRef } from 'react';
import {
  ABSORBED_SOLAR,
  CMB_TEMPERATURE,
  EARTH_EMISSIVITY,
  ROOM_TEMPERATURE,
  SOLAR_ALBEDO,
  SOLAR_CONSTANT,
  STEFAN_BOLTZMANN,
  landauer,
  koomey,
  murrayChild,
  planck,
  potential,
  radiated,
  state,
  wien,
} from './physics';

type Props = { frame: number; portrait: boolean; width: number; height: number };
type Box = { x: number; y: number; w: number; h: number };
type Ctx = CanvasRenderingContext2D;

const VOID = '#050811';
const CYAN = '#06b6d4';
const AMBER = '#f59e0b';
const RED = '#ef4444';
const GOLD = '#facc15';
const WHITE = '#ffffff';
const MUTED = '#9aaabd';
const GRID = '#102031';

const clamp = (v: number, lo: number, hi: number): number => Math.max(lo, Math.min(hi, v));
const mix = (a: number, b: number, t: number): number => a + (b - a) * clamp(t, 0, 1);
const fract = (n: number): number => n - Math.floor(n);

function setFont(c: Ctx, size: number, bold = false): void {
  c.font = `${bold ? '600' : '400'} ${size}px Arial, "PingFang SC", "Noto Sans CJK SC", sans-serif`;
}

function text(
  c: Ctx,
  value: string,
  x: number,
  y: number,
  size = 30,
  color = WHITE,
  align: CanvasTextAlign = 'left',
  bold = false,
): void {
  c.save();
  setFont(c, size, bold);
  c.textAlign = align;
  c.textBaseline = 'alphabetic';
  c.fillStyle = color;
  c.fillText(value, x, y);
  c.restore();
}

function line(c: Ctx, x1: number, y1: number, x2: number, y2: number, color: string, width = 2): void {
  c.beginPath();
  c.strokeStyle = color;
  c.lineWidth = width;
  c.moveTo(x1, y1);
  c.lineTo(x2, y2);
  c.stroke();
}

function arrow(c: Ctx, x1: number, y1: number, x2: number, y2: number, color: string, width = 4): void {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const head = 12 + width;
  c.beginPath();
  c.strokeStyle = color;
  c.fillStyle = color;
  c.lineWidth = width;
  c.moveTo(x1, y1);
  c.lineTo(x2, y2);
  c.stroke();
  c.beginPath();
  c.moveTo(x2, y2);
  c.lineTo(x2 - head * Math.cos(angle - 0.48), y2 - head * Math.sin(angle - 0.48));
  c.lineTo(x2 - head * Math.cos(angle + 0.48), y2 - head * Math.sin(angle + 0.48));
  c.closePath();
  c.fill();
}

function border(c: Ctx, box: Box, color = '#294052'): void {
  c.save();
  c.strokeStyle = color;
  c.lineWidth = 2;
  c.strokeRect(box.x, box.y, box.w, box.h);
  c.restore();
}

function panel(c: Ctx, box: Box, title: string, titleColor = CYAN): void {
  c.save();
  c.fillStyle = 'rgba(6, 15, 27, 0.78)';
  c.fillRect(box.x, box.y, box.w, box.h);
  border(c, box);
  text(c, title, box.x + 18, box.y + 38, 32, titleColor, 'left', true);
  c.restore();
}

function fmtSci(value: number, digits = 2): string {
  if (value === 0) return '0';
  if (!Number.isFinite(value)) return '—';
  const [mantissa, exponent] = value.toExponential(digits).split('e');
  return `${mantissa}×10^${Number(exponent)}`;
}

function plotBounds(portrait: boolean): Box {
  return portrait
    ? { x: 65, y: 490, w: 835, h: 800 }
    : { x: 80, y: 310, w: 1760, h: 540 };
}

function drawBackground(c: Ctx, w: number, h: number, frame: number): void {
  c.fillStyle = VOID;
  c.fillRect(0, 0, w, h);
  const glow = c.createRadialGradient(w * 0.52, h * 0.48, 20, w * 0.52, h * 0.48, Math.max(w, h) * 0.78);
  glow.addColorStop(0, 'rgba(9, 28, 42, 0.22)');
  glow.addColorStop(1, 'rgba(5, 8, 17, 0)');
  c.fillStyle = glow;
  c.fillRect(0, 0, w, h);
  c.save();
  c.strokeStyle = GRID;
  c.lineWidth = 1;
  const offsetX = (frame * 0.34) % 56;
  const offsetY = (frame * 0.19) % 48;
  for (let x = -56 + offsetX; x < w + 56; x += 56) {
    c.beginPath(); c.moveTo(x, 0); c.lineTo(x, h); c.stroke();
  }
  for (let y = -48 + offsetY; y < h + 48; y += 48) {
    c.beginPath(); c.moveTo(0, y); c.lineTo(w, y); c.stroke();
  }
  c.restore();
}

function drawAxes(c: Ctx, x: number, y: number, w: number, h: number): void {
  line(c, x, y, x, y + h, '#7890a4', 2);
  line(c, x, y + h, x + w, y + h, '#7890a4', 2);
}

function drawQuartic(c: Ctx, frame: number, b: Box, portrait: boolean): void {
  panel(c, b, 'DOUBLE-WELL POTENTIAL', CYAN);
  text(c, 'U=x⁴−2αx²+cx', b.x + 18, b.y + 76, 30, WHITE);
  const u = clamp((frame - 720) / 540, 0, 1);
  const alpha = u < 0.45 ? 1 - u / 0.45 : u < 0.75 ? 0 : (u - 0.75) / 0.25;
  const tilt = 0.8 * Math.sin(Math.PI * u);
  const padL = portrait ? 58 : 68;
  const padR = 26;
  const padT = 112;
  const padB = portrait ? 72 : 86;
  const px = b.x + padL;
  const py = b.y + padT;
  const pw = b.w - padL - padR;
  const ph = b.h - padT - padB;
  const xMin = -1.6;
  const xMax = 1.6;
  const yMin = -2.2;
  const yMax = 0.86;
  const sx = (x: number): number => px + ((x - xMin) / (xMax - xMin)) * pw;
  const sy = (u: number): number => py + ((yMax - u) / (yMax - yMin)) * ph;

  c.save();
  c.beginPath(); c.rect(px, py, pw, ph); c.clip();
  for (const x of [-1, 0, 1]) {
    const gx = sx(x);
    line(c, gx, py, gx, py + ph, '#1b3040', 1);
  }
  line(c, px, sy(0), px + pw, sy(0), '#53697c', 1.5);
  c.beginPath();
  c.strokeStyle = GOLD;
  c.lineWidth = 5;
  for (let i = 0; i <= 280; i += 1) {
    const x = xMin + (xMax - xMin) * i / 280;
    const y = potential(x, alpha, tilt);
    if (i === 0) c.moveTo(sx(x), sy(y)); else c.lineTo(sx(x), sy(y));
  }
  c.stroke();

  // Forty deterministic bounded samples. They are a visual ensemble sketch,
  // not a Langevin trajectory or a solved stochastic process.
  for (let i = 0; i < 40; i += 1) {
    const side = i < 20 ? -1 : 1;
    const local = i % 20;
    const phase = local * 1.713 + frame * 0.043;
    const well = Math.sqrt(Math.max(0.25, alpha));
    const initialX = side * well;
    const finalX = -well;
    const resetPhase = clamp(u / 0.45, 0, 1);
    const resetMix = resetPhase * resetPhase * (3 - 2 * resetPhase);
    const x = mix(initialX, finalX, resetMix) + 0.045 * Math.sin(phase);
    const yy = potential(x, alpha, tilt) + 0.04 * Math.sin(phase * 1.29);
    c.beginPath();
    c.fillStyle = i % 4 === 0 ? '#b5fbff' : CYAN;
    c.globalAlpha = 0.68 + 0.27 * ((Math.sin(phase) + 1) / 2);
    c.arc(sx(x), sy(yy), portrait ? 5 : 6, 0, Math.PI * 2);
    c.fill();
  }
  c.restore();

  text(c, `α=${alpha.toFixed(2)}  c=${tilt.toFixed(2)}`, b.x + 18, b.y + b.h - 18, 30, MUTED);
  if (u < 0.02) {
    text(c, 'minimum x=−1 · |0⟩', sx(-1), sy(-1) - 12, 30, CYAN, 'center', true);
    text(c, 'minimum x=+1 · |1⟩', sx(1), sy(-1) - 12, 30, CYAN, 'center', true);
  } else {
    text(c, 'ERASE → |0⟩', px + pw / 2, py + 34, 30, CYAN, 'center', true);
  }
  text(c, '40 SAMPLES · SCHEMATIC', b.x + b.w - 18, b.y + b.h - 18, 30, MUTED, 'right');
  text(c, 'x / x₀', px + pw / 2, py + ph + 22, 30, WHITE, 'center');
  text(c, 'U', b.x + 18, py + ph / 2, 30, WHITE);
}

function triangle(position: number): number {
  const p = fract(position);
  return p < 0.5 ? p * 2 : 2 - p * 2;
}

/** Integral of v(t)/L(t) for a linearly shrinking L=L0(1-u/2). */
function integratedBounce(frame: number, adiabatic: boolean): number {
  const start = 720;
  const duration = 540;
  const t = clamp(frame - start, 0, duration);
  const u = t / duration;
  const v0PerFrame = 0.105;
  const initialMotion = Math.min(Math.max(frame, 0), start) * v0PerFrame;
  if (adiabatic) return initialMotion + duration * v0PerFrame * (2 * u) / (2 - u);
  return initialMotion + 2 * duration * v0PerFrame * Math.log(1 / (1 - u / 2));
}

function drawCylinder(
  c: Ctx,
  frame: number,
  b: Box,
  adiabatic: boolean,
): void {
  const compression = clamp((frame - 720) / 540, 0, 1);
  const x0 = b.x + 25;
  const chamber0 = b.w - 62;
  const chamber = chamber0 * (1 - 0.5 * compression);
  const midY = b.y + b.h / 2;
  c.fillStyle = adiabatic ? 'rgba(245, 158, 11, 0.08)' : 'rgba(6, 182, 212, 0.08)';
  c.fillRect(x0, b.y + 4, chamber, b.h - 8);
  line(c, x0, b.y, x0, b.y + b.h, '#8aa0b2', 4);
  line(c, x0, b.y, x0 + chamber0, b.y, '#52677a', 3);
  line(c, x0, b.y + b.h, x0 + chamber0, b.y + b.h, '#52677a', 3);
  c.fillStyle = adiabatic ? AMBER : '#d8e3eb';
  c.fillRect(x0 + chamber - 8, b.y - 2, 16, b.h + 4);

  const bounceIntegral = integratedBounce(frame, adiabatic);
  const velocityScale = adiabatic ? 1 / (1 - 0.5 * compression) : 1;
  for (let i = 0; i < 8; i += 1) {
    const row = i % 4;
    const seed = i * 0.137;
    const phase = bounceIntegral / 2 + seed;
    const pos = triangle(phase);
    const px = x0 + 12 + pos * Math.max(4, chamber - 28);
    const py = b.y + 12 + row * Math.max(10, (b.h - 24) / 3);
    c.beginPath();
    c.fillStyle = adiabatic ? AMBER : CYAN;
    c.arc(px, py, 5, 0, Math.PI * 2);
    c.fill();
    const dir = fract(phase) < 0.5 ? 1 : -1;
    const arrowLength = (adiabatic ? 25 : 27) * velocityScale;
    arrow(c, px, py, px + dir * arrowLength, py, RED, 3);
  }
  c.fillStyle = '#050811';
  c.fillRect(b.x + b.w - 165, midY - 21, 160, 42);
  text(c, `V/V₀=${(1 - 0.5 * compression).toFixed(2)}`, b.x + b.w - 12, midY + 10, 30, WHITE, 'right', true);
}

function drawPiston(c: Ctx, frame: number, b: Box, portrait: boolean): void {
  panel(c, b, portrait ? 'SZILARD PISTON · TWO PATHS' : 'SZILARD PISTON · TWO THERMODYNAMIC PATHS', AMBER);
  const mainLabelY = b.y + (portrait ? 80 : 96);
  text(c, 'ISOTHERMAL · LANDAUER PATH · v unchanged', b.x + 20, mainLabelY, 30, CYAN, 'left', true);
  text(c, 'Q ≥ kBT ln 2 · V₀ → V₀/2', b.x + 20, portrait ? b.y + 112 : b.y + 130, 30, CYAN, 'left', true);
  const mainBox = portrait
    ? { x: b.x + 18, y: b.y + 120, w: b.w - 36, h: 50 }
    : { x: b.x + 18, y: b.y + 145, w: b.w - 36, h: 76 };
  drawCylinder(c, frame, mainBox, false);
  const label2Y = portrait ? b.y + 220 : b.y + 258;
  text(c, '1D ADIABATIC COMPARISON · v×2 · T×4', b.x + 20, label2Y, 30, AMBER, 'left', true);
  if (portrait) text(c, 'not the Landauer path', b.x + 20, b.y + 251, 30, AMBER);
  const insetBox = portrait
    ? { x: b.x + 18, y: b.y + 261, w: b.w - 36, h: 48 }
    : { x: b.x + 18, y: b.y + 273, w: b.w - 36, h: 72 };
  drawCylinder(c, frame, insetBox, true);
  if (frame >= 960 && frame <= 1040) {
    const pulse = (frame - 960) / 80;
    const radius = 15 + 40 * pulse;
    const cx = b.x + b.w - 110;
    const cy = b.y + (portrait ? 145 : 150);
    c.save();
    c.globalAlpha = 1 - pulse;
    c.strokeStyle = RED;
    c.lineWidth = 8;
    c.beginPath(); c.arc(cx, cy, radius, 0, Math.PI * 2); c.stroke();
    c.restore();
    text(c, 'ΔQ ≥ kBT ln 2', b.x + 20, portrait ? b.y + 342 : b.y + 474, 30, RED, 'left', true);
    text(c, '= 2.87×10^-21 J', b.x + 20, portrait ? b.y + 374 : b.y + 508, 30, RED, 'left', true);
  } else if (frame >= 1041 && frame < 1260) {
    text(c, 'ΔQ ≥ kBT ln 2', b.x + 20, portrait ? b.y + 342 : b.y + 474, 30, RED, 'left', true);
    text(c, '= 2.87×10^-21 J', b.x + 20, portrait ? b.y + 374 : b.y + 508, 30, RED, 'left', true);
  }
}

function drawAct1(c: Ctx, frame: number, portrait: boolean): void {
  const b = plotBounds(portrait);
  const gap = portrait ? 14 : 24;
  const potentialBox = portrait
    ? { x: b.x, y: b.y, w: b.w, h: 398 }
    : { x: b.x, y: b.y, w: (b.w - gap) / 2, h: b.h };
  const pistonBox = portrait
    ? { x: b.x, y: b.y + 412, w: b.w, h: b.h - 412 }
    : { x: b.x + potentialBox.w + gap, y: b.y, w: potentialBox.w, h: b.h };
  drawQuartic(c, frame, potentialBox, portrait);
  drawPiston(c, frame, pistonBox, portrait);
}

function drawPotentialSurface(c: Ctx, frame: number, b: Box): void {
  c.save();
  c.fillStyle = 'rgba(4, 9, 20, 0.45)';
  c.fillRect(b.x, b.y, b.w, b.h);
  const rotation = 0.53 + 0.08 * Math.sin(frame * 0.009);
  const alpha = 0.42 + 0.08 * Math.sin(frame * 0.013);
  const tilt = 0.075;
  const centerX = b.x + b.w * 0.53;
  const baseY = b.y + b.h * 0.70;
  const xScale = Math.min(210, b.w * 0.28);
  const zScale = 95;
  const project = (x: number, z: number, energy: number): [number, number] => {
    const horizontal = x * xScale;
    const depth = z * 170;
    return [centerX + horizontal + depth * 0.48, baseY + depth * Math.sin(rotation) - energy * zScale * Math.cos(rotation)];
  };
  for (let zi = 0; zi <= 12; zi += 1) {
    const z = zi / 12;
    c.beginPath();
    c.strokeStyle = zi % 3 === 0 ? 'rgba(6,182,212,0.66)' : 'rgba(6,182,212,0.22)';
    c.lineWidth = zi % 3 === 0 ? 2 : 1;
    for (let xi = 0; xi <= 100; xi += 1) {
      const x = -1.5 + 3 * xi / 100;
      const e = potential(x, alpha, tilt);
      const [sx, sy] = project(x, z, e);
      if (xi === 0) c.moveTo(sx, sy); else c.lineTo(sx, sy);
    }
    c.stroke();
  }
  for (let xi = 0; xi <= 12; xi += 1) {
    const x = -1.5 + 3 * xi / 12;
    c.beginPath();
    c.strokeStyle = 'rgba(245,158,11,0.22)';
    c.lineWidth = 1;
    for (let zi = 0; zi <= 20; zi += 1) {
      const z = zi / 20;
      const [sx, sy] = project(x, z, potential(x, alpha, tilt));
      if (zi === 0) c.moveTo(sx, sy); else c.lineTo(sx, sy);
    }
    c.stroke();
  }
  c.restore();
  text(c, 'U(x)=x⁴−2αx²+cx · ANALYTICAL SURFACE', b.x + b.w / 2, b.y + b.h - 14, 30, CYAN, 'center');
  // The surface is an equation rendered with perspective; it is not a solved
  // three-dimensional physical dynamics simulation.
}

function drawAct1Title(c: Ctx, frame: number, portrait: boolean): void {
  const b = plotBounds(portrait);
  drawPotentialSurface(c, frame, b);
}

function mapYear(year: number, x: number, w: number): number {
  return x + (year - 1946) / (2080 - 1946) * w;
}

function koomeyYearAt(opsPerJoule: number): number {
  return (Math.log(opsPerJoule * 3_600_000) + 849.259) / 0.440243;
}

function mapLogOps(value: number, y: number, h: number): number {
  const exponent = Math.log10(Math.max(value, 1e-100));
  return y + (22 - clamp(exponent, 3, 22)) / 19 * h;
}

function drawKoomeyChart(c: Ctx, frame: number, b: Box, portrait: boolean): void {
  panel(c, b, portrait ? 'KOOMEY · LOG10 OPS/J' : 'KOOMEY REGRESSION · LOG10 OPS/J', CYAN);
  const left = portrait ? 86 : 86;
  const top = portrait ? 110 : 84;
  const bottom = 140;
  const right = portrait ? 24 : 30;
  const px = b.x + left;
  const py = b.y + top;
  const pw = b.w - left - right;
  const ph = b.h - top - bottom;
  const yAt = (val: number): number => mapLogOps(val, py, ph);
  const xAt = (year: number): number => mapYear(year, px, pw);
  drawAxes(c, px, py, pw, ph);

  c.save();
  c.beginPath(); c.rect(px, py, pw, ph); c.clip();
  const yTicks = [3, 6, 9, 12, 15, 18, 21];
  for (const tick of yTicks) {
    const yy = py + (22 - tick) / 19 * ph;
    line(c, px, yy, px + pw, yy, '#1b3040', 1);
  }
  const xTicks = [1946, 1971, 2009, 2026, 2050, 2080];
  for (const tick of xTicks) {
    const xx = xAt(tick);
    line(c, xx, py, xx, py + ph, '#172b3b', 1);
  }
  const landauerFloor = 1 / landauer(ROOM_TEMPERATURE);
  const wallY = yAt(landauerFloor);
  c.save();
  c.setLineDash([13, 8]);
  line(c, px, wallY, px + pw, wallY, RED, 4);
  c.restore();

  const drawRegression = (startYear: number, endYear: number, color: string, dashed: boolean): void => {
    c.save();
    if (dashed) c.setLineDash([13, 9]);
    c.beginPath();
    c.strokeStyle = color;
    c.lineWidth = 5;
    for (let i = 0; i <= 350; i += 1) {
      const year = startYear + (endYear - startYear) * i / 350;
      const xx = xAt(year);
      const yy = yAt(koomey(year));
      if (i === 0) c.moveTo(xx, yy); else c.lineTo(xx, yy);
    }
    c.stroke();
    c.restore();
  };
  // Solid fit through the observed period; the same equation is dashed after
  // 2009 and is explicitly labeled as an extrapolation, not a forecast.
  const firstVisibleYear = koomeyYearAt(1e3);
  const lastVisibleYear = koomeyYearAt(1e22);
  drawRegression(firstVisibleYear, 2009, CYAN, false);
  drawRegression(2009, Math.min(2080, lastVisibleYear), '#72d3e4', true);

  const brainY = py + (22 - 16) / 19 * ph;
  line(c, px, brainY, px + pw, brainY, 'rgba(245,158,11,0.54)', 2);
  c.beginPath(); c.fillStyle = AMBER; c.arc(px + pw * 0.68, brainY, 11, 0, Math.PI * 2); c.fill();
  text(c, '20 W BRAIN ~10^16 [MODEL]', px + pw - 8, brainY - 15, 30, AMBER, 'right', true);

  // The year cursor animates through the analytical comparison. Milestone
  // captions below are timeline labels; they carry no fabricated measurements.
  const cursorYear = 1946 + 134 * clamp((frame - 1800) / 1800, 0, 1);
  const cursorX = xAt(cursorYear);
  line(c, cursorX, py, cursorX, py + ph, 'rgba(6,182,212,0.8)', 2);
  const cursorOps = koomey(cursorYear);
  if (cursorOps >= 1e3 && cursorOps <= 1e22) {
    c.beginPath(); c.fillStyle = WHITE; c.arc(cursorX, yAt(cursorOps), 7, 0, Math.PI * 2); c.fill();
  }

  c.restore();
  for (const tick of yTicks) {
    const yy = py + (22 - tick) / 19 * ph;
    text(c, `10^${tick}`, px - 10, yy + 9, 30, MUTED, 'right');
  }
  text(c, '300 K ERASURE WALL', px + pw - 8, wallY + 36, 30, RED, 'right', true);
  text(c, '3.48×10^20 BIT ERASURES/J', b.x + 18, b.y + 72, 30, RED, 'left', true);
  const years = [1946, 1971, 2009, 2026, 2050, 2080];
  for (const year of years) text(c, String(year), xAt(year), py + ph + 34, 30, MUTED, 'center');

  if (portrait) {
    text(c, '1946 / 1971 BELOW AXIS', b.x + 18, b.y + 530, 30, AMBER, 'left', true);
    text(c, 'POST-2009: EXTRAPOLATION', b.x + 18, b.y + 565, 30, WHITE, 'left', true);
    text(c, '2026 TENSOR ERA', b.x + b.w - 18, b.y + 530, 30, MUTED, 'right');
  } else {
    text(c, '1946 / 1971 BELOW AXIS · FIT <10^3 OPS/J', b.x + 18, b.y + b.h - 48, 30, WHITE);
    text(c, '2026 TENSOR ERA · ILLUSTRATIVE · 1 ERASURE/OP', b.x + 18, b.y + b.h - 14, 30, MUTED);
  }
  text(c, `YEAR ${Math.round(cursorYear)}`, px + 12, py + 35, 30, CYAN, 'left', true);
}

function drawLattice(c: Ctx, frame: number, b: Box, portrait: boolean): void {
  panel(c, b, portrait ? 'HARMONIC PHONON LATTICE' : 'PHONON LATTICE', RED);
  const x0 = b.x + 24;
  const y0 = b.y + (portrait ? 62 : 82);
  const cols = portrait ? 8 : 7;
  const rows = portrait ? 3 : 4;
  const spanW = b.w - 48;
  const spanH = portrait ? 28 : 220;
  const amp = 2.5 + 10 * clamp((frame - 2500) / 900, 0, 1);
  const omega = frame * 0.095;
  for (let r = 0; r < rows; r += 1) {
    c.beginPath(); c.strokeStyle = '#4b6679'; c.lineWidth = 2;
    for (let col = 0; col < cols; col += 1) {
      const x = x0 + col / (cols - 1) * spanW;
      const baseY = y0 + r / (rows - 1) * spanH;
      const displacement = amp * Math.sin(col * 0.8 - omega + r * 0.7);
      if (col === 0) c.moveTo(x, baseY + displacement); else c.lineTo(x, baseY + displacement);
    }
    c.stroke();
    for (let col = 0; col < cols; col += 1) {
      const x = x0 + col / (cols - 1) * spanW;
      const baseY = y0 + r / (rows - 1) * spanH;
      const displacement = amp * Math.sin(col * 0.8 - omega + r * 0.7);
      c.beginPath(); c.fillStyle = frame > 2700 ? RED : CYAN;
      c.arc(x, baseY + displacement, 7, 0, Math.PI * 2); c.fill();
    }
  }
  if (portrait) {
    text(c, 'u(x,t)=A sin(kx−ωt) · schematic', b.x + 18, b.y + 119, 30, MUTED);
    text(c, '10^38 bit erasures/s × 2.87×10^-21 J', b.x + 18, b.y + 151, 30, RED, 'left', true);
    text(c, '= 2.87×10^17 W at 300 K · ideal floor', b.x + 18, b.y + 183, 30, RED, 'left', true);
  } else {
    text(c, 'u=A sin(kx−ωt) · harmonic schematic', b.x + 18, b.y + b.h - 154, 22, MUTED);
    text(c, '10^38 bit erasures/s × 2.87×10^-21 J', b.x + 18, b.y + b.h - 120, 20, RED, 'left', true);
    text(c, '= 2.87×10^17 W at 300 K · ideal floor', b.x + 18, b.y + b.h - 86, 20, RED, 'left', true);
    text(c, 'not an atomistic simulation', b.x + 18, b.y + b.h - 52, 22, MUTED);
  }
}

function drawAct2(c: Ctx, frame: number, portrait: boolean): void {
  const b = plotBounds(portrait);
  if (portrait) {
    drawKoomeyChart(c, frame, { x: b.x, y: b.y, w: b.w, h: 600 }, true);
    drawLattice(c, frame, { x: b.x, y: b.y + 608, w: b.w, h: 192 }, true);
  } else {
    const latticeW = 392;
    drawKoomeyChart(c, frame, { x: b.x, y: b.y, w: b.w - latticeW - 18, h: b.h }, false);
    drawLattice(c, frame, { x: b.x + b.w - latticeW, y: b.y, w: latticeW, h: b.h }, false);
  }
}

function maxPlanck345(): number {
  let max = 0;
  for (let i = 0; i <= 4800; i += 1) max = Math.max(max, planck(2 + i / 100, 345));
  return max;
}

const PLANCK_AXIS_MAX = maxPlanck345();

function thermalColor(temperature: number): string {
  const t = clamp((temperature - 330) / 15, 0, 1);
  const amber = [245, 158, 11];
  const red = [239, 68, 68];
  const channels = amber.map((v, i) => Math.round(mix(v, red[i], t)));
  return `rgb(${channels[0]},${channels[1]},${channels[2]})`;
}

function drawPlanck(c: Ctx, b: Box, temperature: number, portrait: boolean): void {
  panel(c, b, 'PLANCK SPECTRUM Bλ(λ,T)', thermalColor(temperature));
  const left = 80;
  const top = 86;
  const bottom = portrait ? 97 : 96;
  const right = 22;
  const px = b.x + left;
  const py = b.y + top;
  const pw = b.w - left - right;
  const ph = b.h - top - bottom;
  drawAxes(c, px, py, pw, ph);
  c.save();
  c.beginPath(); c.rect(px, py, pw, ph); c.clip();
  for (let i = 0; i <= 4; i += 1) {
    const yy = py + ph * (1 - i / 4);
    line(c, px, yy, px + pw, yy, '#1b3040', 1);
  }
  for (let lambda = 2; lambda <= 50; lambda += 8) {
    const xx = px + (lambda - 2) / 48 * pw;
    line(c, xx, py, xx, py + ph, '#142635', 1);
  }
  const curveColor = thermalColor(temperature);
  c.beginPath(); c.strokeStyle = curveColor; c.lineWidth = 5;
  for (let i = 0; i <= 480; i += 1) {
    const lambda = 2 + i / 10;
    const value = planck(lambda, temperature);
    const xx = px + (lambda - 2) / 48 * pw;
    const yy = py + ph * (1 - clamp(value / PLANCK_AXIS_MAX, 0, 1));
    if (i === 0) c.moveTo(xx, yy); else c.lineTo(xx, yy);
  }
  c.stroke();
  const peak = wien(temperature);
  const peakX = px + (peak - 2) / 48 * pw;
  line(c, peakX, py, peakX, py + ph, GOLD, 2);
  c.restore();
  for (let i = 0; i <= 4; i += 1) {
    const yy = py + ph * (1 - i / 4);
    const tick = PLANCK_AXIS_MAX * i / 4;
    text(c, i === 0 ? '0' : tick.toFixed(0), px - 9, yy + 9, 30, MUTED, 'right');
  }
  for (let lambda = 2; lambda <= 50; lambda += 8) {
    const xx = px + (lambda - 2) / 48 * pw;
    text(c, String(lambda), xx, py + ph + 30, 30, MUTED, 'center');
  }
  text(c, 'λ (μm) · Bλ (W m^-2 sr^-1 μm^-1)', b.x + b.w / 2, b.y + b.h - 42, portrait ? 30 : 25, MUTED, 'center');
  text(c, `T=${temperature.toFixed(1)} K · λmax=b/T=${peak.toFixed(2)} μm`, b.x + b.w / 2, b.y + b.h - 10, 30, curveColor, 'center', true);
  if (!portrait) text(c, 'fixed vertical scale set by 345 K', px + pw - 5, b.y + 38, 24, MUTED, 'right');
}

function drawEarthBalance(c: Ctx, frame: number, b: Box, temperature: number, portrait: boolean): void {
  panel(c, b, 'EARTH GREYBODY RADIATIVE BALANCE', AMBER);
  const incoming = ABSORBED_SOLAR;
  const outgoing = radiated(temperature, EARTH_EMISSIVITY);
  const compute = Math.max(0, outgoing - incoming);
  const maxPower = Math.max(incoming, outgoing, 1);
  const radius = portrait ? 35 : 58;
  const cx = b.x + b.w / 2;
  const cy = b.y + (portrait ? 112 : 190);
  const bob = 3 * Math.sin(frame * 0.024);

  c.save();
  const globe = c.createRadialGradient(cx - radius * 0.35, cy - radius * 0.4, 4, cx, cy, radius);
  globe.addColorStop(0, '#287a9b'); globe.addColorStop(1, '#0a304a');
  c.fillStyle = globe;
  c.beginPath(); c.arc(cx, cy + bob, radius, 0, Math.PI * 2); c.fill();
  c.strokeStyle = '#63c7df'; c.lineWidth = 3; c.stroke();
  c.restore();

  const incomingY = cy + bob;
  const arrowScale = portrait ? 88 : 134;
  const pinLength = arrowScale * incoming / maxPower;
  const computeLength = arrowScale * compute / maxPower;
  const poutLength = arrowScale * outgoing / maxPower;
  arrow(c, cx - radius - pinLength - 12, incomingY, cx - radius - 12, incomingY, AMBER, 5);
  arrow(c, cx, cy + bob + 12, cx, cy + bob + 12 - computeLength, RED, 4);
  const outAngle = -Math.PI / 4 + 0.03 * Math.sin(frame * 0.014);
  arrow(
    c,
    cx + Math.cos(outAngle) * (radius + 3), cy + bob + Math.sin(outAngle) * (radius + 3),
    cx + Math.cos(outAngle) * (radius + 3 + poutLength), cy + bob + Math.sin(outAngle) * (radius + 3 + poutLength),
    RED,
    5,
  );
  if (portrait) {
    text(c, `Pin=(1−0.30)πR²S = ${fmtSci(incoming)} W`, b.x + 18, b.y + 190, 30, AMBER, 'left', true);
    text(c, `Pcompute=max(0,Pout−Pin) = ${fmtSci(compute)} W`, b.x + 18, b.y + 222, 30, RED, 'left', true);
    text(c, `Pout=4πR²εσT⁴ = ${fmtSci(outgoing)} W`, b.x + 18, b.y + 254, 30, RED, 'left', true);
    text(c, 'Pin + Pcompute = Pout', b.x + 18, b.y + 286, 30, WHITE, 'left', true);
    text(c, `ε=${EARTH_EMISSIVITY.toFixed(2)} · albedo=${SOLAR_ALBEDO.toFixed(2)} · S=${SOLAR_CONSTANT} W/m²`, b.x + 18, b.y + 318, 30, MUTED);
    text(c, 'FIXED GREYBODY SCENARIO', b.x + 18, b.y + 352, 30, MUTED);
  } else {
    text(c, `Pin=(1−${SOLAR_ALBEDO.toFixed(2)})πR²S = ${fmtSci(incoming)} W`, b.x + 20, b.y + 326, 28, AMBER, 'left', true);
    text(c, `Pcompute=max(0,Pout−Pin) = ${fmtSci(compute)} W`, b.x + 20, b.y + 364, 28, RED, 'left', true);
    text(c, `Pout=4πR² εσT⁴ = ${fmtSci(outgoing)} W`, b.x + 20, b.y + 402, 28, RED, 'left', true);
    text(c, 'Pin + Pcompute = Pout', b.x + 20, b.y + 440, 28, WHITE, 'left', true);
    text(c, `ε=${EARTH_EMISSIVITY.toFixed(2)} · albedo=${SOLAR_ALBEDO.toFixed(2)} · S=${SOLAR_CONSTANT} W/m² · R=6371 km`, b.x + 20, b.y + 478, 24, MUTED);
    text(c, 'fixed greybody · not a climate forecast · 345 K not a universal boiling threshold', b.x + 20, b.y + 518, 22, MUTED);
  }
  // The displayed vectors are annotated by values satisfying Pin+Pcompute=Pout.
}

function drawAct3(c: Ctx, frame: number, portrait: boolean): void {
  const b = plotBounds(portrait);
  const s = state(frame);
  if (portrait) {
    drawPlanck(c, { x: b.x, y: b.y, w: b.w, h: 420 }, s.temperature, true);
    drawEarthBalance(c, frame, { x: b.x, y: b.y + 430, w: b.w, h: b.h - 430 }, s.temperature, true);
  } else {
    const leftW = 848;
    drawPlanck(c, { x: b.x, y: b.y, w: leftW, h: b.h }, s.temperature, false);
    drawEarthBalance(c, frame, { x: b.x + leftW + 24, y: b.y, w: b.w - leftW - 24, h: b.h }, s.temperature, false);
  }
}

function deterministicStars(c: Ctx, b: Box, frame: number): void {
  for (let i = 0; i < 34; i += 1) {
    const sx0 = fract(i * 0.61803398875 + 0.13);
    const sy0 = fract(i * 0.41421356237 + 0.27);
    const x = b.x + fract(sx0 + frame * (0.00006 + (i % 5) * 0.000008)) * b.w;
    const y = b.y + sy0 * b.h;
    const alpha = 0.18 + 0.35 * (0.5 + 0.5 * Math.sin(frame * 0.025 + i * 1.9));
    c.save(); c.globalAlpha = alpha; c.fillStyle = i % 3 === 0 ? CYAN : WHITE;
    c.beginPath(); c.arc(x, y, i % 7 === 0 ? 2.5 : 1.5, 0, Math.PI * 2); c.fill(); c.restore();
  }
}

function drawL2Diagram(c: Ctx, frame: number, b: Box, portrait: boolean): void {
  panel(c, b, 'SUN–EARTH L2 · CRYOGENIC MIGRATION', CYAN);
  deterministicStars(c, b, frame);
  const y = b.y + (portrait ? 156 : 175);
  const sunX = b.x + (portrait ? 92 : 100);
  const earthX = b.x + (portrait ? 365 : 350);
  const l2X = b.x + (portrait ? 704 : 690);
  const orbit = 8 * Math.sin(frame * 0.018);
  const sunR = portrait ? 33 : 42;
  const earthR = portrait ? 22 : 30;
  c.save();
  c.fillStyle = AMBER; c.shadowColor = AMBER; c.shadowBlur = 18;
  c.beginPath(); c.arc(sunX, y, sunR, 0, Math.PI * 2); c.fill();
  c.shadowBlur = 0;
  c.fillStyle = '#16749a'; c.strokeStyle = '#68d7f1'; c.lineWidth = 3;
  c.beginPath(); c.arc(earthX + orbit * 0.3, y, earthR, 0, Math.PI * 2); c.fill(); c.stroke();
  line(c, sunX + sunR, y, l2X - 20, y, 'rgba(245,158,11,0.32)', 2);
  for (let i = 0; i < 3; i += 1) arrow(c, sunX + sunR + 8, y - 18 + i * 18, l2X - 42, y - 18 + i * 18, 'rgba(245,158,11,0.42)', 2);
  const l2Y = y + orbit * 0.45;
  // Sunshield layers sit sunward of the radiator. This architecture is a
  // conceptual geometry diagram; no Earth-shadow/umbra is implied.
  c.fillStyle = 'rgba(6,182,212,0.42)'; c.strokeStyle = CYAN; c.lineWidth = 2;
  c.beginPath(); c.moveTo(l2X - 42, l2Y - 39); c.lineTo(l2X - 12, l2Y - 27); c.lineTo(l2X - 12, l2Y + 27); c.lineTo(l2X - 42, l2Y + 39); c.closePath(); c.fill(); c.stroke();
  for (let i = 0; i < 3; i += 1) line(c, l2X - 44, l2Y - 30 + i * 30, l2X - 15, l2Y - 23 + i * 23, '#8cecff', 1.5);
  c.fillStyle = RED; c.fillRect(l2X, l2Y - 23, 10, 46);
  c.restore();
  text(c, 'SUN', sunX, y + sunR + 29, portrait ? 30 : 28, AMBER, 'center', true);
  text(c, 'EARTH', earthX + orbit * 0.3, y + earthR + 29, portrait ? 30 : 28, CYAN, 'center', true);
  text(c, 'L₂', l2X + 5, l2Y + 56, portrait ? 30 : 28, RED, 'center', true);
  if (portrait) {
    text(c, 'L₂ ≈ a(μ/3)^(1/3) ≈ 1.5×10^6 km', b.x + 18, b.y + b.h - 46, 30, WHITE);
    text(c, 'SCHEMATIC · NOT TO SCALE · SUNSHIELD', b.x + 18, b.y + b.h - 14, 30, MUTED);
  } else {
    text(c, 'L₂ ≈ a(μ/3)^(1/3) ≈ 1.5×10^6 km from Earth · diagram not to scale', b.x + 18, b.y + b.h - 44, 25, WHITE);
    text(c, 'conceptual sunshield geometry · radiator faces deep space', b.x + 18, b.y + b.h - 14, 24, MUTED);
  }
}

function branchTree(
  c: Ctx,
  x: number,
  y: number,
  length: number,
  angle: number,
  radius: number,
  depth: number,
  frame: number,
  scale: number,
): void {
  if (depth <= 0) return;
  const sway = 0.026 * Math.sin(frame * 0.018 + depth * 1.3);
  const a1 = angle - 0.48 - sway;
  const a2 = angle + 0.48 + sway;
  const children = [a1, a2];
  for (let i = 0; i < 2; i += 1) {
    const a = children[i];
    const ex = x + Math.cos(a) * length;
    const ey = y + Math.sin(a) * length;
    c.beginPath(); c.strokeStyle = depth % 2 === 0 ? CYAN : '#79e0f1';
    c.lineWidth = Math.max(2, radius * scale); c.lineCap = 'round';
    c.moveTo(x, y); c.lineTo(ex, ey); c.stroke();
    branchTree(c, ex, ey, length * 0.72, a, murrayChild(radius), depth - 1, frame, scale);
  }
}

function drawRadiator(c: Ctx, frame: number, b: Box, portrait: boolean): void {
  panel(c, b, 'MURRAY BRANCHING · RADIATOR FIN TEMPLATE', CYAN);
  const s = state(frame);
  const treeX = b.x + (portrait ? b.w * 0.52 : b.w * 0.48);
  const treeY = b.y + (portrait ? 235 : 335);
  const initialRadius = portrait ? 14 : 18;
  const scale = portrait ? 0.72 : 0.70;
  branchTree(c, treeX, treeY, portrait ? 25 : 50, -Math.PI / 2, initialRadius, 5, frame, scale);
  c.save(); c.fillStyle = '#ecfeff'; c.beginPath(); c.arc(treeX, treeY, 7, 0, Math.PI * 2); c.fill(); c.restore();
  if (portrait) {
    text(c, 'rparent³ = rchild,1³ + rchild,2³', b.x + 18, b.y + 82, 30, GOLD, 'left', true);
    text(c, 'COOLANT BRANCHES / CONCEPT', b.x + 18, b.y + 116, 30, CYAN, 'left', true);
    text(c, 'T_rad=40 K > T_bath=2.725 K', b.x + 18, b.y + 150, 30, WHITE, 'left', true);
    text(c, `Emin(300 K)/Emin(CMB) = ${(landauer(ROOM_TEMPERATURE) / landauer(CMB_TEMPERATURE)).toFixed(2)}×`, b.x + 18, b.y + b.h - 172, 30, GOLD, 'left', true);
    text(c, 'q/A=εσ(T_rad⁴−T_bath⁴)', b.x + 18, b.y + b.h - 140, 30, RED, 'left', true);
    text(c, `≈ ${(EARTH_EMISSIVITY * STEFAN_BOLTZMANN * (40 ** 4 - CMB_TEMPERATURE ** 4)).toFixed(3)} W/m² · A=1 m²`, b.x + 18, b.y + b.h - 108, 30, RED, 'left', true);
    text(c, `state T=${s.temperature.toFixed(2)} K · net includes CMB`, b.x + 18, b.y + b.h - 44, 30, MUTED);
  } else {
    text(c, 'rparent³ = rchild,1³ + rchild,2³', b.x + 18, b.y + 75, 27, GOLD, 'left', true);
    text(c, 'five recursive levels · equal daughters: rchild=rparent·2^-1/3', b.x + 18, b.y + 112, 24, CYAN);
    text(c, 'hydraulic branching template, not an optimum radiation law', b.x + 18, b.y + 145, 23, MUTED);
    text(c, `Emin(300 K)/Emin(CMB) = ${(landauer(ROOM_TEMPERATURE) / landauer(CMB_TEMPERATURE)).toFixed(2)}× · state ${s.temperature.toFixed(2)} K`, b.x + 18, b.y + b.h - 110, 24, GOLD, 'left', true);
    text(c, 'T_rad=40 K · T_bath=2.725 K', b.x + 18, b.y + b.h - 76, 25, WHITE, 'left', true);
    text(c, `q/A=εσ(40⁴−2.725⁴) ≈ ${(EARTH_EMISSIVITY * STEFAN_BOLTZMANN * (40 ** 4 - CMB_TEMPERATURE ** 4)).toFixed(3)} W/m²`, b.x + 18, b.y + b.h - 42, 23, RED);
    text(c, 'A=1 m² · net radiator power includes CMB bath', b.x + 18, b.y + b.h - 12, 23, MUTED);
  }
}

function drawMigration(c: Ctx, frame: number, portrait: boolean): void {
  const b = plotBounds(portrait);
  const leftW = portrait ? b.w : 820;
  const gap = portrait ? 12 : 22;
  const orbitBox = portrait
    ? { x: b.x, y: b.y, w: b.w, h: 330 }
    : { x: b.x, y: b.y, w: leftW, h: b.h };
  const radiatorBox = portrait
    ? { x: b.x, y: b.y + 340, w: b.w, h: b.h - 340 }
    : { x: b.x + leftW + gap, y: b.y, w: b.w - leftW - gap, h: b.h };
  drawL2Diagram(c, frame, orbitBox, portrait);
  drawRadiator(c, frame, radiatorBox, portrait);
  // Current state and the fixed room-temperature-to-CMB floor ratio are shown
  // inside the radiator panel to stay clear of the subtitle-safe region.
}

function drawSpaceField(c: Ctx, b: Box, frame: number): void {
  c.save();
  const bg = c.createLinearGradient(b.x, b.y, b.x + b.w, b.y + b.h);
  bg.addColorStop(0, 'rgba(3,8,20,0.88)'); bg.addColorStop(0.5, 'rgba(6,18,33,0.62)'); bg.addColorStop(1, 'rgba(2,7,18,0.96)');
  c.fillStyle = bg; c.fillRect(b.x, b.y, b.w, b.h);
  c.restore();
  deterministicStars(c, b, frame);
  const centerX = b.x + b.w * 0.5;
  const centerY = b.y + b.h * 0.5;
  c.save(); c.strokeStyle = 'rgba(6,182,212,0.18)'; c.lineWidth = 2;
  c.beginPath(); c.ellipse(centerX, centerY, b.w * 0.40, b.h * 0.27, -0.18, 0, Math.PI * 2); c.stroke(); c.restore();
}

function drawQuote(c: Ctx, frame: number, portrait: boolean): void {
  const b = plotBounds(portrait);
  drawSpaceField(c, b, frame);
}

function drawKey(c: Ctx, cx: number, cy: number, scale: number, angle: number): void {
  c.save();
  c.translate(cx, cy);
  c.rotate(angle);
  c.scale(scale, scale);
  c.strokeStyle = GOLD; c.fillStyle = 'rgba(250,204,21,0.12)'; c.lineWidth = 9; c.shadowColor = GOLD; c.shadowBlur = 18;
  c.beginPath(); c.arc(-36, 0, 32, 0, Math.PI * 2); c.fill(); c.stroke();
  c.beginPath(); c.moveTo(-4, 0); c.lineTo(104, 0); c.lineTo(104, 16); c.lineTo(82, 16); c.lineTo(82, 8); c.lineTo(60, 8); c.lineTo(60, 20); c.lineTo(42, 20); c.lineTo(42, 0); c.stroke();
  c.restore();
}

function drawCortex(c: Ctx, frame: number, b: Box, portrait: boolean): void {
  drawSpaceField(c, b, frame);
  const cx = b.x + (portrait ? b.w * 0.50 : b.w * 0.40);
  const cy = b.y + b.h * 0.52;
  const headW = portrait ? 190 : 260;
  const headH = portrait ? 250 : 310;
  c.save();
  c.strokeStyle = '#c9d7e3'; c.lineWidth = 4;
  c.beginPath();
  c.moveTo(cx - headW * 0.42, cy + headH * 0.42);
  c.bezierCurveTo(cx - headW * 0.62, cy + headH * 0.12, cx - headW * 0.53, cy - headH * 0.43, cx - headW * 0.05, cy - headH * 0.47);
  c.bezierCurveTo(cx + headW * 0.35, cy - headH * 0.50, cx + headW * 0.49, cy - headH * 0.10, cx + headW * 0.37, cy + headH * 0.12);
  c.lineTo(cx + headW * 0.53, cy + headH * 0.28);
  c.lineTo(cx + headW * 0.30, cy + headH * 0.34);
  c.lineTo(cx + headW * 0.24, cy + headH * 0.48);
  c.closePath(); c.stroke();
  c.strokeStyle = CYAN; c.lineWidth = 2;
  for (let i = 0; i < 7; i += 1) {
    const angle = i * 0.77 + frame * 0.002;
    const x1 = cx + Math.cos(angle) * headW * 0.10;
    const y1 = cy + Math.sin(angle) * headH * 0.13;
    const x2 = cx + Math.cos(angle + 0.8) * headW * 0.29;
    const y2 = cy + Math.sin(angle + 0.8) * headH * 0.28;
    arrow(c, x1, y1, x2, y2, CYAN, 2);
  }
  c.restore();
  const keyX = b.x + (portrait ? b.w * 0.50 : b.w * 0.72);
  const keyY = cy + 10;
  drawKey(c, keyX, keyY, 1 + 0.02 * Math.sin(frame * 0.02), 0.04 * Math.sin(frame * 0.018));
  text(c, 'EP06 · SYMBOLIC', b.x + b.w / 2, b.y + b.h - 28, 30, GOLD, 'center', true);
}

function drawClosing(c: Ctx, frame: number, portrait: boolean): void {
  drawCortex(c, frame, plotBounds(portrait), portrait);
}

export const CanvasWorld: React.FC<Props> = ({ frame, portrait, width, height }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  useLayoutEffect(() => {
    const canvas = ref.current;
    const c = canvas?.getContext('2d');
    if (!canvas || !c) return;
    const logicalW = portrait ? 1080 : 1920;
    const logicalH = portrait ? 1920 : 1080;
    const scale = width / logicalW;
    const f = clamp(Math.floor(Number.isFinite(frame) ? frame : 0), 0, 7199);
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, width, height);
    c.setTransform(scale, 0, 0, scale, 0, 0);
    drawBackground(c, logicalW, logicalH, f);
    if (f < 1260) drawAct1(c, f, portrait);
    else if (f < 1800) drawAct1Title(c, f, portrait);
    else if (f < 3600) drawAct2(c, f, portrait);
    else if (f < 5400) drawAct3(c, f, portrait);
    else if (f < 6300) drawMigration(c, f, portrait);
    else if (f < 6930) drawQuote(c, f, portrait);
    else drawClosing(c, f, portrait);
    // Keep the logical portrait canvas matched to its native 9:16 surface.
    void logicalH;
  }, [frame, portrait, width, height]);

  return <canvas ref={ref} width={width} height={height} style={{ position: 'absolute', inset: 0, width, height }} />;
};
