import React from 'react';

type Props = {frame: number; portrait: boolean; width: number; height: number};

const VOID = '#050811';
const AMBER = '#f59e0b';
const CYAN = '#06b6d4';
const VIOLET = '#a855f7';
const GOLD = '#facc15';
const RED = '#ef4444';
const clamp = (n: number, a = 0, b = 1) => Math.max(a, Math.min(b, n));

const SignalCore: React.FC<{
  x: number;
  y: number;
  r: number;
  color: string;
  frame: number;
  index: number;
  opacity?: number;
}> = ({x, y, r, color, frame, index, opacity = 1}) => {
  const turn = frame * (index === 0 ? 0.11 : -0.083) + index * 31;
  const pulse = 1 + Math.sin(frame * 0.035 + index * 2) * 0.045;
  const id = `core-${index}-${color.replace('#', '')}`;
  return <g transform={`translate(${x} ${y}) rotate(${turn}) scale(${pulse})`} opacity={opacity}>
    <defs>
      <radialGradient id={id}>
        <stop offset="0" stopColor="#ffffff" stopOpacity="0.98"/>
        <stop offset="0.18" stopColor={color} stopOpacity="0.92"/>
        <stop offset="0.56" stopColor={color} stopOpacity="0.32"/>
        <stop offset="1" stopColor={color} stopOpacity="0"/>
      </radialGradient>
    </defs>
    <circle r={r * 1.72} fill={`url(#${id})`}/>
    <ellipse rx={r * 1.12} ry={r * 0.4} fill="none" stroke={color} strokeOpacity="0.55" strokeWidth="2" transform="rotate(-28)"/>
    <ellipse rx={r * 0.86} ry={r * 0.31} fill="none" stroke="#ffffff" strokeOpacity="0.43" strokeWidth="1.3" transform={`rotate(${38 + Math.sin(frame * 0.012) * 8})`}/>
    <circle r={r * 0.44} fill={color} fillOpacity="0.26" stroke="#ffffff" strokeOpacity="0.72" strokeWidth="2"/>
    <circle cx={Math.cos(turn * 0.06) * r * 0.92} cy={Math.sin(turn * 0.06) * r * 0.34} r={Math.max(3, r * 0.055)} fill="#ffffff"/>
  </g>;
};

function torusLines(frame: number, cx: number, cy: number, sx: number, sy: number): React.ReactNode[] {
  const R = 1.68;
  const r = 0.72;
  const tilt = 0.78;
  const turn = frame * 0.00215;
  const project = (u0: number, v: number) => {
    const u = u0 + turn;
    const x = (R + r * Math.cos(v)) * Math.cos(u);
    const y = (R + r * Math.cos(v)) * Math.sin(u);
    const z = r * Math.sin(v);
    const y1 = y * Math.cos(tilt) - z * Math.sin(tilt);
    const z1 = y * Math.sin(tilt) + z * Math.cos(tilt);
    const perspective = 1 / (1 + z1 * 0.12);
    return {x: cx + x * sx * perspective, y: cy + y1 * sy * perspective, z: z1};
  };
  const paths: React.ReactNode[] = [];
  for (let ring = 0; ring < 13; ring += 1) {
    const v = (ring / 13) * Math.PI * 2;
    let d = '';
    let depth = 0;
    const steps = 42;
    for (let i = 0; i <= steps; i += 1) {
      const p = project((i / steps) * Math.PI * 2, v);
      d += `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)} `;
      depth += p.z;
    }
    const front = depth / (steps + 1) > 0;
    paths.push(<path key={`u-${ring}`} d={d} fill="none" stroke={ring % 5 === 0 ? '#fff3bd' : front ? GOLD : '#8e6a20'} strokeOpacity={front ? 0.91 : 0.54} strokeWidth={ring % 4 === 0 ? 3 : 2.05}/>);
  }
  for (let line = 0; line < 18; line += 1) {
    const u = (line / 18) * Math.PI * 2;
    let d = '';
    let depth = 0;
    const steps = 36;
    for (let i = 0; i <= steps; i += 1) {
      const p = project(u, (i / steps) * Math.PI * 2);
      d += `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)} `;
      depth += p.z;
    }
    paths.push(<path key={`v-${line}`} d={d} fill="none" stroke={line % 7 === 0 ? '#fff2b4' : depth > 0 ? GOLD : '#856321'} strokeOpacity={depth > 0 ? 0.83 : 0.43} strokeWidth={line % 5 === 0 ? 2.6 : 1.55}/>);
  }
  return paths;
}

