import React, { useLayoutEffect, useRef } from "react";

type CanvasWorldProps = {
  frame: number;
  portrait: boolean;
  width: number;
  height: number;
};

type Point = { x: number; y: number; z: number };

const AMBER = "#f59e0b";
const CYAN = "#06b6d4";
const RED = "#ef4444";
const GOLD = "#facc15";
const VOID = "#050811";
const MAGENTA = "#ec4899";
const CHINESE_FONT = '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
const MONO_FONT = 'Menlo, "SFMono-Regular", Consolas, monospace';
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value));
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
  point: Point,
  cx: number,
  cy: number,
  scale: number,
  yaw: number,
  pitch: number,
): { x: number; y: number; depth: number } {
  const cyaw = Math.cos(yaw);
  const syaw = Math.sin(yaw);
  const cpitch = Math.cos(pitch);
  const spitch = Math.sin(pitch);
  const x1 = point.x * cyaw - point.z * syaw;
  const z1 = point.x * syaw + point.z * cyaw;
  const y1 = point.y * cpitch - z1 * spitch;
  const z2 = point.y * spitch + z1 * cpitch;
  const depth = 4.1 / (4.1 - z2);
  return { x: cx + x1 * scale * depth, y: cy + y1 * scale * depth, depth };
}

function text(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  size: number,
  color: string,
  alpha = 1,
  mono = false,
  align: CanvasTextAlign = "center",
) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.font = "600 " + size + "px " + (mono ? MONO_FONT : CHINESE_FONT);
  ctx.textAlign = align;
  ctx.textBaseline = "middle";
  ctx.fillText(value, x, y);
  ctx.restore();
}

function tag(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  size: number,
  color: string,
  alpha = 1,
  mono = false,
) {
  ctx.save();
  ctx.font = "600 " + size + "px " + (mono ? MONO_FONT : CHINESE_FONT);
  const width = ctx.measureText(value).width + 20;
  const height = size + 14;
  ctx.globalAlpha = alpha;
  ctx.fillStyle = "rgba(5, 8, 17, 0.82)";
  ctx.fillRect(x - width / 2, y - height / 2, width, height);
  ctx.strokeStyle = color;
  ctx.lineWidth = 0.8;
  ctx.globalAlpha = alpha * 0.48;
  ctx.strokeRect(x - width / 2, y - height / 2, width, height);
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(value, x, y);
  ctx.restore();
}

