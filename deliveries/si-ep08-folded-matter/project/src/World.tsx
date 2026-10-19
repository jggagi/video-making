import React from 'react';

type Props = {frame: number; width: number; height: number; mode: 'city' | 'nexus'};
type Point = {x: number; y: number};

const CYAN = '#06b6d4';
const TEAL = '#10b981';
const GOLD = '#facc15';
const AMBER = '#f59e0b';
const WHITE = '#ffffff';
const clamp = (n: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, n));
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const hash = (n: number) => {
  const value = Math.sin(n * 78.233 + 19.19) * 43758.5453;
  return value - Math.floor(value);
};
const cubic = (a: Point, b: Point, c: Point, d: Point, t: number): Point => {
  const u = 1 - t;
  return {
    x: u * u * u * a.x + 3 * u * u * t * b.x + 3 * u * t * t * c.x + t * t * t * d.x,
    y: u * u * u * a.y + 3 * u * u * t * b.y + 3 * u * t * t * c.y + t * t * t * d.y,
  };
};

function CityTower({x, base, w, h, frame, index, opacity}: {x: number; base: number; w: number; h: number; frame: number; index: number; opacity: number}) {
  const sway = Math.sin(frame * 0.0028 + index * 1.7) * w * 0.025;
  const levels = 5;
  const rows = Array.from({length: levels}, (_, row) => {
    const t = row / (levels - 1);
    const taper = 0.18 + 0.82 * Math.sin((t * 0.92 + 0.04) * Math.PI * 0.5);
    const y = base - h * t;
    const spread = w * taper * 0.5;
    const lean = sway * t + Math.sin(t * 5 + index) * w * 0.025;
    return {y, left: x - spread + lean, center: x + lean * 0.45, right: x + spread + lean};
  });
  const ribs: React.ReactNode[] = [];
  const accents = [CYAN, TEAL, '#77e3d3', GOLD];
  for (let row = 0; row < levels - 1; row += 1) {
    const a = rows[row];
    const b = rows[row + 1];
    const color = accents[(row + index) % accents.length];
    ribs.push(<g key={`bay-${row}`} fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d={`M${a.left} ${a.y}Q${mix(a.left, b.left, 0.5) - w * 0.08} ${mix(a.y, b.y, 0.5)} ${b.left} ${b.y}`} stroke={color} strokeOpacity="0.78" strokeWidth={Math.max(2, w * 0.012)}/>
      <path d={`M${a.right} ${a.y}Q${mix(a.right, b.right, 0.5) + w * 0.08} ${mix(a.y, b.y, 0.5)} ${b.right} ${b.y}`} stroke={color} strokeOpacity="0.7" strokeWidth={Math.max(2, w * 0.011)}/>
      <path d={`M${a.center} ${a.y}Q${mix(a.center, b.center, 0.5) + Math.sin(frame * 0.003 + row) * w * 0.035} ${mix(a.y, b.y, 0.5)} ${b.center} ${b.y}`} stroke="#b5fff1" strokeOpacity="0.56" strokeWidth={Math.max(1.5, w * 0.007)}/>
      <path d={`M${a.left} ${a.y}Q${mix(a.left, b.right, 0.5) - w * 0.04} ${mix(a.y, b.y, 0.5) + w * 0.03} ${b.right} ${b.y}`} stroke="#50cdbb" strokeOpacity="0.54" strokeWidth={Math.max(1.5, w * 0.008)}/>
      <path d={`M${a.right} ${a.y}Q${mix(a.right, b.left, 0.5) + w * 0.04} ${mix(a.y, b.y, 0.5) - w * 0.03} ${b.left} ${b.y}`} stroke="#55d5cd" strokeOpacity="0.48" strokeWidth={Math.max(1.5, w * 0.007)}/>
    </g>);
  }
  const outside = <path d={`M${rows[0].left} ${rows[0].y} C${rows[1].left - w * 0.13} ${rows[1].y + h * 0.09} ${rows[3].left - w * 0.08} ${rows[3].y - h * 0.08} ${rows[4].left} ${rows[4].y} Q${x + sway} ${base - h * 1.12} ${rows[4].right} ${rows[4].y} C${rows[3].right + w * 0.08} ${rows[3].y - h * 0.08} ${rows[1].right + w * 0.13} ${rows[1].y + h * 0.09} ${rows[0].right} ${rows[0].y}`} fill="#052e34" fillOpacity="0.24" stroke="#5de4cf" strokeOpacity="0.45" strokeWidth={Math.max(2, w * 0.009)}/>;
  return <g opacity={opacity}>
    {outside}
    {ribs}
    {rows.map((row, i) => <g key={`node-${i}`}>
      <path d={`M${row.left} ${row.y}Q${x + sway * (i / 5)} ${row.y - w * 0.03} ${row.right} ${row.y}`} fill="none" stroke={i === levels - 1 ? GOLD : '#95f5df'} strokeOpacity="0.55" strokeWidth={Math.max(1.5, w * 0.006)}/>
      {[row.left, row.center, row.right].map((px, j) => <circle key={j} cx={px} cy={row.y} r={Math.max(2, w * (j === 1 ? 0.014 : 0.01))} fill={j === 1 && i === levels - 1 ? GOLD : '#8ef3df'} opacity="0.72"/>)}
    </g>)}
    <path d={`M${x - w * 0.22} ${base}Q${x} ${base - h * 0.12} ${x + w * 0.22} ${base}`} fill="none" stroke="#55d8c8" strokeOpacity="0.52" strokeWidth={Math.max(2, w * 0.014)}/>
  </g>;
}