const DogProfile: React.FC<{x: number; y: number; scale: number; opacity: number}> = ({x, y, scale, opacity}) => <g transform={`translate(${x} ${y}) scale(${scale})`} opacity={opacity} stroke={AMBER} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="#f59e0b22">
  <path d="M-47 10 Q-50-9-31-18 L-16-21 Q-4-38 7-44 L11-61 Q16-57 19-43 Q30-42 37-31 L54-25 L46-16 L35-17 Q32-2 24 6 L22 28 L12 28 L8 7 L-16 8 L-23 29 L-33 28 L-31 4 Q-40 7-47 10Z"/>
  <path d="M-45-7 Q-58-16-63-27 M-12-20 Q-2-8 13-6 M-17-23 L-24-34" fill="none"/>
  <circle cx="28" cy="-31" r="2.8" fill="#fff" stroke="none"/>
  <path d="M2-7 Q7-2 13-5" fill="none" stroke="#ffe2a8" strokeWidth="2"/>
</g>;

function Stars({frame, width, height}: {frame: number; width: number; height: number}) {
  return <g>
    {Array.from({length: 58}, (_, i) => {
      const x = ((i * 137.508 + (i % 7) * 19) % 997) / 997 * width;
      const y = ((i * 83.173 + (i % 11) * 23) % 991) / 991 * height;
      const radius = 0.8 + ((i * 17) % 9) / 5;
      const opacity = 0.16 + (0.5 + 0.5 * Math.sin(frame * (0.018 + (i % 5) * 0.003) + i)) * 0.54;
      return <circle key={i} cx={x} cy={y} r={radius} fill={i % 8 === 0 ? AMBER : '#d8e8f4'} opacity={opacity}/>;
    })}
  </g>;
}

function NebulaMesh({frame, cx, cy, portrait}: {frame: number; cx: number; cy: number; portrait: boolean}) {
  const squeeze = clamp((frame - 420) / 300);
  const rx = portrait ? 286 : 390;
  const ry = portrait ? 220 : 194;
  const spin = (frame - 360) * 0.006;
  const project = (lat: number, lon0: number) => {
    const v = Math.sin(lat);
    const shell = Math.cos(lat);
    const narrowing = 1 - squeeze * 0.84 * clamp((v + 0.02) / 0.98);
    const lon = lon0 + spin + v * 0.18;
    const x = shell * Math.cos(lon) * narrowing;
    const z = shell * Math.sin(lon);
    return {x: cx + x * rx, y: cy + (v + z * 0.18) * ry, z};
  };
  const mesh: React.ReactNode[] = [];
  for (let band = 0; band < 17; band += 1) {
    const lat = -1.34 + band * 2.68 / 16;
    let d = '';
    let depth = 0;
    for (let i = 0; i <= 40; i += 1) {
      const p = project(lat, i / 40 * Math.PI * 2);
      d += `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)} `;
      depth += p.z;
    }
    const color = [CYAN, VIOLET, '#e7faff', GOLD][band % 4];
    mesh.push(<path key={`lat-${band}`} d={d} fill="none" stroke={color} strokeOpacity={depth > 0 ? 0.75 : 0.42} strokeWidth={band % 4 === 0 ? 2.5 : 1.65}/>);
  }
  for (let meridian = 0; meridian < 20; meridian += 1) {
    const lon = meridian / 20 * Math.PI * 2;
    let d = '';
    let depth = 0;
    for (let i = 0; i <= 34; i += 1) {
      const p = project(-1.34 + i / 34 * 2.68, lon);
      d += `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)} `;
      depth += p.z;
    }
    mesh.push(<path key={`lon-${meridian}`} d={d} fill="none" stroke={meridian % 5 === 0 ? '#ffffff' : meridian % 2 === 0 ? CYAN : VIOLET} strokeOpacity={depth > 0 ? 0.69 : 0.34} strokeWidth={meridian % 5 === 0 ? 2.1 : 1.25}/>);
  }
  const stars = Array.from({length: 150}, (_, i) => {
    const z = 1 - 2 * (i + 0.5) / 150;
    const lat = Math.asin(z);
    const lon = i * 2.3999632297;
    const p = project(lat, lon);
    const size = 1.1 + i % 4 * 0.75;
    return <circle key={i} cx={p.x} cy={p.y} r={size} fill={[CYAN, '#ffffff', VIOLET, GOLD][i % 4]} opacity={0.48 + (0.5 + 0.5 * Math.sin(frame * 0.047 + i)) * 0.46}/>;
  });
  const opacity = clamp((frame - 330) / 30);
  return <g opacity={opacity}>
    <ellipse cx={cx} cy={cy} rx={rx * 1.24} ry={ry * 1.38} fill="#08a9d3" opacity="0.16"/>
    <ellipse cx={cx} cy={cy} rx={rx * 0.92} ry={ry * 1.05} fill="#8b5cf6" opacity="0.17"/>
    {mesh}{stars}
    <path d={`M${cx - rx * 0.34} ${cy + ry * 0.68} C${cx - 56} ${cy + ry * 1.12} ${cx - 13} ${cy + ry * 1.44} ${cx - 3} ${cy + ry * 1.74} M${cx + rx * 0.31} ${cy + ry * 0.67} C${cx + 65} ${cy + ry * 1.12} ${cx + 16} ${cy + ry * 1.47} ${cx + 3} ${cy + ry * 1.74}`} fill="none" stroke={AMBER} strokeOpacity="0.82" strokeWidth={portrait ? 2.7 : 3.1}/>
  </g>;
}

