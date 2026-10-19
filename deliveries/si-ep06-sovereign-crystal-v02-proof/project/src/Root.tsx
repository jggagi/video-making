import React from 'react';
import {Composition} from 'remotion';
import {VisualProof} from './VisualProof';

export const Root: React.FC = () => <>
  <Composition id="CoffeeStill" component={VisualProof} width={3840} height={2160} fps={60} durationInFrames={1} defaultProps={{scene:'coffee',still:true}} />
  <Composition id="ChoiceStill" component={VisualProof} width={3840} height={2160} fps={60} durationInFrames={1} defaultProps={{scene:'choice',still:true}} />
  <Composition id="CrystalStill" component={VisualProof} width={3840} height={2160} fps={60} durationInFrames={1} defaultProps={{scene:'crystal',still:true}} />
  <Composition id="CrystalProof" component={VisualProof} width={1920} height={1080} fps={60} durationInFrames={720} defaultProps={{scene:'crystal',still:false}} />
</>;