function Block({x, base, w, h, frame, index, opacity}: {x: number; base: number; w: number; h: number; frame: number; index: number; opacity: number}) {
  const lean = Math.sin(frame * 0.0017 + index) * w * 0.01;
  const top = base - h;
  const color = index % 2 === 0 ? '#9ba995' : '#82999a';
  const windows: React.ReactNode[] = [];
  const cols = Math.max(2, Math.floor(w / 35));
  const rows = Math.max(2, Math.floor(h / 48));
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const wx = x - w * 0.37 + col * (w * 0.74 / Math.max(1, cols - 1));
      const wy = top + h * 0.17 + row * (h * 0.68 / Math.max(1, rows - 1));
      const lit = hash(index * 71 + row * 11 + col) > 0.44;
      windows.push(<rect key={`${row}-${col}`} x={wx - w * 0.025} y={wy - h * 0.015} width={w * 0.05} height={h * 0.03} fill={lit ? '#f8cf75' : '#b1d7ce'} opacity={lit ? 0.62 : 0.18}/>);
    }
  }
  return <g opacity={opacity}>
    <path d={`M${x - w / 2} ${base}L${x - w / 2 + lean} ${top}L${x + w / 2 + lean} ${top}L${x + w / 2} ${base}Z`} fill="#0b2025" fillOpacity="0.68" stroke={color} strokeOpacity="0.55" strokeWidth="2"/>
    <path d={`M${x + w / 2} ${base}L${x + w / 2 + w * 0.15} ${base - h * 0.08}L${x + w / 2 + lean + w * 0.15} ${top + h * 0.02}L${x + w / 2 + lean} ${top}Z`} fill="#182a29" fillOpacity="0.8" stroke="#6e8f87" strokeOpacity="0.4" strokeWidth="1.5"/>
    {windows}
    <path d={`M${x - w * 0.42} ${base}H${x + w * 0.62}`} stroke="#97b5a9" strokeOpacity="0.58" strokeWidth="2"/>
  </g>;
}

