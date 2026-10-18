import {Draw, C, arrow, dot, line, mix, rect, text} from './draw';

type Point = [number, number];

function sceneFrame(d: Draw, start: number, end: number) {
  return Math.max(0, Math.min(end - start, d.f - start));
}

function pathFlow(
  d: Draw,
  points: Point[],
  color: string,
  frame: number,
  speed = 180,
  offset = 0,
  dashed = false,
  packets = 3,
) {
  line(d, points, color, 3, dashed ? [9, 9] : []);
  const [x0, y0] = points[points.length - 2];
  const [x1, y1] = points[points.length - 1];
  const angle = Math.atan2(y1 - y0, x1 - x0);
  const head = 11;
  line(d, [
    [x1 - head * Math.cos(angle - .5), y1 - head * Math.sin(angle - .5)],
    [x1, y1],
    [x1 - head * Math.cos(angle + .5), y1 - head * Math.sin(angle + .5)],
  ], color, 3);

  const lengths = points.slice(1).map(([x, y], i) => {
    const [px, py] = points[i];
    return Math.hypot(x - px, y - py);
  });
  const total = lengths.reduce((a, b) => a + b, 0);
  for (let i = 0; i < packets; i++) {
    let distance = (((frame + offset) / speed + i / packets) % 1) * total;
    for (let j = 0; j < lengths.length; j++) {
      if (distance <= lengths[j] || j === lengths.length - 1) {
        const t = lengths[j] ? distance / lengths[j] : 0;
        dot(d, mix(points[j][0], points[j + 1][0], t), mix(points[j][1], points[j + 1][1], t), 5, color);
        break;
      }
      distance -= lengths[j];
    }
  }
}

function drawCells(
  d: Draw,
  values: number[],
  x: number,
  y: number,
  cellW: number,
  cellH: number,
  gap: number,
  activePair = -1,
  stroke = C.cyan,
  fontSize = 37,
) {
  const centers: number[] = [];
  values.forEach((value, i) => {
    const cx = x + i * (cellW + gap) + cellW / 2;
    centers.push(cx);
    const active = activePair >= 0 && (i === activePair || i === activePair + 1);
    rect(d, x + i * (cellW + gap), y, cellW, cellH, active ? C.gold : stroke, active ? '#292414' : '#09121d', 9);
    text(d, cx, y + cellH / 2, String(value), fontSize, active ? C.gold : C.ink, 'center', 600);
  });
  return centers;
}

function checkRow(d: Draw, x: number, y: number, w: number, expression: string, status: string, statusColor: string, active: boolean, portrait = false) {
  const h = portrait ? 54 : 50;
  rect(d, x, y, w, h, active ? C.gold : C.line, active ? '#292414' : '#08111b', 10);
  text(d, x + 17, y + h / 2, expression, portrait ? 39 : 30, active ? C.gold : C.ink, 'left', 500);
  text(d, x + w - 16, y + h / 2, status, portrait ? 36 : 30, statusColor, 'right', 600);
}

