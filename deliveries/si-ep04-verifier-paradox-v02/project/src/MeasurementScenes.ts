import {C, type Draw, clamp, line, rect, dot, text, arrow, pulse} from './draw';

const PHYSICAL_REVEAL = 5760;
const FEEDBACK_ARRIVAL = 5880;

function movingPacket(d: Draw, points: number[][], progress: number, color: string, radius = 7) {
  const lengths: number[] = [];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i][0] - points[i - 1][0];
    const dy = points[i][1] - points[i - 1][1];
    const length = Math.hypot(dx, dy);
    lengths.push(length);
    total += length;
  }
  let distance = clamp(progress) * total;
  for (let i = 0; i < lengths.length; i++) {
    const a = points[i];
    const b = points[i + 1];
    const segmentLength = lengths[i];
    if (distance <= segmentLength || i === lengths.length - 1) {
      const t = segmentLength === 0 ? 1 : clamp(distance / segmentLength);
      dot(d, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, radius, color);
      return;
    }
    distance -= segmentLength;
  }
}

function drawSpring(d: Draw, cx: number, anchorY: number, massTop: number, color: string, vibration: number) {
  line(d, [[cx - 56, anchorY], [cx + 56, anchorY]], C.muted, 5);
  line(d, [[cx, anchorY], [cx, anchorY + 12]], C.muted, 3);
  const coilTop = anchorY + 12;
  const coilBottom = massTop;
  const points: number[][] = [];
  const segments = 28;
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const envelope = Math.sin(Math.PI * t);
    const x = cx + Math.sin(i * Math.PI / 2 + vibration) * 17 * envelope;
    points.push([x, coilTop + (coilBottom - coilTop) * t]);
  }
  line(d, points, color, 4);
  line(d, [[cx, coilBottom], [cx, massTop + 8]], color, 4);
  rect(d, cx - 38, massTop + 8, 76, 42, color, C.panel, 7);
}

function drawRuler(d: Draw, x: number, yZero: number, mmScale: number, scanY: number, portrait: boolean) {
  const yEnd = yZero + 20 * mmScale;
  line(d, [[x, yZero], [x, yEnd]], C.muted, 3);
  for (let mm = 0; mm <= 20; mm += 5) {
    const y = yZero + mm * mmScale;
    const tick = mm % 10 === 0 ? 20 : 13;
    line(d, [[x - tick, y], [x + 3, y]], mm === 15 ? C.red : C.muted, 2);
    text(d, x + (portrait ? 15 : 22), y, String(mm), portrait ? 30 : 29, mm === 15 ? C.red : C.ink, 'left');
  }
  line(d, [[x - (portrait ? 205 : 200), scanY], [x + 7, scanY]], 'rgba(6,182,212,0.72)', 3);
  dot(d, x, scanY, 5, C.cyan);
}