function OpeningWorld({frame, portrait, width, height}: Props) {
  const cx = width / 2 - (portrait ? 60 : 0);
  const dogOpacity = clamp((600 - frame) / 80);
  const focusY = portrait ? 1100 : 686;
  const coreY = portrait ? 530 : 430;
  const leftCore = portrait ? cx - 190 : 790;
  const rightCore = portrait ? cx + 190 : 1130;
  const coreR = portrait ? 104 : 125;
  const funnelTop = portrait ? 678 : 455;
  const phraseSize = portrait ? 58 : 76;
  const coreOpacity = 1 - clamp((frame - 300) / 100) * 0.95;
  const strawWidth = (portrait ? 145 : 220) * (1 - clamp((frame - 500) / 250) * 0.84);
  const dust = Array.from({length: 34}, (_, i) => {
    const t = ((i * 31) % 101) / 100;
    const spread = (1 - t) * (portrait ? 220 : 390) + 16;
    const x = cx + Math.sin(i * 8.73 + frame * 0.012) * spread * 0.62;
    const y = funnelTop + t * (focusY - funnelTop) + Math.sin(frame * 0.018 + i) * 9;
    return <circle key={i} cx={x} cy={y} r={1.3 + (i % 4)} fill={i % 3 === 0 ? '#bac1c7' : '#797f86'} opacity={0.27 + (i % 5) * 0.08}/>;
  });
  return <g>
    <ellipse cx={cx} cy={height * 0.43} rx={width * (portrait ? 0.34 : 0.43)} ry={height * 0.42} fill="#133044" opacity="0.1"/>
    <path d={`M${leftCore} ${funnelTop} C${leftCore + 12} ${funnelTop + 100} ${cx - 135} ${focusY - 160} ${cx - 68} ${focusY - 20} L${cx - 5} ${focusY - 20} C${cx - 32} ${focusY - 200} ${cx - 115} ${funnelTop + 75} ${rightCore} ${funnelTop}`} fill="#f59e0b" fillOpacity="0.075" stroke="none"/>
    <path d={`M${leftCore - 15} ${funnelTop - 20} C${leftCore + 55} ${funnelTop + 150} ${cx - 122} ${focusY - 145} ${cx - 40} ${focusY - 12} M${rightCore + 15} ${funnelTop - 20} C${rightCore - 62} ${funnelTop + 140} ${cx + 110} ${focusY - 135} ${cx + 40} ${focusY - 12}`} fill="none" stroke={AMBER} strokeOpacity="0.66" strokeWidth={portrait ? 2.8 : 3.4}/>
    <path d={`M${cx} ${funnelTop} L${cx} ${focusY - 22}`} stroke="#fff1c5" strokeOpacity="0.5" strokeWidth="1.5" strokeDasharray="3 13"/>
    <path d={`M${cx - strawWidth / 2} ${funnelTop + 18} C${cx - strawWidth / 3} ${focusY - 160} ${cx - 4} ${focusY - 85} ${cx - 2} ${focusY - 21} M${cx + strawWidth / 2} ${funnelTop + 18} C${cx + strawWidth / 3} ${focusY - 160} ${cx + 4} ${focusY - 85} ${cx + 2} ${focusY - 21}`} fill="none" stroke={AMBER} strokeOpacity="0.9" strokeWidth="2.3"/>
    {dust}
    <SignalCore x={leftCore} y={coreY} r={coreR} color={CYAN} frame={frame} index={0} opacity={coreOpacity}/>
    <SignalCore x={rightCore} y={coreY - 25} r={coreR * 0.92} color={VIOLET} frame={frame} index={1} opacity={coreOpacity}/>
    <NebulaMesh frame={frame} cx={cx} cy={portrait ? 560 : 421} portrait={portrait}/>
    <DogProfile x={portrait ? 155 : 388} y={portrait ? 740 : 560} scale={portrait ? 1.04 : 1.18} opacity={dogOpacity}/>
    <text x={cx} y={focusY} textAnchor="middle" fill="#fff1d2" fontFamily="PingFang SC, Hiragino Sans GB, sans-serif" fontSize={phraseSize} fontWeight="500" letterSpacing={portrait ? 7 : 12} opacity={0.72 + Math.sin(frame * 0.025) * 0.1} style={{textShadow: '0 0 22px #f59e0b'}}>
      我 很 难 过
    </text>
    <path d={`M${cx - 160} ${focusY + 20} Q${cx} ${focusY + 34 + Math.sin(frame * 0.016) * 8} ${cx + 160} ${focusY + 20}`} fill="none" stroke={AMBER} strokeOpacity="0.5" strokeWidth="1.4"/>
    {frame >= 640 && Array.from({length: 22}, (_, i) => {
      const age = frame - (640 + i * 12);
      if (age < 0) return null;
      const t = clamp(age / 340);
      const side = i % 2 === 0 ? -1 : 1;
      const startX = cx + side * (13 + (i % 4) * 7);
      const x = startX + side * t * (42 + (i % 7) * 12);
      const y = funnelTop + 95 + (i * 47) % Math.max(100, focusY - funnelTop - 120) + t * (28 + i % 5 * 9);
      const size = 4 + i % 5 * 2.2;
      const shard = `${x - size},${y - size * 0.45} ${x + size},${y - size} ${x + size * 0.35},${y + size} ${x - size * 0.7},${y + size * 0.35}`;
      return <polygon key={`ash-${i}`} points={shard} fill={i % 3 === 0 ? '#c5c9cf' : '#686d74'} opacity={0.76 - t * 0.2} transform={`rotate(${frame * 0.13 + i * 27} ${x} ${y})`}/>;
    })}
  </g>;
}

