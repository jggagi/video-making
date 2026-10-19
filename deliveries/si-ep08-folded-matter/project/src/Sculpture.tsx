import React from 'react';

type Phase = 'human' | 'erode' | 'gold' | 'compare';
type Vec3 = {x: number; y: number; z: number};
type Projected = {x: number; y: number; depth: number};
type Props = {frame: number; phase: Phase; width: number; height: number};

const AMBER = '#f59e0b';
const RED = '#ef4444';
const CYAN = '#06b6d4';
const TEAL = '#10b981';
const GOLD = '#facc15';
const WHITE = '#ffffff';
const clamp = (n: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, n));
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const hash = (n: number) => {
  const v = Math.sin(n * 127.1 + 311.7) * 43758.5453123;
  return v - Math.floor(v);
};
const ease = (t: number) => {
  const x = clamp(t);
  return x * x * (3 - 2 * x);
};

function project(p: Vec3, yaw: number, pitch = 0.43): Projected {
  const c = Math.cos(yaw);
  const s = Math.sin(yaw);
  const x = p.x * c - p.z * s;
  const z = p.x * s + p.z * c;
  const y = p.y * Math.cos(pitch) - z * Math.sin(pitch);
  const depth = p.y * Math.sin(pitch) + z * Math.cos(pitch);
  const perspective = 2.65 / (2.65 + depth * 0.27);
  return {x: x * perspective, y: -y * perspective, depth};
}

