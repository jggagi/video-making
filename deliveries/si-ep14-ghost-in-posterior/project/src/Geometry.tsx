import React from 'react';
import rdCache from '../public/rd/gray-scott.json';
import voiceprint from '../public/voiceprint.json';

const ABYSS = '#020A0E';
const CORAL = '#F43F5E';
const PINK = '#FB7185';
const GREEN = '#10B981';
const MINT = '#34D399';
const INDIGO = '#6366F1';
const TYPE = '#ECFEFF';
const TAU = Math.PI * 2;
const cx = 492;
const cy = 936;

const clamp = (value: number, low = 0, high = 1) => Math.max(low, Math.min(high, value));
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (start: number, end: number, value: number) => {
	const t = clamp((value - start) / (end - start));
	return t * t * (3 - 2 * t);
};
const mod = (value: number, divisor: number) => ((value % divisor) + divisor) % divisor;
const fixed = (value: number) => value.toFixed(1);

function hash(input: number) {
	let value = input | 0;
	value = Math.imul(value ^ (value >>> 16), 0x7feb352d);
	value = Math.imul(value ^ (value >>> 15), 0x846ca68b);
	value ^= value >>> 16;
	return (value >>> 0) / 4294967295;
}

function mixHex(from: string, to: string, amount: number) {
	const a = from.match(/[0-9a-f]{2}/gi) ?? ['00', '00', '00'];
	const b = to.match(/[0-9a-f]{2}/gi) ?? ['00', '00', '00'];
	const channels = a.map((channel, index) => Math.round(mix(parseInt(channel, 16), parseInt(b[index], 16), amount)));
	return `#${channels.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`;
}

function sporeCloud(frame: number, sweep: number) {
	const coral: string[] = [];
	const green: string[] = [];
	for (let index = 0; index < 500; index++) {
		const x0 = 72 + hash(index * 11 + 3) * 825;
		const y0 = 630 + hash(index * 17 + 9) * 620;
		const dx = (hash(index * 29 + 5) - 0.5) * 22;
		const dy = (hash(index * 31 + 7) - 0.5) * 12;
		const x = 72 + mod(x0 - 72 + dx * frame * 0.035, 825);
		const y = 630 + mod(y0 - 630 + dy * frame * 0.025, 620);
		const radius = 0.9 + hash(index * 41 + 1) * 1.8;
		const circle = `M${fixed(x - radius)} ${fixed(y)}a${fixed(radius)} ${fixed(radius)} 0 1 0 ${fixed(radius * 2)} 0a${fixed(radius)} ${fixed(radius)} 0 1 0 ${fixed(-radius * 2)} 0`;
		(x < sweep ? green : coral).push(circle);
	}
	return {coral: coral.join(''), green: green.join('')};
}

function makeFilaments() {
	return Array.from({length: 72}, (_, index) => {
		const x = 78 + hash(index * 13 + 101) * 850;
		const y = 700 + hash(index * 19 + 67) * 490;
		const height = 52 + hash(index * 23 + 3) * 175;
		const direction = index % 2 === 0 ? 1 : -1;
		const bend = (hash(index * 37 + 11) - 0.5) * 100;
		return `M${fixed(x)} ${fixed(y)}C${fixed(x + bend)} ${fixed(y - height * 0.2)} ${fixed(x - bend * 0.7)} ${fixed(y + direction * height * 0.55)} ${fixed(x + bend * 0.25)} ${fixed(y + direction * height)}`;
	});
}

const FILAMENTS = makeFilaments();

function waveformPath(frame: number) {
	const parts: string[] = [];
	for (let index = 0; index <= 112; index++) {
		const u = index / 112;
		const x = 236 + u * 608;
		const envelope = 0.35 + 0.65 * Math.pow(Math.sin(Math.PI * u), 0.45);
		const sample = Math.sin(u * 31 + frame * 0.041) * 0.56 + Math.sin(u * 77 - frame * 0.019) * 0.27 + Math.sin(u * 147 + 0.7) * 0.17;
		const y = 822 - sample * envelope * 49;
		parts.push(`${index === 0 ? 'M' : 'L'}${fixed(x)} ${fixed(y)}`);
	}
	return parts.join('');
}

