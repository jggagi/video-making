import React from 'react';
import {Composition} from 'remotion';
import {Film} from './Film';

export const Root: React.FC = () => (
  <Composition
    id="PortraitVertical"
    component={Film}
    width={2160}
    height={3840}
    fps={60}
    durationInFrames={7200}
    defaultProps={{silent: false, cover: false}}
  />
);