function formalLandscape(d: Draw, u: number) {
  const pair = u < 250 ? Math.floor(u / 115) % 2 : 1;
  const firstPassed = u > 75;
  const failed = u > 250;
  const rejected = u > 390;
  const corrected = u > 520;

  rect(d, 32, 60, 255, 188);
  text(d, 55, 91, '输入数组', 31, C.muted, 'left', 500);
  drawCells(d, [3, 1, 2], 58, 126, 52, 54, 13, -1, C.cyan, 35);

  rect(d, 330, 60, 430, 188, C.cyan);
  text(d, 353, 91, '候选排序输出', 31, C.muted, 'left', 500);
  const candidateCenters = drawCells(d, [1, 3, 2], 388, 124, 70, 56, 17, pair, C.cyan, 36);
  const pointerX = (candidateCenters[pair] + candidateCenters[pair + 1]) / 2;
  arrow(d, pointerX, 218, pointerX, 188, C.gold, 3);
  text(d, 545, 225, '比较指针', 30, C.gold, 'center', 500);

  rect(d, 810, 50, 400, 218, C.line);
  text(d, 833, 82, '相邻顺序检查', 32, C.ink, 'left', 600);
  checkRow(d, 832, 104, 356, '1 ≤ 3', firstPassed ? '通过' : '检查中', firstPassed ? C.green : C.amber, pair === 0);
  checkRow(d, 832, 177, 356, '3 ≤ 2', failed ? '失败' : '待检查', failed ? C.red : C.muted, pair === 1);

  rect(d, 1260, 60, 428, 188, C.red, '#211018');
  text(d, 1290, 112, rejected ? '拒绝候选' : '失败分支', 35, C.red, 'left', 600);
  text(d, 1290, 166, '3 ≤ 2 不成立', 32, C.ink, 'left', 500);

  pathFlow(d, [[287, 154], [326, 154]], C.cyan, u, 95, 0, false, 2);
  pathFlow(d, [[760, 154], [806, 154]], C.cyan, u, 95, 22, false, 2);
  pathFlow(d, [[1210, 154], [1256, 154]], C.red, Math.max(0, u - 240), 120, 30, false, 2);

  pathFlow(d, [[1470, 248], [1470, 286], [790, 286], [790, 307]], C.green, Math.max(0, u - 430), 520, 0, false, 2);
  text(d, 1075, 260, '修正后重排', 30, C.green, 'center', 500);
  rect(d, 360, 312, 850, 163, C.green, '#0a1a19');
  text(d, 384, 344, '修正输出', 31, C.muted, 'left', 500);
  const fixedCenters = drawCells(d, [1, 2, 3], 564, 358, 61, 54, 12, corrected ? Math.floor(u / 100) % 2 : -1, C.green, 35);
  if (corrected) {
    const fx = (fixedCenters[Math.floor(u / 100) % 2] + fixedCenters[Math.floor(u / 100) % 2 + 1]) / 2;
    arrow(d, fx, 446, fx, 420, C.green, 3);
  }
  text(d, 1010, 403, corrected ? '相邻检查全通过' : '等待修正', 30, corrected ? C.green : C.muted, 'center', 600);

  rect(d, 1260, 312, 428, 163, C.gold, '#1a1710');
  text(d, 1474, 343, '证明检查链', 30, C.muted, 'center', 500);
  text(d, 1474, 378, '命题 2+2=4', 30, C.ink, 'center', 500);
  arrow(d, 1474, 395, 1474, 409, C.gold, 2);
  text(d, 1474, 426, '证明项', 30, C.ink, 'center', 500);
  arrow(d, 1474, 442, 1474, 451, C.gold, 2);
  text(d, 1474, 458, '内核检查', 30, C.green, 'center', 500);

  const notes = [
    ['编译 ≠ 正确', 32, 530],
    ['测试只覆盖已测样例', 600, 530],
    ['证明依赖命题与假设', 1168, 530],
  ] as const;
  notes.forEach(([s, x, y]) => {
    rect(d, x, y - 27, 520, 54, C.line, '#0a111b', 12);
    text(d, x + 260, y, s, 30, C.muted, 'center', 500);
  });
}