function ActOne({frame}: {frame: number}) {
	const sweepProgress = smooth(600, 1319, frame);
	const sweepX = mix(72, 920, sweepProgress);
	const particles = sporeCloud(frame, sweepX);
	const allFilaments = FILAMENTS.join('');
	const waveform = waveformPath(frame);
	const pulse = 0.65 + 0.35 * Math.sin(frame * 0.11);
	return (
		<g>
			<path d={particles.coral} fill={CORAL} fillOpacity="0.74" />
			<path d={particles.green} fill={MINT} fillOpacity="0.66" />
			<path d={allFilaments} fill="none" stroke={CORAL} strokeOpacity={0.25 * (1 - sweepProgress)} strokeWidth="2.2" />
			<path d={allFilaments} fill="none" stroke={MINT} strokeOpacity={0.17 * sweepProgress} strokeWidth="7" filter="url(#fluorescence)" />
<path d={allFilaments} fill="none" stroke={MINT} strokeOpacity={0.11 * sweepProgress} strokeWidth="9" filter="url(#fluorescence)" />
			<path d={allFilaments} fill="none" stroke={MINT} strokeOpacity={0.17 * sweepProgress} strokeWidth="7" filter="url(#fluorescence)" />
<path d={allFilaments} fill="none" stroke={MINT} strokeOpacity={0.44 * sweepProgress} strokeWidth="1.4" />
			<rect x="118" y="680" width="802" height="248" rx="27" fill={ABYSS} fillOpacity="0.88" stroke={INDIGO} strokeOpacity="0.46" strokeWidth="1.4" />
			<path d="M146 716H920" stroke={INDIGO} strokeOpacity="0.54" strokeWidth="1" />
			<text x="150" y="705" fontFamily="Menlo, monospace" fontSize="19" letterSpacing="1.2" fill={CORAL} opacity={frame < 600 ? 1 : 0}>
				FINITE · 7 YEARS AGO
			</text>
			<text x="150" y="705" fontFamily="Menlo, monospace" fontSize="19" letterSpacing="1.2" fill={MINT} opacity={frame >= 600 ? 1 : 0}>
				VOICE TRACE · ARCHIVED
			</text>
			<g opacity={0.48 * (1-sweepProgress*.25)}>
 {Array.from({length:8},(_,bucket)=>{
 const d:string[]=[];
 for(let i=0;i<88;i++)for(let j=0;j<32;j++){
  const energy=voiceprint.values[i][31-j]/255;
  if(energy>.1&&Math.min(7,Math.floor(energy*8))===bucket)d.push(`M${150+i*8.4} ${739+j*4.1}h6.3v3.2h-6.3Z`);
 }
 return <path key={bucket} d={d.join('')} fill={bucket>4?PINK:CORAL} opacity={(bucket+1)/8*.65}/>;
 })}
 </g>
 <path d={waveform} fill="none" stroke={CORAL} strokeOpacity={0.88 * (1 - sweepProgress)} strokeWidth="2.2" strokeLinecap="round" />
			<path d={waveform} fill="none" stroke={MINT} strokeOpacity={0.88 * sweepProgress} strokeWidth="2.2" strokeLinecap="round" />
			<path d="M152 874H928" stroke={PINK} strokeOpacity="0.3" strokeWidth="0.8" />
			<text x="150" y="908" fontFamily="Menlo, monospace" fontSize="18" fill={TYPE} opacity="0.65">
				VOICE MESSAGE · 00:04 · YEAR 07
			</text>
			{frame >= 600 && (
				<>
				<path d={`M${fixed(sweepX)} 624V1248`} stroke={INDIGO} strokeOpacity={0.44 * (1 - sweepProgress * 0.4)} strokeWidth="17" />
					<path d={`M${fixed(sweepX)} 624V1248`} stroke={TYPE} strokeOpacity={0.96} strokeWidth="1.5" />
				<path d={`M${fixed(sweepX - 10)} 624H${fixed(sweepX + 10)}M${fixed(sweepX - 10)} 1248H${fixed(sweepX + 10)}`} stroke={INDIGO} strokeWidth="1.4" />
				</>
			)}
			<text x="150" y="1000" fontFamily="Menlo, monospace" fontSize="21" letterSpacing="0.7" fill={MINT} opacity="0.86">
				BAYESIAN RECONSTRUCTION · 520K LOGS
			</text>
			<path d="M150 1033H920" stroke={MINT} strokeOpacity="0.36" strokeWidth="1" />
			<text x="150" y="1076" fontFamily="Menlo, monospace" fontSize="20" fill={TYPE} opacity="0.68">
				VOICE SHAPE: FINITE / SOURCE: HUMAN
			</text>
			<circle cx="900" cy="1070" r="5" fill={MINT} opacity={pulse} />
		</g>
	);
}