function BridgeWorld({frame, portrait, width, height}: Props) {
  const cx = width / 2 - (portrait ? 60 : 0);
  const cy = portrait ? 790 : 555;
  const lx = portrait ? cx - 175 : 730;
  const rx = portrait ? cx + 175 : 1190;
  const breakAge = Math.max(0, frame - 2100);
  const shatter = clamp(breakAge / 240);
  const elems: React.ReactNode[] = [];
  for (let i = 0; i < 72; i += 1) {
    const angle = i * 2.399963 + (i % 5) * 0.07;
    const radius = 12 + ((i * 41) % 135) + shatter * (portrait ? 130 + (i % 8) * 9 : 100 + (i % 8) * 27);
    const x = cx + Math.cos(angle + frame * 0.0005) * radius;
    const y = cy + Math.sin(angle) * radius * (portrait ? 0.76 : 0.48) + Math.sin(frame * 0.014 + i) * 10;
    const size = 4 + (i % 5) * 2;
    const points = `${x},${y - size} ${x + size * 0.92},${y + size * 0.7} ${x - size * 0.72},${y + size * 0.5}`;
    elems.push(<polygon key={i} points={points} fill={[CYAN, VIOLET, GOLD][i % 3]} opacity={frame < 2100 ? 0.05 : 0.62 * (1 - shatter * 0.28)}/>);
  }
  return <g>
    <ellipse cx={cx} cy={cy} rx={portrait ? 360 : 640} ry={portrait ? 350 : 240} fill="#102b3d" opacity="0.26"/>
    {frame < 2100 ? <g>
      <path d={`M${lx + 110} ${cy} C${cx - 200} ${cy - 110} ${cx + 200} ${cy + 110} ${rx - 110} ${cy}`} fill="none" stroke={CYAN} strokeOpacity="0.22" strokeWidth={portrait ? 36 : 48}/>
      <path d={`M${lx + 80} ${cy} C${cx - 170} ${cy - 90} ${cx + 150} ${cy + 90} ${rx - 80} ${cy}`} fill="none" stroke="#e7ffff" strokeOpacity="0.84" strokeWidth="3"/>
      {[0, 1, 2].map(i => <path key={i} d={`M${lx + 90} ${cy + (i - 1) * 23} Q${cx} ${cy + Math.sin(frame * 0.017 + i) * 80 + (i - 1) * 30} ${rx - 90} ${cy + (i - 1) * 23}`} fill="none" stroke={[CYAN, VIOLET, GOLD][i]} strokeOpacity="0.63" strokeWidth="2"/>)}
      {Array.from({length: 6}, (_, i) => {
        const phrase = '正在分析…';
        const progress = ((frame - 1800) * 0.0022 + i * 0.18) % 1;
        const t = progress;
        const x = (1 - t) ** 2 * (lx + 120) + 2 * (1 - t) * t * cx + t ** 2 * (rx - 120);
        const y = (1 - t) ** 2 * cy + 2 * (1 - t) * t * (cy + Math.sin(frame * 0.017 + i) * 80) + t ** 2 * cy;
        return <text key={`crawl-${i}`} x={x} y={y + (i % 2) * 7} textAnchor="middle" fill={i % 2 === 0 ? '#e8ffff' : CYAN} fontFamily="PingFang SC, Menlo, sans-serif" fontSize={portrait ? 28 : 26} opacity="0.92">{phrase[i % phrase.length]}</text>;
      })}
    </g> : <g>
      {Array.from({length: 11}, (_, i) => {
        const p = (i / 11 + (breakAge / 1900)) % 1;
        const radius = p * (portrait ? 360 : 900);
        return <ellipse key={i} cx={cx} cy={cy} rx={radius * 0.9} ry={radius * (portrait ? 0.86 : 0.48)} fill="none" stroke={[CYAN, VIOLET, GOLD][i % 3]} strokeOpacity={0.48 * (1 - p * 0.7)} strokeWidth={i % 3 === 0 ? 3 : 1.7} transform={`rotate(${frame * 0.025 + i * 7} ${cx} ${cy})`}/>;
      })}
      {elems}
    </g>}
    <SignalCore x={lx} y={cy} r={portrait ? 104 : 160} color={CYAN} frame={frame} index={2}/>
    <SignalCore x={rx} y={cy - 30} r={portrait ? 100 : 153} color={VIOLET} frame={frame} index={3}/>
    {frame >= 2100 && <path d={`M${lx + 90} ${cy} Q${cx} ${cy + Math.sin(frame * 0.023) * 60} ${rx - 90} ${cy}`} fill="none" stroke="#facc15" strokeOpacity="0.18" strokeWidth={portrait ? 18 : 24} strokeDasharray="5 22"/>}
  </g>;
}

