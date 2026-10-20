import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {CoverA, CoverB} from './Covers';

const CoverRoot: React.FC = () => (
  <>
    <Composition
      id="cover-A"
      component={CoverA}
      width={1536}
      height={2048}
      fps={1}
      durationInFrames={1}
    />
    <Composition
      id="cover-B"
      component={CoverB}
      width={1536}
      height={2048}
      fps={1}
      durationInFrames={1}
    />
  </>
);

registerRoot(CoverRoot);
