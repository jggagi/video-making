import React from 'react';
import {AbsoluteFill, Audio, Series, staticFile, useCurrentFrame} from 'remotion';
import {GlobalHUD} from './components/GlobalHUD';
import {Act1BiologicalOverload} from './components/Act1BiologicalOverload';
import {Act2LinearVsMatrix} from './components/Act2LinearVsMatrix';
import {Act3DeepCoTManifold} from './components/Act3DeepCoTManifold';
import {Act4OracleProjection} from './components/Act4OracleProjection';
import {Backdrop} from './components/Visuals';
import {C, CN, RENDER_SCALE, SCENE_HEIGHT, SCENE_WIDTH} from './lib/theme';
import timeline from '../timeline.json';

export const MainComposition: React.FC<{withAudio: boolean; audioEdition?: 'score' | 'voiced'}> = ({withAudio, audioEdition = 'score'}) => {
  const frame = useCurrentFrame();
  const boundary = timeline.actStarts.slice(1).find((n) => Math.abs(n - frame) < 12);
  const shutter = boundary === undefined ? 0 : 0.65 * (1 - Math.abs(frame - boundary) / 12);
  return <AbsoluteFill style={{backgroundColor: C.bg, color: C.white, fontFamily: CN, overflow: 'hidden'}}>
    <div data-scene-canvas="uhd-vector" data-render-scale={RENDER_SCALE} lang="zh-CN" style={{position: 'absolute', left: 0, top: 0, width: SCENE_WIDTH, height: SCENE_HEIGHT, transform: `scale(${RENDER_SCALE})`, transformOrigin: '0 0', overflow: 'hidden'}}>
      <Backdrop/>
      <Series>
        <Series.Sequence durationInFrames={timeline.actDurations[0]}><Act1BiologicalOverload/></Series.Sequence>
        <Series.Sequence durationInFrames={timeline.actDurations[1]}><Act2LinearVsMatrix/></Series.Sequence>
        <Series.Sequence durationInFrames={timeline.actDurations[2]}><Act3DeepCoTManifold/></Series.Sequence>
        <Series.Sequence durationInFrames={timeline.actDurations[3]}><Act4OracleProjection/></Series.Sequence>
      </Series>
      <AbsoluteFill style={{backgroundColor: C.bg, opacity: shutter, zIndex: 10, pointerEvents: 'none'}}/>
      <GlobalHUD/>
    </div>
    {withAudio ? <Audio src={staticFile(audioEdition === 'voiced' ? 'audio-voiced-v2/soundtrack.wav' : 'audio/soundtrack.wav')}/> : null}
  </AbsoluteFill>;
};