function City({frame, width, height}: Props) {
  const unit = Math.min(width, height);
  const cx = width / 2;
  const baseline = height * 0.765;
  const rise = clamp((frame - 5360) / 380);
  const organic = [
    {p: 0.12, h: 0.34, w: 0.18}, {p: 0.34, h: 0.46, w: 0.2},
    {p: 0.63, h: 0.4, w: 0.2}, {p: 0.86, h: 0.32, w: 0.18},
  ];
  const blocks = [
    {p: 0.04, w: 0.115, h: 0.16}, {p: 0.22, w: 0.12, h: 0.21},
    {p: 0.48, w: 0.1, h: 0.14}, {p: 0.75, w: 0.12, h: 0.2},
    {p: 0.96, w: 0.12, h: 0.16},
  ];
  const ground = baseline + Math.sin(frame * 0.002) * unit * 0.006;
  const buildings = organic.map((b, i) => <CityTower key={`tower-${i}`} x={width * b.p} base={ground} w={unit * b.w} h={height * b.h * (0.78 + rise * 0.22)} frame={frame} index={i} opacity={0.38 + rise * 0.58}/>);
  const cityBlocks = blocks.map((b, i) => <Block key={`block-${i}`} x={width * b.p} base={ground + unit * (i % 2) * 0.014} w={unit * b.w} h={unit * b.h} frame={frame} index={i} opacity={0.75}/>);
  const rays: React.ReactNode[] = [];
  const vanish = {x: cx + Math.sin(frame * 0.0014) * unit * 0.025, y: ground - height * 0.27};
  for (let i = 0; i < 17; i += 1) {
    const endX = (i / 16) * width;
    const sway = Math.sin(frame * 0.004 + i * 0.67) * unit * 0.006;
    rays.push(<path key={`ray-${i}`} d={`M${vanish.x} ${vanish.y}Q${mix(vanish.x, endX, 0.5) + sway} ${mix(vanish.y, height, 0.5)} ${endX} ${height}`} fill="none" stroke={i % 4 === 0 ? TEAL : CYAN} strokeOpacity={0.12 + (i % 3) * 0.025} strokeWidth={i % 4 === 0 ? 2.4 : 1.2}/>);
  }
  for (let i = 0; i < 10; i += 1) {
    const t = 0.1 + i * 0.084;
    const y = mix(vanish.y, height, t);
    const rx = mix(unit * 0.045, width * 0.49, t);
    rays.push(<path key={`cross-${i}`} d={`M${cx - rx} ${y}Q${cx} ${y + unit * 0.018} ${cx + rx} ${y}`} fill="none" stroke="#58cdb7" strokeOpacity={0.08 + t * 0.12} strokeWidth="1.4"/>);
  }
  const traffic = Array.from({length: 42}, (_, i) => {
    const t = ((frame * (0.00048 + (i % 4) * 0.00005) + i * 0.137) % 1 + 1) % 1;
    const xBase = (i * 0.6180339887) % 1;
    const x = mix(vanish.x, width * xBase, Math.pow(t, 1.45));
    const y = mix(vanish.y, height * 0.98, t);
    const radius = 1.2 + t * 3.3 + (i % 3) * 0.5;
    return <g key={`traffic-${i}`} opacity={0.22 + t * 0.52}>
      <circle cx={x} cy={y} r={radius * 2.6} fill={i % 4 === 0 ? GOLD : CYAN} opacity="0.12"/>
      <circle cx={x} cy={y} r={radius} fill={i % 4 === 0 ? GOLD : i % 2 === 0 ? TEAL : '#b4fff1'}/>
    </g>;
  });
  const windowsGlint = Array.from({length: 18}, (_, i) => {
    const x = width * (0.05 + ((i * 0.173) % 0.9));
    const y = ground - unit * (0.055 + (i % 5) * 0.012);
    return <path key={`glint-${i}`} d={`M${x - unit * 0.009} ${y}H${x + unit * 0.009}`} stroke={i % 3 === 0 ? GOLD : '#b9fff0'} strokeOpacity={0.28 + 0.22 * Math.sin(frame * 0.027 + i)} strokeWidth="2"/>;
  });
  return <g>
    <path d={`M0 ${vanish.y}Q${cx} ${vanish.y - unit * 0.02} ${width} ${vanish.y}`} fill="none" stroke={TEAL} strokeOpacity="0.26" strokeWidth="2"/>
    {rays}
    {buildings}
    {traffic}
    {cityBlocks}
    {windowsGlint}
    <path d={`M0 ${ground}Q${cx} ${ground + unit * 0.02} ${width} ${ground}`} fill="none" stroke="#c7ffe7" strokeOpacity="0.42" strokeWidth="2.2"/>
  </g>;
}

