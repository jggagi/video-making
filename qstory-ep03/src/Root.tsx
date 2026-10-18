import React from 'react';
import {Composition} from 'remotion';
import {Film} from './Film';
export const Root: React.FC = () => <>
  <Composition id="QStory-EP03-4K" component={Film} width={3840} height={2160} fps={30} durationInFrames={5400}/>
  <Composition id="QStory-EP03-Preview" component={Film} width={1920} height={1080} fps={30} durationInFrames={5400}/>
</>;