function line(
  ctx: CanvasRenderingContext2D,
  a: { x: number; y: number },
  b: { x: number; y: number },
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

function drawBackground(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  frame: number,
) {
  ctx.fillStyle = VOID;
  ctx.fillRect(0, 0, width, height);

  const glow = ctx.createRadialGradient(width * 0.5, height * 0.46, 20, width * 0.5, height * 0.46, width * 0.7);
  glow.addColorStop(0, "rgba(8, 25, 42, 0.54)");
  glow.addColorStop(0.55, "rgba(6, 13, 26, 0.24)");
  glow.addColorStop(1, "rgba(5, 8, 17, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  for (let i = 0; i < 250; i += 1) {
    const x = seeded(i + 3) * width;
    const y = seeded(i + 1003) * height;
    const twinkle = 0.22 + 0.2 * (0.5 + 0.5 * Math.sin(frame * 0.018 + i * 2.1));
    const size = i % 29 === 0 ? 1.35 : 0.7;
    ctx.globalAlpha = twinkle;
    ctx.fillStyle = i % 7 === 0 ? "#54b9d0" : "#c4d6e8";
    ctx.fillRect(x, y, size, size);
  }
  ctx.globalAlpha = 1;

  // Fine static raster texture keeps large flat fields from reading as a dead black card.
  for (let i = 0; i < 120; i += 1) {
    const x = seeded(i + 4000) * width;
    const y = seeded(i + 5000) * height;
    ctx.globalAlpha = 0.055;
    ctx.fillStyle = i % 2 === 0 ? "#7aa6ba" : "#263548";
    ctx.fillRect(x, y, 1, 1);
  }
  ctx.globalAlpha = 1;
}

function drawSkull(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, color: string, alpha: number, phase: number) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(phase);
  ctx.globalAlpha = alpha;

  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(0.8, radius * 0.12);
  ctx.beginPath();
  ctx.arc(0, 0, radius * 1.8, 0, Math.PI * 2);
  ctx.stroke();
  ctx.globalAlpha = alpha * 0.72;
  ctx.setLineDash([radius * 0.44, radius * 0.48]);
  ctx.beginPath();
  ctx.arc(0, 0, radius * 2.45, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.globalAlpha = alpha;
  ctx.fillStyle = "rgba(245, 158, 11, 0.12)";
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(0.8, radius * 0.11);
  ctx.beginPath();
  ctx.arc(0, -radius * 0.12, radius, Math.PI * 1.07, Math.PI * 1.93);
  ctx.quadraticCurveTo(radius * 0.94, radius * 0.9, radius * 0.45, radius * 1.03);
  ctx.lineTo(-radius * 0.45, radius * 1.03);
  ctx.quadraticCurveTo(-radius * 0.94, radius * 0.9, -radius, -radius * 0.12);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(-radius * 0.34, radius * 0.05, Math.max(0.65, radius * 0.16), 0, Math.PI * 2);
  ctx.arc(radius * 0.34, radius * 0.05, Math.max(0.65, radius * 0.16), 0, Math.PI * 2);
  ctx.fill();
  ctx.lineWidth = Math.max(0.65, radius * 0.1);
  ctx.beginPath();
  ctx.moveTo(-radius * 0.34, radius * 0.67);
  ctx.lineTo(radius * 0.34, radius * 0.67);
  ctx.stroke();
  ctx.restore();
}

function drawMaster(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, color: string, alpha: number, rotation: number) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rotation);
  ctx.globalAlpha = alpha;

  const glow = ctx.createRadialGradient(0, 0, 2, 0, 0, radius * 2.4);
  glow.addColorStop(0, color === RED ? "rgba(239, 68, 68, 0.48)" : "rgba(245, 158, 11, 0.36)");
  glow.addColorStop(0.36, color === RED ? "rgba(239, 68, 68, 0.12)" : "rgba(245, 158, 11, 0.11)");
  glow.addColorStop(1, "rgba(5, 8, 17, 0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(0, 0, radius * 2.4, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  for (let ring = 0; ring < 4; ring += 1) {
    const r = radius * (0.45 + ring * 0.27);
    ctx.globalAlpha = alpha * (0.92 - ring * 0.13);
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.stroke();
  }
  for (let i = 0; i < 24; i += 1) {
    const a = (Math.PI * 2 * i) / 24;
    const inner = radius * (i % 3 === 0 ? 0.48 : 0.76);
    const outer = radius * (i % 3 === 0 ? 1.28 : 1.02);
    ctx.globalAlpha = alpha * (i % 3 === 0 ? 0.92 : 0.46);
    ctx.lineWidth = i % 3 === 0 ? 1.35 : 0.8;
    ctx.beginPath();
    ctx.moveTo(Math.cos(a) * inner, Math.sin(a) * inner);
    ctx.lineTo(Math.cos(a) * outer, Math.sin(a) * outer);
    ctx.stroke();
  }
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(0, 0, radius * 0.22, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawIslands(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, phase: "islands" | "title") {
  const cx = portrait ? 480 : 960;
  const cy = portrait ? 820 : 550;
  const death = smooth(1018, 1098, frame);
  const collapse = smooth(1020, 1200, frame);
  const titleProgress = phase === "title" ? smooth(1200, 1780, frame) : 0;
  const recede = phase === "title" ? titleProgress : 0;
  const yaw = 0.18 + frame * 0.00042;
  const pitch = (phase === "title" ? 0.96 : 0.13) + Math.sin(frame * 0.0023) * 0.025;
  const scale = (portrait ? 250 : 310) * (1 - recede * 0.42);
  const shiftY = (phase === "title" ? (portrait ? 300 : 170) : 0) * recede;
  const positions: Array<{ x: number; y: number; z: number }> = [];

  for (let i = 0; i < 60; i += 1) {
    const theta = (i / 60) * Math.PI * 2 + frame * 0.00017;
    const ring = i % 5;
    const radial = 0.62 + ring * 0.14 + seeded(i + 22) * 0.09;
    const collapseScale = 1;
    const x = Math.cos(theta) * radial * (portrait ? 0.9 : 1.24) * collapseScale;
    const y = Math.sin(theta) * radial * 0.9 * collapseScale;
    const z = Math.sin(theta * 2.9 + i * 0.7 + frame * 0.001) * 0.38;
    positions.push({ x, y, z });
  }

  // Dashed low-bandwidth signals decay before reaching the next isolated brain.
  for (let i = 0; i < 60; i += 1) {
    const a = project3D(positions[i], cx, cy + shiftY, scale, yaw, pitch);
    const b = project3D(positions[(i + 1) % 60], cx, cy + shiftY, scale, yaw, pitch);
    const signal = (1 - death) * (0.12 + 0.12 * (0.5 + 0.5 * Math.sin(frame * 0.025 + i * 1.8)));
    ctx.save();
    ctx.globalAlpha = signal;
    ctx.strokeStyle = "#b88b4a";
    ctx.lineWidth = 0.75;
    ctx.setLineDash([3, 5]);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    ctx.setLineDash([]);
    for (let k = 0; k < 3; k += 1) {
      const t = 0.3 + 0.12 * k;
      const jitter = Math.sin(frame * 0.035 + i * 7 + k * 3) * 3;
      ctx.globalAlpha = signal * 0.6 * (1 - death);
      ctx.fillStyle = "#98a2aa";
      ctx.fillRect(mix(a.x, b.x, t) + jitter, mix(a.y, b.y, t) - jitter * 0.45, 1.6, 1.6);
    }
    ctx.restore();
  }

  for (let i = 0; i < 60; i += 1) {
    const p = project3D(positions[i], cx, cy + shiftY, scale, yaw, pitch);
    const fade = phase === "title" ? 1 - recede * 0.34 : 1;
    drawSkull(ctx, p.x, p.y, 3.1 + seeded(i + 70) * 1.6, AMBER, fade * (phase === "title" ? 0.68 : 1), frame * 0.00025 + i * 0.04);
  }

  if (phase === "islands") {
    const masterX = cx;
    const masterY = cy - 4;
    const color = frame >= 1020 ? RED : AMBER;
    const masterScale = mix(1, 0.05, collapse);
    const flash = frame >= 1018 && frame < 1040 ? 1 + 0.35 * Math.sin(frame * 1.9) : 1;
    drawMaster(ctx, masterX, masterY, 38 * masterScale * flash, color, 1 - collapse * 0.86, frame * 0.0012);

    if (frame < 1018) {
      tag(ctx, "人类宗师 · 60年直觉积累", cx, cy - 104, 16, AMBER, 0.93);
    } else if (frame < 1200) {
      tag(ctx, "寿命终止  //  记忆未继承", cx, cy - 104, portrait ? 22 : 18, RED, 0.96);
      const babyX = cx + (portrait ? 100 : 128);
      const babyY = cy + 100;
      const babyPulse = 1 + 0.16 * Math.sin(frame * 0.08);
      drawSkull(ctx, babyX, babyY, 4.1 * babyPulse, AMBER, 1, frame * 0.004);
      tag(ctx, "KNOWLEDGE: 0.0%", babyX, babyY + 31, portrait ? 30 : 18, GOLD, 0.98, true);
    }

    const labels: Array<[number, string, number, number]> = [
      [4, "量子物理", cx - (portrait ? 170 : 220), cy - 176],
      [19, "分子生物学", cx + (portrait ? 165 : 220), cy - 142],
      [34, "拓扑数学", cx - (portrait ? 168 : 220), cy + 160],
      [49, "流体力学", cx + (portrait ? 170 : 220), cy + 170],
    ];
    for (const [index, labelText, x, y] of labels) {
      const p = project3D(positions[index], cx, cy, scale, yaw, pitch);
      line(ctx, p, { x, y: y + (y < cy ? 17 : -17) }, AMBER, 0.34 * (1 - death));
      tag(ctx, labelText, x, y, portrait ? 39 : 20, AMBER, 0.92 * (1 - death * 0.65));
    }
  } else {
    drawOpticalGrid(ctx, frame, portrait, recede);
  }
}

function drawOpticalGrid(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, progress: number) {
  const left = portrait ? 60 : 150;
  const right = portrait ? 900 : 1770;
  const horizon = (portrait ? 1010 : 660) + 45 * Math.sin(frame * 0.014);
  const bottom = portrait ? 1310 : 890;
  const alpha = 0.12 + 0.16 * (0.5 + 0.5 * Math.sin(frame * 0.035));
  ctx.save();
  ctx.strokeStyle = CYAN;
  ctx.lineWidth = 0.85;
  ctx.globalAlpha = alpha * (1 - progress * 0.25);
  for (let i = 0; i < 21; i += 1) {
    const t = i / 20;
    const x = mix(left, right, t);
    ctx.beginPath();
    ctx.moveTo((portrait ? 480 : 960) + (x - (portrait ? 480 : 960)) * 0.04, horizon);
    ctx.lineTo(x + Math.sin(frame * 0.01 + i) * 10, bottom);
    ctx.stroke();
  }
  for (let i = 0; i < 13; i += 1) {
    const t = (i + 1) / 14;
    const y = horizon + (bottom - horizon) * t * t;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();
  }
  ctx.restore();
}

function agentPoint(index: number, total: number, frame: number, portrait: boolean, flying: number): Point {
  const u = (index + 0.5) / total;
  const theta = index * GOLDEN_ANGLE + frame * (0.0012 + flying * 0.0025);
  const radius = 0.16 + 1.23 * Math.sqrt(u);
  const shell = Math.sin(index * 0.41) * 0.43 + Math.cos(index * 0.17) * 0.2;
  const drift = Math.sin(frame * 0.005 + index * 0.11) * (0.025 + flying * 0.07);
  return {
    x: Math.cos(theta) * (radius + drift) * (portrait ? 0.9 : 1.0),
    y: Math.sin(theta) * (radius + drift) * (portrait ? 0.88 : 0.8),
    z: shell + Math.sin(theta * 2 + frame * 0.002) * 0.18,
  };
}

function drawHex(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, color: string, alpha: number, rotation: number, upgraded = false) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rotation);
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.fillStyle = upgraded ? "rgba(250, 204, 21, 0.19)" : "rgba(6, 182, 212, 0.12)";
  ctx.lineWidth = upgraded ? 1.35 : 0.85;
  ctx.beginPath();
  const sides = upgraded ? 6 : 6;
  for (let i = 0; i < sides; i += 1) {
    const a = (Math.PI * 2 * i) / sides;
    const px = Math.cos(a) * radius;
    const py = Math.sin(a) * radius;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  if (upgraded) {
    ctx.fillStyle = GOLD;
    ctx.globalAlpha = alpha * 0.95;
    ctx.beginPath();
    ctx.arc(0, 0, Math.max(0.8, radius * 0.24), 0, Math.PI * 2);
    ctx.fill();
  } else {
    ctx.globalAlpha = alpha * 0.75;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(0, 0, Math.max(0.55, radius * 0.17), 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawSwarm(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const cx = portrait ? 480 : 960;
  const cy = portrait ? 820 : 550;
  if (frame < 1920) {
    drawMaster(ctx, cx, cy, 27 + 3 * Math.sin(frame * 0.04), CYAN, smooth(1800, 1920, frame), frame * 0.002);
    return;
  }
  const scale = portrait ? 252 : 318;
  const yaw = frame * 0.00055 + Math.sin(frame * 0.003) * 0.08;
  const pitch = 0.16 + Math.cos(frame * 0.0027) * 0.11;
  const prune = smooth(3000, 3160, frame);
  const dissolve = smooth(3000, 3370, frame);
  const fly = smooth(2640, 3600, frame);
  const count = 900;
  const projected: Array<{ x: number; y: number; depth: number }> = [];
  const survivor = (i: number) => i % 50 >= 47;

  for (let i = 0; i < count; i += 1) {
    const p = agentPoint(i, count, frame, portrait, fly);
    projected.push(project3D(p, cx, cy, scale, yaw, pitch));
  }

  // Sparse structural links reveal the layered lattice without burying the individual hexagons.
  ctx.save();
  ctx.strokeStyle = CYAN;
  ctx.lineWidth = 0.55;
  ctx.globalAlpha = frame < 3000 ? 0.13 : 0.09 * (1 - dissolve);
  for (let i = 0; i < count; i += 1) {
    for (const offset of [1, 9]) {
      const j = (i + offset) % count;
      if (i % 3 !== 0) continue;
      ctx.beginPath();
      ctx.moveTo(projected[i].x, projected[i].y);
      ctx.lineTo(projected[j].x, projected[j].y);
      ctx.stroke();
    }
  }
  ctx.restore();

  for (let i = 0; i < count; i += 1) {
    const p = projected[i];
    const isSurvivor = survivor(i);
    const pulse = 0.82 + 0.18 * Math.sin(frame * 0.036 + i * 1.9);
    const radius = (2.65 + 1.45 * seeded(i + 800)) * (0.82 + 0.22 * p.depth);
    if (frame < 3000) {
      drawHex(ctx, p.x, p.y, radius, CYAN, 0.77 * pulse, frame * 0.0007 + i * 0.013);
    } else if (isSurvivor) {
      drawHex(ctx, p.x, p.y, radius * (1 + prune * 0.18), GOLD, 0.98 * pulse, frame * 0.001 + i * 0.013, true);
    } else {
      const alpha = 0.84 * (1 - dissolve);
      if (alpha > 0.025) {
        drawHex(ctx, p.x + Math.sin(i * 9.1 + frame * 0.11) * dissolve * 15, p.y - dissolve * (12 + seeded(i) * 48), radius, RED, alpha, frame * 0.002 + i * 0.013);
      }
      if (frame >= 3000 && frame < 3150 && i % 5 === 0) {
        ctx.save();
        ctx.globalAlpha = (1 - (frame - 3000) / 150) * 0.86;
        ctx.fillStyle = RED;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.5 + seeded(i + frame) * 1.4, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }
  }

  const rootAlpha = frame < 1920 ? smooth(1800, 1920, frame) : 1;
  const rootColor = frame >= 6000 ? GOLD : CYAN;
  drawMaster(ctx, cx, cy, 27 + 3 * Math.sin(frame * 0.04), rootColor, rootAlpha, frame * 0.002);
  tag(ctx, frame < 3000 ? "ROOT SI WEIGHTS" : "94% PRUNED  ·  6% OPTIMAL", cx, cy + (portrait ? 72 : 70), frame < 3000 ? (portrait ? 30 : 20) : (portrait ? 24 : 18), frame < 3000 ? CYAN : GOLD, 0.95, true);

  if (frame >= 1920 && frame < 2500) {
    const nearIndices = [4, 11, 18, 27];
    for (let i = 0; i < nearIndices.length; i += 1) {
      const p = projected[nearIndices[i]];
      text(ctx, "100%", p.x + 14, p.y - 10, portrait ? 16 : 12, CYAN, 0.9, true);
    }
  }

  if (frame >= 2640 && frame < 3020) {
    const top = portrait ? 470 : 295;
    const offset = portrait ? 205 : 260;
    const labels = ["晶格配比 #8921", "蛋白折叠 #4012", "湍流闭合 #1109"];
    for (let i = 0; i < labels.length; i += 1) {
      const x = cx + (i - 1) * offset;
      const y = top + (portrait && i === 1 ? 45 : 0);
      tag(ctx, labels[i], x, y, portrait ? 10 : 12, i === 2 ? GOLD : CYAN, 0.9, true);
    }
  }

  if (frame >= 3000) {
    const beamAlpha = smooth(3000, 3060, frame) * (0.55 + 0.24 * Math.sin(frame * 0.06));
    for (let i = 0; i < count; i += 1) {
      if (!survivor(i)) continue;
      const a = projected[i];
      const b = projected[(i + 431) % count];
      line(ctx, a, b, GOLD, beamAlpha * 0.3, 0.65);
    }
    if (frame < 3240) {
      const flash = 1 - (frame - 3000) / 240;
      text(ctx, "PRUNED: DEAD END", cx, cy - (portrait ? 170 : 205), portrait ? 13 : 16, RED, flash, true);
    }
  }
}

function drawHumanSpecialists(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean, alpha: number) {
  const cx = portrait ? 480 : 480;
  const cy = portrait ? 560 : 560;
  const scaleX = portrait ? 130 : 156;
  const scaleY = portrait ? 132 : 132;
  const names = ["流体力学", "量子化学", "基因编辑", "编译架构"];
  const points = [
    { x: -1, y: -0.76, z: 0.18 },
    { x: 0.96, y: -0.78, z: -0.15 },
    { x: -0.96, y: 0.72, z: -0.08 },
    { x: 1, y: 0.72, z: 0.22 },
  ];
  const positions = points.map((p) => ({ x: cx + p.x * scaleX, y: cy + p.y * scaleY, z: p.z }));
  const collision = smooth(3720, 3810, frame) * (1 - smooth(3910, 4090, frame));

  ctx.save();
  ctx.globalAlpha = alpha * 0.48;
  ctx.strokeStyle = AMBER;
  ctx.lineWidth = 1.3;
  for (let i = 0; i < positions.length; i += 1) {
    const a = positions[i];
    const b = positions[(i + 1) % positions.length];
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    for (let k = 1; k <= 9; k += 1) {
      const t = k / 10;
      const jag = Math.sin(frame * 0.045 + i * 9 + k * 4) * 7;
      ctx.lineTo(mix(a.x, b.x, t) + jag, mix(a.y, b.y, t) - jag * 0.7);
    }
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  const left = positions[0];
  const right = positions[1];
  const c1 = { x: cx, y: cy - 75 + Math.sin(frame * 0.038) * 9 };
  const c2 = { x: cx, y: cy + 78 + Math.cos(frame * 0.041) * 10 };
  ctx.globalAlpha = alpha * 0.7;
  ctx.strokeStyle = RED;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  ctx.moveTo(left.x, left.y);
  ctx.lineTo(c1.x, c1.y);
  ctx.lineTo(right.x, right.y);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(positions[2].x, positions[2].y);
  ctx.lineTo(c2.x, c2.y);
  ctx.lineTo(positions[3].x, positions[3].y);
  ctx.stroke();

  if (collision > 0.02) {
    for (let i = 0; i < 22; i += 1) {
      const angle = i * GOLDEN_ANGLE + frame * 0.08;
      const radius = collision * (10 + (i % 7) * 4);
      ctx.globalAlpha = alpha * collision * (0.35 + 0.55 * seeded(i + frame * 2));
      ctx.fillStyle = i % 3 === 0 ? "#ff9868" : RED;
      ctx.beginPath();
      ctx.arc(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius, 1.2 + seeded(i + 300) * 1.8, 0, Math.PI * 2);
      ctx.fill();
    }
    tag(ctx, "PROTOCOL MISMATCH  //  学科巴别塔", cx, cy + 5, portrait ? 9 : 11, RED, alpha * collision, true);
  }
  ctx.restore();

  for (let i = 0; i < positions.length; i += 1) {
    const p = positions[i];
    drawSkull(ctx, p.x, p.y, 8, AMBER, alpha, frame * 0.002 + i * 0.4);
    const labelOffsetX = portrait ? (p.x < cx ? -125 : 125) : (p.x < cx ? -6 : 6);
    const labelOffsetY = portrait ? 0 : (p.y < cy ? -30 : 31);
    tag(ctx, names[i], p.x + labelOffsetX, p.y + labelOffsetY, portrait ? 39 : 20, AMBER, alpha);
  }
  text(ctx, "同室 · 无法同步", cx, cy + (portrait ? 170 : 178), portrait ? 10 : 13, AMBER, alpha * 0.8);
}

function drawMesh(
  ctx: CanvasRenderingContext2D,
  frame: number,
  portrait: boolean,
  cx: number,
  cy: number,
  alpha: number,
  upgraded: boolean,
) {
  const cols = 18;
  const rows = 13;
  const points: Array<{ x: number; y: number; nx: number; ny: number }> = [];
  const scale = portrait ? 200 : 335;
  const heightSpread = portrait ? 1.16 : 1.42;
  const yaw = frame * 0.0007 + 0.15;
  const pitch = 0.18 + Math.sin(frame * 0.003) * 0.07;

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const nx = (col / (cols - 1) - 0.5) * 2.05;
      const ny = (row / (rows - 1) - 0.5) * heightSpread;
      const z = Math.sin(col * 0.43 + frame * 0.009) * 0.09 + Math.cos(row * 0.55 + col * 0.13) * 0.06;
      const p = project3D({ x: nx, y: ny, z }, cx, cy, scale, yaw, pitch);
      points.push({ x: p.x, y: p.y, nx, ny });
    }
  }

  const sourceX = 1.025;
  const sourceY = portrait ? -heightSpread / 2 : -0.71;
  const shockProgress = clamp((frame - 4560) / 15);
  const maxDistance = Math.hypot(2.05, heightSpread);
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.lineWidth = upgraded ? 0.8 : 0.65;
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const i = row * cols + col;
      const p = points[i];
      const distance = Math.hypot(p.nx - sourceX, p.ny - sourceY);
      const isGold = upgraded && distance <= maxDistance * shockProgress + 0.001;
      const color = isGold ? GOLD : CYAN;
      if (col < cols - 1) {
        const q = points[i + 1];
        ctx.globalAlpha = alpha * (upgraded && !isGold ? 0.14 : 0.34);
        ctx.strokeStyle = color;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
        ctx.stroke();
      }
      if (row < rows - 1) {
        const q = points[i + cols];
        ctx.globalAlpha = alpha * (upgraded && !isGold ? 0.13 : 0.3);
        ctx.strokeStyle = color;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
        ctx.stroke();
      }
      ctx.globalAlpha = alpha * (upgraded && !isGold ? 0.27 : 0.88);
      drawHex(ctx, p.x, p.y, upgraded && isGold ? 4.2 : 3.3, color, alpha * (upgraded && !isGold ? 0.28 : 0.88), frame * 0.001 + i * 0.05, upgraded && isGold);
    }
  }
  ctx.restore();

  if (frame >= 4560) {
    const wave = shockProgress * (portrait ? 155 : 267);
    ctx.save();
    ctx.globalAlpha = (1 - shockProgress) * 0.9;
    ctx.strokeStyle = GOLD;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.arc(cx + scale * 0.34, cy - scale * 0.23, wave, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
}

function drawSplitScene(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const humanAlpha = 1 - smooth(4440, 4620, frame) * 0.88;
  const meshAlpha = frame < 4440 ? 0.24 : mix(0.24, 1, smooth(4440, 4560, frame));
  if (portrait) {
    // Vertical adaptation: specialists remain above the optical hive, within the world safe zone.
    drawHumanSpecialists(ctx, frame, true, humanAlpha);
    drawMesh(ctx, frame, true, 480, 1020, meshAlpha, frame >= 4560);
    tag(ctx, "SI  ·  GLOBAL TENSOR SYNC", 480, 843, 30, frame >= 4560 ? GOLD : CYAN, 0.95, true);
  } else {
    const dividerAlpha = 0.22 + 0.08 * Math.sin(frame * 0.018);
    line(ctx, { x: 960, y: 270 }, { x: 960, y: 820 }, "#5b7585", dividerAlpha, 1);
    drawHumanSpecialists(ctx, frame, false, humanAlpha);
    drawMesh(ctx, frame, false, 1440, 555, meshAlpha, frame >= 4560);
    tag(ctx, "HUMAN  ·  MISMATCH", 480, 315, 20, AMBER, 0.92, true);
    tag(ctx, "SI  ·  GLOBAL TENSOR SYNC", 1440, 315, 20, frame >= 4560 ? GOLD : CYAN, 0.95, true);
    if (frame >= 4560) {
      tag(ctx, "GLOBAL TENSOR SYNC  ·  0.0004 ms", 1440, 840, 20, GOLD, smooth(4560, 4590, frame), true);
    } else {
      tag(ctx, "1024 TB/s  ·  ZERO-LATENCY MESH", 1440, 840, 16, CYAN, meshAlpha, true);
    }
  }
}

function drawVortex(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  if (frame >= 6000) return;
  const cx = portrait ? 480 : 960;
  const cy = portrait ? 820 : 550;
  const collapse = smooth(5970, 6000, frame);
  const approach = 1 - smooth(5400, 5970, frame) * 0.3;
  const yaw = frame * 0.0008;
  const pitch = 0.16 + Math.sin(frame * 0.002) * 0.14;
  const scale = portrait ? 200 : 320;
  const count = 1800;
  const cyanTrails: Array<[number, number, number, number]> = [];
  const goldTrails: Array<[number, number, number, number]> = [];
  const goldRatio = mix(0.23, 0.42, smooth(5800, 6000, frame));

  for (let i = 0; i < count; i += 1) {
    const u = (i + 0.5) / count;
    const theta = i * GOLDEN_ANGLE + Math.log(0.12 + u) * 3.8 + frame * 0.002;
    const latitudeY = 1 - 2 * u;
    const latitudeRadius = Math.sqrt(Math.max(0, 1 - latitudeY * latitudeY));
    const baseRadius = 0.18 + 1.07 * Math.sqrt(u);
    const radius = baseRadius * approach * (1 - collapse * 0.985);
    const point = {
      x: Math.cos(theta) * latitudeRadius * radius,
      y: latitudeY * radius,
      z: Math.sin(theta) * latitudeRadius * radius,
    };
    const p = project3D(point, cx, cy, scale, yaw, pitch);
    const color = seeded(i + 3000) < goldRatio ? GOLD : CYAN;
    const previousTheta = theta - 0.045;
    const previous = project3D({
      x: Math.cos(previousTheta) * latitudeRadius * radius * 0.985,
      y: latitudeY * radius * 0.985,
      z: Math.sin(previousTheta) * latitudeRadius * radius * 0.985,
    }, cx, cy, scale, yaw, pitch);
    (color === GOLD ? goldTrails : cyanTrails).push([previous.x, previous.y, p.x, p.y]);
    const alpha = 0.36 + 0.52 * seeded(i + 3000);
    const r = 0.85 + 1.35 * seeded(i + 9000);
    ctx.globalAlpha = alpha * (1 - collapse * 0.35);
    ctx.fillStyle = color;
    ctx.fillRect(p.x, p.y, r * p.depth, r * p.depth);
  }
  for (const [trails, color, alpha] of [[cyanTrails, CYAN, 0.27], [goldTrails, GOLD, 0.38]] as const) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    for (const [x1, y1, x2, y2] of trails) {
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
    }
    ctx.stroke();
    ctx.restore();
  }
  ctx.globalAlpha = 1;

}

function icosahedronVertices(): Point[] {
  const phi = (1 + Math.sqrt(5)) / 2;
  return [
    { x: 0, y: -1, z: -phi }, { x: 0, y: -1, z: phi }, { x: 0, y: 1, z: -phi }, { x: 0, y: 1, z: phi },
    { x: -1, y: -phi, z: 0 }, { x: -1, y: phi, z: 0 }, { x: 1, y: -phi, z: 0 }, { x: 1, y: phi, z: 0 },
    { x: -phi, y: 0, z: -1 }, { x: -phi, y: 0, z: 1 }, { x: phi, y: 0, z: -1 }, { x: phi, y: 0, z: 1 },
  ];
}

function dodecahedronVertices(): Point[] {
  const phi = (1 + Math.sqrt(5)) / 2;
  const inv = 1 / phi;
  const points: Point[] = [];
  for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) points.push({ x, y, z });
  for (const a of [-1, 1]) for (const b of [-1, 1]) {
    points.push({ x: 0, y: a * inv, z: b * phi });
    points.push({ x: a * inv, y: b * phi, z: 0 });
    points.push({ x: a * phi, y: 0, z: b * inv });
  }
  return points;
}

function drawPolyhedron(ctx: CanvasRenderingContext2D, vertices: Point[], cx: number, cy: number, scale: number, yaw: number, pitch: number, edgeLength: number, color: string, alpha: number, width: number) {
  const projected = vertices.map((v) => project3D(v, cx, cy, scale, yaw, pitch));
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  for (let i = 0; i < vertices.length; i += 1) {
    for (let j = i + 1; j < vertices.length; j += 1) {
      const dx = vertices[i].x - vertices[j].x;
      const dy = vertices[i].y - vertices[j].y;
      const dz = vertices[i].z - vertices[j].z;
      if (Math.hypot(dx, dy, dz) > edgeLength) continue;
      ctx.beginPath();
      ctx.moveTo(projected[i].x, projected[i].y);
      ctx.lineTo(projected[j].x, projected[j].y);
      ctx.stroke();
    }
  }
  ctx.fillStyle = color;
  for (const p of projected) {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2.2 * p.depth, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawSacredCore(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const cx = portrait ? 480 : 960;
  const cy = portrait ? 820 : 550;
  const yaw = frame * 0.004 + 0.22;
  const pitch = 0.43 + Math.sin(frame * 0.003) * 0.13;
  const pulse = 1 + 0.035 * Math.sin(frame * 0.055);

  const glowRadius = portrait ? 280 : 340;
  const glow = ctx.createRadialGradient(cx, cy, 2, cx, cy, glowRadius);
  glow.addColorStop(0, "rgba(250, 204, 21, 0.34)");
  glow.addColorStop(0.18, "rgba(250, 204, 21, 0.16)");
  glow.addColorStop(0.62, "rgba(6, 182, 212, 0.035)");
  glow.addColorStop(1, "rgba(5, 8, 17, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(cx - glowRadius, cy - glowRadius, glowRadius * 2, glowRadius * 2);

  // Thin deterministic rays give a volumetric impression without per-particle blur.
  ctx.save();
  ctx.globalAlpha = 0.12;
  ctx.strokeStyle = GOLD;
  ctx.lineWidth = 1;
  for (let i = 0; i < 56; i += 1) {
    const a = (Math.PI * 2 * i) / 56 + frame * 0.0009;
    const inner = 68 + 12 * Math.sin(frame * 0.014 + i);
    const outer = (portrait ? 320 : 400) + 12 * Math.sin(i * 1.7 + frame * 0.004);
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner);
    ctx.lineTo(cx + Math.cos(a) * outer, cy + Math.sin(a) * outer);
    ctx.stroke();
  }
  ctx.restore();

  drawPolyhedron(ctx, icosahedronVertices(), cx, cy, (portrait ? 125 : 150) * pulse, yaw, pitch, 2.05, GOLD, 0.94, 1.5);
  drawPolyhedron(ctx, dodecahedronVertices(), cx, cy, (portrait ? 105 : 123) * pulse, -yaw * 0.73, pitch + 0.32, 1.28, "#fff0a8", 0.8, 1.05);
  drawPolyhedron(ctx, icosahedronVertices(), cx, cy, (portrait ? 68 : 81) * pulse, yaw * 1.7, -pitch, 2.05, CYAN, 0.82, 0.9);

  ctx.save();
  ctx.globalAlpha = 0.95;
  ctx.fillStyle = GOLD;
  ctx.beginPath();
  ctx.arc(cx, cy, 7 + 1.5 * Math.sin(frame * 0.06), 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawMobius(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const cx = portrait ? 480 : 960;
  const cy = portrait ? 820 : 550;
  const yaw = frame * 0.018;
  const pitch = 0.43 + Math.sin(frame * 0.035) * 0.13;
  const scale = portrait ? 150 : 185;
  const points: Array<Array<{ x: number; y: number }>> = [];
  const samples = 144;
  const strips = 9;

  for (let j = 0; j < strips; j += 1) {
    const v = -0.34 + (0.68 * j) / (strips - 1);
    const row: Array<{ x: number; y: number }> = [];
    for (let i = 0; i <= samples; i += 1) {
      const t = (Math.PI * 2 * i) / samples;
      const twist = t * 0.5;
      const radius = 1 + (v * 0.5) * Math.cos(twist);
      const x = radius * Math.cos(t);
      const y = radius * Math.sin(t);
      const z = (v * 0.5) * Math.sin(twist);
      row.push(project3D({ x, y, z }, cx, cy, scale, yaw, pitch));
    }
    points.push(row);
  }

  for (let j = 0; j < points.length; j += 1) {
    ctx.save();
    ctx.globalAlpha = j === 0 || j === points.length - 1 ? 0.95 : 0.34;
    ctx.strokeStyle = j % 3 === 0 ? RED : MAGENTA;
    ctx.lineWidth = j === 0 || j === points.length - 1 ? 1.8 : 0.8;
    ctx.beginPath();
    for (let i = 0; i < points[j].length; i += 1) {
      if (i === 0) ctx.moveTo(points[j][i].x, points[j][i].y);
      else ctx.lineTo(points[j][i].x, points[j][i].y);
    }
    ctx.stroke();
    ctx.restore();
  }

  for (let i = 0; i <= samples; i += 12) {
    const t = (Math.PI * 2 * i) / samples;
    const row = i % 24 === 0 ? points[0] : points[points.length - 1];
    const p = row[i];
    const q = row[Math.min(i + 2, samples)];
    line(ctx, p, q, i % 24 === 0 ? RED : MAGENTA, 0.9, 1.05);
    const glitch = Math.sin(frame * 0.8 + i * 3.7);
    if (Math.abs(glitch) > 0.92) {
      ctx.save();
      ctx.globalAlpha = 0.62;
      ctx.fillStyle = i % 2 === 0 ? RED : MAGENTA;
      ctx.fillRect(p.x + glitch * 9, p.y, 4 + Math.abs(glitch) * 5, 1.6);
      ctx.restore();
    }
    void t;
  }

  // A broken three-sided impossible frame hints at a verifier loop around the self-crossing surface.
  const triYaw = -frame * 0.009;
  const triangle = [
    project3D({ x: -0.72, y: -0.58, z: 0.2 }, cx, cy, scale * 1.38, triYaw, pitch),
    project3D({ x: 0.73, y: -0.52, z: -0.1 }, cx, cy, scale * 1.38, triYaw, pitch),
    project3D({ x: 0.02, y: 0.78, z: 0.13 }, cx, cy, scale * 1.38, triYaw, pitch),
  ];
  ctx.save();
  ctx.globalAlpha = 0.36;
  ctx.strokeStyle = RED;
  ctx.lineWidth = 3;
  for (let i = 0; i < 3; i += 1) {
    if ((Math.floor(frame / 5) + i) % 3 === 1) continue;
    ctx.beginPath();
    ctx.moveTo(triangle[i].x, triangle[i].y);
    ctx.lineTo(triangle[(i + 1) % 3].x, triangle[(i + 1) % 3].y);
    ctx.stroke();
  }
  ctx.restore();

  // Deterministic horizontal slices shear selected bands as the loop glitches.
  const slice = Math.floor(frame / 7) % 6;
  const y = cy - 122 + slice * 47;
  const offset = Math.sin(frame * 0.41) * 18;
  ctx.save();
  ctx.globalAlpha = 0.72;
  ctx.fillStyle = "rgba(239, 68, 68, 0.12)";
  ctx.fillRect(cx - 210, y, 420, 7);
  ctx.strokeStyle = MAGENTA;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx - 190 + offset, y + 3);
  ctx.lineTo(cx + 190 + offset, y + 3);
  ctx.stroke();
  ctx.restore();
}

function drawFinale(ctx: CanvasRenderingContext2D, frame: number, portrait: boolean) {
  const cliff = smooth(6930, 6970, frame);
  if (cliff < 1) drawSacredCore(ctx, frame, portrait);

  ctx.save();
  ctx.globalAlpha = cliff;
  if (cliff > 0.01) drawMobius(ctx, frame, portrait);
  ctx.restore();

  if (frame >= 6930) {
    // Small deterministic scan flecks imply the external verifier has gone offline.
    for (let i = 0; i < 32; i += 1) {
      const x = (seeded(i + 900) * (portrait ? 700 : 1450)) + (portrait ? 130 : 235);
      const y = (seeded(i + 2000) * (portrait ? 650 : 560)) + (portrait ? 475 : 270);
      const active = (i + Math.floor(frame / 3)) % 7 === 0;
      if (!active) continue;
      ctx.globalAlpha = 0.7;
      ctx.fillStyle = i % 2 === 0 ? RED : MAGENTA;
      ctx.fillRect(x, y, 2 + (i % 3), 1.4);
    }
    ctx.globalAlpha = 1;
  }
}

export const CanvasWorld: React.FC<CanvasWorldProps> = ({ frame, portrait, width, height }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;
    const logicalWidth = portrait ? 1080 : 1920;
    const logicalHeight = portrait ? 1920 : 1080;
    ctx.setTransform(width / logicalWidth, 0, 0, height / logicalHeight, 0, 0);
    ctx.clearRect(0, 0, logicalWidth, logicalHeight);

    drawBackground(ctx, logicalWidth, logicalHeight, frame);

    if (frame < 1200) {
      drawIslands(ctx, frame, portrait, "islands");
    } else if (frame < 1800) {
      drawIslands(ctx, frame, portrait, "title");
    } else if (frame < 3600) {
      drawSwarm(ctx, frame, portrait);
    } else if (frame < 5400) {
      drawSplitScene(ctx, frame, portrait);
    } else if (frame < 6000) {
      drawVortex(ctx, frame, portrait);
    } else {
      drawVortex(ctx, frame, portrait);
      drawFinale(ctx, frame, portrait);
    }
  }, [frame, portrait, width, height]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        display: "block",
      }}
    />
  );
};