function formalPortrait(d: Draw, u: number) {
  const pair = u < 210 ? Math.floor(u / 90) % 2 : 1;
  const firstPassed = u > 70;
  const failed = u > 210;
  const rejected = u > 320;
  const corrected = u > 430;

  rect(d, 25, 20, 800, 80);
  text(d, 54, 60, '输入', 39, C.muted, 'left', 500);
  drawCells(d, [3, 1, 2], 260, 38, 82, 44, 14, -1, C.cyan, 42);

  rect(d, 25, 112, 800, 138, C.cyan);
  text(d, 54, 143, '候选输出', 39, C.muted, 'left', 500);
  const candidateCenters = drawCells(d, [1, 3, 2], 286, 157, 87, 49, 17, pair, C.cyan, 42);
  const pointerX = (candidateCenters[pair] + candidateCenters[pair + 1]) / 2;
  arrow(d, pointerX, 234, pointerX, 211, C.gold, 3);
  text(d, 651, 229, '比较指针', 30, C.gold, 'center', 500);

  rect(d, 25, 260, 800, 150, C.line);
  text(d, 54, 291, '相邻顺序检查', 39, C.ink, 'left', 600);
  checkRow(d, 54, 321, 346, '1 ≤ 3', firstPassed ? '通过' : '检查中', firstPassed ? C.green : C.amber, pair === 0, true);
  checkRow(d, 420, 321, 372, '3 ≤ 2', failed ? '失败' : '待检查', failed ? C.red : C.muted, pair === 1, true);

  pathFlow(d, [[425, 410], [425, 428]], C.red, Math.max(0, u - 200), 110, 0, false, 2);
  rect(d, 25, 430, 800, 55, C.red, '#211018', 10);
  text(d, 425, 458, rejected ? '拒绝候选：3 ≤ 2 不成立' : '失败分支：候选不满足顺序条件', 39, C.red, 'center', 600);

  pathFlow(d, [[425, 485], [425, 497]], C.green, Math.max(0, u - 350), 130, 0, false, 2);
  rect(d, 25, 498, 800, 62, C.green, '#0a1a19', 10);
  text(d, 425, 529, corrected ? '修正输出：[1,2,3]  ·  相邻检查通过' : '修正排序：[1,2,3]', 39, corrected ? C.green : C.ink, 'center', 600);

  rect(d, 25, 575, 800, 75, C.gold, '#1a1710');
  text(d, 150, 613, '命题 2+2=4', 39, C.ink, 'center', 500);
  arrow(d, 269, 613, 316, 613, C.gold, 2);
  text(d, 425, 613, '证明项', 39, C.ink, 'center', 500);
  arrow(d, 500, 613, 567, 613, C.gold, 2);
  text(d, 691, 613, '内核检查', 39, C.green, 'center', 500);

  text(d, 54, 684, '编译 ≠ 正确', 30, C.muted, 'left', 500);
  text(d, 54, 724, '测试只覆盖已测样例', 30, C.muted, 'left', 500);
  text(d, 54, 764, '证明依赖命题与假设', 30, C.muted, 'left', 500);
}

export function drawFormal(d: Draw) {
  const u = sceneFrame(d, 0, 1200);
  if (d.p) formalPortrait(d, u);
  else formalLandscape(d, u);
}

function timeline(d: Draw, x0: number, x1: number, y: number, color = C.line, dashed = false) {
  line(d, [[x0, y], [x1, y]], color, 3, dashed ? [9, 9] : []);
  arrow(d, x1 - 24, y, x1, y, color, 2);
}

function boundaryLandscape(d: Draw, u: number) {
  text(d, 48, 34, '目标结果', 31, C.muted, 'left', 600);
  text(d, 520, 34, '可观测证据与反馈时间', 31, C.muted, 'left', 600);
  const rows = [
    {y: 60, goal: '代码是否返回正确值', evidence: '返回值 · 即时检查器'},
    {y: 205, goal: '药物是否带来长期疗效', evidence: '长期结局 · 延迟观察'},
    {y: 350, goal: '历史政策的反事实结果', evidence: '历史路径 · 无法原样重放'},
  ];
  rows.forEach((r, i) => {
    rect(d, 35, r.y, 425, 120, C.line);
    text(d, 62, r.y + 42, r.goal, 32, C.ink, 'left', 500);
    rect(d, 490, r.y, 1195, 120, C.line);
    text(d, 520, r.y + 38, r.evidence, 32, i === 2 ? C.amber : C.ink, 'left', 500);
    const y = r.y + 91;
    timeline(d, 535, 1638, y, i === 2 ? C.amber : C.line, i === 2);
    if (i === 0) {
      dot(d, 535 + ((u * 5) % 1103), y, 8, C.cyan);
    } else if (i === 1) {
      const xs = [670, 1050, 1450];
      xs.forEach((x, j) => { if (u > j * 170 + 50) dot(d, x, y, 7, C.gold); });
      dot(d, 535 + ((u * .62) % 1103), y, 8, C.gold);
    } else {
      dot(d, 760, y, 8, C.amber);
      d.ctx.save();
      d.ctx.beginPath();
      d.ctx.arc(1600, y, 11, 0, Math.PI * 2);
      d.ctx.strokeStyle = C.amber;
      d.ctx.lineWidth = 3;
      d.ctx.stroke();
      d.ctx.restore();
      text(d, 1600, y - 23, '?', 30, C.amber, 'center', 600);
    }
  });
  rect(d, 235, 498, 1250, 60, C.cyan, '#091b24');
  text(d, 860, 528, '现实也能检验，但反馈稀疏、昂贵、延迟', 35, C.cyan, 'center', 600);
}

