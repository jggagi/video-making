import {C, type Draw, clamp, mix, text, line, rect, dot} from './draw';

const ALIGN_FRAME = 6590;
const RESET_FRAME = 7020;

function ease(t: number) {
  const x = clamp(t);
  return x * x * (3 - 2 * x);
}

function drawSpring(d: Draw, cx: number, anchorY: number, massTop: number, width: number, phase: number) {
  line(d, [[cx - width, anchorY], [cx + width, anchorY]], C.line, 8);
  line(d, [[cx, anchorY], [cx, anchorY + 16]], C.muted, 5);

  const coilTop = anchorY + 16;
  const coilLength = massTop - coilTop;
  const points: number[][] = [];
  const turns = 8;
  const segments = 80;
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const envelope = Math.sin(Math.PI * t);
    const x = cx + Math.sin(t * turns * Math.PI * 2 + phase) * 22 * envelope;
    points.push([x, coilTop + coilLength * t]);
  }
  line(d, points, C.amber, 6);
  line(d, [[cx, massTop - 5], [cx, massTop + 4]], C.amber, 6);
}

function fillGhost(d: Draw, x: number, y: number, w: number, h: number) {
  const ctx = d.ctx;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, 18);
  ctx.fillStyle = 'rgba(6,182,212,0.14)';
  ctx.fill();
}

function outlineGhost(d: Draw, x: number, y: number, w: number, h: number) {
  line(d, [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]], 'rgba(6,182,212,0.95)', 5, [13, 10]);
}

function drawSpringComparison(d: Draw) {
  const elapsed = d.f - 6300;
  const portrait = d.p;
  const cx = portrait ? 425 : 860;
  const anchorY = portrait ? 128 : 72;
  const massW = portrait ? 320 : 340;
  const massH = portrait ? 126 : 130;
  const baseline = portrait ? 418 : 348;
  const initialGap = portrait ? 150 : 132;
  const massLeft = cx - massW / 2;
  const variation = Math.sin(elapsed * Math.PI * 2 / 190) * (portrait ? 13 : 12)
    + Math.sin(elapsed * Math.PI * 2 / 95) * 3;
  const measuredTop = baseline + variation;
  const alignment = ease((d.f - 6300) / (ALIGN_FRAME - 6300));
  const predictedTop = mix(measuredTop - initialGap, measuredTop, alignment);
  const fontSize = portrait ? 44 : 39;
  const calibrated = d.f >= ALIGN_FRAME;
  const leftLabelX = massLeft - (portrait ? 24 : 30);
  const rightLabelX = massLeft + massW + (portrait ? 24 : 30);
  const phase = elapsed * 0.055;

  drawSpring(d, cx, anchorY, measuredTop, portrait ? 174 : 150, phase);
  fillGhost(d, massLeft, predictedTop, massW, massH);
  rect(d, massLeft, measuredTop, massW, massH, C.gold, C.amber, 18);
  outlineGhost(d, massLeft, predictedTop, massW, massH);

  text(d, leftLabelX, predictedTop + massH / 2, calibrated ? '已校准' : '预测', fontSize, C.cyan, 'right', 500);
  text(d, rightLabelX, measuredTop + massH / 2, '实测', fontSize, C.amber, 'left', 500);
}

export function drawConclusion(d: Draw) {
  drawSpringComparison(d);
}

function drawHeatWave(d: Draw, originX: number, centerY: number, direction: -1 | 1, age: number, radiusLimit: number) {
  for (let i = 0; i < 3; i++) {
    const phase = ((age + i * 31) % 108) / 108;
    const radius = 14 + phase * radiusLimit;
    const points: number[][] = [];
    const segments = 20;
    for (let j = 0; j <= segments; j++) {
      const angle = -Math.PI / 2 + Math.PI * j / segments;
      points.push([
        originX + direction * radius * Math.cos(angle),
        centerY + radius * Math.sin(angle),
      ]);
    }
    const opacity = 0.78 - phase * 0.28;
    line(d, points, `rgba(245,158,11,${opacity})`, 5);
  }

  for (let i = 0; i < 2; i++) {
    const t = ((age + i * 39) % 82) / 82;
    const x = originX + direction * (12 + t * radiusLimit);
    const y = centerY + Math.sin((age + i * 39) * 0.09) * 25;
    dot(d, x, y, 6, 'rgba(245,158,11,0.9)');
  }
}

function drawResetPusher(d: Draw, cx: number, topY: number, endY: number, age: number, plateW: number, plateH: number) {
  const down = ease(age / (RESET_FRAME - 6930));
  const returnUp = ease((age - (RESET_FRAME - 6930)) / 96);
  const plateY = age < RESET_FRAME - 6930
    ? mix(topY, endY, down)
    : mix(endY, topY, returnUp);
  line(d, [[cx, 30], [cx, plateY + 2]], C.amber, 16);
  rect(d, cx - plateW / 2, plateY, plateW, plateH, C.gold, C.amber, 12);
}

function drawLandauerScene(d: Draw) {
  const portrait = d.p;
  const cx = portrait ? 425 : 860;
  const cellW = portrait ? 610 : 580;
  const cellH = portrait ? 270 : 222;
  const cellX = cx - cellW / 2;
  const cellY = portrait ? 396 : 260;
  const centerY = cellY + cellH / 2;
  const age = d.f - RESET_FRAME;
  const reset = d.f >= RESET_FRAME;
  const labelX = portrait ? 190 : 640;
  const labelY = cellY - (portrait ? 46 : 44);
  const fontSize = portrait ? 44 : 40;
  const bitSize = portrait ? 180 : 156;
  const heatY = portrait ? 730 : 535;
  const plateW = portrait ? 190 : 180;
  const plateH = portrait ? 36 : 34;
  const topPlateY = portrait ? 214 : 112;
  const pressedPlateY = cellY - plateH;

  rect(d, cellX, cellY, cellW, cellH, reset ? C.amber : C.cyan, C.panel, 28);

  if (reset) {
    const waveLimit = portrait ? 92 : 110;
    drawHeatWave(d, cellX, centerY, -1, age, waveLimit);
    drawHeatWave(d, cellX + cellW, centerY, 1, age, waveLimit);
  }

  text(d, labelX, labelY, reset ? '清零' : '未知比特', fontSize, reset ? C.amber : C.cyan, 'center', 500);
  text(d, cx, centerY, reset ? '0' : '0 / 1', bitSize, C.ink, 'center', 600);

  drawResetPusher(d, cx, topPlateY, pressedPlateY, d.f - 6930, plateW, plateH);

  if (reset) text(d, cx, heatY, '热量', fontSize, C.amber, 'center', 500);
}

export function drawLandauer(d: Draw) {
  drawLandauerScene(d);
}
