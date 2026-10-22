import React from 'react';

const PAPER = '#EFECE6';
const PAPER_LIGHT = '#F7F4EE';
const BLUE = '#1D3557';
const RED = '#E63946';
const TAUPE = '#D6C8B7';
const SAGE = '#A8ADA0';
const ROSE = '#D9B9AE';
const SLATE = '#6C7780';

const clamp = (value: number, low = 0, high = 1) => Math.max(low, Math.min(high, value));
const mix = (from: number, to: number, amount: number) => from + (to - from) * amount;
const smooth = (from: number, to: number, value: number) => {
  const t = clamp((value - from) / (to - from));
  return t * t * (3 - 2 * t);
};
const mod = (value: number, divisor: number) => ((value % divisor) + divisor) % divisor;

type MarkProps = {x: number; y: number; size: number; color: string; progress?: number; opacity?: number};

function Mark({x, y, size, color, progress = 1, opacity = 1}: MarkProps) {
  const p = clamp(progress);
  return (
    <g transform={`translate(${x} ${y}) scale(${size})`} opacity={opacity}>
      <g opacity={smooth(0, 0.16, p)} transform={`scale(${mix(0.92, 1, smooth(0, 0.16, p))})`}>
        <rect x="-132" y="-128" width="264" height="256" fill={TAUPE} />
        <rect x="-126" y="-122" width="252" height="244" fill={PAPER} />
      </g>
      <g opacity={smooth(0.05, 0.34, p)} transform={`translate(-50 -50) scale(${mix(0.9, 1, smooth(0.05, 0.34, p))}) translate(50 50)`}>
        <circle cx="-50" cy="-50" r="70" fill={color} />
      </g>
      <g opacity={smooth(0.22, 0.5, p)} transform={`translate(97 -63) scale(${mix(0.9, 1, smooth(0.22, 0.5, p))}) translate(-97 63)`}>
        <rect x="62" y="-128" width="70" height="130" fill={color} />
      </g>
      <g opacity={smooth(0.38, 0.68, p)} transform={`translate(0 70) scale(${mix(0.9, 1, smooth(0.38, 0.68, p))}) translate(0 -70)`}>
        <path d="M-84 28C-84 74 -46 112 0 112C46 112 84 74 84 28V122H-84Z" fill={SAGE} />
      </g>
      <g opacity={smooth(0.56, 0.84, p)} transform={`translate(-107 96) scale(${mix(0.9, 1, smooth(0.56, 0.84, p))}) translate(107 -96)`}>
        <rect x="-124" y="68" width="34" height="56" fill={ROSE} />
      </g>
      <g opacity={smooth(0.76, 1, p)} transform={`translate(107 96) scale(${mix(0.9, 1, smooth(0.76, 1, p))}) translate(-107 -96)`}>
        <path d="M90 124H124V68Z" fill={color} />
      </g>
    </g>
  );
}

function Stamp({x, y, progress = 1, scale = 1, color = RED}: {x: number; y: number; progress?: number; scale?: number; color?: string}) {
  const p = smooth(0, 1, progress);
  if (p <= 0.001) return null;
  const lift = mix(-115, 0, p);
  const stampScale = scale * mix(1.2, 1, p);
  return (
    <g transform={`translate(${x} ${y + lift}) rotate(-7) scale(${stampScale})`} opacity={p}>
      <rect x="-142" y="-39" width="284" height="78" fill={PAPER} fillOpacity="0.86" stroke={color} strokeWidth="4" />
      <text x="0" y="17" textAnchor="middle" fill={color} fontSize="48" fontWeight="700" letterSpacing="5">已收录</text>
    </g>
  );
}