function boundaryPortrait(d: Draw, u: number) {
  text(d, 54, 34, '目标  →  可观测证据', 39, C.muted, 'left', 600);
  const rows = [
    {y: 65, objective: '代码目标 · 正确返回值', evidence: '返回值 · 即时检查器'},
    {y: 255, objective: '药物目标 · 长期疗效', evidence: '长期结局 · 延迟观察'},
    {y: 445, objective: '政策目标 · 反事实结果', evidence: '历史路径 · 无法原样重放'},
  ];
  rows.forEach((r, i) => {
    rect(d, 25, r.y, 800, 170, C.line);
    text(d, 52, r.y + 42, r.objective, 39, C.ink, 'left', 500);
    text(d, 52, r.y + 86, r.evidence, 39, i === 2 ? C.amber : C.cyan, 'left', 500);
    const yy = r.y + 137;
    timeline(d, 62, 786, yy, i === 2 ? C.amber : C.line, i === 2);
    if (i === 0) dot(d, 62 + ((u * 5) % 724), yy, 8, C.cyan);
    if (i === 1) {
      [160, 410, 690].forEach((x, j) => { if (u > j * 170 + 50) dot(d, x, yy, 7, C.gold); });
      dot(d, 62 + ((u * 1.2) % 724), yy, 8, C.gold);
    }
    if (i === 2) {
      dot(d, 180, yy, 8, C.amber);
      d.ctx.save();
      d.ctx.beginPath();
      d.ctx.arc(745, yy, 10, 0, Math.PI * 2);
      d.ctx.strokeStyle = C.amber;
      d.ctx.lineWidth = 3;
      d.ctx.stroke();
      d.ctx.restore();
      text(d, 745, yy - 18, '?', 30, C.amber, 'center', 600);
    }
  });
  text(d, 425, 672, '现实也能检验', 39, C.cyan, 'center', 600);
  const labels = [['稀疏', 180], ['昂贵', 425], ['延迟', 670]] as const;
  labels.forEach(([s, x]) => {
    rect(d, x - 94, 710, 188, 58, C.cyan, '#091b24', 12);
    text(d, x, 739, s, 39, C.cyan, 'center', 600);
  });
}

export function drawBoundary(d: Draw) {
  const u = sceneFrame(d, 1200, 1800);
  if (d.p) boundaryPortrait(d, u);
  else boundaryLandscape(d, u);
}