function drawLandscapePhysical(d: Draw, revealed: boolean, quiet: boolean, updated: boolean, feedbackProgress: number) {
  const cx = 220;
  const yZero = 174;
  const mmScale = 11;
  const predictedY = yZero + 10 * mmScale;
  const actualY = yZero + 20 * mmScale;
  const frame = d.f - 5400;
  const phase = ((frame % 240) + 240) % 240 / 240;
  const scanY = quiet ? actualY : revealed ? actualY : yZero + (1 - Math.abs(phase * 2 - 1)) * 20 * mmScale;

  rect(d, 28, 26, 360, 50, C.cyan, C.panel, 12);
  text(d, 208, 51, '校准演示 · 非实测', 30, C.cyan, 'center', 500);
  text(d, 42, 101, '弹性范围示意', 31, C.muted);
  text(d, 392, 142, '标尺扫描', 29, C.cyan);
  const vibration = frame * Math.PI / 90;
  drawSpring(d, cx, 120, revealed ? actualY : predictedY, C.cyan, vibration);
  const massBottom = (revealed ? actualY : predictedY) + 50;
  arrow(d, cx + 60, massBottom - 18, cx + 60, Math.min(massBottom + 55, 535), C.amber, 3);
  text(d, cx + 82, Math.min(massBottom + 24, 520), '外力', 29, C.amber);
  drawRuler(d, 372, yZero, mmScale, scanY, false);
  line(d, [[cx + 38, predictedY + 8], [372, predictedY + 8]], C.cyan, 2, [7, 7]);
  if (revealed) line(d, [[cx + 38, actualY + 8], [372, actualY + 8]], C.amber, 3);
  text(d, 42, 518, 'F = 10 N', 31, C.ink);

  rect(d, 520, 28, 1168, 112, C.line, C.panel, 16);
  text(d, 548, 60, '胡克定律  F = kx', 37, C.ink, 'left', 500);
  text(d, 548, 108, 'F = 10 N', 30, C.muted);
  text(d, 770, 108, updated ? '修正 k = 500 N/m' : '起始假设 k = 1000 N/m', 30, updated ? C.green : C.muted);
  text(d, 1122, 108, '初始预测 x = 10 mm', 30, C.cyan);
  text(d, 1450, 108, updated ? '已校准' : '等待反馈', 30, updated ? C.green : C.muted);

  rect(d, 520, 154, 1168, 262, C.line, C.panel, 16);
  const x0 = 786;
  const x25 = 1605;
  const mm = (x25 - x0) / 25;
  const yPrediction = 232;
  const yMeasurement = 310;
  const thresholdX = x0 + 15 * mm;
  text(d, 548, yPrediction, '模型预测', 31, C.ink);
  text(d, 548, yMeasurement, '读数示例', 31, C.ink);
  line(d, [[x0, yPrediction], [x25, yPrediction]], 'rgba(165,186,201,0.30)', 15);
  line(d, [[x0, yPrediction], [x0 + 10 * mm, yPrediction]], C.cyan, 16);
  dot(d, x0 + 10 * mm, yPrediction, 9, C.cyan);
  text(d, x0 + 10 * mm + 20, yPrediction, '10 mm', 30, C.cyan);
  line(d, [[x0, yMeasurement], [x25, yMeasurement]], 'rgba(165,186,201,0.30)', 15);
  if (revealed) {
    line(d, [[x0, yMeasurement], [x0 + 20 * mm, yMeasurement]], C.amber, 16);
    dot(d, x0 + 20 * mm, yMeasurement, 10, C.amber);
    text(d, x0 + 20 * mm + 17, yMeasurement, '20 mm', 30, C.amber);
  } else {
    rect(d, x0 + 4, yMeasurement - 25, x25 - x0 - 8, 50, C.line, C.bg, 8);
    text(d, 1010, yMeasurement, quiet ? '测量等待 · 静默' : '结果未知', 31, quiet ? C.amber : C.muted, 'center', 500);
  }
  line(d, [[thresholdX, 188], [thresholdX, 347]], C.red, 2, [7, 6]);
  text(d, thresholdX, 180, '15 mm限值', 28, C.red, 'center');
  line(d, [[x0, 365], [x25, 365]], C.muted, 2);
  for (let value = 0; value <= 25; value += 5) {
    const x = x0 + value * mm;
    line(d, [[x, 359], [x, 371]], C.muted, 2);
    text(d, x, 394, String(value), 28, C.muted, 'center');
  }
  text(d, 1628, 394, 'mm', 28, C.muted, 'left');

  rect(d, 520, 424, 1168, 132, revealed ? C.amber : C.line, C.panel, 16);
  if (revealed) {
    text(d, 548, 449, '示例读数 20 mm   ·   预测误差 +10 mm', 33, C.amber, 'left', 500);
    text(d, 548, 489, '20 mm > 验收限值 15 mm   →   拒绝', 33, C.red, 'left', 500);
    text(d, 548, 531, '反例 → 修正参数 → 再验证', 31, C.green, 'left', 500);
  } else {
    text(d, 548, 464, quiet ? '等待测量揭示' : '验收结果尚未知', 34, quiet ? C.amber : C.muted, 'left', 500);
    text(d, 548, 519, '验收限值 15 mm', 31, C.muted);
  }
  if (revealed) {
    const path = [[x0 + 20 * mm, yMeasurement], [1694, yMeasurement], [1694, 85], [1460, 85]];
    line(d, path.slice(0, 3), 'rgba(245,158,11,0.75)', 2, [7, 6]);
    arrow(d, 1694, 85, 1460, 85, C.amber, 2);
    movingPacket(d, path, feedbackProgress, C.amber, 7);
    if (updated) {
      movingPacket(d, path, feedbackProgress - 0.18, C.amber, 6);
      movingPacket(d, path, feedbackProgress - 0.36, C.amber, 5);
    }
  }
}

