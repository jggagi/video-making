import React from 'react';
import {Composition} from 'remotion';
import {CaptionPatch} from './CaptionPatch';
import {Film} from './Film';

export const Root: React.FC = () => <>
  <Composition id="Landscape4K" component={Film} width={3840} height={2160} fps={60} durationInFrames={7200} defaultProps={{portrait: false, silent: false}}/>
  <Composition id="PortraitVertical" component={Film} width={2160} height={3840} fps={60} durationInFrames={7200} defaultProps={{portrait: true, silent: false}}/>
  <Composition id="LandscapeCaptionPatch" component={CaptionPatch} width={3840} height={360} fps={60} durationInFrames={7200} defaultProps={{portrait: false}}/>
  <Composition id="PortraitCaptionPatch" component={CaptionPatch} width={2160} height={360} fps={60} durationInFrames={7200} defaultProps={{portrait: true}}/>
</>;
