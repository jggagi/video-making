import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C} from '../lib/theme';
import {ease, mix} from '../lib/math';
import {DigitalField, GearMechanism, Laboratory} from '../components/Act4SplitWorld';
import {
  PortraitEndingTitle,
  PortraitHeading,
  PortraitPanel,
  PORTRAIT_FONT,
} from './PortraitElements';

const DigitalPanel: React.FC<{frame: number}> = ({frame}) => <PortraitPanel top={500} height={370} accent={C.cyan}>
  <svg width="100%" height="100%" viewBox="0 420 960 520" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
    <DigitalField frame={frame} />
  </svg>
</PortraitPanel>;

const MechanicalPanel: React.FC<{frame: number}> = ({frame}) => <PortraitPanel top={946} height={400} accent={C.amber}>
  <svg width="100%" height="100%" viewBox="960 310 880 630" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
    <GearMechanism frame={frame} />
  </svg>
</PortraitPanel>;

/** A scene-local iris that closes during the transition, then retracts before impact. */
const LaboratoryEyelid: React.FC<{frame: number}> = ({frame}) => {
  if (frame < 1900 || frame >= 2400) return null;

  const closed = frame < 2100
    ? ease(frame, 1900, 2100)
    : 1 - ease(frame, 2100, 2400);
  const upperEdge = mix(205, 572, closed);
  const lowerEdge = mix(940, 572, closed);

  return <svg
    width="100%"
    height="100%"
    viewBox="660 205 920 735"
    preserveAspectRatio="xMidYMid meet"
    style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}
    aria-hidden="true"
  >
    <path
      d={`M660 205H1580V${upperEdge} Q1120 ${upperEdge + 16} 660 ${upperEdge}Z`}
      fill={C.bg}
      stroke={C.cyan}
      strokeOpacity="0.22"
      strokeWidth="1.5"
    />
    <path
      d={`M660 940H1580V${lowerEdge} Q1120 ${lowerEdge - 16} 660 ${lowerEdge}Z`}
      fill={C.bg}
      stroke={C.cyan}
      strokeOpacity="0.22"
      strokeWidth="1.5"
    />
  </svg>;
};

const LaboratoryPanel: React.FC<{frame: number}> = ({frame}) => <PortraitPanel top={470} height={900} accent={C.cyan}>
  <svg width="100%" height="100%" viewBox="660 205 920 735" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
    <Laboratory frame={frame} opacity={1} />
  </svg>
  <LaboratoryEyelid frame={frame} />
</PortraitPanel>;

export const Act4Portrait: React.FC = () => {
  const frame = Math.max(0, Math.min(3599, useCurrentFrame()));
  const splitOpacity = 1 - ease(frame, 1900, 2100);
  const labOpacity = ease(frame, 1900, 2100);
  const fadeToVoid = ease(frame, 3280, 3300);
  const headingTitle = frame < 2100 ? '比特飞驰，原子等待' : '现实接住答案';
  const sceneStatus = frame < 2400 ? '等待原子移动' : '唯一的一击·新的秩序';

  return <div className="portrait-v4-reused-scene" style={{position: 'absolute', inset: 0, width: 1080, height: 1920, overflow: 'hidden', pointerEvents: 'none'}}>
    <style>{'.portrait-v4-reused-scene svg text { display: none; }'}</style>
    <PortraitHeading
      index="04"
      title={headingTitle}
      kicker="BITS / ATOMS"
      opacity={1 - fadeToVoid}
    />

    {frame < 2100 && <div style={{position: 'absolute', inset: 0, opacity: splitOpacity}}>
      <div style={{position: 'absolute', left: 80, top: 454, width: 880, color: C.cyan, fontFamily: PORTRAIT_FONT, fontSize: 28, lineHeight: '34px', letterSpacing: 1}}>
        <span>比特</span><span style={{opacity: 0.42, padding: '0 14px'}}> / </span><span style={{fontSize: 22}}>状态飞速改写</span>
      </div>
      <DigitalPanel frame={frame} />

      <div style={{position: 'absolute', left: 80, top: 900, width: 880, color: C.amber, fontFamily: PORTRAIT_FONT, fontSize: 28, lineHeight: '34px', letterSpacing: 1}}>
        <span>原子</span><span style={{opacity: 0.42, padding: '0 14px'}}> / </span><span style={{fontSize: 22}}>惯性仍在</span>
      </div>
      <MechanicalPanel frame={frame} />
    </div>}

    {frame >= 1900 && <div style={{position: 'absolute', inset: 0, opacity: labOpacity}}>
      <LaboratoryPanel frame={frame} />
      <div style={{position: 'absolute', left: 80, top: 1384, width: 880, textAlign: 'center', color: frame < 2400 ? C.cyan : C.gold, fontFamily: PORTRAIT_FONT, fontSize: 32, lineHeight: '42px', letterSpacing: 2}}>
        {sceneStatus}
      </div>
    </div>}

    {fadeToVoid > 0 && <div style={{position: 'absolute', inset: 0, backgroundColor: C.bg, opacity: fadeToVoid}} />}
    {frame >= 3300 && <PortraitEndingTitle frame={frame} />}
  </div>;
};
