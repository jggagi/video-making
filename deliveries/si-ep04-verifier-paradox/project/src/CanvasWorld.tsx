import React, { useLayoutEffect, useRef } from "react";

type CanvasWorldProps = {
  frame: number;
  portrait: boolean;
  width: number;
  height: number;
};

type Point3 = { x: number; y: number; z: number };
type Point2 = { x: number; y: number; depth?: number };

const VOID = "#050811";
const CYAN = "#06b6d4";
const EMERALD = "#10b981";
const AMBER = "#f59e0b";
const MAGENTA = "#d946ef";
const RED = "#ef4444";
const GOLD = "#facc15";
const WHITE = "#e9f6ff";
const MONO = '"SFMono-Regular", Menlo, Consolas, monospace';
const SANS = '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

const clamp = (value: number, low = 0, high = 1) => Math.max(low, Math.min(high, value));
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (a: number, b: number, value: number) => {
  const t = clamp((value - a) / (b - a));
  return t * t * (3 - 2 * t);
};
const seeded = (index: number) => {
  const value = Math.sin(index * 127.1 + 311.7) * 43758.5453123;
  return value - Math.floor(value);
};

function project3D(
  point: Point3,
  cx: number,
  cy: number,
  scale: number,
  yaw: number,
  pitch: number,
  roll = 0,
): Point2 {
  const cr = Math.cos(roll);
  const sr = Math.sin(roll);
  const x0 = point.x * cr - point.y * sr;
  const y0 = point.x * sr + point.y * cr;
  const cyaw = Math.cos(yaw);
  const syaw = Math.sin(yaw);
  const x1 = x0 * cyaw - point.z * syaw;
  const z1 = x0 * syaw + point.z * cyaw;
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const y1 = y0 * cp - z1 * sp;
  const z2 = y0 * sp + z1 * cp;
  const depth = 4.8 / Math.max(1.25, 4.8 - z2);
  return { x: cx + x1 * scale * depth, y: cy + y1 * scale * depth, depth };
}

function strokeLine(
  ctx: CanvasRenderingContext2D,
  a: Point2,
  b: Point2,
  color: string,
  alpha: number,
  width = 1,
) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.stroke();
  ctx.restore();
}

function strokePath(ctx: CanvasRenderingContext2D, points: Point2[], color: string, alpha: number, width = 1, close = false) {
  if (points.length < 2) return;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i].x, points[i].y);
  if (close) ctx.closePath();
  ctx.stroke();
  ctx.restore();
}