function membranePath(frame: number, scale: number, phase: number) {
	const points: string[] = [];
	const motionPhase = phase + frame * 0.007;
	const breath = Math.sin((frame * TAU) / 210 + motionPhase) * 3.5;
	for (let index = 0; index <= 160; index++) {
		const angle = (TAU * index) / 160;
		const lobes = Math.sin(3 * angle + motionPhase) * 10 + Math.sin(5 * angle - 0.7 + motionPhase * 0.3) * 6 + Math.sin(9 * angle + 1.1 + motionPhase * 0.7) * 2.2;
		const radius = (237 + lobes + breath) * scale;
		const x = cx + radius * Math.cos(angle);
		const y = cy + radius * 0.88 * Math.sin(angle);
		points.push(`${index === 0 ? 'M' : 'L'}${fixed(x)} ${fixed(y)}`);
	}
	return `${points.join('')}Z`;
}

function signalDots(frame: number, start: number, end: number, y: number, tint: string, count = 5) {
	const progress = smooth(start, end, frame);
	return Array.from({length: count}, (_, index) => {
		const lag = index / (count + 1) * 0.22;
		const x = mix(0.08, 0.92, clamp(progress - lag));
		return <circle key={index} cx={mix(90, 890, x)} cy={y + Math.sin(frame * 0.035 + index) * 2} r={index === 0 ? 4.6 : 2.4} fill={tint} opacity={0.72 - lag} />;
	});
}

