import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {ActLabel, Droplet, PetriDish} from './Visuals';
import {C, FONT} from '../lib/theme';
import {ease, mix, seeded} from '../lib/math';

const CIRCUITS = Array.from({length: 24}, (_, i) => {
  const y = 240 + i * 27;
  const bend = 300 + seeded(i + 1) * 1150;
  return {i, y, bend, shift: (i % 2 === 0 ? -1 : 1) * (35 + seeded(i + 80) * 100)};
});

export const Act1Speed: React.FC = () => {
  const frame = useCurrentFrame();
  const detach = ease(frame, 90, 340);
  const zoom = mix(1, 25, ease(frame, 900, 1520));
  const labOpacity = 1 - ease(frame, 1100, 1450);
  const digital = ease(frame, 1030, 1370);
  const blink = ease(frame, 80, 650);
  const overlayAlpha = interpolate(frame, [60, 105, 300, 360], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const chineseLetterSpacing = interpolate(frame, [60, 360], [16, 36], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const oldTitleOpacity = 1 - ease(frame, 1110, 1180);
  const titleSwap = ease(frame, 1220, 1300);
  const dropY = 438 + ease(frame, 0, 900) * 7;
  return <AbsoluteFill>
    <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: 'absolute'}}>
      <defs>
        <radialGradient id="lab-light"><stop stopColor={C.amber} stopOpacity="0.10"/><stop offset="1" stopColor={C.amber} stopOpacity="0"/></radialGradient>
        <linearGradient id="pipette-metal"><stop stopColor="#181b21"/><stop offset=".3" stopColor="#8a8066"/><stop offset=".5" stopColor="#e6c88a"/><stop offset=".7" stopColor="#4b4536"/><stop offset="1" stopColor="#0c1018"/></linearGradient>
        <radialGradient id="fiber-halo"><stop stopColor={C.cyan} stopOpacity="0.14"/><stop offset="1" stopColor={C.cyan} stopOpacity="0"/></radialGradient>
        <clipPath id="act1-circuit-clip"><rect x="0" y="205" width="1920" height="725"/></clipPath>
      </defs>
      <g clipPath="url(#act1-circuit-clip)"><g opacity={labOpacity} transform={`translate(1120 ${dropY}) scale(${zoom}) translate(-1120 ${-dropY})`}>
        <ellipse cx="1120" cy="560" rx="390" ry="370" fill="url(#lab-light)"/>
        <path d="M810 873H1640 M850 878H1600" stroke={C.amber} strokeOpacity=".18"/>
        <path d="M1090 230H1150V304L1131 349V374H1109V349L1090 304Z" fill="url(#pipette-metal)" stroke="#bc9c67" strokeWidth="1.5"/>
        <path d="M1115 244V313L1120 346" fill="none" stroke="#ffe1a0" strokeOpacity=".3" strokeWidth="3"/>
        <path d={`M1116 374Q1114 ${395 + detach * 20} 1120 ${dropY - 56}Q1126 ${395 + detach * 20} 1124 374`} fill={C.amber} opacity={1 - detach}/>
        <Droplet x={1120} y={dropY} id="act1"/>
        <PetriDish/>
        <g stroke={C.amber} strokeOpacity=".35" fill="none">
          <path d="M1465 384H1485 M1475 384V817 M1465 817H1485"/>
          {Array.from({length: 13}, (_, i) => <path key={i} d={`M1475 ${384 + i * 36}h${i % 3 === 0 ? 14 : 7}`}/>)}
        </g>
        <text x="1510" y="606" fill={C.amber} fontSize="18" fontFamily={FONT} opacity={1 - overlayAlpha}>120 mm</text>
        <text x="1120" y="905" textAnchor="middle" fill={C.muted} fontSize="12" letterSpacing="3" fontFamily={FONT} opacity={1 - overlayAlpha}>HUMAN LABORATORY / OBSERVER FRAME</text>
      </g></g>
      <g opacity={labOpacity * blink * 0.65} fill={C.bg}>
        <path d={`M0 194H1920V${235 + 195 * blink}Q960 ${95 + 190 * blink} 0 ${235 + 195 * blink}Z`}/>
        <path d={`M0 938H1920V${920 - 105 * blink}Q960 ${1040 - 100 * blink} 0 ${920 - 105 * blink}Z`}/>
      </g>
      <g opacity={digital} clipPath="url(#act1-circuit-clip)">
        <ellipse cx="1140" cy="550" rx="900" ry="540" fill="url(#fiber-halo)"/>
        {CIRCUITS.map(({i, y, bend, shift}) => {
          const t = ((frame * (9 + i % 5) + seeded(i + 21) * 2200) % 2200) / 2200;
          const x = -100 + t * 2150;
          const pulseY = x < bend ? y : x > bend + 90 ? y + shift : y + shift * (x - bend) / 90;
          return <g key={i}>
            <path d={`M-100 ${y}H${bend}L${bend + 90} ${y + shift}H2020`} fill="none" stroke={C.cyan} strokeOpacity={i % 4 === 0 ? 0.4 : 0.13} strokeWidth={i % 4 === 0 ? 2 : 1}/>
            <circle cx={bend} cy={y} r="3" fill={C.cyan} opacity=".55"/>
            <path d={`M${x - 34} ${pulseY}h34`} stroke={C.cyan} strokeWidth="6" opacity=".15"/>
            <circle cx={x} cy={pulseY} r={i % 3 === 0 ? 3 : 2} fill={C.white}/>
          </g>;
        })}
        {Array.from({length: 15}, (_, i) => <path key={i} d={`M${720 + i * 76} 205V914`} stroke={C.cyan} strokeOpacity=".06"/>)}
        <circle cx="1120" cy="520" r={105 + Math.sin(frame / 30) * 5} fill={C.bg} stroke={C.cyan} strokeWidth="1.5"/>
        <circle cx="1120" cy="520" r="83" fill="none" stroke={C.cyan} strokeOpacity=".3" strokeDasharray="4 10" transform={`rotate(${frame * .6} 1120 520)`}/>
        <text x="1120" y="514" textAnchor="middle" fill={C.white} fontFamily={FONT} fontSize="32" opacity={1 - overlayAlpha}>10¹⁰</text>
        <text x="1120" y="544" textAnchor="middle" fill={C.cyan} fontFamily={FONT} fontSize="11" letterSpacing="2" opacity={1 - overlayAlpha}>COGNITIVE STEPS</text>
      </g>
    </svg>
    <div style={{opacity: 1 - overlayAlpha}}><ActLabel number="01" title="An instant. An eternity." kicker="SPEED / TWO CLOCKS" color={frame < 1150 ? C.amber : C.cyan}/></div>
    <div style={{position: 'absolute', left: 94, top: 403, width: 750, opacity: oldTitleOpacity * (1 - overlayAlpha)}}>
      <div style={{fontSize: 67, lineHeight: 1.13, letterSpacing: -3, fontWeight: 600}}>HALF A SECOND.<br/><span style={{color: C.amber}}>TEN MILLENNIA.</span></div>
      <div style={{marginTop: 33, width: 60, height: 2, backgroundColor: C.amber}}/>
      <div style={{fontSize: 14, color: C.muted, marginTop: 20, letterSpacing: 2}}>THE DROPLET HAS BARELY MOVED.</div>
    </div>
    <div style={{position: 'absolute', left: 94, top: 423, width: 770, opacity: titleSwap * (1 - overlayAlpha), background: 'linear-gradient(90deg,rgba(5,8,17,.9),transparent)', paddingBottom: 30}}>
      <div style={{fontSize: 66, lineHeight: 1.18, letterSpacing: -2.7, fontWeight: 500}}>Thought moves<br/>at another <span style={{color: C.cyan}}>scale.</span></div>
      <div style={{fontSize: 15, color: C.muted, marginTop: 32, letterSpacing: 2}}>THE PHYSICAL WORLD WAITS.</div>
      <div style={{display: 'flex', gap: 35, marginTop: 52, alignItems: 'baseline'}}>
        <span style={{fontSize: 45, color: C.cyan}}>2 × 10¹⁰</span><span style={{fontSize: 13, color: C.muted}}>STEPS / PHYSICAL SECOND</span>
      </div>
    </div>
    <div style={{position: 'absolute', left: 0, right: 0, top: 205, bottom: 143, backgroundColor: C.bg, opacity: overlayAlpha * 0.78, pointerEvents: 'none'}}/>
    <div style={{position: 'absolute', left: 240, right: 240, top: 330, height: 420, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', opacity: overlayAlpha, pointerEvents: 'none'}}>
      <div style={{fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif', fontSize: 88, fontWeight: 300, color: '#fff', textShadow: '0 0 30px rgba(6,182,212,0.5)', letterSpacing: chineseLetterSpacing, lineHeight: 1.25, whiteSpace: 'pre'}}>
        {'一 眼 万 年'}
      </div>
      <div style={{marginTop: 30, fontSize: 20, color: '#06b6d4', letterSpacing: '0.4em', whiteSpace: 'pre', fontFamily: FONT}}>
        {'O N E   B L I N K ,   T E N   M I L L E N N I A'}
      </div>
      <div style={{marginTop: 26, fontSize: 17, color: C.amber, fontFamily: 'monospace', letterSpacing: '0.04em', whiteSpace: 'pre'}}>
        {'[ Δt_atom = 0.30s  |  Δt_bit = 10^4 Years ]'}
      </div>
    </div>
  </AbsoluteFill>;
};