function InitialCard({frame, finalPass = false, compact = false}: {frame: number; finalPass?: boolean; compact?: boolean}) {
  const reveal = finalPass ? clamp((frame - 5520) / 510) : clamp(frame / 145);
  const blueReveal = finalPass ? 1 : smooth(138, 150, frame);
  const stampProgress = finalPass ? clamp((frame - 6012) / 18) : clamp((frame - 162) / 18);
  const half = compact ? 0.42 : 1;
  return (
    <g>
      <rect x={-230 * half + 17 * half} y={-252 * half + 20 * half} width={460 * half} height={504 * half} fill={BLUE} fillOpacity="0.08" stroke={BLUE} strokeWidth={2 * half} />
      <rect x={-230 * half} y={-252 * half} width={460 * half} height={504 * half} fill={PAPER_LIGHT} stroke={TAUPE} strokeWidth={2 * half} />
      <path d={`M${-198 * half} ${-220 * half}H${198 * half}`} stroke={TAUPE} strokeWidth={1.5 * half} />
      <text x={-194 * half} y={-194 * half} fill={BLUE} fontSize={compact ? 18 : 25} fontWeight="600" letterSpacing="2">原稿 / 01</text>
      <g transform={`scale(${half})`}>
        <Mark x={0} y={-8} size={1.05} color={BLUE} progress={blueReveal} opacity={blueReveal * 0.9} />
        <Mark x={0} y={-8} size={1} color={RED} progress={reveal} />
        <Stamp x={0} y={174} progress={stampProgress} scale={0.82} />
      </g>
    </g>
  );
}

function MotifCard({x, y, kind, frame, delay, label}: {x: number; y: number; kind: 'poem' | 'music' | 'blue'; frame: number; delay: number; label: string}) {
  const opacity = smooth(delay, delay + 24, frame);
  if (opacity < 0.01) return null;
  return (
    <g transform={`translate(${x} ${y})`} opacity={opacity}>
      <rect width="236" height="112" fill={PAPER_LIGHT} stroke={TAUPE} strokeWidth="1.5" />
      <text x="14" y="30" fill={BLUE} fontSize="25" fontWeight="600">{label}</text>
      {kind === 'poem' && <g stroke={RED} strokeWidth="3" strokeLinecap="round"><path d="M16 54h132M16 68h168M16 82h106" /></g>}
      {kind === 'music' && <g fill="none" stroke={BLUE} strokeWidth="3"><path d="M16 85V54l70-12v32M86 74V48l70-12v30" /><ellipse cx="10" cy="88" rx="8" ry="5" fill={BLUE} /><ellipse cx="80" cy="77" rx="8" ry="5" fill={BLUE} /><path d="M156 66c12-5 22-4 32 2" /></g>}
      {kind === 'blue' && <g><rect x="16" y="44" width="40" height="44" fill={BLUE} /><rect x="66" y="44" width="40" height="44" fill="#48627F" /><rect x="116" y="44" width="40" height="44" fill={SAGE} /><path d="M166 44v44" stroke={TAUPE} strokeWidth="5" /></g>}
    </g>
  );
}

function LibraryField({frame, opacity, dense = false}: {frame: number; opacity: number; dense?: boolean}) {
  const p = clamp(opacity);
  if (p <= 0.001) return null;
  const cols = dense ? 15 : 13;
  const rows = dense ? 11 : 9;
  const stepX = dense ? 52 : mix(142, 66, p);
  const stepY = dense ? 56 : mix(126, 86, p);
  const cellW = 58;
  const cellH = dense ? 57 : 66;
  const cells: React.ReactNode[] = [];
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const x = 540 + (col - (cols - 1) / 2) * stepX - cellW / 2;
      const y = 900 + (row - (rows - 1) / 2) * stepY - cellH / 2;
      const index = row * cols + col;
      const fill = [PAPER_LIGHT, '#E4E1DA', '#DCE0DF', '#E6D8CE', '#D5DBE0'][mod(index * 7 + row * 3, 5)];
      const spine = [BLUE, SAGE, TAUPE, ROSE][mod(index * 3 + col, 4)];
      const drift = dense ? 0 : Math.sin((frame + index * 17) * 0.004) * 2 * p;
      cells.push(
        <g key={`lib-${row}-${col}`} opacity={p * (dense ? 0.72 : 0.8)} transform={`translate(${drift} 0)`}>
          <rect x={x} y={y} width={cellW} height={cellH} fill={fill} stroke={spine} strokeWidth="1.3" />
          <path d={`M${x + 9} ${y + 12}V${y + cellH - 10}M${x + 16} ${y + 15}H${x + cellW - 8}`} stroke={spine} strokeWidth="2" opacity="0.72" />
          <path d={`M${x + 16} ${y + 23}H${x + cellW - 8}M${x + 16} ${y + 31}H${x + cellW - 14}`} stroke={TAUPE} strokeWidth="1.5" />
        </g>,
      );
    }
  }
  return <g>{cells}</g>;
}