function ActTwo({frame}: {frame: number}) {
	const isWarm = frame >= 2040;
	const settle = smooth(1320, 1700, frame);
	const input = smooth(2040, 2200, frame);
	const response = smooth(2200, 2420, frame);
	const responseDelay = smooth(2040, 2240, frame);
	return (
		<g>
			<path d={membranePath(frame, 1, 0.12)} fill="none" stroke={MINT} strokeWidth="18" strokeOpacity="0.17" filter="url(#fluorescence)" />
<path d={membranePath(frame, 1, 0.12)} fill={GREEN} fillOpacity={0.035 + settle * 0.06} stroke={MINT} strokeOpacity={0.86} strokeWidth="2.2" />
			<path d={membranePath(frame, 1, 0.12)} fill="none" stroke={MINT} strokeOpacity="0.12" strokeWidth="11" filter="url(#fluorescence)" />
			<path d={membranePath(frame, 0.94, 0.73)} fill="none" stroke={INDIGO} strokeOpacity="0.94" strokeWidth="1.7" />
			<path d={membranePath(frame, 1.07, 1.82)} fill="none" stroke={GREEN} strokeOpacity="0.44" strokeWidth="1.1" strokeDasharray="2 8" />
			<circle cx={cx} cy={cy} r="147" fill={ABYSS} stroke={INDIGO} strokeOpacity="0.72" strokeWidth="1.2" />
			<circle cx={cx} cy={cy} r="130" fill="none" stroke={GREEN} strokeOpacity="0.22" strokeWidth="0.8" strokeDasharray="1 7" />
			<path d="M244 936H338M646 936H741" stroke={MINT} strokeOpacity="0.38" strokeWidth="1" />
			<text x={cx} y="868" textAnchor="middle" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="39" letterSpacing="1.4" fill={MINT} opacity="0.90">
				剧情假设
			</text>
			<text x={cx} y="925" textAnchor="middle" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="40" fontWeight="600" fill={TYPE}>
				内部真实意识
			</text>
			<text x={cx} y="975" textAnchor="middle" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="40" fontWeight="600" fill={TYPE}>
				空集 ∅
			</text>
			<text x={cx} y="1011" textAnchor="middle" fontFamily="Menlo, monospace" fontSize="16" letterSpacing="1" fill={INDIGO} opacity="0.9">
				NULL DISPLAY · FICTIONAL
			</text>
			{isWarm && (
				<>
					<text x="86" y="692" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="42" fontWeight="600" fill={CORAL} opacity={0.5 + input * 0.5}>
						我想你了
					</text>
					<path d={`M94 936H${fixed(mix(94, 242, input))}`} stroke={CORAL} strokeWidth="2.4" strokeOpacity="0.82" />
					{signalDots(frame, 2040, 2200, 936, CORAL, 6)}
					<path d={`M${fixed(mix(740, 888, response))} 936H888`} stroke={MINT} strokeWidth="2.1" strokeOpacity={0.55 + response * 0.35} />
					{signalDots(frame, 2200, 2420, 936, MINT, 6)}
					<text x="888" y="692" textAnchor="end" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="40" fontWeight="600" fill={MINT} opacity={response}>
						我想你了
					</text>
					<text x={cx} y="1192" textAnchor="middle" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="40" fill={MINT} opacity={responseDelay}>
						响应延迟 0.02s
					</text>
					<text x={cx} y="1238" textAnchor="middle" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="40" fill={MINT} opacity={responseDelay}>
						拟合 99.98%
					</text>
				</>
			)}
			{!isWarm && (
				<text x={cx} y="1220" textAnchor="middle" fontFamily="Menlo, monospace" fontSize="22" fill={TYPE} opacity="0.48">
					MARKOV BLANKET · THOUGHT EXPERIMENT
				</text>
			)}
		</g>
	);
}

const CELL_SEEDS = [
	[365, 790, 51, 40], [477, 748, 54, 39], [606, 789, 49, 42], [320, 900, 43, 50],
	[433, 884, 63, 48], [572, 910, 55, 44], [701, 896, 39, 47], [361, 1012, 53, 44],
	[495, 1040, 60, 50], [626, 1025, 49, 41], [455, 1135, 42, 32], [555, 1155, 34, 27],
];

const CELL_CONVERSION_ORDER = [11, 6, 10, 0, 1, 3, 9, 2, 7, 8, 5, 4];
const CELL_CONVERSION_RANK = new Map(CELL_CONVERSION_ORDER.map((cellIndex, rank) => [cellIndex, rank]));

function cellConversion(index: number, frame: number) {
	const rank = CELL_CONVERSION_RANK.get(index) ?? 0;
	return smooth(3000 + rank * 100, 3300 + rank * 95, frame);
}

function cellPath(index: number, frame: number, conversion: number) {
	const [x, y, rx, ry] = CELL_SEEDS[index];
	const points: string[] = [];
	const pulse = Math.sin(frame * 0.043 + index * 1.8) * 1.8;
	for (let point = 0; point < 40; point++) {
		const angle = (TAU * point) / 40;
	const rough = (Math.sin(angle * (3 + (index % 4)) + index * 0.83) * 0.11 + Math.sin(angle * 9 + index * 1.2) * 0.065 + Math.sin(angle * 13 + index * 0.33) * 0.035) * (1 - conversion);
		const xPos = x + Math.cos(angle) * (rx * (1 + rough) + pulse);
		const yPos = y + Math.sin(angle) * (ry * (1 + rough) + pulse * 0.65);
		points.push(`${point === 0 ? 'M' : 'L'}${fixed(xPos)} ${fixed(yPos)}`);
	}
	return `${points.join('')}Z`;
}