function CliffordWorld({frame, portrait, width, height}: Props) {
  const cx = width / 2 - (portrait ? 60 : 0);
  const cy = portrait ? 700 : 440;
  const lines = torusLines(frame, cx, cy, portrait ? 134 : 185, portrait ? 130 : 133);
  const boxW = portrait ? 370 : 520;
  const boxH = portrait ? 190 : 178;
  const boxY = portrait ? 1034 : 704;
  const pulse = 0.5 + 0.5 * Math.sin((frame - 3600) * 0.021);
  const overloaded = frame >= 3900;
  const cueIndex = Math.floor(Math.max(0, frame - 3900) / 54) % 4;
  const cues = ['NULL', '语法栈溢出', '维度映射失败', '∅ / NULL'];
  const rays = Array.from({length: 7}, (_, i) => {
    const spread = (i - 3) * (portrait ? 35 : 54);
    const target = (i - 3) * (portrait ? 39 : 58);
    const alpha = overloaded ? 0.34 + 0.25 * (0.5 + 0.5 * Math.sin(frame * 0.11 + i)) : 0.37;
    return <path key={`ray-${i}`} d={`M${cx + spread} ${cy + (portrait ? 162 : 164)} C${cx + spread * 0.8} ${cy + (portrait ? 260 : 260)} ${cx + target} ${boxY - 65} ${cx + target} ${boxY}`} fill="none" stroke={overloaded ? RED : GOLD} strokeOpacity={alpha} strokeWidth={i % 3 === 0 ? 2.3 : 1.3} strokeDasharray="8 12" strokeDashoffset={-frame * 0.8}/>;
  });
  return <g>
    <ellipse cx={cx} cy={cy} rx={portrait ? 370 : 710} ry={portrait ? 240 : 250} fill="#102238" opacity="0.28"/>
    {lines}
    {rays}
    <path d={`M${cx - (portrait ? 320 : 460)} ${cy + (portrait ? 195 : 168)} Q${cx} ${cy + (portrait ? 248 : 210)} ${cx + (portrait ? 320 : 460)} ${cy + (portrait ? 195 : 168)}`} fill="none" stroke={VIOLET} strokeOpacity="0.35" strokeWidth="1.6" strokeDasharray="5 9"/>
    <g transform={`translate(${cx} ${boxY})`}>
      <rect x={-boxW / 2} y={0} width={boxW} height={boxH} rx="8" fill={overloaded ? '#230d15' : '#111019'} fillOpacity="0.94" stroke={overloaded ? RED : AMBER} strokeOpacity={overloaded ? 0.76 + pulse * 0.22 : 0.68 + pulse * 0.25} strokeWidth={overloaded ? 3.2 : 2.2}/>
      <path d={`M${-boxW / 2 + 18} 22 H${boxW / 2 - 18}`} stroke={overloaded ? RED : AMBER} strokeOpacity="0.65" strokeWidth="1.4"/>
      {overloaded ? <>
        <text x="0" y={boxH * 0.53} textAnchor="middle" fill={RED} fontFamily="PingFang SC, Menlo, sans-serif" fontSize={portrait ? 42 : 47} fontWeight="600" letterSpacing="2">人类翻译器</text>
        <text x="0" y={boxH - 36} textAnchor="middle" fill="#ffb4b8" fontFamily="PingFang SC, Menlo, sans-serif" fontSize={portrait ? 27 : 29} letterSpacing="2">{cues[cueIndex]}</text>
      </> : <>
        <text x="0" y={boxH * 0.58} textAnchor="middle" fill="#ffe4ae" fontFamily="PingFang SC, Menlo, sans-serif" fontSize={portrait ? 42 : 44} letterSpacing="2">人类翻译器</text>
        <text x="0" y={boxH - 22} textAnchor="middle" fill={AMBER} fontFamily="Menlo, monospace" fontSize={portrait ? 19 : 23} letterSpacing="2">TRANSLATOR / BUFFER</text>
      </>}
      <circle cx={-boxW / 2 + 22} cy={boxH - 12} r="4" fill={overloaded ? RED : pulse > 0.58 ? AMBER : '#7b5a29'}/>
      <path d={`M${-boxW / 2 + 37} ${boxH - 12} H${boxW / 2 - 23}`} stroke={overloaded ? RED : AMBER} strokeOpacity="0.72" strokeWidth="2" strokeDasharray={`${12 + (frame % 18)} 9`}/>
    </g>
    {overloaded && <text x={cx} y={boxY + boxH + (portrait ? 62 : 67)} textAnchor="middle" fill={RED} fontFamily="Menlo, monospace" fontSize={portrait ? 56 : 62} fontWeight="700" letterSpacing="10" opacity={0.82 + 0.18 * Math.sin((frame - 3900) * 0.13)} style={{textShadow: '0 0 18px #ef4444'}}>????</text>}
  </g>;
}