function SmallTile({x, y, size, row, col, frame, dynamic = true, archived = false}: {x: number; y: number; size: number; row: number; col: number; frame: number; dynamic?: boolean; archived?: boolean}) {
  const index = row * 11 + col;
  const period = 4 + mod(index, 5);
  const changing = dynamic ? Math.floor((frame + index * 3) / period) : 0;
  const variant = mod(index * 7 + changing, 5);
  const base = [PAPER_LIGHT, '#D9DEDF', '#D6C8B7', '#A8ADA0', '#E5D9D1'][mod(row * 5 + col * 3, 5)];
  const ink = archived ? BLUE : ((row + col) % 3 === 0 ? RED : BLUE);
  const inset = size * 0.2;
  const center = size / 2;
  return (
    <g>
      <rect x={x} y={y} width={size} height={size} fill={base} stroke={BLUE} strokeOpacity="0.46" strokeWidth="1.3" />
      {variant === 0 && <circle cx={x + center} cy={y + center} r={size * 0.22} fill="none" stroke={ink} strokeWidth={Math.max(2, size * 0.035)} />}
      {variant === 1 && <path d={`M${x + inset} ${y + center}H${x + size - inset}M${x + center} ${y + inset}V${y + size - inset}`} stroke={ink} strokeWidth={Math.max(2, size * 0.035)} />}
      {variant === 2 && <path d={`M${x + inset} ${y + size - inset}L${x + center} ${y + inset}L${x + size - inset} ${y + size - inset}Z`} fill="none" stroke={ink} strokeWidth={Math.max(2, size * 0.035)} />}
      {variant === 3 && <g stroke={ink} strokeWidth={Math.max(2, size * 0.035)}><path d={`M${x + inset} ${y + inset}L${x + size - inset} ${y + size - inset}`} /><path d={`M${x + size - inset} ${y + inset}L${x + inset} ${y + size - inset}`} /></g>}
      {variant === 4 && <path d={`M${x + inset} ${y + center}A${size * 0.3} ${size * 0.3} 0 0 1 ${x + size - inset} ${y + center}V${y + size - inset}H${x + inset}Z`} fill={ink} fillOpacity="0.82" />}
    </g>
  );
}

function Matrix({frame, count, y = 632, total = 624, dynamic = true, archived = false}: {frame: number; count: 3 | 6; y?: number; total?: number; dynamic?: boolean; archived?: boolean}) {
  const cell = total / count;
  const left = 540 - total / 2;
  const tiles: React.ReactNode[] = [];
  for (let row = 0; row < count; row++) {
    for (let col = 0; col < count; col++) {
      const gap = count === 3 ? 4 : 3;
      tiles.push(<SmallTile key={`tile-${count}-${row}-${col}`} x={left + col * cell + gap / 2} y={y + row * cell + gap / 2} size={cell - gap} row={row} col={col} frame={frame} dynamic={dynamic} archived={archived} />);
    }
  }
  return <g>{tiles}</g>;
}