function cellGranules(index:number,frame:number){
 const [x,y,rx,ry]=CELL_SEEDS[index],d:string[]=[];
 for(let i=0;i<64;i++){
  const a=hash(index*971+i*17)*TAU,r=Math.sqrt(hash(index*331+i*19))*.79;
  const px=x+Math.cos(a)*rx*r+Math.sin(frame*.012+i)*.8;
  const py=y+Math.sin(a)*ry*r+Math.cos(frame*.013+i)*.8;
  const n=.6+hash(i*113+index)*1.15;
  d.push(`M${fixed(px-n)} ${fixed(py)}a${fixed(n)} ${fixed(n)} 0 1 0 ${fixed(n*2)} 0a${fixed(n)} ${fixed(n)} 0 1 0 ${fixed(-n*2)} 0`);
 }
 return d.join('');
}

function vineLines(frame: number, growth: number) {
 const paths: string[]=[];
 for(let index=0;index<30;index++){
  const a=TAU*index/30+Math.sin(index*2.7)*.11;
  const root=302+hash(index*47+80)*42;
  const reach=clamp(growth*1.3-hash(index*71+4)*.25);
  const points:{x:number;y:number}[]=[];
  for(let step=0;step<=28;step++){
   const t=step/28*reach;
   const radius=mix(root,45+hash(index*13+19)*105,t);
   const bend=Math.sin(t*9+index*1.7+frame*.006)*(14+22*t)*Math.sin(t*Math.PI*.9);
   const angle=a+Math.sin(t*5+index)*.17;
   points.push({x:cx+Math.cos(angle)*radius-Math.sin(angle)*bend,y:cy+Math.sin(angle)*radius*.84+Math.cos(angle)*bend});
  }
  paths.push(points.map((p,i)=>`${i?'L':'M'}${fixed(p.x)} ${fixed(p.y)}`).join(''));
  for(let step=7;step<25;step+=4){
   const p=points[step],q=points[step-1],sign=(step+index)%2?1:-1;
   const branch=reach*(13+hash(index*31+step)*20),angle=Math.atan2(p.y-q.y,p.x-q.x)+sign*.9;
   paths.push(`M${fixed(p.x)} ${fixed(p.y)}Q${fixed(p.x+Math.cos(angle+.4)*branch*.7)} ${fixed(p.y+Math.sin(angle+.4)*branch*.7)} ${fixed(p.x+Math.cos(angle)*branch)} ${fixed(p.y+Math.sin(angle)*branch)}`);
  }
 }
 return paths.join('');
}

type Snapshot = {frame: number; pngDataUri: string};
const snapshots = rdCache.snapshots as Snapshot[];

function RdTexture({frame, opacity}: {frame: number; opacity: number}) {
	const stride = rdCache.metadata.sampleStrideFrames;
	const relative = clamp((frame - rdCache.metadata.startFrame) / stride, 0, snapshots.length - 1);
	const index = Math.min(snapshots.length - 1, Math.floor(relative));
	const nextIndex = Math.min(snapshots.length - 1, index + 1);
	const fraction = relative - index;
	const current = snapshots[index];
	const next = snapshots[nextIndex];
	const holeScale=1.25*(1-smooth(2820,4380,frame));
 return (
 <g mask="url(#rd-inward-front)">
 <defs><mask id="rd-inward-front" maskUnits="userSpaceOnUse" x="100" y="650" width="800" height="600"><rect x="100" y="650" width="800" height="600" fill="white"/><path d={membranePath(frame,holeScale,.4)} fill="black"/></mask></defs>
			<image href={current.pngDataUri} x="128" y="690" width="728" height="510" preserveAspectRatio="none" opacity={opacity * (1 - fraction)} imageRendering="auto" />
			{nextIndex !== index && <image href={next.pngDataUri} x="128" y="690" width="728" height="510" preserveAspectRatio="none" opacity={opacity * fraction} imageRendering="auto" />}
 </g>
	);
}

