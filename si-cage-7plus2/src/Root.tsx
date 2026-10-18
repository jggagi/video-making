import React from 'react';
import {Composition} from 'remotion';
import {MainComposition} from './MainComposition';
import timeline from '../timeline.json';
import portrait from '../xhs-timeline.json';
import {MainPortrait} from './xhs/MainPortrait';
import {XHSCover} from './xhs/XHSCover';
export const RemotionRoot: React.FC = () => <>
  <Composition id="CageOfSevenPlusTwoXhsV1" component={MainPortrait} durationInFrames={portrait.durationInFrames} fps={portrait.fps} width={portrait.width} height={portrait.height} defaultProps={{withAudio: true}}/>
  <Composition id="CageOfSevenPlusTwoXhsSilent" component={MainPortrait} durationInFrames={portrait.durationInFrames} fps={portrait.fps} width={portrait.width} height={portrait.height} defaultProps={{withAudio: false}}/>
  <Composition id="CageOfSevenPlusTwoXhsCover" component={XHSCover} durationInFrames={1} fps={60} width={2160} height={2880}/>
  <Composition id="CageOfSevenPlusTwoUhdV3" component={MainComposition} durationInFrames={timeline.durationInFrames} fps={timeline.fps} width={3840} height={2160} defaultProps={{withAudio: true, audioEdition: 'voiced' as const}}/>
  <Composition id="CageOfSevenPlusTwo" component={MainComposition} durationInFrames={timeline.durationInFrames} fps={timeline.fps} width={timeline.width} height={timeline.height} defaultProps={{withAudio: true}}/>
  <Composition id="CageOfSevenPlusTwoSilent" component={MainComposition} durationInFrames={timeline.durationInFrames} fps={timeline.fps} width={timeline.width} height={timeline.height} defaultProps={{withAudio: false}}/>
  <Composition id="CageOfSevenPlusTwoVoicedV2" component={MainComposition} durationInFrames={timeline.durationInFrames} fps={timeline.fps} width={timeline.width} height={timeline.height} defaultProps={{withAudio: true, audioEdition: 'voiced' as const}}/>
</>;