function drawPortraitPhysical(d: Draw, revealed: boolean, quiet: boolean, updated: boolean, feedbackProgress: number) {
  const cx = 280;
  const yZero = 130;
  const mmScale = 8;
  const predictedY = yZero + 10 * mmScale;
  const actualY = yZero + 20 * mmScale;
  const frame = d.f - 5400;
  const phase = ((frame % 240) + 240) % 240 / 240;
  const scanY = quiet ? actualY : revealed ? actualY : yZero + (1 - Math.abs(phase * 2 - 1)) * 20 * mmScale;

  rect(d, 20, 24, 398, 54, C.cyan, C.panel, 12);
  text(d, 219, 51, '校准演示 · 非实测', 30, C.cyan, 'center', 500);
  text(d, 36, 103, '弹性范围示意', 32, C.muted);
  text(d, 615, 103, '标尺扫描', 30, C.cyan);
  const vibration = frame * Math.PI / 90;
  drawSpring(d, cx, 122, revealed ? actualY : predictedY, C.cyan, vibration);
  const massBottom = (revealed ? actualY : predictedY) + 50;
  arrow(d, cx + 63, massBottom - 14, cx + 63, Math.min(massBottom + 44, 366), C.amber, 3);
  text(d, cx + 87, Math.min(massBottom + 22, 356), '外力', 30, C.amber);
  drawRuler(d, 592, yZero, mmScale, scanY, true);
  line(d, [[cx + 39, predictedY + 7], [592, predictedY + 7]], C.cyan, 2, [7, 7]);
  if (revealed) line(d, [[cx + 39, actualY + 7], [592, actualY + 7]], C.amber, 3);

  rect(d, 26, 374, 748, 116, C.line, C.panel, 15);
  text(d, 49, 394, 'F = kx  ·  F = 10 N', 39, C.ink, 'left', 500);
  text(d, 49, 432, '起始假设 k = 1000 N/m', 39, C.muted);
  text(d, 49, 470, updated ? '修正 k = 500 N/m' : revealed ? '反例数据回传中' : '反馈待测量', 39, updated ? C.green : C.muted, 'left', 500);

  const x0 = 194;
  const x25 = 758;
  const mm = (x25 - x0) / 25;
  const yPrediction = 550;
  const yMeasurement = 610;
  const thresholdX = x0 + 15 * mm;
  text(d, 25, yPrediction, '预测', 39, C.ink);
  text(d, 25, yMeasurement, '读数', 39, C.ink);
  line(d, [[x0, yPrediction], [x25, yPrediction]], 'rgba(165,186,201,0.30)', 13);
  line(d, [[x0, yPrediction], [x0 + 10 * mm, yPrediction]], C.cyan, 14);
  dot(d, x0 + 10 * mm, yPrediction, 8, C.cyan);
  text(d, x0 + 10 * mm, yPrediction - 30, '10 mm', 39, C.cyan, 'center', 500);
  line(d, [[x0, yMeasurement], [x25, yMeasurement]], 'rgba(165,186,201,0.30)', 13);
  if (revealed) {
    line(d, [[x0, yMeasurement], [x0 + 20 * mm, yMeasurement]], C.amber, 14);
    dot(d, x0 + 20 * mm, yMeasurement, 9, C.amber);
    text(d, x0 + 20 * mm, yMeasurement - 30, '20 mm', 39, C.amber, 'center', 500);
  } else {
    rect(d, x0 + 3, yMeasurement - 20, x25 - x0 - 6, 40, C.line, C.bg, 8);
    text(d, 350, yMeasurement, quiet ? '测量等待 · 静默' : '结果未知', 32, quiet ? C.amber : C.muted, 'center', 500);
  }
  text(d, thresholdX + 7, 506, '限值 15 mm', 30, C.red);
  line(d, [[thresholdX, 520], [thresholdX, 635]], C.red, 2, [6, 5]);
  for (let value = 0; value <= 25; value += 5) {
    const x = x0 + value * mm;
    line(d, [[x, 648], [x, 656]], value === 15 ? C.red : C.muted, 2);
    text(d, x, 674, String(value), 30, value === 15 ? C.red : C.muted, 'center');
  }
  text(d, 827, 674, 'mm', 29, C.muted, 'right');

  rect(d, 26, 690, 748, 82, revealed ? C.amber : C.line, C.panel, 14);
  if (revealed) {
    text(d, 50, 714, '误差 +10 mm', 39, C.amber, 'left', 500);
    text(d, 50, 750, '20 mm > 15 mm · 拒绝', 39, C.red, 'left', 500);
  } else {
    text(d, 50, 732, quiet ? '等待测量揭示' : '验收结果未知', 39, quiet ? C.amber : C.muted, 'left', 500);
  }
  if (revealed) {
    const path = [[x0 + 20 * mm, yMeasurement], [790, yMeasurement], [790, 430], [760, 430]];
    line(d, path.slice(0, 3), 'rgba(245,158,11,0.75)', 2, [7, 6]);
    arrow(d, 790, 430, 760, 430, C.amber, 2);
    movingPacket(d, path, feedbackProgress, C.amber, 7);
    if (updated) {
      movingPacket(d, path, feedbackProgress - 0.18, C.amber, 6);
      movingPacket(d, path, feedbackProgress - 0.36, C.amber, 5);
    }
    text(d, 425, 817, '反例 → 修正参数 → 再验证', 32, C.green, 'center', 500);
  }
}

