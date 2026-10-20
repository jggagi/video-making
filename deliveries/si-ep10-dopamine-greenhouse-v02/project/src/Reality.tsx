import React from 'react';

type V3 = {x: number; y: number; z: number};
type P2 = {x: number; y: number};
type Face = {a: number; b: number; c: number; key: string};

const CX = 638;
const CY = 850;
const ROW_Y = [-282, -218, -148, -77, -5, 68, 139, 211, 278];
const ROW_W = [8, 49, 88, 116, 122, 108, 82, 49, 15];
const COLS = 5;
const clamp = (v: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
const smooth = (v: number) => { const t = clamp(v); return t * t * (3 - 2 * t); };
const fmt = (v: number) => Number(v.toFixed(2));

function camera(frame: number) {
  const t = frame - 4891;
  return {
    yaw: 0.24 + 0.1 * Math.sin(t * 0.012) + 0.014 * Math.sin(t * 0.0047),
    pitch: 0.032 * Math.sin(t * 0.009 + 0.8),
  };
}

function project(v: V3, frame: number): P2 {
  const {yaw, pitch} = camera(frame);
  const cyaw = Math.cos(yaw);
  const syaw = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const rx = v.x * cyaw + v.z * syaw;
  const rz = -v.x * syaw + v.z * cyaw;
  const ry = v.y * cp - rz * sp;
  const depth = v.y * sp + rz * cp;
  const perspective = 2100 / (2100 - depth);
  return {
    x: CX + (v.x * 0.175) + rx * perspective,
    y: CY + ry * perspective,
  };
}

function cross(a: V3, b: V3, c: V3): V3 {
  const ab = {x: b.x - a.x, y: b.y - a.y, z: b.z - a.z};
  const ac = {x: c.x - a.x, y: c.y - a.y, z: c.z - a.z};
  return {
    x: ab.y * ac.z - ab.z * ac.y,
    y: ab.z * ac.x - ab.x * ac.z,
    z: ab.x * ac.y - ab.y * ac.x,
  };
}

function unit(v: V3): V3 {
  const m = Math.hypot(v.x, v.y, v.z) || 1;
  return {x: v.x / m, y: v.y / m, z: v.z / m};
}

function faceFill(a: V3, b: V3, c: V3, frame: number, index: number): string {
  let n = unit(cross(a, b, c));
  const {yaw, pitch} = camera(frame);
  const nx = n.x * Math.cos(yaw) + n.z * Math.sin(yaw);
  const nz = -n.x * Math.sin(yaw) + n.z * Math.cos(yaw);
  const ny = n.y * Math.cos(pitch) - nz * Math.sin(pitch);
  const nz2 = n.y * Math.sin(pitch) + nz * Math.cos(pitch);
  const light = Math.max(0, nx * -0.42 + ny * -0.5 + nz2 * 0.76);
  const tone = clamp(0.08 + light * 0.88 + 0.08 * Math.sin(index * 2.37), 0, 1);
  const lo = [7, 11, 17];
  const hi = [77, 88, 98];
  const rgb = lo.map((v, i) => Math.round(v + (hi[i] - v) * tone));
  return `#${rgb.map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}

function makeFront(frame: number): V3[] {
  const t = frame - 4891;
  const points: V3[] = [];
  for (let r = 0; r < ROW_Y.length; r++) {
    const width = ROW_W[r];
    for (let c = 0; c < COLS; c++) {
      const across = (c / (COLS - 1)) * 2 - 1;
      const x = width * across + 4.2 * Math.sin(r * 1.17 + c * 2.03) + 1.7 * Math.sin(t * 0.018 + r * 0.8 + c);
      const y = ROW_Y[r] + 3.2 * Math.sin(c * 1.46 + r * 0.83 + t * 0.011);
      const ridge = 27 * (1 - across * across);
      const z = ridge + 9 * Math.sin(r * 0.91 + c * 1.8 + t * 0.008) + 2.5 * Math.sin(t * 0.019 + c + r * 0.6);
      points.push({x, y, z});
    }
  }
  return points;
}

function frontFaces(): Face[] {
  const faces: Face[] = [];
  for (let r = 0; r < ROW_Y.length - 1; r++) {
    for (let c = 0; c < COLS - 1; c++) {
      const a = r * COLS + c;
      const b = a + 1;
      const d = (r + 1) * COLS + c + 1;
      const e = (r + 1) * COLS + c;
      if ((r + c) % 2 === 0) {
        faces.push({a, b, c: d, key: `f${r}-${c}-a`}, {a, b: d, c: e, key: `f${r}-${c}-b`});
      } else {
        faces.push({a, b, c: e, key: `f${r}-${c}-a`}, {a: b, b: d, c: e, key: `f${r}-${c}-b`});
      }
    }
  }
  return faces;
}

const FACES = frontFaces();
const BOUNDARY = [
  ...ROW_Y.map((_, r) => r * COLS),
  ...ROW_Y.map((_, r) => r * COLS + COLS - 1).reverse(),
];

function surfaceAt(x: number, y: number, frame: number): V3 {
  let row = 0;
  while (row < ROW_Y.length - 2 && y > ROW_Y[row + 1]) row++;
  const u = clamp((y - ROW_Y[row]) / (ROW_Y[row + 1] - ROW_Y[row]));
  const width = ROW_W[row] + (ROW_W[row + 1] - ROW_W[row]) * u;
  const safeWidth = Math.max(1, width - 7);
  const across = clamp(x / safeWidth, -1, 1);
  const t = frame - 4891;
  return {
    x,
    y,
    z: 27 * (1 - across * across) + 9 * Math.sin(row * 0.91 + across * 3.6 + t * 0.008),
  };
}

function xyPath(points: P2[], close = false): string {
  if (!points.length) return '';
  return `M${points.map((p) => `${fmt(p.x)} ${fmt(p.y)}`).join('L')}${close ? 'Z' : ''}`;
}

function worldPoints(frame: number) {
  const front = makeFront(frame);
  const back = front.map((p) => ({x: p.x - 2.2, y: p.y + 1.2, z: p.z - 52}));
  return {front, back};
}

function meshPath(front: V3[], frame: number): string {
  return xyPath(BOUNDARY.map((i) => project(front[i], frame)), true);
}

function localImpactPoint(index: number, frame: number): P2 {
  const y = 17 * Math.sin(index * 1.47 + 0.35);
  const v = surfaceAt(-118 + Math.abs(y) * 0.14, y, frame);
  return project(v, frame);
}

function motionPoint(x0: number, y0: number, vx: number, vy: number, gravity: number, drag: number, t: number): P2 {
  return {
    x: x0 + (vx / drag) * (1 - Math.exp(-drag * t)),
    y: y0 + vy * t + 0.5 * gravity * t * t,
  };
}

function particlePath(x: number, y: number, vx: number, vy: number, gravity: number, age: number): string {
  const end = age / 60;
  const start = Math.max(0, end - 0.105);
  const points = Array.from({length: 6}, (_, i) => motionPoint(x, y, vx, vy, gravity, 1.8, start + (end - start) * i / 5));
  return xyPath(points);
}

function emberPoint(frame:number):P2 {
  const index=frame<4900?0:Math.floor((frame-4900)/90);
  const impact=localImpactPoint(index,frame);
  if(frame<4900)return {x:300+(impact.x-300)*smooth((frame-4891)/9),y:impact.y};
  const age=(frame-4900)%90;
  if(age<34) {
    const retreat=smooth(age/34);
    return {x:impact.x-(impact.x-334)*retreat,y:impact.y+12*Math.sin(age*Math.PI/90)};
  }
  const next=localImpactPoint(index+1,frame);
  const q=(age-34)/56,approach=smooth(q);
  return {x:334+(next.x-334)*approach,y:(impact.y+12*Math.sin(34*Math.PI/90))*(1-approach)+next.y*approach+7*Math.sin(q*Math.PI)};
}
function HumanEmber({frame,reveal}:{frame:number;reveal:number}) {
  const p=emberPoint(frame),breath=1+.12*Math.sin((frame-4891)*.11);
  const tail=Array.from({length:10},(_,i)=>emberPoint(Math.max(4891,frame-i*2)));
  return <g opacity={fmt(reveal)}>
    <path d={xyPath(tail)} fill="none" stroke="#f59e0b" strokeWidth="2.4" strokeOpacity=".45"/>
    <circle cx={fmt(p.x)} cy={fmt(p.y)} r={fmt(28*breath)} fill="url(#realSparkCore)" opacity=".48"/>
    <circle cx={fmt(p.x)} cy={fmt(p.y)} r={fmt(6*breath)} fill="#f59e0b"/>
    <circle cx={fmt(p.x-1.5)} cy={fmt(p.y-1.5)} r="2.2" fill="#fff1c4"/>
  </g>;
}

function Plane({frame, reveal}: {frame: number; reveal: number}) {
  const {front, back} = worldPoints(frame);
  const projectedFront = front.map((v) => project(v, frame));
  const projectedBack = back.map((v) => project(v, frame));
  const outline = meshPath(front, frame);
  const backFaces = FACES.map((f) => {
    const a = back[f.a]; const b = back[f.c]; const c = back[f.b];
    const p = [projectedBack[f.a], projectedBack[f.c], projectedBack[f.b]];
    return <polygon key={`back-${f.key}`} points={p.map((v) => `${fmt(v.x)},${fmt(v.y)}`).join(' ')} fill={faceFill(a, b, c, frame, 200 + FACES.indexOf(f))} opacity="0.88" stroke="#3e4a56" strokeOpacity="0.16" strokeWidth="1" />;
  });
  const sides: React.ReactElement[] = [];
  for (let i = 0; i < BOUNDARY.length; i++) {
    const j = (i + 1) % BOUNDARY.length;
    const a = front[BOUNDARY[i]]; const b = front[BOUNDARY[j]];
    const c = back[BOUNDARY[j]]; const d = back[BOUNDARY[i]];
    const p = [projectedFront[BOUNDARY[i]], projectedFront[BOUNDARY[j]], projectedBack[BOUNDARY[j]], projectedBack[BOUNDARY[i]]];
    const fill = faceFill(a, b, c, frame, 400 + i);
    sides.push(<polygon key={`side-${i}`} points={p.map((v) => `${fmt(v.x)},${fmt(v.y)}`).join(' ')} fill={fill} stroke={i % 3 === 0 ? '#89949d' : '#26313b'} strokeOpacity={i % 3 === 0 ? '0.48' : '0.68'} strokeWidth={i % 3 === 0 ? '1.7' : '1.1'} strokeLinejoin="bevel" />);
  }
  const facets = FACES.map((face, index) => {
    const a = front[face.a]; const b = front[face.b]; const c = front[face.c];
    const pts = [projectedFront[face.a], projectedFront[face.b], projectedFront[face.c]];
    const tone = clamp(Math.hypot(...Object.values(cross(a, b, c))) / 12000);
    return <polygon key={face.key} points={pts.map((p) => `${fmt(p.x)},${fmt(p.y)}`).join(' ')} fill={faceFill(a, b, c, frame, index)} stroke={tone > 0.78 ? '#dbe1e4' : '#7a8791'} strokeOpacity={tone > 0.78 ? '0.44' : '0.19'} strokeWidth={tone > 0.78 ? '1.65' : '1.1'} strokeLinejoin="bevel" />;
  });
  const fractureA = [surfaceAt(-114, -57, frame), surfaceAt(-70, -25, frame), surfaceAt(-25, 4, frame)];
  const fractureB = [surfaceAt(-110, 55, frame), surfaceAt(-65, 83, frame), surfaceAt(-44, 126, frame)];
  const fractureC = [surfaceAt(106, -118, frame), surfaceAt(72, -83, frame), surfaceAt(44, -59, frame)];
  const glint1 = project(front[1 * COLS + 3], frame);
  const glint2 = project(front[5 * COLS + 2], frame);
  const shine = 0.36 + 0.31 * (0.5 + 0.5 * Math.sin((frame - 4891) * 0.047));
  return (
    <g opacity={fmt(reveal)}>
      <ellipse cx="652" cy="1143" rx="154" ry="24" fill="url(#realGroundShadow)" opacity="0.82" />
      <ellipse cx="650" cy="1140" rx="104" ry="11" fill="#4c5963" opacity="0.12" />
      <path d={xyPath(BOUNDARY.map((i) => projectedBack[i]), true)} fill="#070b11" stroke="#202a33" strokeWidth="1.2" />
      {backFaces}
      {sides}
      {facets}
      <path d={outline} fill="none" stroke="#cbd2d6" strokeWidth="2.8" strokeOpacity="0.72" strokeLinejoin="bevel" />
      <path d={xyPath(BOUNDARY.slice(0, 5).map((i) => projectedFront[i]))} fill="none" stroke="#fbfcfa" strokeWidth="4" strokeOpacity="0.8" strokeLinejoin="bevel" />
      <path d={xyPath(BOUNDARY.slice(4, 9).map((i) => projectedFront[i]))} fill="none" stroke="#9da8af" strokeWidth="2.2" strokeOpacity="0.62" strokeLinejoin="bevel" />
      <path d={xyPath(fractureA.map((v) => project(v, frame)))} fill="none" stroke="#c5cdd1" strokeWidth="1.3" strokeOpacity="0.58" />
      <path d={xyPath(fractureB.map((v) => project(v, frame)))} fill="none" stroke="#818d96" strokeWidth="1.15" strokeOpacity="0.52" />
      <path d={xyPath(fractureC.map((v) => project(v, frame)))} fill="none" stroke="#9ea8ad" strokeWidth="1.25" strokeOpacity="0.4" />
      <path d={`M${fmt(glint1.x - 4)} ${fmt(glint1.y - 1)}L${fmt(glint1.x + 7)} ${fmt(glint1.y - 4)}M${fmt(glint2.x - 3)} ${fmt(glint2.y + 2)}L${fmt(glint2.x + 6)} ${fmt(glint2.y - 1)}`} fill="none" stroke="#fffef7" strokeWidth="2.2" strokeLinecap="round" opacity={fmt(shine)} />
    </g>
  );
}

function Impacts({frame, reveal}: {frame: number; reveal: number}) {
  const hits = frame < 4900 ? 0 : Math.min(6, Math.floor((frame - 4900) / 90) + 1);
  const children: React.ReactElement[] = [];
  for (let index = 0; index < hits; index++) {
    const impactFrame = 4900 + index * 90;
    const age = frame - impactFrame;
    const hit = localImpactPoint(index, frame);
    const fade = Math.exp(-age / 190);
    const end1 = project(surfaceAt(-85, 5 + 23 * Math.sin(index * 1.5), frame), frame);
    const end2 = project(surfaceAt(-59, -23 + 19 * Math.cos(index * 1.13), frame), frame);
    children.push(
      <g key={`scar-${index}`} opacity={fmt(0.68 * fade)}>
        <path d={`M${fmt(hit.x)} ${fmt(hit.y)}L${fmt(end1.x)} ${fmt(end1.y)}M${fmt(end1.x)} ${fmt(end1.y)}L${fmt(end2.x)} ${fmt(end2.y)}`} fill="none" stroke="#df9d37" strokeWidth="1.5" strokeOpacity="0.62" />
        <path d={`M${fmt(end1.x)} ${fmt(end1.y)}L${fmt(end1.x + 13)} ${fmt(end1.y - 13)}`} fill="none" stroke="#c9b071" strokeWidth="0.9" strokeOpacity="0.56" />
      </g>,
    );
    if (age >= 0 && age <= 36) {
      const t = age / 60;
      for (let particle = 0; particle < 18; particle++) {
        const phase = (particle / 17 - 0.5) * 1.8;
        const angle = Math.PI + phase;
        const speed = 340 + 80 * (0.5 + 0.5 * Math.sin(index * 1.7 + particle * 2.31));
        const vx = speed * Math.cos(angle);
        const vy = speed * Math.sin(angle);
        const gravity = 420 + 140 * (0.5 + 0.5 * Math.sin(index * 0.8 + particle * 1.41));
        const head = motionPoint(hit.x, hit.y, vx, vy, gravity, 1.8, t);
        const opacity = clamp(Math.exp(-age/20) * (0.8 + 0.18 * Math.sin(particle * 1.6 + index)));
        const color = particle % 6 === 0 ? '#ef4444' : particle % 3 === 0 ? '#f59e0b' : '#facc15';
        children.push(
          <g key={`fragment-${index}-${particle}`} opacity={fmt(opacity)}>
            <path d={particlePath(hit.x, hit.y, vx, vy, gravity, age)} fill="none" stroke={color} strokeWidth={particle % 4 === 0 ? '3.1' : '2.2'} strokeLinecap="round" />
            <circle cx={fmt(head.x)} cy={fmt(head.y)} r={particle % 5 === 0 ? '2.5' : '1.65'} fill={particle % 6 === 0 ? '#ff8464' : '#fff0b0'} />
          </g>,
        );
      }
      if (age <= 3) {
        const pulse = (1 - age / 4) * (0.62 + 0.2 * Math.sin(age * 2.1 + index));
        children.push(<circle key={`impact-flash-${index}`} cx={fmt(hit.x)} cy={fmt(hit.y)} r="17" fill="url(#realSparkCore)" opacity={fmt(pulse)} />);
      }
    }
  }
  return <g opacity={fmt(reveal)}>{children}</g>;
}

/** Three-dimensional quartz/obsidian fracture plane struck by a persistent human ember. */
export const RawReality: React.FC<{frame: number}> = ({frame}) => {
  const reveal = smooth((frame - 4891) / 30);
  return (
    <g>
      <defs>
        <radialGradient id="realGroundShadow" cx="50%" cy="52%" r="54%">
          <stop offset="0" stopColor="#77838a" stopOpacity="0.28" />
          <stop offset="0.58" stopColor="#34414a" stopOpacity="0.16" />
          <stop offset="1" stopColor="#050811" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="realSparkCore" cx="50%" cy="50%" r="55%">
          <stop offset="0" stopColor="#fff5c9" stopOpacity="0.98" />
          <stop offset="0.34" stopColor="#facc15" stopOpacity="0.72" />
          <stop offset="0.72" stopColor="#f59e0b" stopOpacity="0.26" />
          <stop offset="1" stopColor="#ef4444" stopOpacity="0" />
        </radialGradient>
      </defs>
      <Plane frame={frame} reveal={reveal} />
      <Impacts frame={frame} reveal={reveal} />
      <HumanEmber frame={frame} reveal={reveal} />
    </g>
  );
};

