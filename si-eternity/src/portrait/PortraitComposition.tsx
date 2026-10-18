import React from 'react';
import {AbsoluteFill, Series, useCurrentFrame} from 'remotion';
import {C, FONT} from '../lib/theme';
import {Soundtrack} from '../components/Soundtrack';
import {PortraitHUD} from './PortraitHUD';
import {Act1Portrait} from './Act1Portrait';
import {Act2Portrait} from './Act2Portrait';
import {Act3Portrait} from './Act3Portrait';
import {Act4Portrait} from './Act4Portrait';

export const PortraitComposition: React.FC = () => {
  const frame = useCurrentFrame();
  const boundary = [1800, 4500, 7200].find((f) => Math.abs(f - frame) < 16);
  const shutter = boundary === undefined ? 0 : 0.7 * (1 - Math.abs(frame - boundary) / 16);
  return <AbsoluteFill style={{backgroundColor: C.bg, color: C.white, fontFamily: FONT, overflow: 'hidden'}}>
    <AbsoluteFill style={{backgroundImage: 'linear-gradient(rgba(148,184,211,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(148,184,211,.025) 1px,transparent 1px)', backgroundSize: '60px 60px'}}/>
    <Series>
      <Series.Sequence durationInFrames={1800}><Act1Portrait/></Series.Sequence>
      <Series.Sequence durationInFrames={2700}><Act2Portrait/></Series.Sequence>
      <Series.Sequence durationInFrames={2700}><Act3Portrait/></Series.Sequence>
      <Series.Sequence durationInFrames={3600}><Act4Portrait/></Series.Sequence>
    </Series>
    <AbsoluteFill style={{backgroundColor: C.bg, opacity: shutter, zIndex: 20, pointerEvents: 'none'}}/>
    <PortraitHUD/>
    <Soundtrack/>
  </AbsoluteFill>;
};