function SettledWorld({frame, portrait, width, height, receding = false}: Props & {receding?: boolean}) {
  const cx = width / 2 - (portrait ? 60 : 0);
  const cy = portrait ? (receding ? 655 : 610) : (receding ? 418 : 440);
  const distance = portrait ? (receding ? 160 + Math.sin(frame * 0.008) * 12 : 170) : (receding ? 220 + Math.sin(frame * 0.008) * 18 : 210);
  const nodeR = portrait ? (receding ? 112 : 104) : (receding ? 235 : 164);
  const terminalY = portrait ? (receding ? 1170 : 1080) : (receding ? 730 : 700);
  return <g>
  <ellipse cx={cx} cy={cy} rx={portrait ? 380 : width * 0.48} ry={height * 0.42} fill="#3b2a0c" opacity="0.2"/>
    <path d={`M${cx - distance} ${cy + 35} C${cx - distance * 0.58} ${cy + 135} ${cx + distance * 0.55} ${terminalY - 120} ${cx} ${terminalY}`} fill="none" stroke={AMBER} strokeOpacity="0.15" strokeWidth={portrait ? 26 : 32}/>
    <path d={`M${cx - distance} ${cy + 35} C${cx - distance * 0.58} ${cy + 135} ${cx + distance * 0.55} ${terminalY - 120} ${cx} ${terminalY}`} fill="none" stroke="#ffe4a6" strokeOpacity="0.8" strokeWidth="2.4"/>
    <path d={`M${cx - distance} ${cy + 35} Q${cx} ${cy + Math.sin(frame * 0.013) * 24} ${cx + distance} ${cy + 35}`} fill="none" stroke={GOLD} strokeOpacity="0.52" strokeWidth="1.5" strokeDasharray="3 13"/>
    <SignalCore x={cx - distance} y={cy} r={nodeR} color={GOLD} frame={frame} index={4}/>
    <SignalCore x={cx + distance} y={cy - 12} r={nodeR * 0.92} color={GOLD} frame={frame} index={5}/>
    <g transform={`translate(${cx} ${terminalY})`} stroke={AMBER} strokeWidth="2.5" fill="#f59e0b16" strokeLinecap="round" strokeLinejoin="round">
      <path d="M-35 20 V-20 H35 V20 Z"/>
      <path d="M-48 21 H48 M-20 20 V31 M20 20 V31 M-27 32 H27"/>
      <circle cx="0" cy="-1" r="10" fill="none" stroke="#ffe7b5"/>
      <path d="M0-11 V-25 M-7-25 H7"/>
    </g>
  </g>;
}