function NodeDefs() {
  return <defs>
    <radialGradient id="world-cyan">
      <stop offset="0" stopColor={WHITE} stopOpacity="0.92"/>
      <stop offset="0.14" stopColor={CYAN} stopOpacity="0.83"/>
      <stop offset="0.52" stopColor={TEAL} stopOpacity="0.3"/>
      <stop offset="1" stopColor={CYAN} stopOpacity="0"/>
    </radialGradient>
    <radialGradient id="world-gold">
      <stop offset="0" stopColor={WHITE} stopOpacity="0.95"/>
      <stop offset="0.15" stopColor={GOLD} stopOpacity="0.85"/>
      <stop offset="0.55" stopColor={AMBER} stopOpacity="0.28"/>
      <stop offset="1" stopColor={GOLD} stopOpacity="0"/>
    </radialGradient>
  </defs>;
}

function spherePoint(lat: number, lon: number, spin: number, tilt: number): {x: number; y: number; z: number} {
  const x0 = Math.cos(lat) * Math.sin(lon + spin);
  const y0 = Math.sin(lat);
  const z0 = Math.cos(lat) * Math.cos(lon + spin);
  return {x: x0, y: y0 * Math.cos(tilt) - z0 * Math.sin(tilt), z: y0 * Math.sin(tilt) + z0 * Math.cos(tilt)};
}

function OrbNode({x, y, r, frame, index, color}: {x: number; y: number; r: number; frame: number; index: number; color: 'cyan' | 'gold'}) {
  const spin = frame * (index === 0 ? 0.0045 : -0.0038) + index * 1.1;
  const tilt = 0.42 + Math.sin(frame * 0.0019 + index) * 0.06;
  const nodeColor = color === 'cyan' ? CYAN : GOLD;
  const grad = color === 'cyan' ? 'url(#world-cyan)' : 'url(#world-gold)';
  const arcs: Array<{d: string; depth: number; key: string}> = [];
  for (let ring = -2; ring <= 2; ring += 1) {
    const lat = ring * 0.27;
    const pts = Array.from({length: 45}, (_, i) => spherePoint(lat, i / 44 * Math.PI * 2, spin, tilt));
    const depth = pts.reduce((s, p) => s + p.z, 0) / pts.length;
    const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${(p.x * r).toFixed(1)},${(p.y * r).toFixed(1)}`).join(' ');
    arcs.push({d, depth, key: `lat-${ring}`});
  }
  for (let meridian = 0; meridian < 8; meridian += 1) {
    const lon = meridian / 8 * Math.PI * 2;
    const pts = Array.from({length: 37}, (_, i) => spherePoint(-Math.PI / 2 + i / 36 * Math.PI, lon, spin, tilt));
    const depth = pts.reduce((s, p) => s + p.z, 0) / pts.length;
    const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${(p.x * r).toFixed(1)},${(p.y * r).toFixed(1)}`).join(' ');
    arcs.push({d, depth, key: `lon-${meridian}`});
  }
  arcs.sort((a, b) => a.depth - b.depth);
  const pulse = 0.62 + 0.32 * (0.5 + 0.5 * Math.sin(frame * 0.026 + index));
  return <g transform={`translate(${x} ${y})`}>
    <circle r={r * 1.48} fill={grad} opacity="0.76"/>
    <circle r={r * 0.88} fill="#07171d" fillOpacity="0.55" stroke={nodeColor} strokeOpacity="0.74" strokeWidth={Math.max(1.5, r * 0.018)}/>
    <circle r={r * 1.08} fill="none" stroke={nodeColor} strokeOpacity="0.34" strokeWidth={Math.max(1, r * 0.009)} strokeDasharray={`${r * 0.12} ${r * 0.08}`} transform={`rotate(${frame * (index ? -0.08 : 0.065)})`}/>
    {arcs.map((arc) => <path key={arc.key} d={arc.d} fill="none" stroke={arc.depth > 0 ? (arc.key.startsWith('lat') ? '#dbfffa' : nodeColor) : nodeColor} strokeOpacity={arc.depth > 0 ? 0.7 : 0.24} strokeWidth={arc.key.startsWith('lat') && arc.key === 'lat-0' ? Math.max(2, r * 0.016) : Math.max(1.1, r * 0.008)} strokeLinecap="round"/>)}
    <circle r={r * 0.13} fill={WHITE} opacity={pulse}/>
    <circle r={r * 0.25} fill="none" stroke={nodeColor} strokeOpacity={pulse} strokeWidth={Math.max(1.5, r * 0.015)}/>
    {[0, 1, 2, 3].map((i) => {
      const a = i * Math.PI / 2 + frame * 0.0035 * (index ? -1 : 1);
      const px = Math.cos(a) * r * 0.76;
      const py = Math.sin(a) * r * 0.76;
      return <circle key={i} cx={px} cy={py} r={Math.max(2.5, r * 0.025)} fill={i === 0 ? WHITE : nodeColor} opacity="0.76"/>;
    })}
  </g>;
}