function CombinatorialScene({frame, hypothetical = false}: {frame: number; hypothetical?: boolean}) {
  if (hypothetical) {
    const archived = frame >= 4470;
    const demo = frame >= 4440 && frame < 4470;
    const demoLocal = demo ? frame - 4440 : 0;
    const timer = frame < 4470 ? Math.min(0.5, (frame - 4440) / 60) : 0.5;
    const compactFrame = demo ? demoLocal : archived ? 31 : 0;
    const grid: React.ReactNode[] = [];
    const n = 6;
    const total = 760;
    const size = total / n;
    const left = 540 - total / 2;
    const top = 570;
    for (let row = 0; row < n; row++) {
      for (let col = 0; col < n; col++) {
        const local = row >= 1 && row <= 4 && col >= 1 && col <= 4;
        grid.push(<SmallTile key={`hyp-${row}-${col}`} x={left + col * size + 2} y={top + row * size + 2} size={size - 4} row={row} col={col} frame={local ? compactFrame + (demo ? 190 : 0) : 2} dynamic={demo && local} archived={archived} />);
      }
    }
    return (
      <g>
        <g>{grid}</g>
        {!archived && <Mark x={540} y={950} size={0.8} color={RED} progress={1} opacity={0.96} />}
        {archived && <Mark x={540} y={950} size={0.8} color={BLUE} progress={1} opacity={0.9} />}
        <text x="130" y="540" fill={RED} fontSize="35" fontWeight="700" letterSpacing="3">假如</text>
        <text x="240" y="540" fill={BLUE} fontSize="27" letterSpacing="2">超级智能列出所有旋律</text>
        {frame >= 4440 && <text x="856" y="540" textAnchor="end" fill={BLUE} fontFamily="Menlo, monospace" fontSize="29">{timer.toFixed(2)}</text>}
        {archived && <text x="540" y="1382" textAnchor="middle" fill={BLUE} fontSize="25" letterSpacing="3">演示设定 · 已归档</text>}
      </g>
    );
  }

  const split = smooth(2220, 2360, frame);
  return (
    <g>
      {frame < 2360 && <g opacity={1 - split}><Matrix frame={frame} count={3} y={570} total={780} /></g>}
      {frame >= 2220 && <g opacity={split}><Matrix frame={frame} count={6} y={570} total={780} /></g>}
      <Mark x={540} y={960} size={0.82} color={RED} progress={1} opacity={0.98} />
      <text x="540" y="1382" textAnchor="middle" fill={SLATE} fontSize="25" letterSpacing="2">组合空间 / 仍在扩张</text>
    </g>
  );
}

function PianoRoll({frame}: {frame: number}) {
  const resolve = smooth(2880, 3260, frame);
  const x = 140;
  const y = 644;
  const width = 790;
  const height = 570;
  const notes = [
    [0, 0.78, 0], [1, 0.62, 0], [2, 0.83, 1], [3, 0.48, 0], [4, 0.72, 1], [5, 0.56, 0],
    [6, 0.9, 0], [7, 0.68, 1], [8, 0.52, 0], [9, 0.82, 0], [10, 0.64, 1], [11, 0.74, 0],
  ];
  const grid: React.ReactNode[] = [];
  for (let i = 0; i <= 12; i++) {
    const yy = y + (height * i) / 12;
    grid.push(<path key={`r${i}`} d={`M${x} ${yy}H${x + width}`} stroke={i % 3 === 0 ? SAGE : TAUPE} strokeWidth={i % 3 === 0 ? 1.8 : 1} opacity="0.8" />);
  }
  for (let i = 0; i <= 16; i++) {
    const xx = x + (width * i) / 16;
    grid.push(<path key={`c${i}`} d={`M${xx} ${y}V${y + height}`} stroke={TAUPE} strokeWidth="1" opacity="0.72" />);
  }
  const bars = notes.map(([row, fraction, accent], i) => {
    const barY = y + 22 + row * 44;
    const full = 72 + fraction * 585;
    const barW = full * resolve;
    const color = accent ? RED : i % 4 === 0 ? BLUE : '#58718B';
    return <g key={`note-${i}`} opacity={resolve}><rect x={x + 18} y={barY} width={barW} height="25" fill={color} /><path d={`M${x + 18 + barW} ${barY - 5}V${barY + 30}`} stroke={PAPER_LIGHT} strokeWidth="2" /></g>;
  });
  return (
    <g>
      <rect x="140" y="630" width="790" height="606" fill={PAPER_LIGHT} stroke={TAUPE} strokeWidth="2" />
      <g>{grid}</g>
      <g opacity={1 - resolve} fill="none" stroke={BLUE} strokeWidth="3"><path d="M164 942C220 846 248 1066 310 904S400 1026 455 868S544 1056 606 902S712 1006 758 866S850 1003 916 882" /></g>
      {bars}
    </g>
  );
}