function TeaserWorld({frame, portrait, width, height}: Props) {
  const p = clamp((frame - 6930) / 270);
  const cx = width / 2 - (portrait ? 60 : 0);
  const cy = portrait ? 790 : 560;
  const radius = portrait ? 265 : 365;
  const spokes = Array.from({length: 12}, (_, i) => {
    const a = Math.PI * 2 * i / 12 + Math.sin(frame * 0.007) * 0.055;
    const r0 = radius * (0.35 + 0.08 * Math.sin(i * 2.1));
    const x0 = cx + Math.cos(a) * r0;
    const y0 = cy + Math.sin(a) * r0 * (portrait ? 1.15 : 0.62);
    const x1 = cx + Math.cos(a) * radius;
    const y1 = cy + Math.sin(a) * radius * (portrait ? 1.15 : 0.62);
    return <g key={i}>
      <path d={`M${cx} ${cy} L${x1} ${y1}`} stroke={AMBER} strokeOpacity={0.55 * (1 - p)} strokeWidth="2.5"/>
      <path d={`M${x0} ${y0} Q${cx + Math.cos(a + 0.62) * radius * 0.5} ${cy + Math.sin(a + 0.62) * radius * (portrait ? 0.58 : 0.3)} ${x1} ${y1}`} fill="none" stroke={CYAN} strokeOpacity={0.58 * p} strokeWidth="2.1"/>
      <circle cx={x1} cy={y1} r={3 + 2 * Math.sin(frame * 0.018 + i)} fill={p > 0.5 ? CYAN : GOLD} opacity="0.78"/>
    </g>;
  });
  return <g>
    <g opacity={1 - p * 0.8} transform={`rotate(${frame * 0.018} ${cx} ${cy})`}>
      <path d={`M${cx - radius} ${cy} Q${cx} ${cy - (portrait ? 100 : 90)} ${cx + radius} ${cy} Q${cx} ${cy + (portrait ? 100 : 90)} ${cx - radius} ${cy}`} fill="none" stroke={AMBER} strokeOpacity="0.7" strokeWidth="3"/>
      <path d={`M${cx} ${cy - (portrait ? radius * 1.15 : radius * 0.62)} L${cx + radius} ${cy} L${cx} ${cy + (portrait ? radius * 1.15 : radius * 0.62)} L${cx - radius} ${cy} Z`} fill="none" stroke={GOLD} strokeOpacity="0.55" strokeWidth="2"/>
      {spokes}
    </g>
    <g opacity={p} transform={`rotate(${Math.sin(frame * 0.004) * 2} ${cx} ${cy})`} fill="none" stroke={CYAN} strokeOpacity="0.72" strokeWidth="2.2">
      {Array.from({length: 7}, (_, i) => {
        const y = cy - radius + i * radius * 0.33;
        const widthAtY = Math.sqrt(Math.max(0, 1 - ((y - cy) / radius) ** 2)) * radius;
        return <path key={i} d={`M${cx - widthAtY} ${y} C${cx - widthAtY * 0.35} ${y - 26} ${cx + widthAtY * 0.35} ${y + 26} ${cx + widthAtY} ${y}`} strokeOpacity={0.22 + i % 3 * 0.13}/>;
      })}
      {Array.from({length: 9}, (_, i) => {
        const x = cx - radius + i * radius * 0.25;
        const h = Math.sqrt(Math.max(0, 1 - ((x - cx) / radius) ** 2)) * radius * (portrait ? 1.15 : 0.62);
        return <path key={`v-${i}`} d={`M${x} ${cy - h} Q${x + Math.sin(i) * 30} ${cy} ${x} ${cy + h}`}/>;
      })}
    </g>
  </g>;
}