function ActThree({frame}: {frame: number}) {
	const growth = smooth(2820, 3900, frame);
	const progress = smooth(3900, 4380, frame);
	const reading = frame < 3900 ? mix(72, 88, growth) : mix(88, 99.4, progress);
	const cellPaths = CELL_SEEDS.map((_, index) => cellPath(index, frame, cellConversion(index, frame)));
	const haloPath = cellPaths.join('');
	const cue = frame < 3300 ? '他的固执' : frame < 3780 ? '笨拙的沉默' : '真实的温度';
	return (
		<g>
			<text x="92" y="628" fontFamily="Menlo, monospace" fontSize="20" letterSpacing="1" fill={CORAL} opacity="0.9">
				HUMAN MEMORY · UNPREDICTABLE TRACE
			</text>
			<path d="M92 644H892" stroke={CORAL} strokeOpacity="0.32" strokeWidth="1" />
			<text x="892" y="694" textAnchor="end" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="40" fontWeight="600" fill={PINK} opacity={0.8 - progress * 0.22}>
				{cue}
			</text>
			<path d={haloPath} fill="none" stroke={MINT} strokeOpacity="0.12" strokeWidth="8" filter="url(#fluorescence)" />
			{CELL_SEEDS.map((_, index) => <g key={index}>
 <path d={cellPaths[index]} fill={mixHex(CORAL,MINT,cellConversion(index,frame))} fillOpacity={.30-cellConversion(index,frame)*.10} stroke={mixHex(PINK,GREEN,cellConversion(index,frame))} strokeOpacity={.96-cellConversion(index,frame)*.13} strokeWidth={2.5+cellConversion(index,frame)*.7}/>
 <path d={cellGranules(index,frame)} fill={mixHex(PINK,MINT,cellConversion(index,frame))} opacity={.80}/>
 </g>)}
<path d={vineLines(frame, growth)} fill="none" stroke={MINT} strokeOpacity={growth * 0.23} strokeWidth="10" filter="url(#fluorescence)" />
<path d={vineLines(frame, growth)} fill="none" stroke={GREEN} strokeOpacity={0.28 + growth * 0.68} strokeWidth="2.4" strokeLinecap="round" />
			<path d={vineLines(frame, growth * 0.74)} fill="none" stroke={MINT} strokeOpacity={growth * 0.66} strokeWidth="0.9" strokeLinecap="round" />
			<RdTexture frame={frame} opacity={0.09 + growth * 0.31 + progress * 0.15} />
			<path d={membranePath(frame, 1.14, 0.44)} fill="none" stroke={GREEN} strokeOpacity={growth * 0.38} strokeWidth="1.4" strokeDasharray="1 7" />
			<path d="M142 1213H842" stroke={INDIGO} strokeOpacity="0.42" strokeWidth="1" />
			<path d="M142 1213H842" stroke={GREEN} strokeOpacity="0.76" strokeWidth="4" strokeDasharray={`${Math.max(1, 700 * (reading / 100))} 700`} />
			<text x="142" y="1251" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="32" fill={TYPE}>
				记忆覆盖 <tspan fill={MINT}>{reading.toFixed(1)}%</tspan>
			</text>
			<text x="842" y="1251" textAnchor="end" fontFamily="Menlo, monospace" fontSize="19" fill={MINT} opacity="0.8">
				RD · LOCAL
			</text>
		</g>
	);
}