function ExpandingLattice({frame}: {frame: number}) {
  const progress = clamp((frame - 3540) / 600);
  const cols = 5 + Math.floor(progress * 9);
  const rows = 4 + Math.floor(progress * 8);
  const x = 120;
  const y = frame >= 4140 ? 625 : 570;
  const w = 790;
  const h = frame >= 4140 ? 644 : 730;
  const cw = w / cols;
  const ch = h / rows;
  const pieces: React.ReactNode[] = [];
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const xx = x + col * cw;
      const yy = y + row * ch;
      const color = [BLUE, SAGE, TAUPE, ROSE][mod(row * 3 + col * 5, 4)];
      pieces.push(
        <g key={`lattice-${row}-${col}`} opacity="0.78">
          <rect x={xx + 2} y={yy + 2} width={cw - 4} height={ch - 4} fill={PAPER_LIGHT} stroke={color} strokeWidth="1.1" />
          <path d={`M${xx + 10} ${yy + 10}V${yy + ch - 10}M${xx + 17} ${yy + 14}H${xx + cw - 8}M${xx + 17} ${yy + 22}H${xx + cw - 14}`} stroke={color} strokeWidth="1.5" opacity="0.7" />
          {row === Math.floor(rows / 2) && col === Math.floor(cols / 2) && <path d={`M${xx + cw * 0.35} ${yy + ch * 0.62}H${xx + cw * 0.74}`} stroke={RED} strokeWidth="3" />}
        </g>,
      );
    }
  }
  return (
    <g>
      {pieces}
      {frame >= 4140 && <g><rect x="128" y="552" width="190" height="48" fill={RED} /><text x="223" y="585" textAnchor="middle" fill={PAPER_LIGHT} fontSize="27" fontWeight="700" letterSpacing="2">科幻设定</text></g>}
    </g>
  );
}

function StackedCatalog({frame}: {frame: number}) {
  const progress = clamp((frame - 5040) / 480);
  const shelves: React.ReactNode[] = [];
  for (let row = 0; row < 5; row++) {
    for (let col = 0; col < 14; col++) {
      const x = 110 + col * 57;
      const y = 575 + row * 145;
      const color = [BLUE, '#425B78', SAGE, TAUPE, ROSE][mod(row * 7 + col * 3, 5)];
      shelves.push(<g key={`shelf-${row}-${col}`} opacity={0.2 + progress * 0.38}><rect x={x} y={y} width="52" height="118" fill={PAPER_LIGHT} stroke={color} strokeWidth="1.2" /><path d={`M${x + 10} ${y + 14}V${y + 104}M${x + 16} ${y + 22}H${x + 44}`} stroke={color} strokeWidth="2" opacity="0.72" /></g>);
    }
  }
  const pathProgress = clamp((frame - 5200) / 160);
  return (
    <g>
      <g>{shelves}</g>
      <g>
        <rect x="325" y="600" width="430" height="258" fill={PAPER_LIGHT} stroke={TAUPE} strokeWidth="2" />
        <text x="354" y="640" fill={BLUE} fontSize="27" fontWeight="600" letterSpacing="1">你的手稿</text>
        <Mark x={540} y={750} size={0.55} color={RED} progress={1} />
      </g>
      <path d="M540 850V925" stroke={RED} strokeWidth="8" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - pathProgress} />
      <g>
        <rect x="325" y="922" width="430" height="258" fill={PAPER_LIGHT} stroke={BLUE} strokeWidth="2" />
        <text x="354" y="963" fill={BLUE} fontSize="27" fontWeight="600" letterSpacing="1">预存目录副本</text>
        <Mark x={540} y={1074} size={0.55} color={BLUE} progress={1} />
      </g>
      <rect x="355" y="1196" width="370" height="80" fill={PAPER} fillOpacity="0.94" />
      <text x="540" y="1232" textAnchor="middle" fill={RED} fontSize="45" fontWeight="700" letterSpacing="3">#00004719</text>
      <text x="540" y="1264" textAnchor="middle" fill={BLUE} fontSize="23" letterSpacing="3">示意编号</text>
    </g>
  );
}