export function drawPhysical(d: Draw) {
  const revealed = d.f >= PHYSICAL_REVEAL;
  const quiet = d.f >= 5740 && d.f < PHYSICAL_REVEAL;
  const updated = d.f >= FEEDBACK_ARRIVAL;
  const feedbackProgress = d.f <= FEEDBACK_ARRIVAL
    ? clamp((d.f - PHYSICAL_REVEAL) / (FEEDBACK_ARRIVAL - PHYSICAL_REVEAL))
    : ((d.f - FEEDBACK_ARRIVAL) % 180) / 180;
  if (d.p) drawPortraitPhysical(d, revealed, quiet, updated, feedbackProgress);
  else drawLandscapePhysical(d, revealed, quiet, updated, feedbackProgress);
}

function drawCycleNode(d: Draw, x: number, y: number, w: number, h: number, title: string, note: string, color: string, portrait: boolean) {
  rect(d, x, y, w, h, color, C.panel, 16);
  if (portrait) {
    text(d, x + w / 2, y + 28, title, 43, color, 'center', 600);
    text(d, x + w / 2, y + 70, note, 39, C.ink, 'center');
  } else {
    text(d, x + w / 2, y + 48, title, 43, color, 'center', 600);
    text(d, x + w / 2, y + 105, note, 30, C.ink, 'center');
  }
}

export function drawConclusion(d: Draw) {
  const elapsed = d.f - 6300;
  if (d.p) {
    text(d, 425, 282, '预测 → 实验 → 误差 → 修正', 39, C.ink, 'center', 500);
    const x = 76;
    const w = 620;
    const h = 96;
    const ys = [326, 439, 552, 665];
    const nodes = [
      ['预测', '先给出可检验的结果', C.cyan],
      ['实验', '独立读数进入证据', C.green],
      ['误差', '与预设阈值比较', C.amber],
      ['修正', '更新这组模型参数', C.magenta],
    ] as const;
    nodes.forEach(([title, note, color], i) => drawCycleNode(d, x, ys[i], w, h, title, note, color, true));
    for (let i = 0; i < 3; i++) pulse(d, 386, ys[i] + h, 386, ys[i + 1], C.cyan, 120, i * 36);
    const feedback = [[696, ys[3] + h / 2], [772, ys[3] + h / 2], [772, ys[0] + h / 2], [700, ys[0] + h / 2]];
    line(d, feedback.slice(0, 3), C.amber, 3, [8, 7]);
    arrow(d, 772, ys[0] + h / 2, 700, ys[0] + h / 2, C.amber, 3);
    movingPacket(d, feedback, ((elapsed % 360) + 360) % 360 / 360, C.amber, 7);
    text(d, 425, 790, '修正后仍须再验证 · 不保证适用于所有情形', 30, C.muted, 'center');
  } else {
    text(d, 860, 204, '预测 → 实验 → 误差 → 修正', 34, C.ink, 'center', 500);
    const xs = [30, 450, 870, 1290];
    const w = 360;
    const y = 242;
    const h = 158;
    const nodes = [
      ['预测', '给出可检验结果', C.cyan],
      ['实验', '读取独立证据', C.green],
      ['误差', '比较预设阈值', C.amber],
      ['修正', '更新模型参数', C.magenta],
    ] as const;
    nodes.forEach(([title, note, color], i) => drawCycleNode(d, xs[i], y, w, h, title, note, color, false));
    for (let i = 0; i < 3; i++) pulse(d, xs[i] + w, y + h / 2, xs[i + 1], y + h / 2, C.cyan, 120, i * 36);
    const feedback = [[xs[3] + w / 2, y + h], [xs[3] + w / 2, 470], [xs[0] + w / 2, 470], [xs[0] + w / 2, y + h]];
    line(d, feedback.slice(0, 3), C.amber, 3, [8, 7]);
    arrow(d, xs[0] + w / 2, 470, xs[0] + w / 2, y + h, C.amber, 3);
    movingPacket(d, feedback, ((elapsed % 360) + 360) % 360 / 360, C.amber, 7);
    text(d, 860, 505, '修正参数后回到预测，重新检验', 31, C.green, 'center', 500);
    text(d, 860, 548, '一次反例不保证普遍修复 · 仍需再验证', 30, C.muted, 'center');
  }
}