type Lane = {a: Point; c1: Point; c2: Point; b: Point; color: string; direction: 1 | -1; key: string};

function Nexus({frame, width, height}: Props) {
  const unit = Math.min(width, height);
  const portrait = width < 950;
  const a = portrait ? {x: width * 0.5, y: height * 0.28} : {x: width * 0.28, y: height * 0.5};
  const b = portrait ? {x: width * 0.5, y: height * 0.72} : {x: width * 0.72, y: height * 0.5};
  const radius = unit * (portrait ? 0.102 : 0.112);
  const offset = portrait ? width * 0.24 : height * 0.18;
  const lanes: Lane[] = portrait ? [
    {a: {x: a.x - radius * 0.16, y: a.y + radius * 0.8}, c1: {x: a.x - offset, y: (a.y + b.y) / 2}, c2: {x: b.x - offset, y: (a.y + b.y) / 2}, b: {x: b.x - radius * 0.16, y: b.y - radius * 0.8}, color: CYAN, direction: 1, key: 'left'},
    {a: {x: b.x + radius * 0.16, y: b.y - radius * 0.8}, c1: {x: b.x + offset, y: (a.y + b.y) / 2}, c2: {x: a.x + offset, y: (a.y + b.y) / 2}, b: {x: a.x + radius * 0.16, y: a.y + radius * 0.8}, color: GOLD, direction: -1, key: 'right'},
  ] : [
    {a: {x: a.x + radius * 0.8, y: a.y - radius * 0.12}, c1: {x: (a.x + b.x) / 2, y: a.y - offset}, c2: {x: (a.x + b.x) / 2, y: b.y - offset}, b: {x: b.x - radius * 0.8, y: b.y - radius * 0.12}, color: CYAN, direction: 1, key: 'upper'},
    {a: {x: b.x - radius * 0.8, y: b.y + radius * 0.12}, c1: {x: (a.x + b.x) / 2, y: b.y + offset}, c2: {x: (a.x + b.x) / 2, y: a.y + offset}, b: {x: a.x + radius * 0.8, y: a.y + radius * 0.12}, color: GOLD, direction: -1, key: 'lower'},
  ];
  const lanePath = (lane: Lane) => `M${lane.a.x} ${lane.a.y}C${lane.c1.x} ${lane.c1.y} ${lane.c2.x} ${lane.c2.y} ${lane.b.x} ${lane.b.y}`;
  const particles: React.ReactNode[] = [];
  lanes.forEach((lane, laneIndex) => {
    const forward = lane.direction === 1;
    const start = forward ? lane.a : lane.b;
    const c1 = forward ? lane.c1 : lane.c2;
    const c2 = forward ? lane.c2 : lane.c1;
    const end = forward ? lane.b : lane.a;
    for (let i = 0; i < 3; i += 1) {
      const period = 190;
      const travel = 118;
      const age = ((frame + i * 63 + laneIndex * 29) % period + period) % period;
      if (age >= travel) continue;
      const t = age / travel;
      const p = cubic(start, c1, c2, end, t);
      const tail = cubic(start, c1, c2, end, Math.max(0, t - 0.075));
      const fade = Math.min(1, t * 9, (1 - t) * 8);
      const r = unit * (0.0021 + (i % 2) * 0.0008);
      particles.push(<g key={`${lane.key}-packet-${i}`} opacity={0.24 + fade * 0.72}>
        <path d={`M${tail.x} ${tail.y}L${p.x} ${p.y}`} stroke={lane.color} strokeOpacity="0.66" strokeWidth={r * 1.25} strokeLinecap="round"/>
        <circle cx={p.x} cy={p.y} r={r * 4.2} fill={lane.color} opacity="0.18"/>
        <circle cx={p.x} cy={p.y} r={r} fill={WHITE}/>
      </g>);
    }
    const d = lanePath(lane);
    particles.push(<g key={`lane-${lane.key}`} fill="none">
      <path d={d} stroke={lane.color} strokeOpacity="0.12" strokeWidth={Math.max(3, unit * 0.004)}/>
      <path d={d} stroke={lane.color} strokeOpacity="0.39" strokeWidth={Math.max(1.5, unit * 0.0014)} strokeDasharray={`${unit * 0.012} ${unit * 0.009}`}/>
      <path d={d} stroke="#cffff6" strokeOpacity="0.23" strokeWidth={Math.max(1, unit * 0.0008)}/>
    </g>);
  });
  const specks = Array.from({length: 48}, (_, i) => {
    const spread = 0.5 + hash(i + 8) * 0.45;
    const angle = i * 2.39996 + frame * (0.0013 + (i % 4) * 0.0002);
    const x = mix(a.x, b.x, hash(i + 88)) + Math.cos(angle) * radius * spread * (portrait ? 1.8 : 2.2);
    const y = mix(a.y, b.y, hash(i + 44)) + Math.sin(angle) * radius * spread * 1.45;
    const r = 1.2 + hash(i + 111) * unit * 0.002;
    return <circle key={`speck-${i}`} cx={x} cy={y} r={r} fill={i % 7 === 0 ? GOLD : i % 3 === 0 ? TEAL : '#b8fff2'} opacity={0.18 + (0.5 + 0.5 * Math.sin(frame * 0.018 + i)) * 0.42}/>;
  });
  const orbitTilt = frame * 0.017;
  return <g>
    <path d={portrait ? `M${a.x} ${a.y}Q${a.x - offset * 0.65} ${(a.y + b.y) / 2} ${b.x} ${b.y}` : `M${a.x} ${a.y}Q${(a.x + b.x) / 2} ${a.y - offset * 0.68} ${b.x} ${b.y}`} fill="none" stroke="#d9fff4" strokeOpacity="0.12" strokeWidth={unit * 0.12}/>
    <ellipse cx={a.x} cy={a.y} rx={radius * 1.39} ry={radius * 0.48} fill="none" stroke={CYAN} strokeOpacity="0.24" strokeWidth="2" transform={`rotate(${orbitTilt} ${a.x} ${a.y})`}/>
    <ellipse cx={b.x} cy={b.y} rx={radius * 1.39} ry={radius * 0.48} fill="none" stroke={GOLD} strokeOpacity="0.24" strokeWidth="2" transform={`rotate(${-orbitTilt} ${b.x} ${b.y})`}/>
    {particles}
    {specks}
    <OrbNode x={a.x} y={a.y} r={radius} frame={frame} index={0} color="cyan"/>
    <OrbNode x={b.x} y={b.y} r={radius * 1.04} frame={frame} index={1} color="gold"/>
  </g>;
}

const World: React.FC<Props> = ({frame, width, height, mode}) => <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} xmlns="http://www.w3.org/2000/svg" fill="none" overflow="hidden">
  {mode === 'city' ? <City frame={frame} width={width} height={height} mode={mode}/> : <>
    <NodeDefs/>
    <Nexus frame={frame} width={width} height={height} mode={mode}/>
  </>}
</svg>;

export default World;
