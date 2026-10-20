import React from 'react';

type Point = {x: number; y: number};

const C = {
  night: '#050811',
  amber: '#f59e0b',
  cyan: '#06b6d4',
  magenta: '#d946ef',
  gold: '#facc15',
  red: '#ef4444',
  pale: '#fff4df',
  stone: '#e6e5e1',
};

const CX = 486;
const CY = 875;
const clamp = (v: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
const smooth = (v: number) => {
  const t = clamp(v);
  return t * t * (3 - 2 * t);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const fmt = (v: number) => Number(v.toFixed(1));
const polar = (r: number, angle: number): Point => ({
  x: Math.cos(angle) * r,
  y: Math.sin(angle) * r,
});

const bubbleCells = Array.from({length: 27 * 28}, (_, i) => {
  const row = Math.floor(i / 27);
  const col = i % 27;
  return {
    x: 80 + col * 30 + (row % 2) * 15,
    y: 498 + row * 27.3,
    phase: i * 0.73,
    tone: i % 7,
  };
});

function Background(): React.ReactElement {
  return (
    <>
      <rect width="1080" height="1920" fill="url(#ep10Background)" />
      <rect width="1080" height="1920" fill="url(#ep10Dither)" opacity="0.42" />
      <path d="M64 470 H908 M64 1280 H908" stroke="#18303a" strokeWidth="1" opacity="0.24" />
    </>
  );
}

function Eye({frame, opacity = 1}: {frame: number; opacity?: number}): React.ReactElement {
  const pupil = 116 + 48 * smooth(frame / 760) + 5 * Math.sin(frame * 0.035);
  const scanY = 770 + 190 * (0.5 + 0.5 * Math.sin(frame * 0.012));
  return (
    <g opacity={opacity}>
      <ellipse cx={CX} cy={CY} rx="407" ry="330" fill="url(#ep10EyeAura)" />
      <path d="M74 875 C221 565 746 565 898 875 C746 1185 221 1185 74 875 Z" fill="url(#ep10Sclera)" stroke="#786348" strokeWidth="5" />
      <path d="M87 875 C240 614 731 614 885 875" fill="none" stroke="#d5a35e" strokeWidth="11" opacity="0.78" />
      <path d="M87 875 C240 1136 731 1136 885 875" fill="none" stroke="#855c43" strokeWidth="10" opacity="0.72" />
      <circle cx={CX} cy={CY} r="264" fill="url(#ep10Iris)" stroke="#e5a34b" strokeWidth="4" />
      {Array.from({length: 64}, (_, i) => {
        const a = (Math.PI * 2 * i) / 64 + frame * 0.0007;
        const p1 = polar(174 + 5 * Math.sin(i * 2.7), a);
        const p2 = polar(239 + 7 * Math.cos(i * 1.9), a);
        return (
          <line
            key={i}
            x1={fmt(CX + p1.x)}
            y1={fmt(CY + p1.y)}
            x2={fmt(CX + p2.x)}
            y2={fmt(CY + p2.y)}
            stroke={i % 4 === 0 ? C.gold : '#ffb751'}
            strokeWidth={i % 4 === 0 ? 3 : 1.3}
            opacity={i % 4 === 0 ? 0.72 : 0.42}
          />
        );
      })}
      <circle cx={CX} cy={CY} r={fmt(pupil + 24)} fill="none" stroke="#ffe0a0" strokeWidth="2" opacity="0.75" />
      <circle cx={CX} cy={CY} r={fmt(pupil)} fill="url(#ep10Pupil)" stroke="#f7bc65" strokeWidth="3" />
      <ellipse cx={CX - 27} cy={CY - 35} rx="21" ry="37" fill="#fff5df" opacity="0.3" transform={`rotate(24 ${CX - 27} ${CY - 35})`} />
      <g fill="none" stroke={C.cyan} strokeLinecap="round">
        <circle cx={CX} cy={CY} r={fmt(286 + 8 * Math.sin(frame * 0.018))} strokeWidth="2.5" opacity="0.72" />
        <circle cx={CX} cy={CY} r="321" strokeWidth="1.5" strokeDasharray="4 15" strokeDashoffset={fmt(-frame * 1.1)} opacity="0.6" />
        <circle cx={CX} cy={CY} r="356" strokeWidth="1.2" strokeDasharray="38 19 5 19" strokeDashoffset={fmt(frame * 0.8)} opacity="0.43" />
        <path d={`M91 ${fmt(scanY)} H881`} strokeWidth="2" strokeDasharray="5 13" opacity="0.52" />
        <path d={`M${CX} 514 V1236`} strokeWidth="1.4" strokeDasharray="3 18" opacity="0.23" />
      </g>
      <g stroke={C.cyan} strokeLinecap="round" opacity="0.72">
        {Array.from({length: 8}, (_, i) => {
          const a = (Math.PI * 2 * i) / 8 + frame * 0.0018;
          const p1 = polar(366, a);
          const p2 = polar(382 + 5 * Math.sin(frame * 0.02 + i), a);
          return <line key={i} x1={fmt(CX + p1.x)} y1={fmt(CY + p1.y)} x2={fmt(CX + p2.x)} y2={fmt(CY + p2.y)} strokeWidth="3" />;
        })}
      </g>
    </g>
  );
}

function Petals({frame, bloom}: {frame: number; bloom: number}): React.ReactElement {
  const rotation = frame * 0.012;
  return (
    <g transform={`translate(${CX} ${CY}) scale(${fmt(bloom)})`}>
      <g transform={`rotate(${fmt(rotation)})`}>
        {Array.from({length: 12}, (_, i) => (
          <path
            key={i}
            d="M0 22 C-43 -42 -78 -153 0 -306 C78 -153 43 -42 0 22 Z"
            transform={`rotate(${i * 30})`}
            fill={i % 2 === 0 ? 'url(#ep10PetalGold)' : 'url(#ep10PetalPink)'}
            stroke={i % 2 === 0 ? C.gold : '#f0a2eb'}
            strokeWidth="2.2"
            opacity="0.94"
          />
        ))}
      </g>
      <g transform={`rotate(${fmt(-rotation * 0.72 + 15)}) scale(.68)`}>
        {Array.from({length: 10}, (_, i) => (
          <path
            key={i}
            d="M0 12 C-29 -36 -48 -100 0 -174 C48 -100 29 -36 0 12 Z"
            transform={`rotate(${i * 36})`}
            fill={i % 2 === 0 ? '#facc15' : '#e879f9'}
            fillOpacity="0.72"
            stroke="#ffe69b"
            strokeWidth="2"
          />
        ))}
      </g>
      <circle r="142" fill="url(#ep10FlowerHeart)" stroke="#ffd973" strokeWidth="3" />
      <circle r="86" fill="#090811" opacity="0.93" />
      <circle r="49" fill="url(#ep10Spark)" />
      <circle cx="-14" cy="-20" r="9" fill="#fff7da" opacity="0.95" />
    </g>
  );
}

function Convergence({frame}: {frame: number}): React.ReactElement {
  const t = clamp((frame - 720) / 600);
  const bloom = mix(0.13, 1, smooth(t / 0.64));
  const eyeFade = 1 - smooth(t / 0.52);
  const vectorFade = 0.78 * (1 - smooth(t / 0.58));
  return (
    <>
      <Eye frame={Math.min(frame, 719)} opacity={eyeFade * 0.76} />
      <g strokeLinecap="round" fill="none" opacity={vectorFade}>
        {Array.from({length: 18}, (_, i) => {
          const a = (Math.PI * 2 * i) / 18 + frame * 0.001;
          const start = polar(396, a);
          const control = polar(188 + 12 * Math.sin(frame * 0.015 + i), a + 0.12 * Math.sin(frame * 0.01 + i));
          return (
            <g key={i}>
              <path
                d={`M${fmt(CX + start.x)} ${fmt(CY + start.y)} Q${fmt(CX + control.x)} ${fmt(CY + control.y)} ${CX} ${CY}`}
                stroke={i % 3 === 0 ? C.gold : C.cyan}
                strokeWidth={i % 3 === 0 ? 2.5 : 3}
                strokeDasharray="5 14"
                strokeDashoffset={fmt(-frame * (i % 2 ? 1.2 : 0.86))}
              />
              <circle
                cx={fmt(mix(CX + start.x, CX, smooth(t / 0.68)))}
                cy={fmt(mix(CY + start.y, CY, smooth(t / 0.68)))}
                r={fmt(4 + 2 * Math.sin(frame * 0.04 + i))}
                fill={C.cyan}
              />
            </g>
          );
        })}
      </g>
      <circle cx={CX} cy={CY} r={fmt(mix(118, 154, smooth(t)))} fill="#080910" stroke="#f5c267" strokeWidth="3" opacity="0.95" />
      <Petals frame={frame} bloom={bloom} />
      <circle cx={CX} cy={CY} r={fmt(325 * bloom)} fill="none" stroke={C.cyan} strokeWidth="2" strokeDasharray="5 17" strokeDashoffset={fmt(-frame * 0.8)} opacity={0.62 * (1 - smooth(t / 0.88)) + 0.12} />
    </>
  );
}

function Label({x, y, text, color, width = 174, opacity = 1}: {x: number; y: number; text: string; color: string; width?: number; opacity?: number}): React.ReactElement {
  return (
    <g transform={`translate(${x} ${y})`} opacity={opacity}>
      <rect width={width} height="58" rx="29" fill="#090c17" fillOpacity="0.94" stroke={color} strokeWidth="2" strokeOpacity="0.82" />
      <circle cx="19" cy="29" r="5" fill={color} />
      <text x={width / 2 + 8} y="40" textAnchor="middle" fill={C.pale} fontFamily="PingFang SC, sans-serif" fontSize="32" fontWeight="500">{text}</text>
    </g>
  );
}

function Cocoon({x, y, scale, frame, style = 'warm'}: {x: number; y: number; scale: number; frame: number; style?: 'warm' | 'cool'}): React.ReactElement {
  const sway = 2.4 * Math.sin(frame * 0.013 + (style === 'cool' ? 1.2 : 0));
  const shell = style === 'warm' ? 'url(#ep10Cocoon)' : 'url(#ep10CocoonCool)';
  const accent = style === 'warm' ? C.gold : C.cyan;
  const line = style === 'warm' ? C.magenta : '#f0abfc';
  return (
    <g transform={`translate(${x} ${y}) rotate(${fmt(sway)}) scale(${fmt(scale)})`}>
      <ellipse rx="337" ry="378" fill="url(#ep10CocoonAura)" opacity="0.45" />
      <path d="M0 -346 C210 -327 303 -176 294 6 C286 188 133 337 0 355 C-145 332 -290 180 -294 6 C-299 -176 -204 -323 0 -346 Z" fill={shell} stroke={line} strokeWidth="7" />
      <path d="M0 -390 C234 -352 334 -168 321 8 C310 195 144 368 0 393 C-171 364 -327 189 -321 8 C-315 -176 -233 -351 0 -390 Z" fill="none" stroke={accent} strokeWidth="4" strokeOpacity="0.84" />
      <path d="M-235 -268 C-99 -164 124 -121 239 -250 M-278 -94 C-128 -22 111 24 279 -83 M-249 107 C-112 52 133 81 248 153 M-160 264 C-65 196 79 191 167 286" fill="none" stroke={accent} strokeWidth="3" strokeOpacity="0.6" />
      <path d="M-201 -312 C-276 -101 -215 153 -71 312 M201 -312 C276 -101 215 153 71 312" fill="none" stroke="#fff1d4" strokeWidth="2" strokeOpacity="0.56" />
      <ellipse rx="224" ry="279" fill="none" stroke={style === 'warm' ? '#f472b6' : C.magenta} strokeWidth="3" strokeDasharray="4 12" strokeDashoffset={fmt(-frame * 1.1)} opacity="0.86" />
      <ellipse rx="146" ry="193" fill="url(#ep10CocoonCore)" opacity="0.8" />
      <circle r="96" fill="url(#ep10Spark)" />
      <circle cx="-23" cy="-35" r="11" fill="#fff4d7" opacity="0.9" />
    </g>
  );
}

const debris = Array.from({length: 13}, (_, i) => {
  const angle = i * 2.399963 + 0.24;
  const origin = polar(345 + (i % 3) * 10, angle);
  const points = Array.from({length: 9}, (_, j) => {
    const a = (Math.PI * 2 * j) / 9;
    const r = 17 + ((i * 13 + j * 11) % 18);
    return {x: Math.cos(a) * r, y: Math.sin(a) * r};
  });
  return {angle, origin, polygon: points.map((p) => `${fmt(p.x)},${fmt(p.y)}`).join(' '), start: 1470 + i * 95};
});

function FeedingFragments({frame}: {frame: number}): React.ReactElement {
  return (
    <>
      {debris.map((item, i) => {
        const p = smooth((frame - item.start) / 330);
        const x = CX + mix(item.origin.x, 0, p);
        const y = CY + mix(item.origin.y, 0, p);
        const arrived = smooth((frame - item.start - 250) / 100);
        const opacity = clamp((frame - item.start + 30) / 42) * (1 - arrived);
        const size = mix(1, 0.32, p);
        const warm = p > 0.36;
        const tailX = CX + mix(item.origin.x, item.origin.x * 0.18, p);
        const tailY = CY + mix(item.origin.y, item.origin.y * 0.18, p);
        return (
          <g key={i} opacity={opacity}>
            <path d={`M${fmt(tailX)} ${fmt(tailY)} Q${fmt(mix(x, CX, 0.44))} ${fmt(mix(y, CY, 0.44) - 16)} ${fmt(x)} ${fmt(y)}`} fill="none" stroke={warm ? C.gold : '#758092'} strokeWidth={warm ? 3 : 2} strokeDasharray="3 9" opacity="0.72" />
            {warm ? (
              <g transform={`translate(${fmt(x)} ${fmt(y)}) scale(${fmt(size)}) rotate(${fmt(frame * 0.25 + i * 29)})`}>
                <path d="M0 -25 C16 -9 13 7 0 19 C-13 7 -16 -9 0 -25 Z" fill="url(#ep10Drop)" stroke={C.gold} strokeWidth="2" />
                <circle cy="-4" r="4" fill="#fff6d7" />
              </g>
            ) : (
              <polygon points={item.polygon} transform={`translate(${fmt(x)} ${fmt(y)}) rotate(${fmt(frame * 0.1 + i * 17)}) scale(${fmt(size)})`} fill={i % 3 === 0 ? '#717987' : '#9aa1a8'} stroke={i % 3 === 0 ? C.red : '#e26862'} strokeWidth="3" />
            )}
          </g>
        );
      })}
    </>
  );
}

function Greenhouse({frame}: {frame: number}): React.ReactElement {
  const pulse = 1 + 0.009 * Math.sin(frame * 0.045);
  const labelsIn = smooth((frame - 1490) / 150);
  return (
    <>
      <ellipse cx={CX} cy={CY} rx="399" ry="401" fill="url(#ep10CocoonAura)" opacity="0.62" />
      <g opacity={0.34 + 0.08 * Math.sin(frame * 0.02)}>
        <path d="M64 498 C196 568 347 615 483 648 M908 505 C771 574 626 621 489 656 M77 1210 C220 1157 354 1114 484 1081 M899 1205 C761 1154 620 1112 490 1081" fill="none" stroke={C.cyan} strokeWidth="2" strokeOpacity="0.32" />
      </g>
      <Cocoon x={CX} y={CY} scale={0.79 * pulse} frame={frame} />
      <FeedingFragments frame={frame} />
      <Label x={77} y={638} text="异见" color={C.cyan} opacity={labelsIn} />
      <Label x={721} y={638} text="等待" color={C.gold} opacity={labelsIn} />
      <Label x={77} y={1055} text="拒绝" color={C.red} opacity={labelsIn} />
      <Label x={721} y={1055} text="冷场" color={C.magenta} opacity={labelsIn} />
    </>
  );
}

function BubbleField({frame}: {frame: number}): React.ReactElement {
  const p = clamp((frame - 2820) / 780);
  const spread = smooth(p / 0.58);
  const heroRadius = 313 * Math.exp(-4.1 * p);
  const heroAlpha = 1 - smooth((p - 0.34) / 0.26);
  return (
    <>
      <g transform={`translate(${CX} ${CY}) rotate(${fmt(-1.8 * p)}) scale(${1 + 0.05 * p}) translate(${-CX + 8 * Math.sin(frame * 0.004)} ${-CY + p * 10})`}>
        {bubbleCells.map((cell, i) => {
          const tone = cell.tone;
          const color = tone === 0 || tone === 4 ? C.gold : tone === 1 || tone === 5 ? C.magenta : tone === 2 ? C.cyan : '#aab4c2';
          const breathe = 0.78 + 0.08 * Math.sin(frame * 0.024 + cell.phase);
          const opacity = spread * (0.11 + 0.12 * breathe + 0.05 * Math.sin(cell.phase * 1.7));
          const r = (9.2 + 1.8 * Math.sin(cell.phase)) * (0.48 + 0.52 * spread);
          return (
            <g key={i}>
              <circle cx={fmt(cell.x)} cy={fmt(cell.y)} r={fmt(r * 1.7)} fill={color} opacity={opacity * 0.14} />
              <circle cx={fmt(cell.x)} cy={fmt(cell.y)} r={fmt(r)} fill="url(#ep10BubbleFill)" fillOpacity={opacity} stroke={color} strokeOpacity={opacity * 1.8} strokeWidth="1.1" />
              <path d={`M${fmt(cell.x - r * 0.46)} ${fmt(cell.y - r * 0.42)} Q${fmt(cell.x - r * 0.12)} ${fmt(cell.y - r * 0.72)} ${fmt(cell.x + r * 0.25)} ${fmt(cell.y - r * 0.43)}`} fill="none" stroke="#fff7e6" strokeWidth="1" opacity={opacity * 1.8} />
            </g>
          );
        })}
      </g>
      <g opacity={heroAlpha} transform={`translate(${CX} ${CY}) scale(${fmt(heroRadius / 313)})`}>
        <ellipse rx="300" ry="331" fill="url(#ep10CocoonAura)" opacity="0.48" />
        <path d="M0 -280 C174 -266 260 -127 251 11 C245 150 108 273 0 285 C-120 265 -251 127 -250 7 C-250 -134 -166 -268 0 -280 Z" fill="url(#ep10Cocoon)" stroke={C.magenta} strokeWidth="7" />
        <path d="M0 -317 C199 -285 281 -127 274 9 C267 166 126 303 0 320 C-144 295 -278 157 -275 8 C-273 -145 -195 -286 0 -317 Z" fill="none" stroke={C.cyan} strokeWidth="4" />
        <circle r="114" fill="url(#ep10Spark)" />
        <circle cx="-24" cy="-31" r="12" fill="#fff8de" />
      </g>
      {Array.from({length: 9}, (_, i) => {
        const angle = (Math.PI * 2 * i) / 9 + frame * 0.0018;
        const start = polar(mix(18, 355, smooth(p)), angle);
        const end = polar(mix(140, 485, smooth(p)), angle);
        return (
          <path
            key={i}
            d={`M${fmt(CX + start.x)} ${fmt(CY + start.y)} Q${fmt(CX + (start.x + end.x) * 0.46)} ${fmt(CY + (start.y + end.y) * 0.46)} ${fmt(CX + end.x)} ${fmt(CY + end.y)}`}
            fill="none"
            stroke={i % 2 ? C.cyan : C.magenta}
            strokeWidth="2"
            strokeDasharray="3 15"
            strokeDashoffset={fmt(-frame * 0.9)}
            opacity={0.45 * (1 - spread)}
          />
        );
      })}
    </>
  );
}

function ComparisonCocoon({x, y, rx, ry, frame, flavor}: {x: number; y: number; rx: number; ry: number; frame: number; flavor: 'near' | 'far'}): React.ReactElement {
  const pulse = 1 + 0.012 * Math.sin(frame * 0.032 + (flavor === 'far' ? 1.4 : 0));
  const accent = flavor === 'near' ? C.gold : C.cyan;
  const accent2 = flavor === 'near' ? C.magenta : '#f0abfc';
  return (
    <g transform={`translate(${x} ${y}) scale(${fmt(pulse)})`}>
      <ellipse rx={rx + 30} ry={ry + 34} fill={flavor === 'near' ? 'url(#ep10CocoonAura)' : 'url(#ep10CoolAura)'} opacity="0.7" />
      <ellipse rx={rx} ry={ry} fill={flavor === 'near' ? 'url(#ep10Cocoon)' : 'url(#ep10CocoonCool)'} fillOpacity="0.54" stroke={accent2} strokeWidth="4" />
      <ellipse rx={rx * 0.82} ry={ry * 0.91} fill="none" stroke={accent} strokeWidth="2" strokeDasharray="4 8" strokeDashoffset={fmt(-frame)} opacity="0.92" />
      <ellipse rx={rx * 0.56} ry={ry * 0.72} fill="none" stroke={accent2} strokeWidth="2.5" opacity="0.72" />
      <path d={`M${fmt(-rx * 0.75)} ${fmt(-ry * 0.15)} Q0 ${fmt(ry * 0.33)} ${fmt(rx * 0.74)} ${fmt(-ry * 0.23)}`} fill="none" stroke={accent} strokeWidth="2" opacity="0.7" />
      <circle cx={-rx * 0.25} cy={-ry * 0.31} r="5" fill="#fff4da" opacity="0.86" />
    </g>
  );
}

function Person({x, y, mirror, frame}: {x: number; y: number; mirror: boolean; frame: number}): React.ReactElement {
  const phoneTilt = 3 * Math.sin(frame * 0.018 + (mirror ? 1.4 : 0));
  return (
    <g transform={`translate(${x} ${y}) scale(${mirror ? -1 : 1} 1)`}>
      <path d="M6 40 C46 39 87 54 112 88 L129 272 L-21 272 L-14 104 C-8 72 -12 52 6 40 Z" fill="url(#ep10HumanCloth)" stroke="#facc15" strokeWidth="3" />
      <path d="M11 50 C51 61 86 76 102 116 L81 180 C57 142 29 121 -5 111 Z" fill="#f8ad2b" opacity="0.54" />
      <path d="M26 116 C-10 127 -42 151 -80 177" fill="none" stroke="#e8a044" strokeWidth="28" strokeLinecap="round" />
      <path d="M26 116 C-10 127 -42 151 -80 177" fill="none" stroke="#ffd17c" strokeWidth="7" strokeLinecap="round" opacity="0.72" />
      <path d="M-3 241 C30 232 79 239 112 253 L145 317 L27 326 L-22 290 Z" fill="#8d5723" stroke="#d79037" strokeWidth="3" />
      <path d="M29 275 L132 289" stroke="#f5b656" strokeWidth="5" opacity="0.7" />
      <circle cx="-108" cy="204" r="47" fill="url(#ep10PhoneAura)" opacity="0.8" />
      <rect x="-130" y="168" width="43" height="70" rx="8" fill="#111926" stroke="#f8dca0" strokeWidth="3" transform={`rotate(${fmt(phoneTilt)} -108 203)`} />
      <rect x="-125" y="176" width="33" height="51" rx="3" fill={mirror ? '#173648' : '#302036'} transform={`rotate(${fmt(phoneTilt)} -108 203)`} />
      <path d="M-120 185 H-97" stroke={mirror ? C.cyan : C.gold} strokeWidth="3" strokeLinecap="round" transform={`rotate(${fmt(phoneTilt)} -108 203)`} />
      <circle cx="-109" cy="232" r="2.5" fill="#fff0d0" />
      <path d="M18 36 C-17 36 -34 13 -31 -20 C-29 -59 1 -79 34 -65 C61 -52 67 -20 56 10 C49 29 34 40 18 36 Z" fill="url(#ep10HumanSkin)" stroke="#ffd181" strokeWidth="2.8" />
      <path d="M-27 -23 C-37 -53 -15 -82 14 -83 C45 -86 64 -58 59 -25 C42 -45 8 -49 -13 -34 Z" fill="#492c24" stroke="#bd782e" strokeWidth="2" />
      <path d="M-29 -17 L-43 -7 L-31 3" fill="none" stroke="#ffd181" strokeWidth="3" strokeLinecap="round" />
      <circle cx="-15" cy="-8" r="3" fill="#36221d" />
      <path d="M18 33 L25 63" stroke="#e9ad6c" strokeWidth="25" strokeLinecap="round" />
      <path d="M-73 180 Q-104 183 -119 199" fill="none" stroke="#efc17d" strokeWidth="13" strokeLinecap="round" />
    </g>
  );
}

function Sofa({frame}: {frame: number}): React.ReactElement {
  const glint = 0.35 + 0.12 * Math.sin(frame * 0.021);
  return (
    <g>
      <path d="M104 1022 Q110 981 159 981 H823 Q872 981 878 1022 V1134 H104 Z" fill="url(#ep10Sofa)" stroke="#bb7c33" strokeWidth="4" />
      <path d="M126 1016 Q138 1000 170 1000 H811 Q844 1000 857 1017 V1070 H126 Z" fill="#39251f" stroke="#d49342" strokeWidth="3" />
      <path d="M148 1093 H832 V1150 Q828 1162 811 1162 H168 Q148 1162 148 1145 Z" fill="#7d4c27" stroke="#d39142" strokeWidth="4" />
      <path d="M173 1100 H471 M506 1100 H808" stroke="#ffc76e" strokeWidth="3" opacity={glint} />
      <path d="M173 1161 L153 1214 M811 1161 L835 1214" stroke="#6b4328" strokeWidth="16" strokeLinecap="round" />
      <path d="M96 1207 H878" stroke="#d49b54" strokeWidth="3" opacity="0.4" />
    </g>
  );
}

function Together({frame}: {frame: number}): React.ReactElement {
  const p = clamp((frame - 3600) / 780);
  return (
    <>
      <ComparisonCocoon x={315} y={818} rx={120 + 8 * p} ry={202 + 8 * p} frame={frame} flavor="near" />
      <ComparisonCocoon x={657} y={815} rx={211 + 18 * p} ry={286 + 18 * p} frame={frame} flavor="far" />
      <Sofa frame={frame} />
      <Person x={357} y={754} mirror={false} frame={frame} />
      <Person x={615} y={754} mirror={true} frame={frame} />
      <path d="M482 838 Q486 818 490 838 V1005" fill="none" stroke="#ffd881" strokeWidth="3" strokeDasharray="2 10" opacity="0.7" />
      <Label x={176} y={543} text="10厘米" color={C.gold} width={208} />
      <Label x={552} y={512} text="10,000光年" color={C.cyan} width={286} />
      <circle cx="315" cy="819" r={fmt(4 + 2 * Math.sin(frame * 0.05))} fill="#fff8df" />
      <circle cx="657" cy="815" r={fmt(5 + 2 * Math.sin(frame * 0.043 + 1))} fill="#fff8df" />
    </>
  );
}

function spiralPath(turns: number, radius: number, phase: number, frame: number): string {
  const points: string[] = [];
  const steps = 180;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const a = phase + t * turns * Math.PI * 2 + frame * 0.0024;
    const r = 12 + t * radius;
    points.push(`${fmt(CX + Math.cos(a) * r)},${fmt(CY + Math.sin(a) * r * 0.92)}`);
  }
  return `M${points.join(' L')}`;
}

function Pleasure({frame}: {frame: number}): React.ReactElement {
  const p = clamp((frame - 4380) / 480);
  const intensity = smooth(p);
  const turn = 6.5 + 4.2 * intensity;
  const radius = 366 + 42 * intensity;
  return (
    <>
      <ellipse cx={CX} cy={CY} rx={fmt(285 + intensity * 115)} ry={fmt(330 + intensity * 110)} fill="url(#ep10PleasureAura)" opacity={0.24 + 0.23 * intensity} />
      <g fill="none" strokeLinecap="round">
        {Array.from({length: 5}, (_, i) => (
          <path
            key={i}
            d={spiralPath(turn + (i % 2) * 1.2, radius - i * 25, i * Math.PI * 0.4, frame)}
            stroke={i % 2 === 0 ? 'url(#ep10SpiralGold)' : 'url(#ep10SpiralPink)'}
            strokeWidth={fmt(3 + intensity * 7 - i * 0.3)}
            opacity={0.58 + 0.26 * intensity}
          />
        ))}
        {Array.from({length: 18}, (_, i) => {
          const a = (Math.PI * 2 * i) / 18 + frame * 0.002;
          const inner = 156 + 22 * Math.sin(frame * 0.015 + i);
          const outer = 250 + 125 * intensity + 15 * Math.cos(frame * 0.012 + i * 2);
          const q1 = polar(inner, a);
          const q2 = polar(outer, a + 0.15 * Math.sin(frame * 0.01 + i));
          return <path key={i} d={`M${fmt(CX + q1.x)} ${fmt(CY + q1.y)} Q${CX + fmt(q2.x * 0.72)} ${CY + fmt(q2.y * 0.72)} ${fmt(CX + q2.x)} ${fmt(CY + q2.y)}`} stroke={i % 3 === 0 ? C.gold : C.magenta} strokeWidth={fmt(1.8 + intensity * 1.6)} opacity={0.48 + intensity * 0.24} />;
        })}
      </g>
      <circle cx={CX} cy={CY} r={fmt(86 + intensity * 102)} fill="url(#ep10PleasureCore)" opacity="0.82" />
      <circle cx={CX} cy={CY} r={fmt(22 + 18 * intensity)} fill="#fff3cb" opacity={0.75 + 0.16 * Math.sin(frame * 0.015)} />
    </>
  );
}

const stonePath = 'M258 1004 L269 939 L310 917 L338 846 L405 827 L441 769 L503 790 L548 750 L598 790 L667 785 L702 836 L749 859 L752 925 L726 960 L748 1012 L697 1057 L671 1125 L603 1147 L548 1118 L485 1152 L430 1124 L367 1142 L330 1090 L280 1073 Z';

function RoughWorld({frame}: {frame: number}): React.ReactElement {
  const fade = smooth((frame - 4890) / 10);
  const since = Math.max(0, frame - 4900);
  const impact = Math.exp(-since / 78);
  const burstAlpha = frame >= 4900 ? Math.exp(-since / 210) : 0;
  const pulse = 0.48 + 0.12 * Math.sin(frame * 0.019);
  const sparkX = frame < 4900 ? mix(225, 486, smooth((frame - 4890) / 10)) : 486;
  const sparkY = frame < 4900 ? mix(600, 826, smooth((frame - 4890) / 10)) : 826;
  return (
    <g opacity={fade}>
      <path d="M64 1082 Q180 1032 292 1067 T516 1063 T730 1065 T908 1047 V1276 H64 Z" fill="#0b0e16" stroke="#343943" strokeWidth="3" />
      <path d="M64 1131 Q227 1088 345 1129 T579 1118 T790 1128 T908 1098" fill="none" stroke="#54565b" strokeWidth="4" opacity="0.54" />
      <path d="M94 1194 L246 1164 L326 1187 M677 1189 L767 1153 L886 1172 M154 1082 L183 1047 L209 1067 M812 1076 L854 1038 L891 1057" fill="none" stroke="#73747a" strokeWidth="3" opacity="0.35" />
      <path d={stonePath} fill="url(#ep10Stone)" stroke="#f3f1e8" strokeWidth="5" />
      <path d="M276 1000 L354 982 L395 1028 L458 1012 L491 1053 L544 1018 L590 1048 L665 1007 L730 1021" fill="none" stroke="#8e8d88" strokeWidth="5" opacity="0.66" />
      <path d="M338 849 L371 903 L353 950 L411 974 L438 1024 M548 756 L523 833 L562 884 L534 934 L581 982 M668 791 L630 856 L662 904 L621 955" fill="none" stroke="#77787c" strokeWidth="4" opacity="0.56" />
      <path d="M486 832 L472 875 L499 907 L478 948 L505 986 L489 1020" fill="none" stroke="#a75c28" strokeWidth={fmt(3 + impact * 6)} opacity={pulse + 0.43 * impact} />
      <path d="M486 832 L472 875 L499 907 L478 948 L505 986 L489 1020" fill="none" stroke="#ffd566" strokeWidth={fmt(1.6 + impact * 3)} opacity={0.4 + 0.46 * impact} />
      <ellipse cx="486" cy="891" rx={fmt(74 + 96 * impact)} ry={fmt(54 + 80 * impact)} fill="url(#ep10ImpactAura)" opacity={0.18 + 0.42 * impact} />
      {Array.from({length: 28}, (_, i) => {
        const angle = (Math.PI * 2 * i) / 28;
        const r1 = 28 + 12 * Math.sin(i * 2.7);
        const r2 = 80 + 32 * Math.cos(i * 1.8);
        const scatter = 1 + 0.85 * Math.min(1, since / 48);
        const dx = Math.cos(angle) * (r2 + since * 0.17);
        const dy = Math.sin(angle) * (r2 + since * 0.17);
        const color = i % 4 === 0 ? C.red : i % 4 === 1 ? C.pale : C.gold;
        const opacity = i % 4 === 0 ? 0.82 : 0.92;
        return (
          <line
            key={i}
            x1={fmt(sparkX + Math.cos(angle) * r1)}
            y1={fmt(sparkY + Math.sin(angle) * r1)}
            x2={fmt(sparkX + dx * scatter)}
            y2={fmt(sparkY + dy * scatter)}
            stroke={color}
            strokeWidth={i % 5 === 0 ? 4 : 2.4}
            strokeLinecap="round"
            opacity={opacity * burstAlpha}
          />
        );
      })}
      <circle cx={fmt(sparkX)} cy={fmt(sparkY)} r={fmt(7 + 12 * impact)} fill="#fff7de" />
      {Array.from({length: 23}, (_, i) => {
        const x = 97 + ((i * 137) % 778);
        const y0 = 615 + ((i * 83) % 575);
        const x1 = 75 + ((i * 163) % 804);
        const y1 = 645 + ((i * 67) % 560);
        const drift = Math.sin(frame * 0.013 + i * 1.8) * 8;
        const r = 1.4 + (i % 3) * 0.7;
        return <circle key={i} cx={fmt(mix(x, x1, (frame % 240) / 240) + drift)} cy={fmt(mix(y0, y1, (frame % 240) / 240))} r={r} fill={i % 4 === 0 ? C.gold : '#c0c5cf'} opacity={0.2 + 0.16 * Math.sin(frame * 0.03 + i)} />;
      })}
    </g>
  );
}

function Definitions(): React.ReactElement {
  return (
    <defs>
      <clipPath id="ep10ForegroundClip" clipPathUnits="userSpaceOnUse">
        <rect x="64" y="470" width="844" height="810" />
      </clipPath>
      <linearGradient id="ep10Background" x1="0" y1="0" x2="0.8" y2="1">
        <stop offset="0" stopColor="#08101b" />
        <stop offset="0.5" stopColor="#050811" />
        <stop offset="1" stopColor="#080912" />
      </linearGradient>
      <pattern id="ep10Dither" width="24" height="24" patternUnits="userSpaceOnUse">
        <circle cx="2" cy="3" r="0.62" fill="#b8c5d2" fillOpacity="0.17" />
        <circle cx="13" cy="7" r="0.48" fill="#8995a6" fillOpacity="0.14" />
        <circle cx="21" cy="17" r="0.57" fill="#d4c9b0" fillOpacity="0.12" />
        <circle cx="7" cy="20" r="0.45" fill="#6d8296" fillOpacity="0.16" />
      </pattern>
      <radialGradient id="ep10EyeAura">
        <stop offset="0" stopColor="#7c3931" stopOpacity="0.47" />
        <stop offset="0.64" stopColor="#152336" stopOpacity="0.28" />
        <stop offset="1" stopColor="#050811" stopOpacity="0" />
      </radialGradient>
      <radialGradient id="ep10Sclera" cx="50%" cy="46%">
        <stop offset="0" stopColor="#f2d09c" />
        <stop offset="0.65" stopColor="#b4784a" />
        <stop offset="1" stopColor="#271927" />
      </radialGradient>
      <radialGradient id="ep10Iris" cx="48%" cy="45%">
        <stop offset="0" stopColor="#1b0b19" />
        <stop offset="0.25" stopColor="#85342f" />
        <stop offset="0.55" stopColor="#e68a31" />
        <stop offset="0.76" stopColor="#5d756d" />
        <stop offset="1" stopColor="#131a28" />
      </radialGradient>
      <radialGradient id="ep10Pupil" cx="42%" cy="39%">
        <stop offset="0" stopColor="#010208" />
        <stop offset="0.75" stopColor="#070813" />
        <stop offset="0.92" stopColor="#17242e" />
        <stop offset="1" stopColor="#070813" />
      </radialGradient>
      <linearGradient id="ep10PetalGold" x1="0" y1="0" x2="0.65" y2="1">
        <stop offset="0" stopColor="#fff2b0" stopOpacity="0.96" />
        <stop offset="0.27" stopColor="#facc15" stopOpacity="0.84" />
        <stop offset="0.72" stopColor="#f59e0b" stopOpacity="0.65" />
        <stop offset="1" stopColor="#9d315b" stopOpacity="0.45" />
      </linearGradient>
      <linearGradient id="ep10PetalPink" x1="0" y1="0" x2="0.7" y2="1">
        <stop offset="0" stopColor="#ffe0ff" stopOpacity="0.94" />
        <stop offset="0.3" stopColor="#d946ef" stopOpacity="0.84" />
        <stop offset="0.76" stopColor="#a22c95" stopOpacity="0.67" />
        <stop offset="1" stopColor="#401b3a" stopOpacity="0.48" />
      </linearGradient>
      <radialGradient id="ep10FlowerHeart">
        <stop offset="0" stopColor="#fff4c7" />
        <stop offset="0.24" stopColor="#facc15" />
        <stop offset="0.75" stopColor="#a72f68" stopOpacity="0.9" />
        <stop offset="1" stopColor="#201020" stopOpacity="0.3" />
      </radialGradient>
      <radialGradient id="ep10CocoonAura">
        <stop offset="0" stopColor="#facc15" stopOpacity="0.4" />
        <stop offset="0.36" stopColor="#d946ef" stopOpacity="0.34" />
        <stop offset="0.7" stopColor="#06b6d4" stopOpacity="0.13" />
        <stop offset="1" stopColor="#050811" stopOpacity="0" />
      </radialGradient>
      <radialGradient id="ep10CoolAura">
        <stop offset="0" stopColor="#06b6d4" stopOpacity="0.32" />
        <stop offset="0.5" stopColor="#d946ef" stopOpacity="0.27" />
        <stop offset="1" stopColor="#050811" stopOpacity="0" />
      </radialGradient>
      <linearGradient id="ep10Cocoon" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#facc15" stopOpacity="0.44" />
        <stop offset="0.35" stopColor="#d946ef" stopOpacity="0.38" />
        <stop offset="0.72" stopColor="#8e2368" stopOpacity="0.31" />
        <stop offset="1" stopColor="#f59e0b" stopOpacity="0.35" />
      </linearGradient>
      <linearGradient id="ep10CocoonCool" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#06b6d4" stopOpacity="0.35" />
        <stop offset="0.46" stopColor="#d946ef" stopOpacity="0.42" />
        <stop offset="1" stopColor="#facc15" stopOpacity="0.3" />
      </linearGradient>
      <radialGradient id="ep10CocoonCore">
        <stop offset="0" stopColor="#fff4c9" stopOpacity="0.78" />
        <stop offset="0.42" stopColor="#facc15" stopOpacity="0.42" />
        <stop offset="1" stopColor="#d946ef" stopOpacity="0" />
      </radialGradient>
      <radialGradient id="ep10Spark">
        <stop offset="0" stopColor="#fff9dd" />
        <stop offset="0.16" stopColor="#fff0a1" />
        <stop offset="0.34" stopColor="#facc15" stopOpacity="0.9" />
        <stop offset="0.64" stopColor="#f59e0b" stopOpacity="0.52" />
        <stop offset="1" stopColor="#d946ef" stopOpacity="0" />
      </radialGradient>
      <linearGradient id="ep10Drop" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#fff6c7" />
        <stop offset="0.4" stopColor="#facc15" />
        <stop offset="1" stopColor="#f59e0b" />
      </linearGradient>
      <radialGradient id="ep10BubbleFill" cx="36%" cy="30%">
        <stop offset="0" stopColor="#fff7e6" stopOpacity="0.64" />
        <stop offset="0.18" stopColor="#d946ef" stopOpacity="0.28" />
        <stop offset="0.62" stopColor="#06b6d4" stopOpacity="0.14" />
        <stop offset="1" stopColor="#0d1420" stopOpacity="0.1" />
      </radialGradient>
      <linearGradient id="ep10HumanCloth" x1="0" y1="0" x2="1" y2="0.9">
        <stop offset="0" stopColor="#ffe5a0" />
        <stop offset="0.34" stopColor="#f59e0b" />
        <stop offset="0.68" stopColor="#bc7227" />
        <stop offset="1" stopColor="#412a29" />
      </linearGradient>
      <radialGradient id="ep10HumanSkin" cx="35%" cy="28%">
        <stop offset="0" stopColor="#ffe1ae" />
        <stop offset="0.7" stopColor="#d79a5a" />
        <stop offset="1" stopColor="#8b4d35" />
      </radialGradient>
      <radialGradient id="ep10PhoneAura">
        <stop offset="0" stopColor="#facc15" stopOpacity="0.32" />
        <stop offset="0.38" stopColor="#06b6d4" stopOpacity="0.2" />
        <stop offset="1" stopColor="#06b6d4" stopOpacity="0" />
      </radialGradient>
      <linearGradient id="ep10Sofa" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#aa672d" />
        <stop offset="0.45" stopColor="#714525" />
        <stop offset="1" stopColor="#33231f" />
      </linearGradient>
      <linearGradient id="ep10SpiralGold" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#facc15" stopOpacity="0.28" />
        <stop offset="0.38" stopColor="#fff1a8" />
        <stop offset="0.62" stopColor="#f59e0b" />
        <stop offset="1" stopColor="#d946ef" stopOpacity="0.56" />
      </linearGradient>
      <linearGradient id="ep10SpiralPink" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#d946ef" stopOpacity="0.24" />
        <stop offset="0.42" stopColor="#ffb2f5" />
        <stop offset="0.72" stopColor="#d946ef" />
        <stop offset="1" stopColor="#facc15" stopOpacity="0.6" />
      </linearGradient>
      <radialGradient id="ep10PleasureAura">
        <stop offset="0" stopColor="#d946ef" stopOpacity="0.72" />
        <stop offset="0.48" stopColor="#facc15" stopOpacity="0.4" />
        <stop offset="1" stopColor="#d946ef" stopOpacity="0" />
      </radialGradient>
      <radialGradient id="ep10PleasureCore">
        <stop offset="0" stopColor="#fff9de" />
        <stop offset="0.17" stopColor="#facc15" />
        <stop offset="0.58" stopColor="#d946ef" stopOpacity="0.84" />
        <stop offset="1" stopColor="#facc15" stopOpacity="0" />
      </radialGradient>
      <linearGradient id="ep10Stone" x1="0" y1="0" x2="0.8" y2="1">
        <stop offset="0" stopColor="#fffef5" />
        <stop offset="0.28" stopColor="#d4d3ce" />
        <stop offset="0.68" stopColor="#92959b" />
        <stop offset="1" stopColor="#3d414b" />
      </linearGradient>
      <radialGradient id="ep10ImpactAura">
        <stop offset="0" stopColor="#fff5c8" stopOpacity="0.96" />
        <stop offset="0.24" stopColor="#facc15" stopOpacity="0.66" />
        <stop offset="0.58" stopColor="#ef4444" stopOpacity="0.22" />
        <stop offset="1" stopColor="#050811" stopOpacity="0" />
      </radialGradient>
    </defs>
  );
}

const NormalFrame: React.FC<{frame: number}> = ({frame}) => (
  <>
    <Background />
    <g clipPath="url(#ep10ForegroundClip)">
      {frame < 720 ? <Eye frame={frame} /> : null}
      {frame >= 720 && frame < 1320 ? <Convergence frame={frame} /> : null}
      {frame >= 1320 && frame < 2820 ? <Greenhouse frame={frame} /> : null}
      {frame >= 2820 && frame < 3600 ? <BubbleField frame={frame} /> : null}
      {frame >= 3600 && frame < 4380 ? <Together frame={frame} /> : null}
      {frame >= 4380 && frame < 4860 ? <Pleasure frame={frame} /> : null}
      {frame > 4890 ? <RoughWorld frame={frame} /> : null}
    </g>
  </>
);

export const Scenes: React.FC<{frame: number}> = ({frame}) => {
  if (frame >= 4861 && frame <= 4890) {
    return (
      <svg width="1080" height="1920" viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg">
        <rect width="1080" height="1920" fill="#000000" />
      </svg>
    );
  }
  return (
    <svg width="1080" height="1920" viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg">
      <Definitions />
      {frame === 4860 ? (
        <>
          <rect width="1080" height="1920" fill="#000000" />
          <path d="M126 875 H900" fill="none" stroke="#ffffff" strokeWidth="3" />
        </>
      ) : (
        <NormalFrame frame={frame} />
      )}
    </svg>
  );
};

export default Scenes;