function FinalShelves({frame}: {frame: number}) {
  const progress = smooth(6150, 6540, frame);
  const rows: React.ReactNode[] = [];
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 12; col++) {
      const x = 106 + col * 68;
      const y = 570 + row * 92;
      const color = [BLUE, '#405B78', '#5A7086', SAGE, TAUPE][mod(row * 5 + col * 7, 5)];
      const selected = (row + col) % 4 !== 1;
      if (!selected) continue;
      rows.push(<g key={`final-${row}-${col}`} opacity={0.16 + 0.58 * progress}><rect x={x} y={y} width="57" height="78" fill={color} /><path d={`M${x + 9} ${y + 8}V${y + 70}M${x + 17} ${y + 16}H${x + 49}`} stroke={PAPER_LIGHT} strokeWidth="1.4" opacity="0.52" /></g>);
    }
  }
  const scale = mix(0.62, 0.24, smooth(6540, 6780, frame));
  return (
    <g>
      <g>{rows}</g>
      <path d="M120 558H960M120 1320H960" stroke={BLUE} strokeWidth="3" opacity="0.45" />
      <g transform={`translate(540 1120) scale(${scale})`}>
        <path d="M-114 0L0 -62L114 0V96H-114Z" fill={PAPER_LIGHT} stroke={RED} strokeWidth="6" />
        <path d="M0 -62V95M-114 0L0 30L114 0" fill="none" stroke={RED} strokeWidth="5" />
        <circle cx="0" cy="-10" r="12" fill={BLUE} />
      </g>
    </g>
  );
}

function CoverArchive() {
  const blocks: React.ReactNode[] = [];
  for (let row = 0; row < 6; row++) {
    for (let col = 0; col < 9; col++) {
      const x = 118 + col * 88;
      const y = 620 + row * 96;
      const index = row * 9 + col;
      const fill = [BLUE, '#405B78', '#60758A', SAGE][mod(index * 3 + row, 4)];
      const center = row >= 2 && row <= 3 && col >= 3 && col <= 5;
      if (center) continue;
      blocks.push(<g key={`cover-block-${row}-${col}`} opacity="0.7"><rect x={x} y={y} width="82" height="82" fill={PAPER_LIGHT} stroke={fill} strokeWidth="2" /><path d={`M${x + 13} ${y + 13}V${y + 69}M${x + 22} ${y + 20}H${x + 68}`} stroke={fill} strokeWidth="2" /></g>);
    }
  }
  return <g>{blocks}</g>;
}

export const Geometry: React.FC<{frame: number; cover?: boolean}> = ({frame, cover = false}) => {
  if (cover) {
    return (
      <g>
        <CoverArchive />
        <g transform="translate(540 965) scale(1.1)"><InitialCard frame={240} /></g>
      </g>
    );
  }

  if (frame < 2040) {
    const pullback = smooth(1380, 2040, frame);
    const cardX = mix(540, 540, pullback);
    const cardY = mix(914, 916, pullback);
    return (
      <g>
        {frame >= 1380 && <LibraryField frame={frame} opacity={pullback} />}
        {frame < 1380 && <g>
          <MotifCard x={200} y={454} kind="poem" label="那句诗" frame={frame} delay={660} />
          <MotifCard x={610} y={454} kind="music" label="那段旋律" frame={frame} delay={790} />
          <MotifCard x={422} y={1280} kind="blue" label="那抹蓝" frame={frame} delay={920} />
        </g>}
        <g transform={`translate(${cardX} ${cardY}) scale(${mix(1.3, 0.32, pullback)})`}>
          <InitialCard frame={frame} />
        </g>
      </g>
    );
  }

  if (frame < 2880) return <CombinatorialScene frame={frame} />;
  if (frame < 3540) return <PianoRoll frame={frame} />;
  if (frame < 4260) return <ExpandingLattice frame={frame} />;
  if (frame < 5040) return <CombinatorialScene frame={frame} hypothetical />;
  if (frame < 5520) return <StackedCatalog frame={frame} />;
  if (frame < 6780) {
    const pullback = smooth(6140, 6780, frame);
    const artProgress = clamp((frame - 5520) / 510);
    const scale = mix(1.3, 0.22, pullback);
    const shelves = smooth(6120, 6660, frame);
    return (
      <g>
        <LibraryField frame={frame} opacity={shelves} dense />
        <g transform={`translate(540 914) scale(${scale})`}>
          <InitialCard frame={frame} finalPass />
        </g>
        {frame < 6030 && <path d={`M414 1010H${414 + artProgress * 252}`} stroke={RED} strokeWidth="5" opacity={0.9} />}
      </g>
    );
  }
  return <FinalShelves frame={frame} />;
};