function projectedPath(points: Vec3[], yaw: number, frame: number, flex = 0, steps = 7): {d: string; depth: number} {
  const all: Projected[] = [];
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    for (let j = 0; j < steps; j += 1) {
      const t = j / steps;
      const t2 = t * t;
      const t3 = t2 * t;
      const q = (axis: 'x' | 'y' | 'z') => 0.5 * (
        2 * p1[axis] + (-p0[axis] + p2[axis]) * t +
        (2 * p0[axis] - 5 * p1[axis] + 4 * p2[axis] - p3[axis]) * t2 +
        (-p0[axis] + 3 * p1[axis] - 3 * p2[axis] + p3[axis]) * t3
      );
      const wobble = flex * Math.sin(frame * 0.018 + i * 1.27 + j * 0.11);
      all.push(project({x: q('x'), y: q('y') + wobble * 0.09, z: q('z') + wobble * 0.2}, yaw));
    }
  }
  all.push(project(points[points.length - 1], yaw));
  const d = all.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(3)},${p.y.toFixed(3)}`).join(' ');
  return {d, depth: all.reduce((sum, p) => sum + p.depth, 0) / all.length};
}

type BoneMaterial = 'gold' | 'cyan';

function tube(d: string, width: number, depth: number, key: string, opacity = 1, strong = false, material: BoneMaterial = 'gold'): React.ReactNode {
  const front = depth > 0;
  const base = material === 'cyan'
    ? (front ? (strong ? '#5ce3d0' : '#30b6ab') : (strong ? '#157f78' : '#0d625f'))
    : (front ? (strong ? '#f3c85a' : '#d6a23e') : (strong ? '#9c5e15' : '#77501e'));
  const shine = material === 'cyan' ? (front ? '#e1fff8' : '#70d5c8') : (front ? '#fff4c5' : '#d49b37');
  return <g key={key} opacity={opacity} fill="none" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} stroke="#291b0d" strokeOpacity={front ? 0.72 : 0.54} strokeWidth={width + 0.035}/>
    <path d={d} stroke={base} strokeOpacity={front ? 0.98 : 0.83} strokeWidth={width}/>
    <path d={d} transform="translate(-0.012 -0.013)" stroke={shine} strokeOpacity={front ? 0.74 : 0.34} strokeWidth={Math.max(0.009, width * 0.22)}/>
    {strong && <path d={d} transform="translate(0.013 0.012)" stroke="#8c570e" strokeOpacity="0.5" strokeWidth={Math.max(0.008, width * 0.18)}/>}
  </g>;
}

function boneScene(frame: number, yaw: number, opacity = 1, detail = true, phase = 1, material: BoneMaterial = 'gold'): React.ReactNode[] {
  const elements: React.ReactNode[] = [];
  const flex = phase * (0.035 + Math.sin(frame * 0.013) * 0.018);
  const layers = detail ? [-0.34, 0.34] : [0.34];
  const joints: Array<{p: Vec3; key: string; r: number}> = [];
  const struts: Array<{d: string; depth: number; w: number; key: string; strong: boolean}> = [];
  const outerXY: Array<[number, number]> = [
    [-0.83, -0.88], [-0.89, -0.55], [-0.9, -0.1], [-0.88, 0.31],
    [-0.77, 0.54], [-0.52, 0.71], [-0.2, 0.79], [0.16, 0.78],
    [0.49, 0.7], [0.75, 0.54], [0.88, 0.3], [0.9, -0.1],
    [0.89, -0.55], [0.83, -0.88],
  ];
  for (const z of layers) {
    const pathPoints = outerXY.map(([x, y], i) => ({
      x,
      y: y + flex * Math.sin(frame * 0.016 + i * 0.71) * (0.45 + 0.35 * (1 - Math.abs(x))),
      z: z + flex * Math.sin(frame * 0.012 + i) * 0.22,
    }));
    const ring = projectedPath(pathPoints, yaw, frame, flex, 5);
    struts.push({d: ring.d, depth: ring.depth, w: 0.132, key: `outer-${z}`, strong: true});
    pathPoints.forEach((p, i) => joints.push({p, key: `outer-j-${z}-${i}`, r: i % 4 === 0 ? 0.031 : 0.024}));
  }

  // Uneven nodes and bowed branches leave broad, unequal pores through the bracket web.
  const webXY: Array<[number, number]> = [
    [-0.66, 0.2], [-0.24, 0.42], [0.46, 0.23],
    [-0.61, -0.39], [-0.035, -0.12], [0.62, -0.42],
    [0.25, 0.56],
  ];
  const connections: Array<{a: number; b: number; bend: Vec3; strong: boolean}> = [
    {a: 0, b: 1, bend: {x: 0.04, y: 0.17, z: 0.025}, strong: true},
    {a: 1, b: 2, bend: {x: -0.11, y: -0.17, z: -0.035}, strong: true},
    {a: 3, b: 4, bend: {x: -0.13, y: 0.2, z: 0.035}, strong: true},
    {a: 4, b: 5, bend: {x: 0.17, y: -0.18, z: -0.025}, strong: true},
    {a: 0, b: 4, bend: {x: 0.12, y: 0.08, z: 0.06}, strong: false},
    {a: 1, b: 4, bend: {x: 0.09, y: -0.01, z: -0.055}, strong: true},
    {a: 2, b: 4, bend: {x: -0.15, y: -0.12, z: 0.04}, strong: false},
    {a: 1, b: 6, bend: {x: 0.09, y: 0.1, z: 0.035}, strong: true},
    {a: 6, b: 2, bend: {x: 0.02, y: -0.13, z: -0.04}, strong: false},
    {a: 4, b: 6, bend: {x: -0.16, y: 0.15, z: 0.055}, strong: false},
  ];
  const anchorBranches: Array<{node: number; x: number; y: number; bend: Vec3}> = [
    {node: 0, x: -0.86, y: 0.13, bend: {x: -0.11, y: -0.09, z: 0.02}},
    {node: 3, x: -0.83, y: -0.82, bend: {x: -0.04, y: 0.12, z: -0.01}},
    {node: 6, x: 0.02, y: 0.72, bend: {x: -0.08, y: 0.1, z: 0.02}},
    {node: 2, x: 0.86, y: 0.13, bend: {x: 0.11, y: -0.07, z: 0.015}},
    {node: 5, x: 0.83, y: -0.82, bend: {x: 0.04, y: 0.12, z: -0.015}},
  ];
  const webLayers: Vec3[][] = [];
  for (let layerIndex = 0; layerIndex < layers.length; layerIndex += 1) {
    const z = layers[layerIndex];
    const web = webXY.map(([x, y], i) => {
      const id = layerIndex * 37 + i * 3;
      const p = {
        x: x + (hash(id + 8) - 0.5) * 0.12,
        y: y + (hash(id + 43) - 0.5) * 0.095 + flex * Math.sin(frame * 0.019 + id) * 0.18,
        z: z + (hash(id + 81) - 0.5) * 0.075 + flex * Math.cos(frame * 0.014 + id) * 0.24,
      };
      joints.push({p, key: `web-j-${id}`, r: 0.02 + hash(id + 119) * 0.012});
      return p;
    });
    webLayers.push(web);
    connections.forEach((connection, connectionIndex) => {
      const a = web[connection.a];
      const b = web[connection.b];
      const bend = connection.bend;
      const middle = {
        x: (a.x + b.x) / 2 + bend.x,
        y: (a.y + b.y) / 2 + bend.y,
        z: (a.z + b.z) / 2 + bend.z,
      };
      const path = projectedPath([a, middle, b], yaw, frame, flex, 10);
      const width = connection.strong ? 0.094 + hash(connectionIndex + layerIndex * 17) * 0.035 : 0.065 + hash(connectionIndex + 29) * 0.025;
      struts.push({d: path.d, depth: path.depth, w: width, key: `web-${layerIndex}-${connectionIndex}`, strong: connection.strong});
    });
    anchorBranches.forEach((branch, branchIndex) => {
      const start = web[branch.node];
      const end = {x: branch.x, y: branch.y, z: z + (hash(branchIndex + 77) - 0.5) * 0.04};
      const bend = branch.bend;
      const middle = {x: (start.x + end.x) / 2 + bend.x, y: (start.y + end.y) / 2 + bend.y, z: (start.z + end.z) / 2 + bend.z};
      const path = projectedPath([start, middle, end], yaw, frame, flex, 10);
      struts.push({d: path.d, depth: path.depth, w: 0.096 + (branchIndex % 2) * 0.018, key: `branch-${layerIndex}-${branchIndex}`, strong: true});
      joints.push({p: end, key: `branch-j-${layerIndex}-${branchIndex}`, r: 0.025});
    });
  }

  // A few curved depth ribs make the gold form read as a spatial bracket.
  if (webLayers.length > 1) {
    [0, 2, 4, 6].forEach((index, i) => {
      const back = webLayers[0][index];
      const front = webLayers[webLayers.length - 1][index];
      const middle = {x: (back.x + front.x) / 2 + (i % 2 ? 0.035 : -0.035), y: (back.y + front.y) / 2 + (i % 2 ? 0.05 : -0.04), z: (back.z + front.z) / 2};
      const path = projectedPath([back, middle, front], yaw, frame, flex, 8);
      struts.push({d: path.d, depth: path.depth, w: 0.075, key: `depth-rib-${i}`, strong: true});
    });
  }

  struts.sort((a, b) => a.depth - b.depth);
  struts.forEach((s) => elements.push(tube(s.d, s.w, s.depth, s.key, opacity, s.strong, material)));

  const loadPoints: Vec3[] = [
    {x: -0.83, y: -0.81, z: 0.37}, {x: -0.71, y: -0.48, z: 0.37},
    {x: -0.48, y: -0.18, z: 0.38}, {x: -0.13, y: 0.16, z: 0.39},
    {x: 0, y: 0.58, z: 0.37}, {x: 0.2, y: 0.2, z: 0.39},
    {x: 0.52, y: -0.14, z: 0.38}, {x: 0.72, y: -0.48, z: 0.37}, {x: 0.83, y: -0.81, z: 0.37},
  ];
  const load = projectedPath(loadPoints, yaw, frame, flex, 8);
  const pulse = 0.55 + 0.45 * Math.sin(frame * 0.026);
  elements.push(<g key="load-path" opacity={opacity * phase} fill="none" strokeLinecap="round" strokeLinejoin="round">
    <path d={load.d} stroke={CYAN} strokeOpacity={0.12 + pulse * 0.12} strokeWidth="0.13"/>
    <path d={load.d} stroke={TEAL} strokeOpacity="0.85" strokeWidth="0.035"/>
    <path d={load.d} stroke="#d5ffff" strokeOpacity={0.82} strokeWidth="0.009"/>
  </g>);
  const along = ((frame * 0.006) % 1 + 1) % 1;
  const pulseIndex = Math.min(loadPoints.length - 2, Math.floor(along * (loadPoints.length - 1)));
  const pulseT = along * (loadPoints.length - 1) - pulseIndex;
  const a = loadPoints[pulseIndex];
  const b = loadPoints[pulseIndex + 1];
  const pulsePos = project({x: mix(a.x, b.x, pulseT), y: mix(a.y, b.y, pulseT), z: mix(a.z, b.z, pulseT)}, yaw);
  elements.push(<g key="load-pulse" opacity={opacity * phase}>
    <circle cx={pulsePos.x} cy={pulsePos.y} r="0.075" fill={CYAN} opacity="0.23"/>
    <circle cx={pulsePos.x} cy={pulsePos.y} r="0.026" fill={WHITE}/>
  </g>);

  joints.sort((a, b) => project(a.p, yaw).depth - project(b.p, yaw).depth);
  joints.forEach(({p, key, r}) => {
    const q = project(p, yaw);
    const outer = material === 'cyan' ? '#075f5b' : '#482d0c';
    const middle = material === 'cyan' ? (q.depth > 0 ? '#48d6c6' : '#187e77') : (q.depth > 0 ? '#f4cd66' : '#a66b20');
    const glint = material === 'cyan' ? '#dcfff8' : '#fff4c2';
    elements.push(<g key={key} opacity={opacity}>
      <circle cx={q.x} cy={q.y} r={r} fill={outer} stroke={material === 'cyan' ? '#8dfff0' : '#f6d071'} strokeOpacity="0.48" strokeWidth="0.009"/>
      <circle cx={q.x - r * 0.16} cy={q.y - r * 0.18} r={r * 0.58} fill={middle}/>
      <circle cx={q.x - r * 0.27} cy={q.y - r * 0.34} r={r * 0.17} fill={glint} opacity="0.78"/>
    </g>);
  });

  [-1, 1].forEach((side) => {
    const mount = project({x: side * 0.83, y: -0.84, z: 0.38}, yaw);
    const hole = material === 'cyan' ? '#092b2b' : '#442d12';
    elements.push(<g key={`mount-${side}`} opacity={opacity}>
      <circle cx={mount.x} cy={mount.y} r="0.088" fill={hole} stroke={material === 'cyan' ? '#8df5df' : '#ffe19a'} strokeOpacity="0.8" strokeWidth="0.018"/>
      <circle cx={mount.x} cy={mount.y} r="0.052" fill="#071417" stroke={material === 'cyan' ? '#20aaa1' : '#b17a23'} strokeWidth="0.009"/>
      <circle cx={mount.x - 0.025} cy={mount.y - 0.03} r="0.012" fill={WHITE} opacity="0.55"/>
    </g>);
  });
  return elements;
}

type Face = {points: Vec3[]; color: string; depth: number; key: string};
const metalPalette = ['#f3b12e', '#c17b12', '#ffdc78', '#9b5d0d', '#e99a18', '#a56712'];

function boxFaces(box: {x0: number; x1: number; y0: number; y1: number; z0: number; z1: number}, yaw: number, prefix: string): Face[] {
  const {x0, x1, y0, y1, z0, z1} = box;
  const v: Vec3[] = [
    {x: x0, y: y0, z: z0}, {x: x1, y: y0, z: z0}, {x: x1, y: y1, z: z0}, {x: x0, y: y1, z: z0},
    {x: x0, y: y0, z: z1}, {x: x1, y: y0, z: z1}, {x: x1, y: y1, z: z1}, {x: x0, y: y1, z: z1},
  ];
  const definitions = [[0, 1, 2, 3], [4, 5, 6, 7], [3, 2, 6, 7], [0, 1, 5, 4], [0, 3, 7, 4], [1, 2, 6, 5]];
  return definitions.map((indexes, i) => {
    const points = indexes.map((index) => v[index]);
    const depth = points.reduce((sum, p) => sum + project(p, yaw).depth, 0) / points.length;
    return {points, color: metalPalette[i], depth, key: `${prefix}-${i}`};
  });
}

function prismFaces(poly: Array<[number, number]>, z0: number, z1: number, yaw: number, prefix: string): Face[] {
  const front = poly.map(([x, y]) => ({x, y, z: z1}));
  const back = poly.map(([x, y]) => ({x, y, z: z0}));
  const faces: Face[] = [
    {points: front, color: '#f3ae28', depth: front.reduce((s, p) => s + project(p, yaw).depth, 0) / front.length, key: `${prefix}-front`},
    {points: back, color: '#9c5e10', depth: back.reduce((s, p) => s + project(p, yaw).depth, 0) / back.length, key: `${prefix}-back`},
  ];
  for (let i = 0; i < poly.length; i += 1) {
    const j = (i + 1) % poly.length;
    const points = [front[i], front[j], back[j], back[i]];
    faces.push({points, color: i % 2 ? '#b87311' : '#d48a19', depth: points.reduce((s, p) => s + project(p, yaw).depth, 0) / points.length, key: `${prefix}-side-${i}`});
  }
  return faces;
}

function rigidFaces(yaw: number, broken = false): Face[] {
  const boxes = [
    {x0: -0.94, x1: -0.69, y0: -0.82, y1: 0.51, z0: -0.32, z1: 0.32},
    {x0: 0.69, x1: 0.94, y0: -0.82, y1: 0.51, z0: -0.32, z1: 0.32},
    {x0: -0.94, x1: broken ? -0.1 : 0.94, y0: 0.38, y1: 0.7, z0: -0.32, z1: 0.32},
    ...broken ? [{x0: 0.1, x1: 0.94, y0: 0.38, y1: 0.7, z0: -0.32, z1: 0.32}] : [],
    {x0: -0.99, x1: -0.64, y0: -0.98, y1: -0.78, z0: -0.42, z1: 0.42},
    {x0: 0.64, x1: 0.99, y0: -0.98, y1: -0.78, z0: -0.42, z1: 0.42},
  ];
  const faces = boxes.flatMap((box, i) => boxFaces(box, yaw, `box-${i}`));
  faces.push(...prismFaces([[-0.84, 0.43], [-0.54, 0.43], [-0.7, 0.05]], -0.31, 0.31, yaw, 'gusset-l'));
  faces.push(...prismFaces([[0.84, 0.43], [0.54, 0.43], [0.7, 0.05]], -0.31, 0.31, yaw, 'gusset-r'));
  if (broken) {
    faces.push(...boxFaces({x0: -0.066, x1: -0.025, y0: 0.5, y1: 0.6, z0: -0.2, z1: 0.22}, yaw, 'fracture-left'));
    faces.push(...boxFaces({x0: 0.028, x1: 0.075, y0: 0.44, y1: 0.54, z0: -0.18, z1: 0.2}, yaw, 'fracture-right'));
  }
  return faces.sort((a, b) => a.depth - b.depth);
}

function drawRigid(yaw: number, frame: number, broken: boolean, opacity = 1): React.ReactNode[] {
  const elements: React.ReactNode[] = rigidFaces(yaw, broken).map((face) => {
    const points = face.points.map((p) => project(p, yaw));
    const d = points.map((p) => `${p.x},${p.y}`).join(' ');
    return <polygon key={face.key} points={d} fill={face.color} fillOpacity="0.96" stroke="#ffe09a" strokeOpacity="0.39" strokeWidth="0.012" strokeLinejoin="round" opacity={opacity}/>;
  });
  const bolts = [-0.82, 0.82].flatMap((x, i) => [-0.89, -0.77].map((y, j) => {
    const p = project({x, y, z: 0.425}, yaw);
    return <g key={`bolt-${i}-${j}`} opacity={opacity}>
      <circle cx={p.x} cy={p.y} r="0.075" fill="#5d390d" stroke="#ffe49f" strokeWidth="0.018"/>
      <circle cx={p.x} cy={p.y} r="0.042" fill="#241a11" stroke="#d99b35" strokeWidth="0.009"/>
      <path d={`M${p.x - 0.022} ${p.y}H${p.x + 0.022}`} stroke="#e4c27a" strokeWidth="0.008"/>
    </g>;
  }));
  elements.push(...bolts);
  const stressAt = [project({x: -0.77, y: 0.42, z: 0.35}, yaw), project({x: 0.77, y: 0.42, z: 0.35}, yaw)];
  stressAt.forEach((p, i) => {
    const pulse = 0.55 + Math.sin(frame * 0.035 + i) * 0.18;
    elements.push(<g key={`stress-${i}`} opacity={opacity * pulse}>
      <circle cx={p.x} cy={p.y} r="0.23" fill="url(#sc-stress)"/>
      <path d={`M${p.x - 0.14} ${p.y}Q${p.x} ${p.y - 0.16} ${p.x + 0.14} ${p.y}`} fill="none" stroke={RED} strokeWidth="0.018" strokeOpacity="0.88"/>
      <circle cx={p.x} cy={p.y} r="0.045" fill="#ffd5b8" stroke={RED} strokeWidth="0.016"/>
    </g>);
  });
  return elements;
}

function debris(frame: number, progress: number): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  for (let i = 0; i < 62; i += 1) {
    const birth = hash(i + 901);
    if (progress <= birth) continue;
    const age = clamp((progress - birth) / (1 - birth));
    const sx = (hash(i + 77) - 0.5) * 1.65;
    const sy = (hash(i + 188) - 0.5) * 1.18;
    const dx = sx === 0 ? 0.2 : sx * 0.85;
    const dy = sy === 0 ? -0.15 : sy * 0.82 - 0.14;
    const x = sx + dx * age + Math.sin(frame * 0.018 + i) * 0.025;
    const y = sy + dy * age + Math.cos(frame * 0.02 + i * 0.5) * 0.025;
    const size = 0.018 + hash(i + 144) * 0.043;
    out.push(<rect key={`debris-${i}`} x={x} y={y} width={size} height={size} rx={size * 0.12}
      fill={i % 8 === 0 ? RED : i % 5 === 0 ? '#d7b970' : AMBER} opacity={(1 - age) * (0.35 + (i % 4) * 0.11)}
      transform={`rotate(${i * 31 + age * 90} ${x} ${y})`}/>);
  }
  return out;
}

function forceArrows(frame: number, color: string, broken: boolean): React.ReactNode[] {
  const amp = 0.86 + Math.sin(frame * 0.028) * 0.12;
  return [-0.55, 0, 0.55].map((x, i) => {
    const tipY = broken && i === 1 ? -0.5 : -0.56;
    return <g key={`force-${i}`} opacity={0.52 + amp * 0.36} stroke={color} fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d={`M${x} -1.14V${tipY - 0.12}`} strokeWidth="0.014" strokeDasharray="0.06 0.08"/>
      <path d={`M${x - 0.055} ${tipY - 0.11}L${x} ${tipY}L${x + 0.055} ${tipY - 0.11}`} strokeWidth="0.023"/>
      <circle cx={x} cy="-1.14" r="0.035" fill={color} fillOpacity="0.42" stroke="none"/>
    </g>;
  });
}

function SculptureDefs() {
  return <defs>
    <radialGradient id="sc-stress">
      <stop offset="0" stopColor="#fff0d0" stopOpacity="0.94"/>
      <stop offset="0.24" stopColor={RED} stopOpacity="0.72"/>
      <stop offset="1" stopColor={RED} stopOpacity="0"/>
    </radialGradient>
    <radialGradient id="sc-core">
      <stop offset="0" stopColor="#ffffff" stopOpacity="0.75"/>
      <stop offset="0.26" stopColor={GOLD} stopOpacity="0.24"/>
      <stop offset="1" stopColor={GOLD} stopOpacity="0"/>
    </radialGradient>
  </defs>;
}

function drawBracketGroup(frame: number, yaw: number, scale: number, cx: number, cy: number, style: 'rigid' | 'broken' | 'bone', opacity = 1, detail = true) {
  return <g transform={`translate(${cx} ${cy}) scale(${scale})`}>
    {style !== 'bone' && drawRigid(yaw, frame, style === 'broken', opacity)}
    {style !== 'rigid' && boneScene(frame, yaw, opacity, detail, 1)}
  </g>;
}

const Sculpture: React.FC<Props> = ({frame, phase, width, height}) => {
  const minDimension = Math.min(width, height);
  const centerX = width / 2;
  const centerY = height / 2;
  const portrait = width < 950;
  const landscape = !portrait;
  const yaw = phase === 'compare'
    ? 0.34 + 0.42 * Math.sin((frame - 4440) / 420)
    : 0.32 + 0.55 * Math.sin(frame / 550);

  let scene: React.ReactNode;
  if (phase === 'human') {
    scene = <g transform={`translate(${centerX} ${centerY}) scale(${minDimension * 0.38})`}>
      {drawRigid(yaw, frame, false)}
      {forceArrows(frame, RED, false)}
    </g>;
  } else if (phase === 'erode') {
    const progress = ease((frame - 1800) / 1800);
    scene = <g transform={`translate(${centerX} ${centerY}) scale(${minDimension * 0.38})`}>
      {drawRigid(yaw, frame, false, 1 - progress)}
      <g opacity={progress}>{boneScene(frame, yaw, 1, true, progress, frame <= 3600 ? 'cyan' : 'gold')}</g>
      {debris(frame, progress)}
      {forceArrows(frame, RED, false).map((arrow, i) => <g key={`erode-force-${i}`} opacity={1 - progress}>{arrow}</g>)}
    </g>;
  } else if (phase === 'gold') {
    scene = <g transform={`translate(${centerX} ${centerY}) scale(${minDimension * 0.38})`}>
      <circle r="1.22" fill="url(#sc-core)" opacity="0.72"/>
      {boneScene(frame, yaw, 1, true, 1)}
      {forceArrows(frame, CYAN, false).map((arrow, i) => <g key={`gold-force-${i}`} opacity="0.54">{arrow}</g>)}
    </g>;
  } else {
    const panelWidth = landscape ? width / 2 : width;
    const panelHeight = landscape ? height : height / 2;
    const panelScale = Math.min(panelWidth / 2.65, panelHeight / 2.5);
    const dividerColor = '#f4d273';
    if (landscape) {
      scene = <g>
        <path d={`M${centerX} ${height * 0.12}V${height * 0.88}`} stroke={dividerColor} strokeOpacity="0.35" strokeWidth={Math.max(2, minDimension * 0.001)}/>
        <g transform={`translate(${width * 0.25} ${centerY}) scale(${panelScale})`}>
          {drawRigid(yaw, frame, true, 1)}
          {forceArrows(frame, RED, true)}
        </g>
        <g transform={`translate(${width * 0.75} ${centerY}) scale(${panelScale})`}>
          {boneScene(frame, yaw + 0.25, 1, false, 1)}
          {forceArrows(frame, CYAN, false).map((arrow, i) => <g key={`compare-good-${i}`} opacity="0.68">{arrow}</g>)}
        </g>
      </g>;
    } else {
      scene = <g>
        <path d={`M${width * 0.12} ${centerY}H${width * 0.88}`} stroke={dividerColor} strokeOpacity="0.35" strokeWidth={Math.max(2, minDimension * 0.001)}/>
        <g transform={`translate(${centerX} ${height * 0.25}) scale(${panelScale})`}>
          {drawRigid(yaw, frame, true, 1)}
          {forceArrows(frame, RED, true)}
        </g>
        <g transform={`translate(${centerX} ${height * 0.75}) scale(${panelScale})`}>
          {boneScene(frame, yaw + 0.25, 1, false, 1)}
          {forceArrows(frame, CYAN, false).map((arrow, i) => <g key={`compare-good-${i}`} opacity="0.68">{arrow}</g>)}
        </g>
      </g>;
    }
  }

  return <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} xmlns="http://www.w3.org/2000/svg" fill="none" overflow="hidden">
    <SculptureDefs/>
    {scene}
  </svg>;
};

export default Sculpture;