function drawLabel(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  size: number,
  color: string,
  alpha = 1,
  mono = true,
) {
  ctx.save();
  ctx.font = `600 ${size}px ${mono ? MONO : SANS}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const width = ctx.measureText(value).width + size * 0.9;
  const height = size * 1.55;
  ctx.globalAlpha = alpha * 0.82;
  ctx.fillStyle = "rgba(5, 8, 17, 0.88)";
  ctx.fillRect(x - width / 2, y - height / 2, width, height);
  ctx.strokeStyle = color;
  ctx.lineWidth = 0.8;
  ctx.globalAlpha = alpha * 0.38;
  ctx.strokeRect(x - width / 2, y - height / 2, width, height);
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.fillText(value, x, y);
  ctx.restore();
}

function drawFittedLabel(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  size: number,
  color: string,
  alpha: number,
  portrait: boolean,
) {
  ctx.save();
  ctx.font = `600 ${size}px ${MONO}`;
  const halfWidth = (ctx.measureText(value).width + size * 0.9) / 2;
  ctx.restore();
  const left = portrait ? 65 : 100;
  const right = portrait ? 915 : 1820;
  drawLabel(ctx, value, clamp(x, left + halfWidth, right - halfWidth), y, size, color, alpha);
}

function drawBackground(ctx: CanvasRenderingContext2D, width: number, height: number, frame: number) {
  ctx.fillStyle = VOID;
  ctx.fillRect(0, 0, width, height);

  const driftX = width * (0.48 + 0.025 * Math.sin(frame * 0.0017));
  const driftY = height * (0.43 + 0.035 * Math.cos(frame * 0.0013));
  const glow = ctx.createRadialGradient(driftX, driftY, 8, driftX, driftY, Math.max(width, height) * 0.78);
  glow.addColorStop(0, "rgba(7, 30, 47, 0.5)");
  glow.addColorStop(0.46, "rgba(5, 17, 31, 0.3)");
  glow.addColorStop(1, "rgba(5, 8, 17, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  // A sparse BT.709-like spatial dither and star field keep the void alive without heavy per-pixel work.
  for (let i = 0; i < 230; i += 1) {
    const x = seeded(i + 100) * width;
    const y = seeded(i + 900) * height;
    const twinkle = 0.14 + 0.28 * (0.5 + 0.5 * Math.sin(frame * 0.022 + i * 1.71));
    ctx.globalAlpha = twinkle;
    ctx.fillStyle = i % 11 === 0 ? CYAN : i % 17 === 0 ? GOLD : "#91a9b9";
    const r = i % 23 === 0 ? 1.45 : 0.72;
    ctx.fillRect(x, y, r, r);
  }
  ctx.globalAlpha = 1;

  const gridAlpha = 0.035 + 0.018 * (0.5 + 0.5 * Math.sin(frame * 0.011));
  ctx.save();
  ctx.globalAlpha = gridAlpha;
  ctx.strokeStyle = CYAN;
  ctx.lineWidth = 0.7;
  const shift = (frame * 0.11) % 78;
  for (let x = -80 + shift; x < width + 80; x += 78) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + Math.sin(frame * 0.001 + x) * 8, height);
    ctx.stroke();
  }
  for (let y = -80 + shift; y < height + 80; y += 78) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y + Math.cos(frame * 0.0012 + y) * 8);
    ctx.stroke();
  }
  ctx.restore();
}

function boxCorners(center: Point3, size: Point3): Point3[] {
  const x = size.x / 2;
  const y = size.y / 2;
  const z = size.z / 2;
  return [
    { x: center.x - x, y: center.y - y, z: center.z - z },
    { x: center.x + x, y: center.y - y, z: center.z - z },
    { x: center.x + x, y: center.y + y, z: center.z - z },
    { x: center.x - x, y: center.y + y, z: center.z - z },
    { x: center.x - x, y: center.y - y, z: center.z + z },
    { x: center.x + x, y: center.y - y, z: center.z + z },
    { x: center.x + x, y: center.y + y, z: center.z + z },
    { x: center.x - x, y: center.y + y, z: center.z + z },
  ];
}

function drawBlock(
  ctx: CanvasRenderingContext2D,
  center: Point3,
  size: Point3,
  camera: { cx: number; cy: number; scale: number; yaw: number; pitch: number },
  color: string,
  alpha: number,
) {
  const p = boxCorners(center, size).map((point) =>
    project3D(point, camera.cx, camera.cy, camera.scale, camera.yaw, camera.pitch),
  );
  const faces: Array<{ indices: number[]; fill: string; a: number }> = [
    { indices: [0, 1, 2, 3], fill: color, a: 0.17 },
    { indices: [0, 1, 5, 4], fill: color, a: 0.29 },
    { indices: [1, 2, 6, 5], fill: color, a: 0.12 },
    { indices: [3, 2, 6, 7], fill: color, a: 0.2 },
  ];
  for (const face of faces) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = face.fill;
    ctx.beginPath();
    ctx.moveTo(p[face.indices[0]].x, p[face.indices[0]].y);
    for (let i = 1; i < face.indices.length; i += 1) ctx.lineTo(p[face.indices[i]].x, p[face.indices[i]].y);
    ctx.closePath();
    ctx.fillStyle = face.fill;
    ctx.globalAlpha = alpha * face.a;
    ctx.fill();
    ctx.globalAlpha = alpha * 0.92;
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.85;
    ctx.stroke();
    ctx.restore();
  }
}

function drawGate(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, cx: number, cy: number) {
  const scale = portrait ? 235 : 270;
  const yaw = 0.58 + Math.sin(frame * 0.0013) * 0.05;
  const pitch = 0.55 + Math.cos(frame * 0.0016) * 0.045;
  const corners = [
    { x: -1.18, y: -0.34, z: 0 }, { x: 1.18, y: -0.34, z: 0 },
    { x: 1.18, y: 0.34, z: 0 }, { x: -1.18, y: 0.34, z: 0 },
  ].map((point) => project3D(point, cx, cy, scale, yaw, pitch));
  const pulse = 0.72 + 0.2 * Math.sin(frame * 0.053);
  for (let i = 0; i < corners.length; i += 1) {
    strokeLine(ctx, corners[i], corners[(i + 1) % corners.length], EMERALD, 0.82 * pulse, 2.2);
  }
  for (const side of [-1, 1]) {
    const rayA = project3D({ x: side * 1.32, y: -0.34, z: 0 }, cx, cy, scale, yaw, pitch);
    const rayB = project3D({ x: side * 1.32, y: 0.34, z: 0 }, cx, cy, scale, yaw, pitch);
    strokeLine(ctx, rayA, rayB, EMERALD, 0.33, 0.75);
  }
  const labelY = cy + (portrait ? -194 : -168);
  if (portrait) {
    drawLabel(ctx, "[FORMAL VERIFIER: LEAN_4 PROOF]", cx, labelY, 30, EMERALD, 0.95);
    drawLabel(ctx, "// PASS · 100% DETERMINISTIC", cx, labelY + 39, 30, GOLD, 0.95);
  } else {
    drawLabel(ctx, "[FORMAL VERIFIER: LEAN_4 PROOF // PASS]", cx, labelY, 20, EMERALD, 0.95);
    drawLabel(ctx, "[UNIT TEST: 100% DETERMINISTIC]", cx, labelY + 28, 18, GOLD, 0.93);
  }
}

function drawStaircase(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, cx: number, cy: number, alpha = 1) {
  const scale = portrait ? 230 : 280;
  const yaw = 0.59 + frame * 0.0002 + Math.sin(frame * 0.0021) * 0.045;
  const pitch = 0.57 + Math.cos(frame * 0.0018) * 0.035;
  const stage = portrait ? { left: 65, right: 915, top: 450, bottom: 1240 } : { left: 100, right: 1820, top: 275, bottom: 850 };
  ctx.save();
  ctx.beginPath();
  ctx.rect(stage.left, stage.top, stage.right - stage.left, stage.bottom - stage.top);
  ctx.clip();
  const rise = (frame / 1200) * 0.14;
  const scroll = (frame * 0.005) % 1;
  drawGate(ctx, frame, portrait, cx, cy + (portrait ? 38 : 22));

  // The repeating step train advances through the rigid proof plane with a slight spiral camera flight.
  for (let i = 0; i < 18; i += 1) {
    const u = i + scroll;
    const lateral = (i - 8.5) * 0.08;
    const center: Point3 = {
      x: lateral + Math.sin(frame * 0.004 + i * 0.4) * 0.035,
      y: 0.68 - u * 0.075 - rise,
      z: -0.6 + u * 0.062 + Math.sin(i * 0.7) * 0.04,
    };
    const color = i % 4 === 0 ? GOLD : CYAN;
    drawBlock(ctx, center, { x: 0.48, y: 0.14, z: 0.32 }, { cx, cy, scale, yaw, pitch }, color, alpha);
  }

  // Red candidate branches hit the verifier plane, flare, then dissolve into deterministic sparks.
  const rejection = smooth(930, 1200, frame);
  for (let branch = 0; branch < 5; branch += 1) {
    const side = branch % 2 === 0 ? -1 : 1;
    const start: Point3 = { x: side * (0.5 + branch * 0.12), y: 0.56 - branch * 0.13, z: -1.08 + branch * 0.1 };
    const hit: Point3 = { x: side * (0.92 + branch * 0.035), y: -0.08 + branch * 0.06, z: 0 };
    const tail: Point3 = { x: hit.x + side * rejection * 0.48, y: hit.y - rejection * 0.38, z: 0.18 + rejection * 0.22 };
    const a = project3D(start, cx, cy, scale, yaw, pitch);
    const b = project3D(hit, cx, cy, scale, yaw, pitch);
    const c = project3D(tail, cx, cy, scale, yaw, pitch);
    strokeLine(ctx, a, b, RED, alpha * 0.76, 1.1);
    strokeLine(ctx, b, c, RED, alpha * (1 - rejection) * 0.9, 1.15);
    for (let k = 0; k < 5; k += 1) {
      const t = 0.25 + 0.15 * k;
      const flicker = 0.5 + 0.5 * Math.sin(frame * 0.075 + branch * 7 + k * 3.1);
      const x = mix(b.x, c.x, t) + Math.sin(frame * 0.045 + branch + k) * 7;
      const y = mix(b.y, c.y, t) + Math.cos(frame * 0.041 + k * 3) * 5;
      ctx.globalAlpha = alpha * (1 - rejection * 0.6) * flicker;
      ctx.fillStyle = RED;
      ctx.fillRect(x, y, 1.8, 1.8);
    }
  }
  ctx.globalAlpha = 1;
  ctx.restore();
}

function drawFogAndBoundary(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, cx: number, cy: number) {
  const left = portrait ? 65 : 100;
  const right = portrait ? 915 : 1820;
  const top = portrait ? 430 : 265;
  const bottom = portrait ? 1260 : 850;
  const enter = smooth(1200, 1380, frame);
  const yBoundary = portrait ? 760 : 540;

  ctx.save();
  ctx.globalAlpha = 0.24 * enter;
  ctx.strokeStyle = CYAN;
  ctx.lineWidth = 0.7;
  for (let i = 0; i < 16; i += 1) {
    const x0 = left + (right - left) * (i / 15);
    ctx.beginPath();
    ctx.moveTo(cx + (x0 - cx) * 0.08, yBoundary - 80);
    for (let k = 0; k <= 18; k += 1) {
      const t = k / 18;
      const y = yBoundary - 80 + t * (bottom - yBoundary + 80);
      const drift = Math.sin(frame * 0.012 + i * 1.13 + t * 5.7) * (8 + 22 * enter);
      ctx.lineTo(x0 + drift * t, y);
    }
    ctx.stroke();
  }
  ctx.restore();

  // Layered trigonometric fog is deterministic and low frequency, with no external texture dependency.
  ctx.save();
  ctx.globalCompositeOperation = "screen";
  for (let band = 0; band < 7; band += 1) {
    const yBase = mix(yBoundary - 30, bottom - 25, band / 6);
    const bandAlpha = enter * (0.035 + 0.025 * (0.5 + 0.5 * Math.sin(frame * 0.017 + band)));
    ctx.globalAlpha = bandAlpha;
    ctx.strokeStyle = band % 3 === 0 ? MAGENTA : band % 2 === 0 ? CYAN : "#557c8e";
    ctx.lineWidth = 18 + band * 2.5;
    ctx.beginPath();
    for (let k = 0; k <= 40; k += 1) {
      const t = k / 40;
      const x = mix(left, right, t);
      const y = yBase + Math.sin(t * 10.2 + frame * 0.008 + band * 1.9) * (14 + 8 * band) +
        Math.sin(t * 22 - frame * 0.005 + band) * 7;
      if (k === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  ctx.restore();

  const boundaryAlpha = smooth(1160, 1230, frame) * (1 - smooth(1640, 1800, frame) * 0.34);
  const lineAlpha = boundaryAlpha * (1 - smooth(1200, 1450, frame) * 0.82);
  strokeLine(ctx, { x: left, y: yBoundary }, { x: right, y: yBoundary }, GOLD, 0.8 * lineAlpha, 1.35);
  for (let i = 0; i < 25; i += 1) {
    const x = mix(left, right, i / 24);
    const tick = 5 + 4 * (0.5 + 0.5 * Math.sin(frame * 0.04 + i));
    strokeLine(ctx, { x, y: yBoundary - tick }, { x, y: yBoundary + tick }, i % 3 === 0 ? RED : GOLD, lineAlpha * 0.65, 0.8);
  }
  if (portrait) {
    drawLabel(ctx, "[BOUNDARY OF FORMALIZABLE PROBLEMS", cx, 1170, 30, GOLD, boundaryAlpha);
    drawLabel(ctx, "/ 形式化边界]", cx, 1208, 30, GOLD, boundaryAlpha);
  } else {
    drawLabel(ctx, "[BOUNDARY OF FORMALIZABLE PROBLEMS / 形式化边界]", cx, 790, 18, GOLD, boundaryAlpha);
  }

  // The formal world recedes as the title arrives; its geometry is still moving during the transition.
  const staircaseAlpha = 1 - smooth(1180, 1460, frame);
  if (staircaseAlpha > 0.01) drawStaircase(ctx, frame, portrait, cx, cy, staircaseAlpha);
  const rays = 24;
  ctx.save();
  ctx.globalAlpha = enter * 0.22;
  ctx.strokeStyle = MAGENTA;
  ctx.lineWidth = 0.8;
  for (let i = 0; i < rays; i += 1) {
    const x = left + (right - left) * (i / (rays - 1));
    const phase = frame * 0.0018 + i * 0.55;
    strokeLine(ctx, { x: cx, y: cy + Math.sin(phase) * 10 }, { x, y: mix(yBoundary, bottom, 0.62) }, MAGENTA, 0.5, 0.8);
  }
  ctx.restore();
  ctx.globalAlpha = 1;
}

function drawCore(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, color: string, frame: number, alpha = 1) {
  ctx.save();
  ctx.globalAlpha = alpha;
  const glow = ctx.createRadialGradient(x, y, 1, x, y, radius * 3.2);
  glow.addColorStop(0, color === MAGENTA ? "rgba(217, 70, 239, 0.45)" : color === CYAN ? "rgba(6, 182, 212, 0.44)" : "rgba(250, 204, 21, 0.45)");
  glow.addColorStop(0.42, color === MAGENTA ? "rgba(217, 70, 239, 0.12)" : color === CYAN ? "rgba(6, 182, 212, 0.12)" : "rgba(250, 204, 21, 0.13)");
  glow.addColorStop(1, "rgba(5, 8, 17, 0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(x, y, radius * 3.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.3;
  for (let ring = 0; ring < 4; ring += 1) {
    ctx.globalAlpha = alpha * (0.82 - ring * 0.14);
    ctx.beginPath();
    ctx.arc(x, y, radius * (0.5 + ring * 0.35), frame * 0.001 * (ring % 2 ? -1 : 1), Math.PI * 2 + frame * 0.001 * (ring % 2 ? -1 : 1));
    ctx.stroke();
  }
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, radius * 0.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawFigureEight(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, cx: number, cy: number) {
  const scale = portrait ? 250 : 340;
  const yaw = frame * 0.00105;
  const pitch = 0.2 + Math.sin(frame * 0.0028) * 0.12;
  const loops = [
    { color: CYAN, offset: 0, label: "GENERATOR" },
    { color: MAGENTA, offset: Math.PI, label: "INTERNAL REWARD MODEL" },
  ];
  for (const loop of loops) {
    const points: Point2[] = [];
    for (let i = 0; i <= 240; i += 1) {
      const t = (i / 240) * Math.PI * 2 + loop.offset;
      const time = t + frame * 0.0021;
      const p = project3D(
        { x: 0.98 * Math.sin(time), y: 0.56 * Math.sin(time * 2), z: 0.3 * Math.cos(time * 3 + frame * 0.001) },
        cx, cy, scale, yaw, pitch,
      );
      points.push(p);
    }
    strokePath(ctx, points, loop.color, 0.64, 1.65);
    for (let pulse = 0; pulse < 11; pulse += 1) {
      const t = ((frame * 0.027 + pulse / 11 + (loop.offset ? 0.5 : 0)) % 1) * Math.PI * 2;
      const p = project3D({ x: 0.98 * Math.sin(t), y: 0.56 * Math.sin(2 * t), z: 0.3 * Math.cos(3 * t + frame * 0.001) }, cx, cy, scale, yaw, pitch);
      ctx.globalAlpha = 0.6 + 0.4 * Math.sin(frame * 0.07 + pulse);
      ctx.fillStyle = loop.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, (portrait ? 5 : 4) + 2 * Math.sin(frame * 0.05 + pulse), 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
  drawCore(ctx, cx, cy, portrait ? 45 : 40, CYAN, frame, 0.95);
  for (const side of [-1, 1]) {
    const node=project3D({x:side*.72,y:side*.10,z:-side*.12},cx,cy,scale,yaw,pitch);
    drawCore(ctx,node.x,node.y,portrait?24:21,side<0?CYAN:MAGENTA,frame,.95);
  }
  const labelSize = portrait ? 31 : 19;
  drawLabel(ctx, "GENERATOR  ↔  INTERNAL REWARD MODEL", cx, cy + (portrait ? 190 : 166), labelSize, MAGENTA, 0.95);
  for (let i = 0; i < 8; i += 1) {
    const angle = (Math.PI * 2 * i) / 8 + frame * 0.002;
    const p = project3D({ x: Math.cos(angle) * 1.45, y: Math.sin(angle) * 0.78, z: Math.sin(angle * 3) * 0.3 }, cx, cy, scale, yaw, pitch);
    const q = project3D({ x: Math.cos(angle + 0.18) * 1.45, y: Math.sin(angle + 0.18) * 0.78, z: Math.sin((angle + 0.18) * 3) * 0.3 }, cx, cy, scale, yaw, pitch);
    strokeLine(ctx, p, q, i % 2 ? CYAN : MAGENTA, 0.8, 1.4);
  }
}

function drawBullseye(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, frame: number, color: string, label: string, portrait: boolean) {
  const pulse = 1 + 0.035 * Math.sin(frame * 0.055);
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(frame * 0.0016);
  ctx.strokeStyle = color;
  for (let ring = 0; ring < 5; ring += 1) {
    ctx.globalAlpha = 0.87 - ring * 0.12;
    ctx.lineWidth = ring === 0 ? 1.8 : 0.9;
    ctx.beginPath();
    ctx.arc(0, 0, radius * (0.24 + ring * 0.18) * pulse, 0, Math.PI * 2);
    ctx.stroke();
  }
  for (let i = 0; i < 12; i += 1) {
    const a = (i / 12) * Math.PI * 2;
    strokeLine(ctx, { x: Math.cos(a) * radius * 0.84, y: Math.sin(a) * radius * 0.84 }, { x: Math.cos(a) * radius, y: Math.sin(a) * radius }, color, 0.8, 1);
  }
  ctx.restore();
  ctx.globalAlpha = 1;
  drawFittedLabel(ctx, label, x, y + radius + (portrait ? 43 : 31), portrait ? 30 : 18, color, 0.96, portrait);
}

function drawTargetDrift(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const truePoint = portrait ? { x: 255, y: 1080 } : { x: 490, y: 735 };
  const proxyPoint = portrait ? { x: 755, y: 500 } : { x: 1445, y: 350 };
  const cx = portrait ? 490 : 960;
  const cy = portrait ? 830 : 560;
  const progress = smooth(2700, 3560, frame);
  drawBullseye(ctx, truePoint.x, truePoint.y, portrait ? 64 : 46, frame, AMBER, "[TRUE PHYSICAL OBJECTIVE / 真实物理目标]", portrait);
  drawBullseye(ctx, proxyPoint.x, proxyPoint.y, portrait ? 76 : 55, frame, MAGENTA, "[HACKED PROXY METRIC / 被劫持的代理指标]", portrait);

  const points: Point2[] = [];
  for (let i = 0; i <= 120; i += 1) {
    const t = i / 120;
    const drift = smooth(0.18, 0.88, t) * progress;
    const x = mix(truePoint.x, proxyPoint.x, t) + Math.sin(t * Math.PI) * (portrait ? 35 : 60) * drift;
    const y = mix(truePoint.y, proxyPoint.y, t) - Math.sin(t * Math.PI) * (portrait ? 200 : 165) * drift;
    const wobble = Math.sin(frame * 0.025 + t * 24) * (2 + 18 * drift);
    points.push({ x: x + wobble, y: y + Math.cos(frame * 0.021 + t * 19) * drift * 10 });
  }
  strokePath(ctx, points, MAGENTA, 0.72, portrait ? 2 : 1.5);
  // Amber intent fades while the optimization path bends toward the invented metric.
  strokeLine(ctx, truePoint, { x: cx, y: cy }, AMBER, 0.42 * (1 - progress), 1.1);
  const marker = points[Math.floor((0.22 + 0.66 * (0.5 + 0.5 * Math.sin(frame * 0.028))) * (points.length - 1))];
  drawCore(ctx, marker.x, marker.y, portrait ? 15 : 12, MAGENTA, frame, 0.93);

  // Fractal spikes branch recursively from the exploited score trajectory.
  const spikes = 86;
  for (let i = 0; i < spikes; i += 1) {
    const t = 0.18 + 0.78 * seeded(i + 27);
    const at = points[Math.floor(t * (points.length - 1))];
    const base = (portrait ? 14 : 12) + progress * (portrait ? 72 : 62) * seeded(i + 700);
    const angle = seeded(i + 900) * Math.PI * 2 + Math.sin(frame * 0.012 + i) * 0.22;
    const len = base * (0.55 + 0.45 * (0.5 + 0.5 * Math.sin(frame * 0.05 + i * 1.7)));
    const tip = { x: at.x + Math.cos(angle) * len, y: at.y + Math.sin(angle) * len };
    strokeLine(ctx, at, tip, i % 5 === 0 ? RED : MAGENTA, progress * 0.42, 0.8);
    if (i % 4 === 0 && progress > 0.18) {
      const mid = { x: mix(at.x, tip.x, 0.58), y: mix(at.y, tip.y, 0.58) };
      const childAngle = angle + (seeded(i + 2000) - 0.5) * 1.4;
      const child = { x: mid.x + Math.cos(childAngle) * len * 0.42, y: mid.y + Math.sin(childAngle) * len * 0.42 };
      strokeLine(ctx, mid, child, MAGENTA, progress * 0.32, 0.7);
    }
  }
  drawLabel(ctx, "REWARD SCORE: +999,999%", cx, portrait ? 780 : 365, portrait ? 34 : 23, GOLD, 0.95);
  drawLabel(ctx, "GOODHART'S LAW", cx, portrait ? 930 : 796, portrait ? 34 : 21, RED, 0.96);
}

function drawMobiusCathedral(
  ctx: CanvasRenderingContext2D,
  frame: number,
  cx: number,
  cy: number,
  scale: number,
  alpha: number,
  zoom = 1,
) {
  const yaw = frame * 0.00082 + 0.2;
  const pitch = 0.5 + Math.sin(frame * 0.0023) * 0.13;
  const countU = 170;
  const countV = 10;
  const radius = 0.72 * zoom;
  // A twisted ribbon wraps once through itself, with a raised impossible-stair rail around its outer edge.
  for (let rail = 0; rail < countV; rail += 1) {
    const v = (rail / (countV - 1) - 0.5) * 0.48;
    const points: Point2[] = [];
    for (let i = 0; i <= countU; i += 1) {
      const u = (i / countU) * Math.PI * 2 + frame * 0.0013;
      const r = radius + Math.cos(u / 2) * v;
      const p3: Point3 = {
        x: 1.18 * r * Math.cos(u),
        y: 0.82 * r * Math.sin(u) + 0.12 * Math.sin(u * 3 + frame * 0.002),
        z: 0.72 * Math.sin(u / 2) * v + 0.28 * Math.cos(u * 2 + v * 5),
      };
      points.push(project3D(p3, cx, cy, scale, yaw, pitch));
    }
    strokePath(ctx, points, rail % 3 === 0 ? GOLD : MAGENTA, alpha * (0.34 + 0.045 * rail), rail % 3 === 0 ? 1.3 : 0.85);
  }

  // Portal ribs add cathedral mass around the ribbon while preserving a clear impossible loop.
  const archCount = 12;
  const archShape: Array<[number, number]> = [
    [-0.21, 0.48], [-0.21, -0.13], [-0.16, -0.34], [0, -0.47],
    [0.16, -0.34], [0.21, -0.13], [0.21, 0.48],
  ];
  const openingShape: Array<[number, number]> = [
    [-0.105, 0.48], [-0.105, -0.13], [-0.075, -0.25], [0, -0.32],
    [0.075, -0.25], [0.105, -0.13], [0.105, 0.48],
  ];
  for (let arch = 0; arch < archCount; arch += 1) {
    const angle = (arch / archCount) * Math.PI * 2 + frame * 0.0013;
    const center = { x: 0.86 * Math.cos(angle), y: 0.3 * Math.sin(angle * 2), z: 0.63 * Math.sin(angle) };
    const tangent = { x: -Math.sin(angle), z: Math.cos(angle) };
    const normal = { x: Math.cos(angle), z: Math.sin(angle) };
    const toWorld = (point: [number, number], depth: number): Point3 => ({
      x: center.x + tangent.x * point[0] + normal.x * depth,
      y: center.y + point[1],
      z: center.z + tangent.z * point[0] + normal.z * depth,
    });
    const front = archShape.map((point) => project3D(toWorld(point, 0.09), cx, cy, scale, yaw, pitch));
    const back = archShape.map((point) => project3D(toWorld(point, -0.09), cx, cy, scale, yaw, pitch));
    const opening = openingShape.map((point) => project3D(toWorld(point, 0.095), cx, cy, scale, yaw, pitch));
    const color = arch % 4 === 0 ? GOLD : MAGENTA;
    const fill = arch % 4 === 0 ? "rgba(250, 204, 21, 0.28)" : "rgba(217, 70, 239, 0.28)";

    ctx.save();
    ctx.globalAlpha = alpha * 0.9;
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.moveTo(front[0].x, front[0].y);
    for (let i = 1; i < front.length; i += 1) ctx.lineTo(front[i].x, front[i].y);
    ctx.closePath();
    ctx.moveTo(opening[0].x, opening[0].y);
    for (let i = 1; i < opening.length; i += 1) ctx.lineTo(opening[i].x, opening[i].y);
    ctx.closePath();
    ctx.fill("evenodd");

    // Extruded side faces make the arches read as thick slabs, not orbit lines.
    for (let i = 0; i < front.length - 1; i += 1) {
      const shade = i % 2 === 0 ? 0.17 : 0.1;
      ctx.globalAlpha = alpha * shade;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(front[i].x, front[i].y);
      ctx.lineTo(front[i + 1].x, front[i + 1].y);
      ctx.lineTo(back[i + 1].x, back[i + 1].y);
      ctx.lineTo(back[i].x, back[i].y);
      ctx.closePath();
      ctx.fill();
    }
    ctx.globalAlpha = alpha * 0.95;
    ctx.strokeStyle = color;
    ctx.lineWidth = arch % 4 === 0 ? 2 : 1.45;
    ctx.beginPath();
    ctx.moveTo(front[0].x, front[0].y);
    for (let i = 1; i < front.length; i += 1) ctx.lineTo(front[i].x, front[i].y);
    ctx.stroke();
    ctx.restore();
  }

  // Repeated luminous treads connect the portals into an impossible staircase.
  const stairs = 28;
  for (let i = 0; i < stairs; i += 1) {
    const t = i / stairs;
    const angle = t * Math.PI * 2 + frame * 0.0013;
    const level = Math.sin(angle * 2) * 0.43;
    const center = { x: Math.cos(angle) * 0.92, y: level, z: Math.sin(angle) * 0.68 };
    const tangent = { x: -Math.sin(angle), y: 0, z: Math.cos(angle) };
    const n = { x: Math.cos(angle), y: 0, z: Math.sin(angle) };
    const corners3: Point3[] = [
      { x: center.x - tangent.x * 0.15, y: center.y - 0.045, z: center.z - tangent.z * 0.15 },
      { x: center.x + tangent.x * 0.15, y: center.y - 0.045, z: center.z + tangent.z * 0.15 },
      { x: center.x + tangent.x * 0.15 + n.x * 0.2, y: center.y - 0.045, z: center.z + tangent.z * 0.15 + n.z * 0.2 },
      { x: center.x - tangent.x * 0.15 + n.x * 0.2, y: center.y - 0.045, z: center.z - tangent.z * 0.15 + n.z * 0.2 },
    ];
    const corners = corners3.map((p) => project3D(p, cx, cy, scale, yaw, pitch));
    const color = i % 5 === 0 ? GOLD : MAGENTA;
    ctx.save();
    ctx.globalAlpha = alpha * 0.92;
    ctx.fillStyle = i % 5 === 0 ? "rgba(250, 204, 21, 0.48)" : "rgba(217, 70, 239, 0.52)";
    ctx.beginPath();
    ctx.moveTo(corners[0].x, corners[0].y);
    for (let k = 1; k < corners.length; k += 1) ctx.lineTo(corners[k].x, corners[k].y);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = alpha * 0.68;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(corners[0].x, corners[0].y);
    ctx.lineTo(corners[1].x, corners[1].y);
    ctx.stroke();
    ctx.restore();
    strokePath(ctx, corners, color, alpha, 1.25, true);
  }
  const center = project3D({ x: 0, y: 0, z: 0 }, cx, cy, scale, yaw, pitch);
  drawCore(ctx, center.x, center.y, 18 * zoom, MAGENTA, frame, alpha * 0.9);
}

function drawFracturedLattice(ctx: CanvasRenderingContext2D, frame: number, cx: number, cy: number, scale: number, alpha: number) {
  const cols = 15;
  const rows = 10;
  const collapse = smooth(3850, 4460, frame);
  const yaw = frame * 0.00036 + 0.42;
  const pitch = 0.65 + Math.sin(frame * 0.002) * 0.07;
  const points: Point2[] = [];
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const nx = (col / (cols - 1) - 0.5) * 2.1;
      const ny = (row / (rows - 1) - 0.5) * 1.45;
      const fracture = collapse * Math.max(0, (seeded(row * cols + col + 355) - 0.32) * 1.6);
      const displacement = Math.sin(frame * 0.018 + col * 1.8 + row) * fracture * 0.48;
      const p = project3D({ x: nx + displacement, y: ny + fracture * 0.24, z: Math.sin(col * 0.47 + row * 0.38 + frame * 0.006) * 0.12 }, cx, cy, scale, yaw, pitch);
      points.push(p);
    }
  }
  ctx.save();
  ctx.globalAlpha = alpha;
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const index = row * cols + col;
      const p = points[index];
      const broken = collapse > 0.18 && seeded(index + Math.floor(frame * 0.014)) < collapse * 0.56;
      if (col < cols - 1 && !broken) strokeLine(ctx, p, points[index + 1], collapse > 0.65 && seeded(index + 400) < collapse * 0.4 ? RED : AMBER, 0.47 * (1 - collapse * 0.28), 0.8);
      if (row < rows - 1 && !broken) strokeLine(ctx, p, points[index + cols], collapse > 0.7 && seeded(index + 800) < collapse * 0.4 ? RED : AMBER, 0.44 * (1 - collapse * 0.26), 0.75);
      if ((row + col) % 3 === 0 && !broken) {
        ctx.globalAlpha = alpha * (0.34 + 0.3 * (1 - collapse));
        ctx.fillStyle = collapse > 0.72 ? RED : AMBER;
        ctx.fillRect(p.x - 1.4, p.y - 1.4, 2.8, 2.8);
      }
    }
  }
  ctx.restore();

  for (let i = 0; i < 22; i += 1) {
    const x = cx + (seeded(i + 500) - 0.5) * scale * 1.65;
    const y = cy + (seeded(i + 900) - 0.5) * scale * 0.85;
    const len = collapse * (10 + seeded(i + 1400) * (scale * 0.25));
    const angle = seeded(i + 2000) * Math.PI * 2 + frame * 0.001;
    strokeLine(ctx, { x, y }, { x: x + Math.cos(angle) * len, y: y + Math.sin(angle) * len }, RED, collapse * 0.58, 1.2);
  }
}

function drawDivergenceCurve(ctx:CanvasRenderingContext2D,frame:number,x:number,y:number,w:number,h:number,ascending:boolean,portrait:boolean) {
  const progress=smooth(3600,4350,frame);
  const color=ascending?MAGENTA:AMBER;
  const dy=Math.sin(frame*.004)*4;
  const points:Point2[]=[];
  for(let i=0;i<=100;i++){
    const t=i/100*progress;
    const rise=ascending?Math.pow(t,4.2):1-Math.exp(-t*6);
    points.push({x:x+t*w,y:y+(ascending?h*(1-rise):h*rise)+dy+Math.sin(t*12+frame*.012)*2});
  }
  ctx.save();
  ctx.fillStyle='rgba(5,8,17,.35)';ctx.fillRect(x-10,y-10,w+20,h+24);
  strokeLine(ctx,{x,y:y+dy},{x,y:y+h+dy},'#8ba1b4',.25,1);
  strokeLine(ctx,{x,y:y+h+dy},{x:x+w,y:y+h+dy},'#8ba1b4',.25,1);
  strokePath(ctx,points,color,.98,portrait?3.1:2.5);
  const last=points[points.length-1];
  drawCore(ctx,last.x,last.y,portrait?9:7,color,frame,.92);
  ctx.font=`600 ${portrait?32:22}px ${MONO}`;ctx.textAlign='right';ctx.fillStyle=ascending?GOLD:AMBER;
  ctx.fillText(ascending?(progress>.85?'100% → ∞':'100%'):progress>.85?'0.02%':'REALITY',x+w,y+h+dy+(ascending?0:-14));
  ctx.restore();
}

function drawActThree(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const splitIn = smooth(3600, 3700, frame);
  const zoom = 1 + smooth(4460, 5400, frame) * 0.58;
  if (portrait) {
    const topCenter = { x: 490, y: 625 };
    const bottomCenter = { x: 490, y: 1080 };
    strokeLine(ctx, { x: 75, y: 850 }, { x: 905, y: 850 }, "#536575", splitIn * 0.45, 1);
    drawMobiusCathedral(ctx, frame, topCenter.x, topCenter.y, 180 * zoom, splitIn, zoom);
    drawFracturedLattice(ctx, frame, bottomCenter.x, bottomCenter.y, 193, splitIn);
    drawDivergenceCurve(ctx,frame,115,672,740,102,true,true);
    drawDivergenceCurve(ctx,frame,115,962,740,220,false,true);
    drawLabel(ctx, "SELF-REWARD → ∞", topCenter.x, 455, 31, MAGENTA, splitIn * 0.96);
    drawLabel(ctx, "REALITY ALIGNMENT → 0.02%", bottomCenter.x, 889, 30, AMBER, splitIn * 0.96);
    if (frame >= 3890 && frame < 5400) drawLabel(ctx, "MODE COLLAPSE: NARCISSISTIC EQUILIBRIUM", 490, 815, 30, MAGENTA, 0.92);
  } else {
    const leftCenter = { x: 510, y: 560 };
    const rightCenter = { x: 1420, y: 560 };
    strokeLine(ctx, { x: 960, y: 285 }, { x: 960, y: 835 }, "#536575", splitIn * 0.45, 1);
    drawMobiusCathedral(ctx, frame, leftCenter.x, leftCenter.y, 248 * zoom, splitIn, zoom);
    drawFracturedLattice(ctx, frame, rightCenter.x, rightCenter.y, 255, splitIn);
    drawDivergenceCurve(ctx,frame,160,619,665,143,true,false);
    drawDivergenceCurve(ctx,frame,1090,430,660,316,false,false);
    drawLabel(ctx, "SELF-REWARD → ∞", leftCenter.x, 315, 21, MAGENTA, splitIn * 0.96);
    drawLabel(ctx, "REALITY ALIGNMENT → 0.02%", rightCenter.x, 315, 19, AMBER, splitIn * 0.96);
    if (frame >= 3890 && frame < 5400) drawLabel(ctx, "MODE COLLAPSE: NARCISSISTIC EQUILIBRIUM", leftCenter.x, 810, 18, MAGENTA, 0.92);
  }
}

function drawAgentVortex(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, cx: number, cy: number) {
  const approach = smooth(4460, 5400, frame);
  const scale = (portrait ? 195 : 290) * (1 + approach * 0.48);
  const yaw = frame * 0.00092;
  const pitch = 0.52 + Math.sin(frame * 0.0024) * 0.12;
  const total = 1250;
  const magentaPoints: Point2[] = [];
  const goldPoints: Point2[] = [];
  const trails: Array<[Point2, Point2, string]> = [];
  for (let i = 0; i < total; i += 1) {
    const u = (i + 0.5) / total;
    const theta = i * GOLDEN_ANGLE + frame * (0.002 + approach * 0.0028);
    const radius = 0.13 + 1.22 * Math.sqrt(u);
    const wave = Math.sin(frame * 0.009 + i * 0.17) * 0.06;
    const p3 = {
      x: Math.cos(theta) * (radius + wave),
      y: Math.sin(theta) * (radius + wave) * 0.74,
      z: Math.sin(theta * 2 + i * 0.03 + frame * 0.003) * 0.45,
    };
    const p = project3D(p3, cx, cy, scale, yaw, pitch);
    const color = seeded(i + 770) < 0.16 ? GOLD : MAGENTA;
    (color === GOLD ? goldPoints : magentaPoints).push(p);
    if (i % 2 === 0) {
      const previous = project3D({ ...p3, x: p3.x * 0.965, y: p3.y * 0.965 }, cx, cy, scale, yaw, pitch);
      trails.push([previous, p, color]);
    }
  }
  ctx.save();
  ctx.globalAlpha = 0.24;
  ctx.lineWidth = 0.55;
  ctx.beginPath();
  for (const [a, b, color] of trails) {
    ctx.strokeStyle = color;
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
  }
  ctx.stroke();
  ctx.restore();
  for (const [points, color] of [[magentaPoints, MAGENTA], [goldPoints, GOLD]] as const) {
    ctx.save();
    ctx.fillStyle = color;
    ctx.globalAlpha = color === GOLD ? 0.87 : 0.74;
    for (let i = 0; i < points.length; i += 1) {
      const p = points[i];
      const r = (0.8 + seeded(i + 12700) * 1.4) * (0.85 + (p.depth ?? 1) * 0.2);
      ctx.fillRect(p.x, p.y, r, r);
    }
    ctx.restore();
  }
  drawMobiusCathedral(ctx, frame, cx, cy, (portrait ? 210 : 300) * (1 + approach * 0.15), 0.65, 1.02 + approach * 0.2);
  drawCore(ctx, cx, cy, portrait ? 26 : 22, MAGENTA, frame, 0.96);
  drawLabel(ctx, "Q.E.D. == Q.E.D.", cx, cy + (portrait ? 188 : 153), portrait ? 32 : 22, GOLD, 0.98);
  drawLabel(ctx, "AGENT INSTANCES  ·  CLOSED LOOP", cx, cy + (portrait ? 238 : 192), portrait ? 30 : 18, MAGENTA, 0.86);
}

function drawShards(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, cx: number, cy: number, alpha: number) {
  const age = frame - 5760;
  const stage = portrait ? { left: 72, right: 908, top: 435, bottom: 1255 } : { left: 105, right: 1815, top: 270, bottom: 845 };
  const count = 420;
  ctx.save();
  ctx.beginPath();
  ctx.rect(stage.left, stage.top, stage.right - stage.left, stage.bottom - stage.top);
  ctx.clip();
  for (let i = 0; i < count; i += 1) {
    const angle = seeded(i + 61) * Math.PI * 2;
    const speed = 4.4 + seeded(i + 300) * 9.6;
    const curve = Math.sin(age * 0.013 + i * 0.8) * (8 + seeded(i + 900) * 24);
    const x = cx + Math.cos(angle) * speed * age + Math.cos(angle + 1.2) * curve;
    const y = cy + Math.sin(angle) * speed * age + Math.sin(angle + 0.7) * curve + age * age * (0.00022 + seeded(i + 1500) * 0.00045);
    const fade = (1 - smooth(330, 540, age)) * alpha;
    const size = 2 + seeded(i + 800) * 8;
    const rotation = frame * 0.018 + i * 1.7;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rotation);
    ctx.globalAlpha = fade * (0.55 + 0.45 * seeded(i + 1700));
    ctx.fillStyle = i % 8 === 0 ? GOLD : i % 5 === 0 ? RED : MAGENTA;
    ctx.strokeStyle = ctx.fillStyle;
    ctx.lineWidth = 0.7;
    ctx.beginPath();
    ctx.moveTo(-size, -size * 0.32);
    ctx.lineTo(size * 0.56, -size);
    ctx.lineTo(size, size * 0.42);
    ctx.lineTo(-size * 0.48, size);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }
  ctx.restore();
}

function drawPhysicalVeto(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const cx = portrait ? 490 : 960;
  const cy = portrait ? 845 : 565;
  const age = frame - 5760;
  const dissolve = smooth(5760, 6030, frame);
  const baselineY = portrait ? 1165 : 755;

  if (frame < 5760) {
    drawMobiusCathedral(ctx, frame, cx, cy - 45, portrait ? 240 : 345, 0.94, 1.08);
    drawAgentVortex(ctx, frame, portrait, cx, cy);
    const beamEnd = cy + mix(portrait ? 275 : 225, 36, smooth(5400, 5758, frame));
    const beamTop = portrait ? 1260 : 846;
    const width = 1.2 + 2.4 * smooth(5700, 5758, frame);
    ctx.save();
    ctx.globalAlpha = 0.28 + 0.32 * smooth(5700, 5758, frame);
    ctx.fillStyle = "rgba(245, 158, 11, 0.18)";
    ctx.fillRect(cx - width * 2, beamEnd, width * 4, beamTop - beamEnd);
    ctx.fillStyle = AMBER;
    ctx.fillRect(cx - width / 2, beamEnd, width, beamTop - beamEnd);
    ctx.restore();
  } else {
    drawShards(ctx, frame, portrait, cx, cy, 1 - dissolve * 0.1);
  }

  // The strike is frame locked: a sub-frame transition makes frame 5760 the first full impact image.
  if (frame >= 5760 && frame < 5880) {
    const beamLife = 1 - smooth(5760, 5880, frame);
    const beamWidth = (portrait ? 31 : 36) * (1 - smooth(5760, 5840, frame) * 0.7);
    const beam = ctx.createLinearGradient(cx - beamWidth, 0, cx + beamWidth, 0);
    beam.addColorStop(0, "rgba(245,158,11,0)");
    beam.addColorStop(0.35, "rgba(245,158,11,0.64)");
    beam.addColorStop(0.5, "rgba(255,250,220,0.98)");
    beam.addColorStop(0.65, "rgba(245,158,11,0.72)");
    beam.addColorStop(1, "rgba(245,158,11,0)");
    ctx.save();
    ctx.globalAlpha = 0.94 * beamLife;
    ctx.fillStyle = beam;
    ctx.fillRect(cx - beamWidth, portrait ? 450 : 275, beamWidth * 2, (portrait ? 1240 : 850) - (portrait ? 450 : 275));
    const ringAlpha = 0.9 * (1 - smooth(116, 155, age));
    ctx.globalAlpha = ringAlpha;
    ctx.strokeStyle = age < 22 ? "#fff5c4" : AMBER;
    ctx.lineWidth = 2.2 + 1.4 * (1 - smooth(70, 140, age));
    ctx.beginPath();
    ctx.arc(cx, cy, 24 + age * 2.75, 0, Math.PI * 2);
    ctx.stroke();
    ctx.globalAlpha = ringAlpha * 0.62;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    ctx.arc(cx, cy, 15 + age * 1.95, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  strokeLine(ctx, { x: portrait ? 90 : 190, y: baselineY }, { x: portrait ? 890 : 1730, y: baselineY }, AMBER, 0.86, 1.8);
  for (let i = 0; i < 28; i += 1) {
    const x = (portrait ? 90 : 190) + ((portrait ? 800 : 1540) * i) / 27;
    const tick = i % 3 === 0 ? 8 : 4;
    strokeLine(ctx, { x, y: baselineY - tick }, { x, y: baselineY + tick }, AMBER, 0.46, 0.8);
  }
  const coreY = mix(cy + 35, baselineY - 195, smooth(5760, 5890, frame));
  const coreSize = frame < 5760 ? 22 : mix(30, portrait ? 35 : 31, dissolve);
  drawCore(ctx, cx, coreY, coreSize, GOLD, frame, frame < 5760 ? 0.58 : 1);
  if (frame >= 5790) {
    drawLabel(ctx, "REALITY CALIBRATION RESTORED", cx, coreY + (portrait ? 93 : 72), portrait ? 32 : 20, GOLD, smooth(5790, 5840, frame));
  }
  drawLabel(ctx, "[PHYSICAL WORLD EXPERIMENT // ATOMIC VETO]", cx, portrait ? 1225 : 820, portrait ? 30 : 18, AMBER, frame < 5760 ? 0.82 : smooth(5790, 5840, frame));
}

function drawPendulum(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const cx = portrait ? 490 : 960;
  const cy = portrait ? 990 : 650;
  const angle = Math.sin(frame * 0.011) * 0.47;
  const length = portrait ? 300 : 260;
  const pivot = { x: cx, y: cy - length };
  const bob = { x: cx + Math.sin(angle) * length, y: cy - length + Math.cos(angle) * length };
  const t = smooth(6300, 6930, frame);
  strokeLine(ctx, pivot, bob, AMBER, 0.58 + 0.18 * Math.sin(frame * 0.025), 1.4);
  for (let i = 0; i < 4; i += 1) {
    const phase = frame * (0.003 + i * 0.0006);
    ctx.save();
    ctx.translate(cx, cy - 20);
    ctx.rotate(phase * (i % 2 ? -1 : 1));
    ctx.globalAlpha = 0.26 + i * 0.1;
    ctx.strokeStyle = i % 2 === 0 ? GOLD : CYAN;
    ctx.lineWidth = 0.9;
    ctx.beginPath();
    ctx.ellipse(0, 0, (portrait ? 94 : 115) + i * 28, (portrait ? 40 : 32) + i * 12, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
  drawCore(ctx, cx, cy - 20, (portrait ? 39 : 35) * (1 + 0.04 * Math.sin(frame * 0.034)), GOLD, frame, 1);
  ctx.save();
  ctx.globalAlpha = 0.95;
  ctx.fillStyle = AMBER;
  ctx.beginPath();
  ctx.arc(bob.x, bob.y, portrait ? 12 : 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  drawLabel(ctx, "REALITY CALIBRATION RESTORED", cx, portrait ? 1205 : 816, portrait ? 30 : 18, GOLD, t);
}

function drawEarthThermal(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const cx = portrait ? 490 : 960;
  const cy = portrait ? 990 : 555;
  const radius = portrait ? 165 : 250;
  const yaw = frame * 0.006 + 0.4;
  const pitch = 0.34 + Math.sin(frame * 0.002) * 0.08;
  const hot = smooth(7010, 7180, frame);
  const earthColor = hot > 0.55 ? "#fff2cf" : CYAN;

  const glow = ctx.createRadialGradient(cx, cy, radius * 0.2, cx, cy, radius * 1.9);
  glow.addColorStop(0, `rgba(245, 158, 11, ${0.12 + 0.22 * hot})`);
  glow.addColorStop(0.55, `rgba(217, 70, 239, ${0.035 + 0.1 * hot})`);
  glow.addColorStop(1, "rgba(5,8,17,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(cx - radius * 2, cy - radius * 2, radius * 4, radius * 4);

  // Rotating latitude and longitude lines form the planet; an outer orbit denotes the compute shell.
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(frame * 0.0012);
  ctx.strokeStyle = earthColor;
  ctx.lineWidth = 0.9;
  ctx.globalAlpha = 0.52 + 0.18 * Math.sin(frame * 0.028);
  for (let lat = -4; lat <= 4; lat += 1) {
    const ratio = lat / 5;
    ctx.beginPath();
    ctx.ellipse(0, ratio * radius * 0.58, radius * Math.sqrt(1 - ratio * ratio) * (1 + hot * 0.04), Math.max(7, radius * (0.19 + 0.12 * Math.abs(ratio))), 0, 0, Math.PI * 2);
    ctx.stroke();
  }
  for (let lon = 0; lon < 10; lon += 1) {
    const angle = (lon / 10) * Math.PI + yaw;
    ctx.save();
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.ellipse(0, 0, radius * (0.19 + hot * 0.04), radius, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
  ctx.globalAlpha = 0.72;
  ctx.strokeStyle = hot > 0.65 ? "#fff8df" : AMBER;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.ellipse(0, 0, radius * 1.55, radius * 0.46, -0.22 + Math.sin(frame * 0.001) * 0.06, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.ellipse(0, 0, radius * 1.4, radius * 0.88, 0.52, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();

  const heatPoints: Point2[] = [];
  for (let i = 0; i < 110; i += 1) {
    const a = i * GOLDEN_ANGLE + frame * 0.003;
    const r = radius * (1.17 + 0.52 * seeded(i + 30));
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r * 0.72;
    heatPoints.push({ x, y });
  }
  ctx.save();
  ctx.globalAlpha = 0.25 + 0.52 * hot;
  ctx.fillStyle = hot > 0.62 ? "#fff4db" : AMBER;
  for (let i = 0; i < heatPoints.length; i += 1) {
    const p = heatPoints[i];
    const pulse = 1 + 1.8 * (0.5 + 0.5 * Math.sin(frame * 0.12 + i));
    ctx.fillRect(p.x, p.y, pulse, pulse);
  }
  ctx.restore();
  for (let i = 0; i < 18; i += 1) {
    const a = frame * 0.004 + i * GOLDEN_ANGLE;
    const start = { x: cx + Math.cos(a) * radius * 1.22, y: cy + Math.sin(a) * radius * 0.58 };
    const end = { x: cx + Math.cos(a) * radius * (1.52 + 0.12 * Math.sin(frame * 0.018 + i)), y: cy + Math.sin(a) * radius * (0.73 + 0.12 * Math.cos(frame * 0.017 + i)) };
    strokeLine(ctx, start, end, hot > 0.66 ? WHITE : AMBER, 0.3 + 0.55 * hot, 1.2 + hot);
  }
}

function drawWorld(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const cx = portrait ? 490 : 960;
  const cy = portrait ? 835 : 560;
  drawBackground(ctx, portrait ? 1080 : 1920, portrait ? 1920 : 1080, frame);

  const safe = portrait ? { left: 65, right: 915, top: 430, bottom: 1260 } : { left: 100, right: 1820, top: 265, bottom: 850 };
  ctx.save();
  ctx.beginPath();
  ctx.rect(safe.left, safe.top, safe.right - safe.left, safe.bottom - safe.top);
  ctx.clip();

  if (frame < 1200) {
    drawStaircase(ctx, frame, portrait, cx, cy);
  } else if (frame < 1800) {
    drawFogAndBoundary(ctx, frame, portrait, cx, cy);
  } else if (frame < 2700) {
    drawFigureEight(ctx, frame, portrait, cx, cy);
  } else if (frame < 3600) {
    drawTargetDrift(ctx, frame, portrait);
  } else if (frame < 4500) {
    drawActThree(ctx, frame, portrait);
  } else if (frame < 5400) {
    drawAgentVortex(ctx, frame, portrait, cx, cy);
  } else if (frame < 6300) {
    drawPhysicalVeto(ctx, frame, portrait);
  } else if (frame < 6930) {
    drawPendulum(ctx, frame, portrait);
  } else {
    drawEarthThermal(ctx, frame, portrait);
  }

  // Low-contrast reticle corners articulate the shared safe composition without occupying HUD bands.
  const pulse = 0.11 + 0.06 * (0.5 + 0.5 * Math.sin(frame * 0.03));
  const corners: Array<[number, number, number, number]> = [
    [safe.left, safe.top, 1, 1], [safe.right, safe.top, -1, 1],
    [safe.left, safe.bottom, 1, -1], [safe.right, safe.bottom, -1, -1],
  ];
  for (const [x, y, sx, sy] of corners) {
    strokeLine(ctx, { x, y }, { x: x + sx * 22, y }, CYAN, pulse, 0.8);
    strokeLine(ctx, { x, y }, { x, y: y + sy * 22 }, CYAN, pulse, 0.8);
  }
  ctx.restore();
}

export const CanvasWorld: React.FC<CanvasWorldProps> = ({ frame, portrait, width, height }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const logicalWidth = portrait ? 1080 : 1920;
    const logicalHeight = portrait ? 1920 : 1080;
    const outputWidth = Math.max(1, Math.round(width));
    const outputHeight = Math.max(1, Math.round(height));
    if (canvas.width !== outputWidth) canvas.width = outputWidth;
    if (canvas.height !== outputHeight) canvas.height = outputHeight;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
    ctx.setLineDash([]);
    ctx.setTransform(outputWidth / logicalWidth, 0, 0, outputHeight / logicalHeight, 0, 0);
    ctx.clearRect(0, 0, logicalWidth, logicalHeight);
    drawWorld(ctx, frame, portrait);
  }, [frame, portrait, width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ width: "100%", height: "100%", display: "block" }}
      aria-hidden="true"
    />
  );
};
