import React from 'react';
import {Composition} from 'remotion';
import {MainComposition} from './MainComposition';
import {PortraitComposition} from './portrait/PortraitComposition';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="OneBlinkTenMillenniaPortraitV4" component={PortraitComposition} durationInFrames={10800} fps={60} width={1080} height={1920}/>
    <Composition
      id="OneBlinkTenMillennia"
      component={MainComposition}
      durationInFrames={10800}
      fps={60}
      width={1920}
      height={1080}
    />
    <Composition
      id="OneBlinkTenMillenniaVoicedV3"
      component={MainComposition}
      durationInFrames={10800}
      fps={60}
      width={1920}
      height={1080}
      defaultProps={{withAudio: true}}
    />
  </>
);
