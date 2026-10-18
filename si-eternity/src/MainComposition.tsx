import React from 'react';
import {AbsoluteFill, Series, useCurrentFrame} from 'remotion';
import {GlobalHUD} from './components/GlobalHUD';
import {Act1Speed} from './components/Act1Speed';
import {Act2BreadthMCTS} from './components/Act2BreadthMCTS';
import {Act3DepthManifold} from './components/Act3DepthManifold';
import {Act4SplitWorld} from './components/Act4SplitWorld';
import {Backdrop} from './components/Visuals';
import {Soundtrack} from './components/Soundtrack';
import {C, FONT} from './lib/theme';

export const MainComposition: React.FC<{withAudio?: boolean}> = ({withAudio = false}) => {
  const frame = useCurrentFrame();
  const boundary = [1800, 4500, 7200].find((f) => Math.abs(f - frame) < 16);
  const shutter = boundary === undefined ? 0 : 0.7 * (1 - Math.abs(frame - boundary) / 16);
  return (
    <AbsoluteFill style={{backgroundColor: C.bg, color: C.white, fontFamily: FONT, overflow: 'hidden'}}>
      <Backdrop frame={frame} accent={frame < 1100 || frame >= 7200 ? C.amber : C.cyan}/>
      <Series>
        <Series.Sequence durationInFrames={1800}><Act1Speed/></Series.Sequence>
        <Series.Sequence durationInFrames={2700}><Act2BreadthMCTS/></Series.Sequence>
        <Series.Sequence durationInFrames={2700}><Act3DepthManifold/></Series.Sequence>
        <Series.Sequence durationInFrames={3600}><Act4SplitWorld/></Series.Sequence>
      </Series>
      <AbsoluteFill style={{backgroundColor: C.bg, opacity: shutter, pointerEvents: 'none', zIndex: 10}}/>
      <GlobalHUD withAudio={withAudio}/>
      {withAudio ? <Soundtrack/> : null}
    </AbsoluteFill>
  );
};