function drawWell(d: Draw, x: number, y: number, w: number, h: number, label: string, color: string, portrait: boolean) {
  rect(d, x, y, w, h, color, C.panel, 14);
  text(d, x + w / 2, y + (portrait ? 25 : 24), label, portrait ? 39 : 31, C.ink, 'center', 500);
  const left = x + w * 0.2;
  const right = x + w * 0.8;
  const top = y + (portrait ? 48 : 47);
  const bottom = y + h - (portrait ? 22 : 18);
  line(d, [[left, top], [left + w * 0.14, bottom - 7], [x + w / 2, bottom], [right - w * 0.14, bottom - 7], [right, top]], color, 3);
  dot(d, x + w / 2, bottom - 7, portrait ? 8 : 7, color);
}

export function drawLandauer(d: Draw) {
  const elapsed = d.f - 6930;
  if (d.p) {
    text(d, 425, 42, '擦除 1 个等概率未知比特', 43, C.ink, 'center', 500);
    drawWell(d, 28, 91, 365, 160, '可能输入 0', C.cyan, true);
    drawWell(d, 457, 91, 365, 160, '可能输入 1', C.green, true);
    rect(d, 268, 314, 314, 92, C.amber, C.panel, 16);
    text(d, 425, 338, 'RESET', 40, C.amber, 'center', 600);
    text(d, 425, 385, '清零', 39, C.ink, 'center');
    pulse(d, 210, 251, 350, 314, C.cyan, 110, elapsed);
    pulse(d, 640, 251, 500, 314, C.green, 110, elapsed + 38);
    drawWell(d, 257, 469, 336, 143, '已知输出 0', C.cyan, true);
    pulse(d, 425, 406, 425, 469, C.cyan, 110, elapsed + 72);
    rect(d, 607, 320, 215, 145, C.amber, C.panel, 14);
    text(d, 714, 353, '热浴 T', 40, C.amber, 'center', 500);
    text(d, 714, 405, '吸热 Q', 39, C.ink, 'center');
    pulse(d, 582, 363, 607, 363, C.amber, 75, elapsed + 24);
    text(d, 425, 671, 'Q ≥ k_B T ln 2', 50, C.gold, 'center', 600);
    text(d, 425, 728, '等概率擦除 1 个比特 · 等温理想下限', 31, C.ink, 'center');
    text(d, 425, 780, '可逆计算另论 · 不代表所有计算的能耗下限', 30, C.muted, 'center');
  } else {
    text(d, 36, 46, '等概率未知比特：逻辑擦除', 37, C.ink, 'left', 500);
    drawWell(d, 48, 128, 270, 150, '可能输入 0', C.cyan, false);
    drawWell(d, 48, 318, 270, 150, '可能输入 1', C.green, false);
    rect(d, 680, 180, 280, 112, C.amber, C.panel, 16);
    text(d, 820, 218, 'RESET', 43, C.amber, 'center', 600);
    text(d, 820, 260, '清零', 30, C.ink, 'center');
    pulse(d, 318, 203, 680, 218, C.cyan, 150, elapsed);
    pulse(d, 318, 393, 680, 265, C.green, 125, elapsed + 45);
    drawWell(d, 1030, 175, 300, 138, '已知输出 0', C.cyan, false);
    pulse(d, 960, 231, 1030, 231, C.cyan, 95, elapsed + 80);
    rect(d, 1440, 360, 242, 120, C.amber, C.panel, 16);
    text(d, 1561, 396, '热浴 T', 40, C.amber, 'center', 500);
    text(d, 1561, 444, '温度 T · 吸热 Q', 29, C.ink, 'center');
    const heatPath = [[820, 292], [820, 420], [1440, 420]];
    line(d, heatPath.slice(0, 2), C.amber, 3);
    arrow(d, 820, 420, 1440, 420, C.amber, 3);
    movingPacket(d, heatPath, ((elapsed % 150) + 150) % 150 / 150, C.amber, 7);
    text(d, 1115, 396, '热量 Q', 29, C.amber, 'center');
    text(d, 860, 470, 'Q ≥ k_B T ln 2', 54, C.gold, 'center', 600);
    text(d, 860, 552, '等概率未知比特 · 等温理想下限 · 可逆计算另论 · 不代表所有计算', 30, C.ink, 'center');
  }
}
