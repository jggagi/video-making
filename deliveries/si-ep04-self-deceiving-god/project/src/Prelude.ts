const CYAN = "#06b6d4";
const EMERALD = "#10b981";
const AMBER = "#f59e0b";
const MAGENTA = "#d946ef";
const GOLD = "#facc15";
const RED = "#ef4444";
const VOID = "#050811";

type Box = { x: number; y: number; w: number; h: number };
type Point = { x: number; y: number };

const clamp = (v: number, lo = 0, hi = 1): number => Math.max(lo, Math.min(hi, v));
const smooth = (v: number): number => {
  const t = clamp(v);
  return t * t * (3 - 2 * t);
};
const fract = (v: number): number => v - Math.floor(v);
const shortSide = (b: Box): number => Math.min(b.w, b.h);

function drawBackdrop(ctx: CanvasRenderingContext2D, b: Box, frame: number, warmth = 0) {
  const bg = ctx.createLinearGradient(b.x, b.y, b.x + b.w * 0.22, b.y + b.h);
  bg.addColorStop(0, VOID);
  bg.addColorStop(0.6, warmth > 0 ? `rgb(7, 8, ${17 + Math.round(5 * warmth)})` : "#070a13");
  bg.addColorStop(1, "#02040a");
  // The full-frame world provides the void; avoid a visible rectangular matte.

  const vignette = ctx.createRadialGradient(
    b.x + b.w * 0.5,
    b.y + b.h * 0.43,
    shortSide(b) * 0.08,
    b.x + b.w * 0.5,
    b.y + b.h * 0.5,
    shortSide(b) * 0.72,
  );
  vignette.addColorStop(0, "rgba(0,0,0,0)");
  vignette.addColorStop(1, "rgba(0,0,0,0.56)");
  // Keep the vignette off the rectangular object viewport.

  // Fixed, indexed stars drift imperceptibly with the shot. No random source is used.
  ctx.fillStyle = "rgba(120, 181, 207, 0.33)";
  for (let i = 0; i < 58; i += 1) {
    const sx = b.x + fract(Math.sin(i * 127.1 + 2.4) * 43758.5453) * b.w;
    const sy = b.y + fract(Math.sin(i * 311.7 + 8.1) * 24634.6345) * b.h;
    const drift = (frame * (0.00005 + (i % 4) * 0.000012)) % 1;
    const y = b.y + ((sy - b.y + b.h * drift) % b.h);
    const r = i % 9 === 0 ? 1.7 : 0.8;
    ctx.globalAlpha = 0.35 + 0.35 * (0.5 + 0.5 * Math.sin(frame * 0.012 + i));
    ctx.beginPath();
    ctx.arc(sx, y, r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function glow(ctx: CanvasRenderingContext2D, color: string, blur: number, alpha = 1) {
  ctx.shadowColor = color;
  ctx.shadowBlur = blur;
  ctx.globalAlpha = alpha;
}

function text(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  size: number,
  color: string,
  align: CanvasTextAlign = "center",
  alpha = 1,
  weight = 650,
) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.font = `${weight} ${size}px ui-sans-serif, system-ui, -apple-system, "Arial", sans-serif`;
  ctx.textAlign = align;
  ctx.textBaseline = "middle";
  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 0;
  ctx.fillText(value, x, y);
  ctx.restore();
}

function projectTower(
  x: number,
  y: number,
  z: number,
  b: Box,
  cameraY: number,
  yaw: number,
  unit: number,
): Point {
  const c = Math.cos(yaw);
  const s = Math.sin(yaw);
  const depth = x * s + z * c;
  const screenSide = x * c - z * s;
  const perspective = 5.6 / (5.6 + depth * 0.42);
  const verticalUnit = unit * 0.65;
  return {
    x: b.x + b.w * 0.5 + screenSide * unit * perspective,
    y: b.y + b.h * 0.53 - (y - cameraY) * verticalUnit * perspective + depth * unit * 0.13,
  };
}

function drawTower(ctx: CanvasRenderingContext2D, b: Box, frame: number, alpha: number) {
  if (alpha <= 0.005) return;
  const unit = shortSide(b) * 0.12;
  const cameraY = frame / 15;
  const height = 6 + frame / 15;
  const yaw = 0.33 + frame * 0.00033;
  const first = Math.max(0, Math.floor(cameraY - 5.6));
  const last = Math.min(Math.ceil(height), Math.ceil(cameraY + 5.8));
  const sides = [-1, 1];

  ctx.save();
  ctx.globalAlpha = alpha;
  // Deep faces give the open lattice weight without obscuring its clean silhouette.
  for (let level = first; level < last; level += 1) {
    const p00 = projectTower(-1.8, level, -1.8, b, cameraY, yaw, unit);
    const p10 = projectTower(1.8, level, -1.8, b, cameraY, yaw, unit);
    const p11 = projectTower(1.8, level + 1, -1.8, b, cameraY, yaw, unit);
    const p01 = projectTower(-1.8, level + 1, -1.8, b, cameraY, yaw, unit);
    ctx.fillStyle = level % 2 === 0 ? "rgba(6,182,212,0.045)" : "rgba(16,185,129,0.028)";
    ctx.beginPath();
    ctx.moveTo(p00.x, p00.y);
    ctx.lineTo(p10.x, p10.y);
    ctx.lineTo(p11.x, p11.y);
    ctx.lineTo(p01.x, p01.y);
    ctx.closePath();
    ctx.fill();
  }

  // A low-cost shadow pass separates front struts from the darker rear lattice.
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = "rgba(0, 12, 28, 0.92)";
  ctx.lineWidth = Math.max(6, unit * 0.12);
  ctx.beginPath();
  for (let level = first; level <= last; level += 1) {
    for (const x of sides) {
      for (const z of sides) {
        const p = projectTower(x * 1.8, level, z * 1.8, b, cameraY, yaw, unit);
        if (level < last) {
          const q = projectTower(x * 1.8, level + 1, z * 1.8, b, cameraY, yaw, unit);
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
        }
      }
    }
  }
  ctx.stroke();

  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  glow(ctx, CYAN, 14, alpha);
  ctx.strokeStyle = CYAN;
  ctx.lineWidth = Math.max(1.8, unit * 0.023);
  ctx.beginPath();
  for (let level = first; level <= last; level += 1) {
    for (const x of sides) {
      for (const z of sides) {
        const p = projectTower(x * 1.1, level, z * 1.1, b, cameraY, yaw, unit);
        if (level < last) {
          const q = projectTower(x * 1.1, level + 1, z * 1.1, b, cameraY, yaw, unit);
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
        }
      }
    }
    if (level < last) {
      const corners = [
        [-1.8, -1.8],
        [1.8, -1.8],
        [1.8, 1.8],
        [-1.8, 1.8],
      ] as const;
      for (let side = 0; side < 4; side += 1) {
        const [x1, z1] = corners[side];
        const [x2, z2] = corners[(side + 1) % 4];
        const p = projectTower(x1, level, z1, b, cameraY, yaw, unit);
        const q = projectTower(x2, level, z2, b, cameraY, yaw, unit);
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
      }
      // Cross bracing on each face makes the tower read as an engineered scaffold.
      const facePairs: Array<[[number, number], [number, number]]> = [
        [[-1.8, -1.8], [1.8, -1.8]],
        [[1.8, -1.8], [1.8, 1.8]],
        [[1.8, 1.8], [-1.8, 1.8]],
        [[-1.8, 1.8], [-1.8, -1.8]],
      ];
      for (const [[x1, z1], [x2, z2]] of facePairs) {
        const a = projectTower(x1, level, z1, b, cameraY, yaw, unit);
        const d = projectTower(x2, level, z2, b, cameraY, yaw, unit);
        const c = projectTower(x2, level + 1, z2, b, cameraY, yaw, unit);
        const e = projectTower(x1, level + 1, z1, b, cameraY, yaw, unit);
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(c.x, c.y);
        ctx.moveTo(d.x, d.y);
        ctx.lineTo(e.x, e.y);
      }
    }
  }
  ctx.stroke();
  ctx.shadowBlur = 0;

  const topY = Math.floor(height);
  const top = [
    projectTower(-1.8, topY, -1.8, b, cameraY, yaw, unit),
    projectTower(1.8, topY, -1.8, b, cameraY, yaw, unit),
    projectTower(1.8, topY, 1.8, b, cameraY, yaw, unit),
    projectTower(-1.8, topY, 1.8, b, cameraY, yaw, unit),
  ];
  glow(ctx, GOLD, 18, alpha);
  ctx.strokeStyle = GOLD;
  ctx.lineWidth = Math.max(3, unit * 0.052);
  ctx.beginPath();
  ctx.moveTo(top[0].x, top[0].y);
  for (let i = 1; i < top.length; i += 1) ctx.lineTo(top[i].x, top[i].y);
  ctx.closePath();
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.restore();
}

function drawLaserAndCandidates(
  ctx: CanvasRenderingContext2D,
  b: Box,
  frame: number,
  portrait: boolean,
  alpha: number,
) {
  if (alpha <= 0.005) return;
  const short = shortSide(b);
  const cx = b.x + b.w * 0.5;
  const planeY = b.y + b.h * 0.52;
  const unit = short * 0.092;
  const eventAge = frame % 15;
  const rise = clamp(eventAge / 5);

  ctx.save();
  ctx.globalAlpha = alpha;
  const plane = ctx.createLinearGradient(b.x, planeY, b.x + b.w, planeY);
  plane.addColorStop(0, "rgba(16,185,129,0)");
  plane.addColorStop(0.17, "rgba(16,185,129,0.34)");
  plane.addColorStop(0.5, "rgba(110,255,205,0.97)");
  plane.addColorStop(0.83, "rgba(16,185,129,0.34)");
  plane.addColorStop(1, "rgba(16,185,129,0)");
  glow(ctx, EMERALD, 25, alpha);
  ctx.strokeStyle = plane;
  ctx.lineWidth = Math.max(3, short * 0.0045);
  ctx.beginPath();
  ctx.moveTo(b.x, planeY);
  ctx.lineTo(b.x + b.w, planeY);
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Ten independently visible candidates cross the razor. Nine flare red and vanish;
  // the tenth becomes the persistent gold crown at the tower's growing tip.
  const spread = Math.min(b.w * 0.31, short * 0.92);
  for (let i = 0; i < 10; i += 1) {
    const offset = (i - 4.5) / 4.5;
    const x = cx + offset * spread * 0.5;
    if (i < 9) {
      const y = planeY + unit * (0.76 - rise * 1.15);
      const flicker = clamp(1 - Math.max(0, eventAge - 3) / 12);
      if (eventAge <= 6) {
        ctx.save();
        glow(ctx, RED, 16, alpha * flicker);
        ctx.strokeStyle = RED;
        ctx.lineWidth = Math.max(1.5, short * 0.002);
        ctx.beginPath();
        ctx.moveTo(x - 5, y + 12);
        ctx.lineTo(x + 4, y - 16);
        ctx.stroke();
        ctx.shadowBlur = 0;
        ctx.restore();
      }
      if (eventAge >= 3 && eventAge <= 8) {
        ctx.save();
        glow(ctx, RED, 12, alpha * (1 - (eventAge - 3) / 6));
        ctx.fillStyle = RED;
        for (let spark = 0; spark < 3; spark += 1) {
          const phase = frame * 0.9 + i * 2.3 + spark * 3.1;
          const sx = x + Math.sin(phase) * (5 + spark * 2);
          const sy = planeY + Math.cos(phase * 1.31) * (6 + spark * 2);
          ctx.beginPath();
          ctx.arc(sx, sy, spark === 0 ? 2.2 : 1.3, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.shadowBlur = 0;
        ctx.restore();
      }
    } else {
      const endY = planeY - unit * (0.36 + rise * 1.25);
      ctx.save();
      glow(ctx, GOLD, 24, alpha);
      ctx.strokeStyle = GOLD;
      ctx.lineWidth = Math.max(2.5, short * 0.0038);
      ctx.beginPath();
      ctx.moveTo(x, planeY + unit * 0.28);
      ctx.lineTo(x, endY);
      ctx.stroke();
      ctx.fillStyle = GOLD;
      ctx.beginPath();
      ctx.arc(x, endY, Math.max(3.5, short * 0.005), 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();
    }
  }

  const labelSize = portrait ? 30 : 22;
  if (portrait) {
    text(ctx, "[FORMAL VERIFIER: LEAN_4 /", cx, planeY - short * 0.11, labelSize, EMERALD, "center", alpha, 700);
    text(ctx, "COMPILER GUILLOTINE]", cx, planeY - short * 0.075, labelSize, EMERALD, "center", alpha, 700);
  } else {
    text(ctx, "[FORMAL VERIFIER: LEAN_4 / COMPILER GUILLOTINE]", cx, planeY - short * 0.095, labelSize, EMERALD, "center", alpha, 700);
  }
  text(ctx, "[AXIOM VIOLATION: 0.0001%]", cx, planeY + short * 0.105, labelSize, RED, "center", alpha, 700);
  ctx.restore();
}

function drawCeilingBreak(ctx: CanvasRenderingContext2D, b: Box, frame: number) {
  const age = Math.max(0, frame - 1260);
  const alpha = 0.72 * (1 - smooth(age / 45));
  if (alpha > 0.005) {
    drawTower(ctx, b, 1260, alpha);
    const cx = b.x + b.w * 0.5;
    const y = b.y + b.h * 0.53;
    ctx.save();
    ctx.globalAlpha = alpha * (1 - smooth(age / 60));
    ctx.fillStyle = "rgba(16,185,129,0.09)";
    ctx.fillRect(b.x, y - 8, b.w, 16);
    ctx.strokeStyle = EMERALD;
    ctx.lineWidth = 3;
    ctx.shadowColor = EMERALD;
    ctx.shadowBlur = 20;
    ctx.beginPath();
    ctx.moveTo(b.x + b.w * 0.07, y);
    ctx.lineTo(b.x + b.w * 0.93, y);
    ctx.stroke();
    ctx.restore();

    // A few large fragments preserve the sense of a real boundary giving way.
    for (let i = 0; i < 12; i += 1) {
      const phase = i * 2.17;
      const x = cx + Math.sin(phase) * shortSide(b) * 0.31 + Math.cos(phase) * age * 0.75;
      const yy = y + Math.cos(phase * 1.7) * shortSide(b) * 0.05 + Math.sin(phase) * age * 0.75;
      if (x < b.x || x > b.x + b.w || yy < b.y || yy > b.y + b.h) continue;
      ctx.save();
      ctx.globalAlpha = 0.82 * (1 - smooth(age / 120));
      ctx.strokeStyle = i % 4 === 0 ? GOLD : CYAN;
      ctx.lineWidth = i % 4 === 0 ? 3 : 2;
      ctx.shadowColor = ctx.strokeStyle;
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.moveTo(x - 4, yy - 8);
      ctx.lineTo(x + 5, yy + 6);
      ctx.lineTo(x - 2, yy + 11);
      ctx.stroke();
      ctx.restore();
    }
  }

  // The tower's last unsupported extension arcs away from the center title area.
  const u = shortSide(b);
  const drift = clamp((frame - 1260) / 540);
  const start = { x: b.x + b.w * 0.81, y: b.y + b.h * 0.86 };
  const bend = { x: b.x + b.w * 0.94, y: b.y + b.h * 0.54 };
  const end = { x: b.x + b.w * 0.81, y: b.y + b.h * 0.1 };
  ctx.save();
  ctx.globalAlpha = smooth(drift) * 0.86;
  ctx.strokeStyle = CYAN;
  ctx.lineWidth = Math.max(2, u * 0.004);
  ctx.shadowColor = CYAN;
  ctx.shadowBlur = 27;
  ctx.beginPath();
  ctx.moveTo(start.x, start.y);
  ctx.quadraticCurveTo(bend.x, bend.y, end.x, end.y);
  ctx.stroke();
  ctx.strokeStyle = "rgba(6,182,212,0.18)";
  ctx.lineWidth = Math.max(14, u * 0.025);
  ctx.shadowBlur = 32;
  ctx.stroke();
  ctx.restore();
}

function drawCore(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, frame: number, color: string, alpha = 1) {
  ctx.save();
  const pulse = 0.88 + 0.12 * Math.sin(frame * 0.095);
  ctx.globalAlpha = alpha;
  const halo = ctx.createRadialGradient(x, y, radius * 0.1, x, y, radius * 3.4);
  halo.addColorStop(0, color);
  halo.addColorStop(0.12, color === CYAN ? "rgba(6,182,212,0.86)" : "rgba(217,70,239,0.76)");
  halo.addColorStop(0.5, color === CYAN ? "rgba(6,182,212,0.18)" : "rgba(217,70,239,0.16)");
  halo.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(x, y, radius * 3.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowColor = color;
  ctx.shadowBlur = radius * 1.4;
  ctx.fillStyle = "rgba(220,255,255,0.96)";
  ctx.beginPath();
  ctx.arc(x, y, radius * pulse, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.restore();
}

function drawWaitScene(ctx: CanvasRenderingContext2D, b: Box, frame: number, portrait: boolean, alpha: number) {
  if (alpha <= 0.005) return;
  const local = frame - 1800;
  const short = shortSide(b);
  const cx = b.x + b.w * 0.5;
  const cy = b.y + b.h * 0.43;
  const radius = short * (portrait ? 0.355 : 0.365);
  const splitTension = smooth((frame - 2700) / 180);

  ctx.save();
  ctx.globalAlpha = alpha;
  // The dial's hand barely moves over fifteen seconds: the stillness is the point.
  ctx.strokeStyle = "rgba(245,158,11,0.23)";
  ctx.lineWidth = Math.max(1.4, short * 0.0022);
  for (const scale of [1, 0.88, 0.68]) {
    ctx.beginPath();
    ctx.arc(cx, cy, radius * scale, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.lineWidth = Math.max(1.2, short * 0.0016);
  ctx.strokeStyle = "rgba(245,158,11,0.3)";
  ctx.beginPath();
  for (let i = 0; i < 72; i += 1) {
    const a = (i / 72) * Math.PI * 2 - Math.PI / 2;
    const inner = radius * (i % 6 === 0 ? 0.84 : 0.94);
    ctx.moveTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner);
    ctx.lineTo(cx + Math.cos(a) * radius, cy + Math.sin(a) * radius);
  }
  ctx.stroke();

  ctx.save();
  ctx.strokeStyle = AMBER;
  ctx.lineWidth = Math.max(2, short * 0.0034);
  ctx.shadowColor = AMBER;
  ctx.shadowBlur = 16;
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.96, -Math.PI / 2, -Math.PI / 2 + 0.028 + local * 0.000008);
  ctx.stroke();
  const handAngle = -Math.PI / 2 + 0.028 + local * 0.000008;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx + Math.cos(handAngle) * radius * 0.9, cy + Math.sin(handAngle) * radius * 0.9);
  ctx.stroke();
  ctx.fillStyle = GOLD;
  ctx.beginPath();
  ctx.arc(cx, cy, short * 0.012, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  // A frantic intelligence is compressed into a small, vibrating light at the center.
  const coreRadius = short * (0.027 + splitTension * 0.007);
  for (let i = 0; i < 3; i += 1) {
    const spin = local * (0.085 + i * 0.018) + i * 2.1;
    const rr = coreRadius * (1.8 + i * 0.84);
    ctx.strokeStyle = i === 1 ? "rgba(16,185,129,0.65)" : "rgba(6,182,212,0.72)";
    ctx.lineWidth = Math.max(1.2, short * 0.0018);
    ctx.beginPath();
    ctx.ellipse(cx, cy, rr * 1.52, rr * 0.51, spin * 0.12, spin, spin + Math.PI * 1.56);
    ctx.stroke();
  }
  drawCore(ctx, cx, cy, coreRadius, frame, CYAN, alpha);

  const largeTextSize = portrait ? 67 : 61;
  text(ctx, "10 YEARS", cx, cy + radius * 0.57, largeTextSize, AMBER, "center", alpha * 0.94, 720);

  // The amber physical probe is visually tiny and moves only a few pixels in fifteen seconds.
  const probeX = cx + radius * 0.69;
  const probeY = b.y + b.h * 0.84 + local * short * 0.000006;
  ctx.save();
  ctx.strokeStyle = "rgba(245,158,11,0.25)";
  ctx.lineWidth = Math.max(1, short * 0.0012);
  ctx.setLineDash([short * 0.006, short * 0.012]);
  ctx.beginPath();
  ctx.moveTo(probeX, cy + radius * 1.08);
  ctx.lineTo(probeX, probeY - short * 0.02);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = AMBER;
  ctx.shadowColor = AMBER;
  ctx.shadowBlur = 15;
  ctx.beginPath();
  ctx.arc(probeX, probeY, Math.max(3.5, short * 0.0043), 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  const labelY = Math.min(b.y + b.h * 0.79, probeY - short * 0.032);
  const labelX = cx + radius * 0.42;
  const labelSize = portrait ? 30 : 22;
  if (portrait) {
    text(ctx, "[PHYSICAL CLINICAL", labelX, labelY - labelSize * 0.55, labelSize, AMBER, "center", alpha, 700);
    text(ctx, "TRIAL #01]", labelX, labelY + labelSize * 0.55, labelSize, AMBER, "center", alpha, 700);
  } else {
    text(ctx, "[PHYSICAL CLINICAL TRIAL #01]", labelX, labelY, labelSize, AMBER, "center", alpha, 700);
  }

  // A slight, radial cyan squeeze announces the coming split without changing the clock.
  if (splitTension > 0) {
    ctx.globalAlpha = alpha * splitTension * 0.45;
    ctx.strokeStyle = CYAN;
    ctx.lineWidth = Math.max(1, short * 0.0015);
    for (let i = 0; i < 12; i += 1) {
      const a = (i / 12) * Math.PI * 2 + frame * 0.014;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * coreRadius * 1.5, cy + Math.sin(a) * coreRadius * 1.5);
      ctx.lineTo(cx + Math.cos(a) * (coreRadius + short * 0.12), cy + Math.sin(a) * (coreRadius + short * 0.12));
      ctx.stroke();
    }
  }
  ctx.restore();
}

function figureEight(t: number, a: number, c: number): Point {
  const den = 1 + Math.cos(t) * Math.cos(t);
  return { x: (a * Math.sin(t)) / den, y: (c * Math.sin(t) * Math.cos(t)) / den };
}

function rotatePoint(p: Point, angle: number, cx: number, cy: number): Point {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  return { x: cx + p.x * c - p.y * s, y: cy + p.x * s + p.y * c };
}

function drawPairScene(ctx: CanvasRenderingContext2D, b: Box, frame: number, portrait: boolean) {
  if (frame < 2880) return;
  const local = frame - 2880;
  const split = smooth(local / 150);
  if (split <= 0) {
    // At the exact cut, a single white-cyan fracture flashes through the trapped core.
    const short = shortSide(b);
    const cx = b.x + b.w * 0.5;
    const cy = b.y + b.h * 0.43;
    ctx.save();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "rgba(210,255,255,0.98)";
    ctx.shadowColor = CYAN;
    ctx.shadowBlur = 28;
    ctx.lineWidth = short * 0.004;
    ctx.beginPath();
    ctx.moveTo(cx - short * 0.1, cy);
    ctx.lineTo(cx - short * 0.025, cy - short * 0.014);
    ctx.lineTo(cx, cy + short * 0.01);
    ctx.lineTo(cx + short * 0.028, cy - short * 0.018);
    ctx.lineTo(cx + short * 0.11, cy);
    ctx.stroke();
    ctx.restore();
    return;
  }

  const short = shortSide(b);
  const cx = b.x + b.w * 0.5;
  const cy = b.y + b.h * 0.43;
  const orbit = 0.004 + local * 0.00042;
  const camera = local * 0.0032;
  const a = short * (portrait ? 0.23 : 0.24) * split;
  const c = short * 0.145 * split;
  const phase = local * 0.011;
  const ca = Math.cos(phase);
  const sa = Math.sin(phase);
  const leftLocal = { x: -a * ca, y: c * sa };
  const rightLocal = { x: a * ca, y: -c * sa };
  const left = rotatePoint(leftLocal, camera, cx, cy);
  const right = rotatePoint(rightLocal, camera, cx, cy);

  ctx.save();
  ctx.globalAlpha = split;
  // Six luminous lemniscate paths turn around one another as if the camera were orbiting them.
  for (let layer = 0; layer < 6; layer += 1) {
    const points: Point[] = [];
    const layerScale = 0.72 + layer * 0.075;
    const phaseOffset = layer * 0.19 + orbit;
    const count = 94;
    for (let i = 0; i <= count; i += 1) {
      const t = (i / count) * Math.PI * 2 + phaseOffset;
      const p = figureEight(t, short * 0.285 * layerScale, short * 0.16 * layerScale);
      points.push(rotatePoint(p, camera + layer * 0.095, cx, cy));
    }
    const alpha = 0.23 + 0.06 * (layer % 3);
    ctx.globalAlpha = split * alpha;
    ctx.strokeStyle = layer % 2 === 0 ? CYAN : MAGENTA;
    ctx.lineWidth = Math.max(1.1, short * (0.0011 + (layer % 2) * 0.00045));
    ctx.shadowColor = layer % 2 === 0 ? CYAN : MAGENTA;
    ctx.shadowBlur = layer % 2 === 0 ? 8 : 12;
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i].x, points[i].y);
    ctx.stroke();
  }
  ctx.shadowBlur = 0;

  // Bidirectional reward streams braid between the two halves. Curves pulse on a fixed index.
  ctx.globalAlpha = split;
  for (let lane = 0; lane < 18; lane += 1) {
    const side = lane % 2 === 0;
    const from = side ? left : right;
    const to = side ? right : left;
    const offset = (lane - 8.5) * short * 0.012;
    const bendX = cx + Math.sin(lane * 2.13 + phase) * short * (0.14 + (lane % 4) * 0.018);
    const bendY = cy + Math.cos(lane * 1.71 - phase * 0.7) * short * 0.19 + offset;
    const grad = ctx.createLinearGradient(from.x, from.y, to.x, to.y);
    grad.addColorStop(0, side ? CYAN : MAGENTA);
    grad.addColorStop(0.48, lane % 3 === 0 ? GOLD : MAGENTA);
    grad.addColorStop(1, side ? MAGENTA : CYAN);
    ctx.strokeStyle = grad;
    ctx.lineWidth = Math.max(1.2, short * (0.0017 + (lane % 5) * 0.00025));
    ctx.globalAlpha = split * (0.26 + 0.12 * (0.5 + 0.5 * Math.sin(local * 0.04 + lane)));
    ctx.shadowColor = lane % 2 === 0 ? MAGENTA : CYAN;
    ctx.shadowBlur = 9;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.quadraticCurveTo(bendX, bendY, to.x, to.y);
    ctx.stroke();
  }
  ctx.shadowBlur = 0;

  // Fast reward particles stream both ways through the loops on deterministic paths.
  ctx.globalAlpha = split * 0.85;
  for (let i = 0; i < 36; i += 1) {
    const lane = i % 18;
    const side = i < 18;
    const from = side ? left : right;
    const to = side ? right : left;
    const t = fract(i * 0.173 + local * (0.0014 + lane * 0.000018));
    const controlX = cx + Math.sin(lane * 2.13 + phase) * short * (0.14 + (lane % 4) * 0.018);
    const controlY = cy + Math.cos(lane * 1.71 - phase * 0.7) * short * 0.19 + (lane - 8.5) * short * 0.012;
    const u = 1 - t;
    const x = u * u * from.x + 2 * u * t * controlX + t * t * to.x;
    const y = u * u * from.y + 2 * u * t * controlY + t * t * to.y;
    ctx.fillStyle = lane % 4 === 0 ? GOLD : (side ? CYAN : MAGENTA);
    ctx.shadowColor = ctx.fillStyle;
    ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.arc(x, y, Math.max(2.1, short * 0.0032), 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.shadowBlur = 0;
  ctx.restore();

  const coreRadius = short * (0.039 + 0.009 * split);
  drawCore(ctx, left.x, left.y, coreRadius, frame, CYAN, split);
  drawCore(ctx, right.x, right.y, coreRadius * 0.95, frame + 8, MAGENTA, split);

  // Keep the labels attached to the moving cores while leaving a small visual gap around each.
  const labelSize = portrait ? 30 : 22;
  const dy = short * 0.085;
  const labelWidth = Math.min(b.w * 0.46, short * 0.52);
  ctx.save();
  ctx.font = `700 ${labelSize}px ui-sans-serif, system-ui, -apple-system, "Arial", sans-serif`;
  ctx.textAlign = "center";
  const leftX = clamp(left.x, b.x + labelWidth * 0.53, b.x + b.w - labelWidth * 0.53);
  const rightX = clamp(right.x, b.x + labelWidth * 0.53, b.x + b.w - labelWidth * 0.53);
  text(ctx, "GENERATOR", leftX, left.y + dy, labelSize, CYAN, "center", split, 720);
  text(ctx, "INTERNAL REWARD JUDGE", rightX, right.y + dy, labelSize, MAGENTA, "center", split, 720);
  ctx.restore();
}

/** Draws the deterministic first-half sequence for Episode 04. */
export function drawPrelude(
  ctx: CanvasRenderingContext2D,
  frame: number,
  portrait: boolean,
  box: { x: number; y: number; w: number; h: number },
): void {
  const b: Box = box;
  const f = Math.max(0, Math.floor(frame));
  ctx.save();
  ctx.beginPath();
  ctx.rect(b.x, b.y, b.w, b.h);
  ctx.clip();

  drawBackdrop(ctx, b, f, f >= 1800 && f < 2880 ? 0.55 : 0);

  if (f < 1260) {
    drawTower(ctx, b, f, 1);
    drawLaserAndCandidates(ctx, b, f, portrait, 1);
  } else if (f < 1800) {
    drawCeilingBreak(ctx, b, f);
  }

  if (f >= 1800 && f < 2880) {
    const waitAlpha = f < 2700 ? 1 : 1 - smooth((f - 2700) / 180);
    drawWaitScene(ctx, b, f, portrait, waitAlpha);
  }

  if (f >= 2700 && f < 3600) drawPairScene(ctx, b, f, portrait);

  ctx.restore();
}
