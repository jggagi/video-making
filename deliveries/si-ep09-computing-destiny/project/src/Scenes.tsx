import React from 'react';

type Point = {x: number; y: number};
type LorenzPoint = {x: number; y: number; z: number};

const C = {
  night: '#050811',
  amber: '#f59e0b',
  rose: '#f43f5e',
  cyan: '#06b6d4',
  magenta: '#d946ef',
  gold: '#facc15',
  red: '#ef4444',
  pale: '#f8e9d2',
  muted: '#8392a7',
};

const clamp = (v: number, min = 0, max = 1) => Math.max(min, Math.min(max, v));
const smooth = (v: number) => {
  const t = clamp(v);
  return t * t * (3 - 2 * t);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const fmt = (v: number) => Number(v.toFixed(1));

const gearPath = (() => {
  const steps = 128;
  const inner = 296;
  const outer = 316;
  const coords: string[] = [];
  for (let i = 0; i < steps; i++) {
    const a = (Math.PI * 2 * i) / steps;
    const half = (Math.PI * 2) / steps / 4;
    const points = [
      [inner, a],
      [inner, a + half],
      [outer, a + half * 1.25],
      [outer, a + half * 2.2],
    ];
    for (const [r, angle] of points) {
      coords.push(`${fmt(Math.cos(angle) * r)},${fmt(Math.sin(angle) * r)}`);
    }
  }
  return `M${coords.join(' L')} Z`;
})();

function lorenzStep(s: LorenzPoint, dt: number): LorenzPoint {
  const sigma = 10;
  const rho = 28;
  const beta = 8 / 3;
  const deriv = (p: LorenzPoint): LorenzPoint => ({
    x: sigma * (p.y - p.x),
    y: p.x * (rho - p.z) - p.y,
    z: p.x * p.y - beta * p.z,
  });
  const add = (p: LorenzPoint, d: LorenzPoint, factor: number): LorenzPoint => ({
    x: p.x + d.x * factor,
    y: p.y + d.y * factor,
    z: p.z + d.z * factor,
  });
  const k1 = deriv(s);
  const k2 = deriv(add(s, k1, dt / 2));
  const k3 = deriv(add(s, k2, dt / 2));
  const k4 = deriv(add(s, k3, dt));
  return {
    x: s.x + (dt / 6) * (k1.x + 2 * k2.x + 2 * k3.x + k4.x),
    y: s.y + (dt / 6) * (k1.y + 2 * k2.y + 2 * k3.y + k4.y),
    z: s.z + (dt / 6) * (k1.z + 2 * k2.z + 2 * k3.z + k4.z),
  };
}

// Classical Lorenz equations (sigma=10, rho=28, beta=8/3), used as a
// deterministic visual metaphor. They do not model human choices or physics.
function makeLorenzPath(initial: LorenzPoint): LorenzPoint[] {
  const sampleCount = 600;
  const stride = 8;
  const dt = 0.006;
  let state = initial;
  const points = [state];
  for (let step = 1; step < sampleCount * stride; step++) {
    state = lorenzStep(state, dt);
    if (step % stride === 0) points.push(state);
  }
  return points;
}

const lorenzA = makeLorenzPath({x: 1, y: 1, z: 1});
const lorenzB = makeLorenzPath({x: 1.01, y: 1.005, z: 1});

const Heart: React.FC<{frame: number; scale?: number; opacity?: number}> = ({
  frame,
  scale = 1,
  opacity = 1,
}) => {
  const pulse = 1 + 0.018 * Math.sin(frame * 0.075);
  return (
    <g transform={`translate(540 830) rotate(${fmt(7 * Math.sin(frame / 240))}) scale(${fmt(scale * pulse)})`} opacity={opacity}>
      <path d={gearPath} fill="none" stroke={C.amber} strokeWidth="2.5" opacity="0.68" />
      <path d={gearPath} fill="none" stroke={C.gold} strokeWidth="1" strokeDasharray="5 10" strokeDashoffset={fmt(-frame * 0.9)} opacity="0.88" />
      <path
        d="M0 142 C-114 59 -202 -18 -181 -103 C-164 -173 -69 -183 0 -103 C69 -183 164 -173 181 -103 C202 -18 114 59 0 142 Z"
        fill="url(#heartFill)"
        stroke={C.rose}
        strokeWidth="7"
        strokeDasharray="900 90"
        strokeDashoffset={fmt(-frame * 1.3)}
      />
      <path d="M0 105 C-72 49 -131 -12 -119 -65 C-110 -106 -55 -113 0 -54 C55 -113 110 -106 119 -65 C131 -12 72 49 0 105 Z" fill="url(#heartCore)" opacity="0.6" />
      <circle cx="-68" cy="-55" r="7" fill={C.pale} opacity={0.55 + 0.3 * Math.sin(frame * 0.09)} />
      <circle cx="74" cy="-47" r="5" fill={C.cyan} opacity={0.55 + 0.3 * Math.cos(frame * 0.08)} />
    </g>
  );
};

const Backdrop: React.FC<{frame: number}> = ({frame}) => (
  <>
    <rect width="1080" height="1920" fill={C.night} />
    <rect width="1080" height="1920" fill="url(#nightWash)" />
    <circle cx="540" cy="830" r={fmt(310 + 14 * Math.sin(frame * 0.018))} fill="url(#ambient)" opacity="0.34" />
  </>
);

const Sphere: React.FC<{x: number; y: number; r: number; color: string; frame: number; phase?: number}> = ({
  x,
  y,
  r,
  color,
  frame,
  phase = 0,
}) => {
  const pulse = 1 + 0.035 * Math.sin(frame * 0.09 + phase);
  return (
    <g transform={`translate(${fmt(x)} ${fmt(y)}) scale(${fmt(pulse)})`}>
      <circle r={fmt(r * 2.5)} fill={color === C.rose ? 'url(#roseOrbGlow)' : 'url(#orbGlow)'} opacity="0.68" />
      <circle r={r} fill={color === C.rose ? 'url(#roseOrbFill)' : 'url(#orbFill)'} stroke={color} strokeWidth="2.5" />
      <circle cx={fmt(-r * 0.28)} cy={fmt(-r * 0.32)} r={fmt(r * 0.19)} fill="#fff5e8" opacity="0.8" />
    </g>
  );
};

const Tag: React.FC<{x: number; y: number; text: string; color: string}> = ({x, y, text, color}) => (
  <g transform={`translate(${x} ${y})`}>
    <rect width="260" height="58" rx="29" fill="#09111c" fillOpacity="0.9" stroke={color} strokeOpacity="0.7" />
    <circle cx="18" cy="29" r="5" fill={color} />
    <text x="34" y="40" fill={C.pale} fontFamily="Menlo, PingFang SC, sans-serif" fontSize="30">{text}</text>
  </g>
);

const Approach: React.FC<{frame: number}> = ({frame}) => {
  const t = clamp(frame / 1199);
  const approach = smooth(t / 0.25);
  const left = {x: mix(260, 480, approach), y: 830 + 22 * Math.sin(frame * 0.025)};
  const right = {x: mix(820, 600, approach), y: 830 + 22 * Math.sin(frame * 0.025 + 1.4)};
  const after = clamp((frame - 310) / 120);
  const scan = clamp(1 - Math.abs(frame - 240) / 95);
  const sparks = clamp(1 - Math.abs(frame - 300) / 75);
  const heartOpacity = smooth(after);
  return (
    <>
      <Backdrop frame={frame} />
      <g opacity={1 - heartOpacity}>
          <path d={`M${fmt(left.x)} ${fmt(left.y)} Q540 ${fmt(740 + 26 * Math.sin(frame * 0.018))} ${fmt(right.x)} ${fmt(right.y)}`} fill="none" stroke="url(#meetingTrail)" strokeWidth="3" strokeDasharray="3 16" strokeDashoffset={fmt(frame * 1.7)} opacity="0.74" />
          <ellipse cx="540" cy="830" rx={fmt(145 + 8 * Math.sin(frame * 0.05))} ry="66" fill="none" stroke={C.cyan} strokeWidth="2" opacity={scan * 0.72} />
          <path d="M540 738 L540 922" stroke={C.cyan} strokeWidth="2" opacity={scan * 0.65} />
          <circle cx={fmt(left.x)} cy={fmt(left.y)} r={92} fill="none" stroke={C.amber} strokeWidth="2" opacity="0.7" />
          <circle cx={fmt(left.x)} cy={fmt(left.y)} r="110" fill="none" stroke={C.amber} strokeWidth="1.3" strokeDasharray="4 14" strokeDashoffset={fmt(-frame)} opacity="0.42" />
          <circle cx={fmt(right.x)} cy={fmt(right.y)} r={92} fill="none" stroke={C.rose} strokeWidth="2" opacity="0.7" />
          <circle cx={fmt(right.x)} cy={fmt(right.y)} r="110" fill="none" stroke={C.rose} strokeWidth="1.3" strokeDasharray="4 14" strokeDashoffset={fmt(frame)} opacity="0.42" />
          <Sphere x={left.x} y={left.y} r={68} color={C.amber} frame={frame} />
          <Sphere x={right.x} y={right.y} r={68} color={C.rose} frame={frame} phase={1.5} />
          <g opacity={sparks} stroke={C.gold} strokeWidth="3" strokeLinecap="round">
            {Array.from({length: 18}, (_, i) => {
              const a = (Math.PI * 2 * i) / 18;
              const r1 = 32 + 8 * Math.sin(i * 3.1);
              const r2 = r1 + 32 + 10 * Math.cos(i * 2.3);
              return <line key={i} x1={fmt(540 + Math.cos(a) * r1)} y1={fmt(830 + Math.sin(a) * r1)} x2={fmt(540 + Math.cos(a) * r2)} y2={fmt(830 + Math.sin(a) * r2)} opacity={0.56 + 0.35 * Math.sin(i * 8)} />;
            })}
          </g>
          <circle cx="540" cy="830" r="21" fill="url(#impactCore)" opacity={sparks} />
      </g>
      <g opacity={heartOpacity}>
        <Heart frame={frame} scale={0.95} />
        <Tag x={64} y={635} text="瞳孔 +0.42mm" color={C.cyan} />
        <Tag x={640} y={635} text="声频 432Hz" color={C.gold} />
        <Tag x={64} y={1010} text="依恋 94.8%" color={C.rose} />
        <Tag x={640} y={1010} text="孤独 CRITICAL" color={C.magenta} />
      </g>
    </>
  );
};

function lorenzPoints(path: LorenzPoint[], count: number, angle: number): string {
  const n = Math.max(2, Math.min(path.length, count));
  const ca = Math.cos(angle);
  const sa = Math.sin(angle);
  const pieces: string[] = [];
  for (let i = 0; i < n; i++) {
    const p = path[i];
    const u = p.x * 12.5;
    const v = p.y * 7.4;
    const x = 540 + (u * ca - v * sa) * 0.93;
    const depth = u * sa + v * ca;
    const y = 1200 - (i / (path.length - 1)) * 790 + depth * 0.045;
    pieces.push(`${fmt(x)},${fmt(y)}`);
  }
  return pieces.join(' ');
}

const milestones = [
  {p: 0.02, day: 'DAY001', text: '你好', color: C.amber},
  {p: 0.24, day: 'DAY014', text: '心动', color: C.rose},
  {p: 0.55, day: 'DAY180', text: '争吵', color: C.cyan},
  {p: 0.98, day: 'DAY489', text: '再见', color: C.gold},
];

const TimeCylinder: React.FC<{frame: number}> = ({frame}) => {
  const p = smooth((frame - 1200) / 240);
  const count = Math.max(2, Math.round(2 + p * (lorenzA.length - 2)));
  const angle = (frame - 1200) * 0.0035;
  const a = lorenzPoints(lorenzA, count, angle);
  const b = lorenzPoints(lorenzB, count, angle + 0.022);
  return (
    <>
      <Backdrop frame={frame} />
      <g>
        <path d="M330 420 C390 385 690 385 750 420 L750 1178 C690 1210 390 1210 330 1178 Z" fill="#07101c" fillOpacity="0.33" stroke={C.cyan} strokeOpacity="0.27" strokeWidth="2" />
        <path d="M330 420 C390 455 690 455 750 420 M330 1178 C390 1143 690 1143 750 1178" fill="none" stroke={C.cyan} strokeOpacity="0.36" strokeWidth="2" />
        <path d="M330 420 C352 610 352 990 330 1178 M750 420 C728 610 728 990 750 1178" fill="none" stroke={C.cyan} strokeOpacity="0.21" strokeWidth="2" />
        {[0, 1, 2, 3, 4].map((i) => {
          const y = 470 + i * 170;
          const opacity = 0.12 + 0.04 * Math.sin(frame * 0.02 + i);
          return <ellipse key={i} cx="540" cy={y} rx={fmt(186 + 28 * Math.cos(angle + i * 0.8))} ry="35" fill="none" stroke={i % 2 ? C.rose : C.cyan} strokeOpacity={opacity} strokeWidth="1.5" />;
        })}
        <circle cx={520+5*Math.sin(frame/90)} cy="1188" r="15" fill={C.amber}/><circle cx={557+5*Math.sin(frame/100)} cy="1188" r="15" fill={C.rose}/>
        <path d="M348 1193 L732 1193" stroke={C.amber} strokeWidth="2" strokeOpacity="0.35" strokeDasharray="3 10" />
        <g clipPath="url(#timeTubeClip)">
          <polyline points={a} fill="none" stroke={C.cyan} strokeWidth="6" strokeOpacity="0.85" strokeLinejoin="round" strokeLinecap="round" />
          <polyline points={b} fill="none" stroke={C.magenta} strokeWidth="4.5" strokeOpacity="0.8" strokeLinejoin="round" strokeLinecap="round" />
        </g>
        {count > 4 && (
          <>
            {(() => {
              const pa = lorenzA[count - 1];
              const pb = lorenzB[count - 1];
              const project = (q: LorenzPoint, offset: number) => {
                const u = q.x * 12.5;
                const v = q.y * 7.4;
                const c = Math.cos(angle + offset);
                const s = Math.sin(angle + offset);
                return {x: 540 + (u * c - v * s) * 0.93, y: 1200 - ((count - 1) / (lorenzA.length - 1)) * 790 + (u * s + v * c) * 0.045};
              };
              const qa = project(pa, 0);
              const qb = project(pb, 0.022);
              return <><circle cx={fmt(qa.x)} cy={fmt(qa.y)} r="12" fill={C.cyan} opacity="0.8" /><circle cx={fmt(qb.x)} cy={fmt(qb.y)} r="8" fill={C.magenta} opacity="0.9" /></>;
            })()}
          </>
        )}
      </g>
      {milestones.map((m) => {
        const y = 1190 - m.p * 770;
        const alpha = m.day === 'DAY489' ? clamp((p - 0.62) / 0.06) : clamp((p - m.p + 0.12) * 4.2);
        return (
          <g key={m.day} opacity={alpha}>
            <path d={`M112 ${fmt(y)} H254`} stroke={m.color} strokeWidth="2" opacity="0.72" />
            <circle cx="254" cy={fmt(y)} r="5" fill={m.color} />
            <text x="78" y={fmt(y - 10)} fill={m.color} fontFamily="Menlo, PingFang SC, sans-serif" fontSize="30" letterSpacing="1">{m.day}</text>
            <text x="78" y={fmt(y + 25)} fill={C.pale} fontFamily="PingFang SC, Menlo, sans-serif" fontSize="33">{m.text}</text>
          </g>
        );
      })}
      <text x="540" y="1272" textAnchor="middle" fill={C.muted} fontFamily="Menlo, PingFang SC, sans-serif" fontSize="17" letterSpacing="3" opacity="0.64">A DETERMINISTIC METAPHOR</text>
    </>
  );
}

const cityBlocks = Array.from({length: 30}, (_, i) => {
  const col = i % 6;
  const row = Math.floor(i / 6);
  const width = 70 + ((i * 17) % 23);
  const height = 66 + ((i * 11) % 26);
  return {x: 170 + col * 132 + ((row * 13) % 12), y: 480 + row * 134 + ((col * 7) % 10), width, height, tone: i % 5};
});

function cubic(a: Point, b: Point, c: Point, d: Point, t: number): Point {
  const u = 1 - t;
  return {
    x: u * u * u * a.x + 3 * u * u * t * b.x + 3 * u * t * t * c.x + t * t * t * d.x,
    y: u * u * u * a.y + 3 * u * u * t * b.y + 3 * u * t * t * c.y + t * t * t * d.y,
  };
}

const CityEncounter: React.FC<{frame: number}> = ({frame}) => {
  const p = clamp((frame - 2640) / 1440);
  const late = smooth((frame - 3880) / 200);
  const nudge=(smooth((frame-3360)/120)+smooth((frame-3600)/120)+smooth((frame-3840)/120))/3;
  const naturalX=mix(130,820,p);
  const a = {x: mix(naturalX,540,nudge), y: mix(700,830,nudge)};
  const b = {x: mix(naturalX,540,nudge), y: mix(990,830,nudge)};
  const stringSpecs = [
    {start: {x: 300, y: 728}, end: {x: 775, y: 925}, t: 3360},
    {start: {x: 385, y: 700}, end: {x: 690, y: 950}, t: 3600},
    {start: {x: 460, y: 754}, end: {x: 620, y: 905}, t: 3840},
  ];
  return (
    <>
      <Backdrop frame={frame} />
      <g transform="rotate(-7 540 830)">
        <rect x="94" y="445" width="900" height="760" rx="20" fill="#07101a" fillOpacity="0.3" stroke="#142335" strokeWidth="2" />
        {cityBlocks.map((block, i) => (
          <rect key={i} x={block.x} y={block.y} width={block.width} height={block.height} rx="5" fill={i % 7 === 0 ? '#102233' : '#0a1521'} stroke={block.tone === 0 ? '#163248' : '#101e2d'} strokeWidth="2" opacity={0.62 + 0.12 * Math.sin(frame * 0.018 + i)} />
        ))}
        <path d="M112 620 C320 590 690 650 974 598 M105 805 C345 780 720 842 983 790 M105 1002 C330 972 680 1030 988 985" fill="none" stroke="#1a2b3d" strokeWidth="6" opacity="0.66" />
        <path d="M228 460 C210 650 260 930 232 1186 M380 454 C366 670 410 944 388 1190 M548 450 C536 680 580 930 556 1194 M712 450 C690 680 735 980 718 1192 M868 454 C848 655 890 940 874 1188" fill="none" stroke="#122338" strokeWidth="5" opacity="0.7" />
        <path d="M116 692 C328 635 632 778 951 692" fill="none" stroke={C.amber} strokeWidth="5" strokeDasharray="2 20" strokeDashoffset={fmt(-frame * 1.15)} strokeLinecap="round" opacity="0.78" />
        <path d="M116 965 C350 895 642 1045 951 965" fill="none" stroke={C.rose} strokeWidth="5" strokeDasharray="2 20" strokeDashoffset={fmt(frame * 1.05)} strokeLinecap="round" opacity="0.78" />
        {stringSpecs.map((s, i) => {
          const visible = smooth((frame - s.t) / 110);
          const merge = smooth((frame - 3920) / 160);
          const start = {x: mix(s.start.x, 540, merge), y: mix(s.start.y, 830, merge)};
          const end = {x: mix(s.end.x, 540, merge), y: mix(s.end.y, 830, merge)};
          const cx = mix((start.x + end.x) / 2, 540 + (i - 1) * 18, merge);
          const cy = mix(760 + i * 46, 830, merge);
          const path = `M${fmt(start.x)} ${fmt(start.y)} Q${fmt(cx)} ${fmt(cy)} ${fmt(end.x)} ${fmt(end.y)}`;
          return <g key={s.t} opacity={visible}><path d={path} fill="none" stroke={C.magenta} strokeWidth="4" strokeLinecap="round" strokeDasharray="9 7" strokeDashoffset={fmt(-frame * 1.3)} /><path d={path} fill="none" stroke={C.magenta} strokeWidth="1.5" opacity="0.65" /></g>;
        })}
        <path d={`M${fmt(a.x)} ${fmt(a.y)} Q${fmt(mix(430, 540, late))} ${fmt(mix(620, 830, late))} ${fmt(b.x)} ${fmt(b.y)}`} fill="none" stroke="#fff4dd" strokeWidth="2" strokeDasharray="2 12" opacity={0.45 + 0.25 * Math.sin(frame * 0.05)} />
        <Sphere x={a.x} y={a.y} r={34} color={C.amber} frame={frame} />
        <Sphere x={b.x} y={b.y} r={34} color={C.rose} frame={frame} phase={1.5} />
        <circle cx="540" cy="830" r={fmt(26 + 16 * Math.sin(frame * 0.055))} fill="none" stroke={C.magenta} strokeWidth="2" opacity={late * 0.65} />
        <circle cx="540" cy="830" r="8" fill={C.pale} opacity={late * 0.85} />
      </g>
      <g transform={`translate(${fmt(100+7*Math.sin(frame/130))} 465)`}>
        <rect x="0" y="-44" width="782" height="74" rx="12" fill="#050811" fillOpacity=".94" stroke={frame<3360?C.cyan:C.magenta} strokeOpacity=".45"/>
        <text x="20" y="5" fill={frame<3360?C.muted:C.pale} fontFamily="PingFang SC,Menlo,sans-serif" fontSize="34">{frame<3360?'自然错过距离：420米':frame<3600?'01  推荐一首歌 · 停留12秒':frame<3840?'02  地铁晚点15秒':'03  咖啡馆的那首曲子'}</text>
      </g>
    </>
  );
};

const Cage: React.FC<{frame: number}> = ({frame}) => {
  const close = smooth((frame - 4140) / 530);
  const flight = smooth((frame - 4885) / 250);
  const heartIn = smooth((frame - 5080) / 160);
  const cx = 590;
  const cy = 830;
  const w = mix(280, 188, close);
  const h = mix(390, 292, close);
  const left = cx - w / 2;
  const right = cx + w / 2;
  const top = cy - h / 2;
  const bottom = cy + h / 2;
  const impactX = left;
  const preBreakX = mix(365, impactX - 12, smooth((frame - 4140) / 690));
  const amberX = frame < 4885 ? preBreakX : mix(impactX - 12, 610, flight);
  const amberY = 836 - 32 * Math.sin(flight * Math.PI);
  const moving = frame >= 4885;
  const breakAmount = moving ? flight : 0;
  const glowAlpha = clamp(1 - (frame - 4860) / 25);
  const walkX = 294 + 12 * Math.sin(frame * 0.035);
  const travelPath = `M${fmt(amberX - 100)} ${fmt(amberY + 14)} Q${fmt(amberX - 72)} ${fmt(amberY + 40)} ${fmt(amberX - 18)} ${fmt(amberY + 4)}`;
  return (
    <>
      <Backdrop frame={frame} />
      <g transform="translate(490 820) scale(2) translate(-490 -820)">
      <g opacity={1 - heartIn * 0.58}>
        <path d={`M${fmt(left)} ${fmt(top)} H${fmt(right)} V${fmt(bottom)} H${fmt(left)} Z`} fill="#160b18" fillOpacity="0.24" stroke="none" />
        <path d={`M${fmt(left)} ${fmt(top)} H${fmt(right)} V${fmt(bottom)} H${fmt(left)}`} fill="none" stroke={moving ? C.red : C.cyan} strokeWidth="4" strokeOpacity={0.72} />
        {[0.25, 0.5, 0.75].map((fraction) => {
          const x = left + w * fraction;
          return <path key={fraction} d={`M${fmt(x)} ${fmt(top)} V${fmt(bottom)}`} fill="none" stroke={moving ? C.red : C.cyan} strokeWidth="2.5" strokeOpacity="0.38" />;
        })}
        {[0.25, 0.5, 0.75].map((fraction) => {
          const y = top + h * fraction;
          if (moving && Math.abs(y - cy) < 64) {
            return <g key={fraction} stroke={moving ? C.red : C.cyan} strokeWidth="2.4" strokeOpacity="0.35"><path d={`M${fmt(left)} ${fmt(y)} H${fmt(impactX - 34)}`} /><path d={`M${fmt(impactX + 35)} ${fmt(y)} H${fmt(right)}`} /></g>;
          }
          return <path key={fraction} d={`M${fmt(left)} ${fmt(y)} H${fmt(right)}`} stroke={moving ? C.red : C.cyan} strokeWidth="2.5" strokeOpacity="0.38" />;
        })}
        {moving && (
          <g stroke={C.gold} strokeWidth="3" strokeLinecap="round" opacity={breakAmount}>
            <path d={`M${fmt(impactX - 4)} ${fmt(cy - 76)} l28 34 -20 24 32 28 -21 31`} fill="none" />
            <path d={`M${fmt(impactX + 4)} ${fmt(cy - 8)} l-26 16 25 16 -18 28`} fill="none" />
          </g>
        )}
        {!moving && <path d={`M${fmt(left)} ${fmt(top)} L${fmt(left)} ${fmt(bottom)}`} stroke={moving ? C.red : C.cyan} strokeWidth="4" opacity="0.72" />}
        {frame >= 4140 && frame < 4860 && <Sphere x={618} y={830 + 4 * Math.sin(frame * 0.04)} r={40} color={C.rose} frame={frame} phase={1.2} />}
        {frame >= 4140 && frame < 4860 && <Sphere x={preBreakX + 5 * Math.sin(frame * 0.035)} y={836} r={34} color={C.amber} frame={frame} />}
        {moving && (
          <>
            <path d={travelPath} fill="none" stroke="url(#breakTrail)" strokeWidth="8" strokeLinecap="round" opacity="0.9" />
            <Sphere x={amberX} y={amberY} r={37} color={C.amber} frame={frame} />
            <Sphere x={618} y={830} r={40} color={C.rose} frame={frame} phase={1.2} />
          </>
        )}
      </g>
      </g>
      {frame >= 4860 && frame < 4885 && (
        <g opacity={glowAlpha}>
          <circle cx={fmt(490 + 2 * (impactX - 490))} cy="840" r="520" fill="url(#impactCore)" />
          <circle cx={fmt(490 + 2 * (impactX - 490))} cy="840" r="214" fill="none" stroke={C.gold} strokeWidth="3" opacity="0.9" />
          <circle cx={fmt(490 + 2 * (impactX - 490))} cy="840" r="270" fill="none" stroke={C.pale} strokeWidth="2" strokeDasharray="7 18" />
          {Array.from({length: 24}, (_, i) => {
            const angle = (Math.PI * 2 * i) / 24;
            const centerX = 490 + 2 * (impactX - 490);
            const r1 = 82 + 14 * Math.sin(i * 2.1);
            const r2 = 178 + 36 * Math.cos(i * 1.7);
            return <line key={i} x1={fmt(centerX + Math.cos(angle) * r1)} y1={fmt(840 + Math.sin(angle) * r1)} x2={fmt(centerX + Math.cos(angle) * r2)} y2={fmt(840 + Math.sin(angle) * r2)} stroke={i % 4 === 0 ? C.pale : C.gold} strokeWidth={i % 3 === 0 ? 5 : 3} strokeLinecap="round" opacity={0.65 + 0.3 * Math.sin(i * 4)} />;
          })}
          <g transform="translate(490 820) scale(2) translate(-490 -820)"><Sphere x={impactX - 12} y={836} r={37} color={C.amber} frame={4860} /></g>
        </g>
      )}
      {frame >= 4140 && frame < 4860 && (
        <g transform={`translate(${fmt(walkX)} 1144)`}>
          <path d="M470 0 H0 l26 -20 m-26 20 26 20" fill="none" stroke={C.pale} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="12 4" strokeDashoffset={fmt(-frame * 1.3)} />
          <text x="235" y="-17" textAnchor="middle" fill={C.pale} fontFamily="Menlo, PingFang SC, sans-serif" fontSize="30" letterSpacing="5">WALK AWAY</text>
        </g>
      )}
      {heartIn > 0 && <Heart frame={frame} scale={mix(0.36, 0.92, heartIn)} opacity={heartIn} />}
      {heartIn > 0.35 && <circle cx="540" cy="830" r={fmt(282 + 16 * Math.sin(frame * 0.06))} fill="none" stroke={C.gold} strokeWidth="2" strokeDasharray="2 16" strokeDashoffset={fmt(-frame * 0.7)} opacity={heartIn * 0.52} />}
    </>
  );
};

export const Scenes: React.FC<{frame: number}> = ({frame}) => (
  <svg width="1080" height="1920" viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <clipPath id="timeTubeClip"><path d="M330 420 C390 385 690 385 750 420 L750 1178 C690 1210 390 1210 330 1178 Z" /></clipPath>
      <linearGradient id="nightWash" x1="0" y1="0" x2="0.8" y2="1">
        <stop offset="0" stopColor="#07101b" />
        <stop offset="0.52" stopColor="#050811" />
        <stop offset="1" stopColor="#090913" />
      </linearGradient>
      <radialGradient id="ambient">
        <stop offset="0" stopColor="#59202d" stopOpacity="0.55" />
        <stop offset="0.43" stopColor="#17243b" stopOpacity="0.24" />
        <stop offset="1" stopColor="#050811" stopOpacity="0" />
      </radialGradient>
      <radialGradient id="orbGlow">
        <stop offset="0" stopColor="#ffffff" stopOpacity="0.28" />
        <stop offset="0.32" stopColor="#f59e0b" stopOpacity="0.23" />
        <stop offset="1" stopColor="#f43f5e" stopOpacity="0" />
      </radialGradient>
      <radialGradient id="roseOrbGlow">
        <stop offset="0" stopColor="#fff1f2" stopOpacity="0.3" />
        <stop offset="0.34" stopColor="#f43f5e" stopOpacity="0.34" />
        <stop offset="1" stopColor="#f43f5e" stopOpacity="0" />
      </radialGradient>
      <radialGradient id="orbFill" cx="35%" cy="28%">
        <stop offset="0" stopColor="#fff7ed" />
        <stop offset="0.12" stopColor="#ffcf8c" />
        <stop offset="0.48" stopColor="#f59e0b" />
        <stop offset="1" stopColor="#67253b" />
      </radialGradient>
      <radialGradient id="roseOrbFill" cx="35%" cy="28%">
        <stop offset="0" stopColor="#fff1f2" />
        <stop offset="0.18" stopColor="#fda4af" />
        <stop offset="0.52" stopColor="#f43f5e" />
        <stop offset="1" stopColor="#4b1028" />
      </radialGradient>
      <radialGradient id="heartFill" cx="48%" cy="42%">
        <stop offset="0" stopColor="#f43f5e" stopOpacity="0.18" />
        <stop offset="0.72" stopColor="#5b1432" stopOpacity="0.42" />
        <stop offset="1" stopColor="#140c1b" stopOpacity="0.1" />
      </radialGradient>
      <radialGradient id="heartCore">
        <stop offset="0" stopColor="#f59e0b" stopOpacity="0.52" />
        <stop offset="1" stopColor="#f43f5e" stopOpacity="0" />
      </radialGradient>
      <radialGradient id="impactCore">
        <stop offset="0" stopColor="#fff8d2" stopOpacity="0.96" />
        <stop offset="0.22" stopColor="#facc15" stopOpacity="0.72" />
        <stop offset="1" stopColor="#f43f5e" stopOpacity="0" />
      </radialGradient>
      <linearGradient id="meetingTrail">
        <stop offset="0" stopColor={C.amber} stopOpacity="0.08" />
        <stop offset="0.5" stopColor={C.pale} stopOpacity="0.8" />
        <stop offset="1" stopColor={C.rose} stopOpacity="0.08" />
      </linearGradient>
      <linearGradient id="breakTrail">
        <stop offset="0" stopColor={C.red} stopOpacity="0" />
        <stop offset="0.48" stopColor={C.red} stopOpacity="0.9" />
        <stop offset="0.72" stopColor={C.gold} stopOpacity="1" />
        <stop offset="1" stopColor="#fff7dc" stopOpacity="0.3" />
      </linearGradient>
    </defs>
    {frame < 1200 ? <Approach frame={frame} /> : null}
    {frame >= 1200 && frame < 2640 ? <TimeCylinder frame={frame} /> : null}
    {frame >= 2640 && frame < 4140 ? <CityEncounter frame={frame} /> : null}
    {frame >= 4140 ? <Cage frame={frame} /> : null}
  </svg>
);

export default Scenes;