function feedbackLandscape(d: Draw, u: number) {
  rect(d, 45, 142, 390, 220, C.cyan);
  text(d, 240, 181, '候选生成', 36, C.ink, 'center', 600);
  text(d, 240, 228, '多个候选项', 31, C.muted, 'center', 500);
  [['A', 140], ['B', 240], ['C', 340]].forEach(([s, x]) => {
    rect(d, (x as number) - 33, 270, 66, 58, C.cyan, '#08131d', 10);
    text(d, x as number, 299, s as string, 34, C.ink, 'center', 600);
  });

  rect(d, 665, 142, 390, 220, C.gold, '#1b1710');
  text(d, 860, 191, '代理评审', 36, C.ink, 'center', 600);
  text(d, 860, 244, '按代理指标筛选', 31, C.muted, 'center', 500);
  rect(d, 760, 282, 200, 48, C.gold, '#100e0a', 12);
  text(d, 860, 306, '候选排序', 30, C.gold, 'center', 500);

  rect(d, 1285, 142, 390, 220, C.green, '#0b1916');
  text(d, 1480, 191, '入选候选', 36, C.ink, 'center', 600);
  text(d, 1480, 244, '进入下一轮', 31, C.muted, 'center', 500);
  rect(d, 1380, 282, 200, 48, C.green, '#07110e', 12);
  text(d, 1480, 306, '被选中', 30, C.green, 'center', 500);

  pathFlow(d, [[435, 252], [661, 252]], C.cyan, u, 230, 0);
  pathFlow(d, [[1055, 252], [1281, 252]], C.green, u, 230, 75);
  pathFlow(d, [[1480, 142], [1480, 77], [240, 77], [240, 138]], C.cyan, u, 560, 0, false, 4);
  text(d, 860, 48, '新一轮候选', 30, C.cyan, 'center', 500);

  rect(d, 690, 425, 410, 118, C.amber, '#1b1710');
  text(d, 895, 461, '独立测量结果', 34, C.ink, 'center', 600);
  text(d, 895, 505, '长期结局 · 延迟到达', 30, C.amber, 'center', 500);
  const toMeasure: Point[] = [[1480, 362], [1480, 484], [1104, 484]];
  line(d, toMeasure, C.amber, 3, [9, 9]);
  arrow(d, 1128, 484, 1104, 484, C.amber, 3);
  if (u > 300) pathFlow(d, toMeasure, C.amber, u - 300, 560, 0, true, 1);
  const returnPath: Point[] = [[690, 484], [615, 484], [615, 392], [860, 392], [860, 366]];
  line(d, returnPath, C.amber, 3, [9, 9]);
  arrow(d, 860, 392, 860, 366, C.amber, 3);
  if (u > 650) pathFlow(d, returnPath, C.amber, u - 650, 700, 0, true, 1);
  text(d, 500, 522, '延迟回流', 30, C.amber, 'center', 500);
}

function feedbackPortrait(d: Draw, u: number) {
  rect(d, 95, 42, 660, 124, C.cyan);
  text(d, 425, 74, '候选生成', 39, C.ink, 'center', 600);
  [['A', 280], ['B', 425], ['C', 570]].forEach(([s, x]) => {
    rect(d, (x as number) - 37, 100, 74, 48, C.cyan, '#08131d', 9);
    text(d, x as number, 124, s as string, 32, C.ink, 'center', 600);
  });

  rect(d, 95, 230, 660, 124, C.gold, '#1b1710');
  text(d, 425, 271, '代理评审', 39, C.ink, 'center', 600);
  text(d, 425, 321, '按代理指标筛选', 39, C.muted, 'center', 500);

  rect(d, 95, 418, 660, 124, C.green, '#0b1916');
  text(d, 425, 459, '入选候选', 39, C.ink, 'center', 600);
  text(d, 425, 509, '进入下一轮', 39, C.muted, 'center', 500);

  pathFlow(d, [[425, 166], [425, 226]], C.cyan, u, 210, 0, false, 2);
  pathFlow(d, [[425, 354], [425, 414]], C.green, u, 210, 70, false, 2);
  pathFlow(d, [[755, 480], [794, 480], [794, 104], [755, 104]], C.cyan, u, 620, 0, false, 4);
  text(d, 690, 145, '循环', 30, C.cyan, 'center', 500);

  rect(d, 95, 668, 660, 132, C.amber, '#1b1710');
  text(d, 425, 709, '独立测量结果', 39, C.ink, 'center', 600);
  text(d, 425, 758, '长期结局 · 延迟到达', 39, C.amber, 'center', 500);
  const measured: Point[] = [[425, 542], [425, 664]];
  line(d, measured, C.amber, 3, [9, 9]);
  arrow(d, 425, 640, 425, 664, C.amber, 3);
  if (u > 280) pathFlow(d, measured, C.amber, u - 280, 500, 0, true, 1);
  const returnPath: Point[] = [[95, 733], [25, 733], [25, 292], [90, 292]];
  line(d, returnPath, C.amber, 3, [9, 9]);
  arrow(d, 66, 292, 90, 292, C.amber, 3);
  if (u > 650) pathFlow(d, returnPath, C.amber, u - 650, 720, 0, true, 1);
  text(d, 50, 643, '延迟回流', 30, C.amber, 'left', 500);
}

export function drawFeedback(d: Draw) {
  const u = sceneFrame(d, 1800, 2700);
  if (d.p) feedbackPortrait(d, u);
  else feedbackLandscape(d, u);
}