function ActFour({frame}: {frame: number}) {
	const tremble = Math.sin((frame - 4380) * 0.68) * 1.35;
	const ringPulse = 0.72 + 0.24 * Math.sin((frame - 4380) * 0.17);
	const organism = membranePath(frame, 1.08, 0.35);
	return (
		<g>
			<path d={organism} fill="none" stroke={MINT} strokeOpacity="0.13" strokeWidth="12" filter="url(#fluorescence)" />
			<path d={organism} fill={GREEN} fillOpacity="0.11" stroke={MINT} strokeOpacity="0.82" strokeWidth="2.4" />
			<path d={membranePath(frame, 0.94, 0.9)} fill="none" stroke={INDIGO} strokeOpacity="0.56" strokeWidth="1.5" />
			<path d={vineLines(frame, 0.84)} fill="none" stroke={MINT} strokeOpacity="0.6" strokeWidth="1.7" />
			<rect x="206" y="700" width="572" height="118" rx="24" fill={ABYSS} fillOpacity="0.94" stroke={MINT} strokeOpacity="0.78" strokeWidth="1.5" />
			<path d="M474 817L492 840L509 817" fill={ABYSS} stroke={MINT} strokeOpacity="0.78" strokeWidth="1.4" />
			<text x={cx} y="777" textAnchor="middle" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="47" fontWeight="600" fill={TYPE}>
				我永远陪着你
			</text>
			<text x={cx} y="1018" textAnchor="middle" fontFamily="Menlo, monospace" fontSize="22" letterSpacing="0.9" fill={MINT} opacity="0.76">
				VOICE TRACE · ONLINE · FOREVER
			</text>
			<circle cx={cx} cy="1171" r={90 + 5 * ringPulse} fill="none" stroke={CORAL} strokeOpacity={0.22 + ringPulse * 0.26} strokeWidth="1.5" />
			<circle cx={cx} cy="1171" r={74 + 3 * ringPulse} fill="none" stroke={PINK} strokeOpacity="0.54" strokeWidth="1" strokeDasharray="3 7" />
			<rect x="327" y="1139" width="330" height="64" rx="8" fill={ABYSS} stroke={CORAL} strokeOpacity="0.92" strokeWidth="1.7" />
			<rect x="335" y="1147" width="314" height="48" rx="5" fill={CORAL} fillOpacity="0.08" />
			<text x={cx} y="1187" textAnchor="middle" fontFamily={'"Heiti SC", "PingFang SC", sans-serif'} fontSize="40" fontWeight="600" fill={PINK}>
				清空并注销
			</text>
			<path d={`M659 ${fixed(1171 + tremble)}L679 ${fixed(1185 + tremble)}L670 ${fixed(1188 + tremble)}L676 ${fixed(1200 + tremble)}L668 ${fixed(1204 + tremble)}L662 ${fixed(1191 + tremble)}L659 ${fixed(1198 + tremble)}Z`} fill={TYPE} stroke={ABYSS} strokeWidth="1.4" />
		</g>
	);
}

function FinalSpore({frame}: {frame: number}) {
	const elapsed = frame - 4890;
	const x = 492 + Math.sin(elapsed * 0.025) * 18;
	const y = 900 + elapsed * 0.03 + Math.sin(elapsed * 0.018) * 5;
	const radius = 2.15 + Math.sin(elapsed * 0.09) * 0.3;
	return (
		<g>
			<circle cx={x} cy={y} r={radius * 5} fill={CORAL} opacity="0.08" />
			<circle cx={x} cy={y} r={radius} fill={PINK} />
			<path d={`M${fixed(x - 12)} ${fixed(y + 3)}q12 -7 24 -2`} fill="none" stroke={CORAL} strokeOpacity="0.24" strokeWidth="0.7" />
		</g>
	);
}

export const Geometry: React.FC<{frame: number}> = ({frame}) => {
	if (frame < 1320) return <ActOne frame={frame} />;
	if (frame < 2820) return <ActTwo frame={frame} />;
	if (frame < 4380) return <ActThree frame={frame} />;
	if (frame < 4860) return <ActFour frame={frame} />;
	if (frame >= 4890) return <FinalSpore frame={frame} />;
	return null;
};