export const CanvasWorld: React.FC<Props> = ({frame, portrait, width, height}) => {
  const inOpening = frame < 1260;
  const inTitle = frame >= 1260 && frame < 1800;
  const inBridge = frame >= 1800 && frame < 3600;
  const inTorus = frame >= 3600 && frame < 5400;
  const inSettled = frame >= 5400 && frame < 6300;
  const inReceding = frame >= 6300 && frame < 6930;
  const stageColor = inOpening ? AMBER : inBridge ? CYAN : inTorus ? VIOLET : inSettled || inReceding ? GOLD : CYAN;
  return <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
    <defs>
      <radialGradient id="void-glow"><stop offset="0" stopColor="#0d2030" stopOpacity="0.72"/><stop offset="0.55" stopColor="#09111f" stopOpacity="0.28"/><stop offset="1" stopColor={VOID} stopOpacity="0"/></radialGradient>
      <linearGradient id="space-ribbon" x1="0" x2="1" y1="0" y2="1"><stop stopColor={CYAN}/><stop offset="0.52" stopColor={VIOLET}/><stop offset="1" stopColor={GOLD}/></linearGradient>
    </defs>
    <rect width={width} height={height} fill={VOID}/>
    <ellipse cx={width / 2} cy={height * 0.48} rx={width * 0.74} ry={height * 0.72} fill="url(#void-glow)"/>
    <Stars frame={frame} width={width} height={height}/>
    {inOpening && <OpeningWorld frame={frame} portrait={portrait} width={width} height={height}/>}
    {inTitle && <g>
      <ellipse cx={width / 2} cy={height * 0.49} rx={width * 0.39} ry={height * 0.21} fill="none" stroke="url(#space-ribbon)" strokeOpacity="0.33" strokeWidth="2" transform={`rotate(${frame * 0.025} ${width / 2} ${height * 0.49})`}/>
      <SignalCore x={width / 2 - (portrait ? 150 : 240)} y={height * 0.48} r={portrait ? 100 : 126} color={CYAN} frame={frame} index={6} opacity={0.45}/>
      <SignalCore x={width / 2 + (portrait ? 150 : 240)} y={height * 0.48} r={portrait ? 100 : 126} color={GOLD} frame={frame} index={7} opacity={0.42}/>
    </g>}
    {inBridge && <BridgeWorld frame={frame} portrait={portrait} width={width} height={height}/>}
    {inTorus && <CliffordWorld frame={frame} portrait={portrait} width={width} height={height}/>}
    {inSettled && <SettledWorld frame={frame} portrait={portrait} width={width} height={height}/>}
    {inReceding && <SettledWorld frame={frame} portrait={portrait} width={width} height={height} receding/>}
    {frame >= 6930 && <TeaserWorld frame={frame} portrait={portrait} width={width} height={height}/>}
    <path d={`M${width * 0.04} ${height * 0.87} Q${width * 0.5} ${height * (0.88 + Math.sin(frame * 0.006) * 0.012)} ${width * 0.96} ${height * 0.87}`} fill="none" stroke={stageColor} strokeOpacity="0.13" strokeWidth="1.4"/>
  </svg>;
};
