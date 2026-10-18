import React from 'react';
import {Composition} from 'remotion';
import {LantingFilm} from './LantingFilm';
import timeline from './timeline.json';
import {MuseumFilm} from './museum/MuseumFilm';
import museumTimeline from './museum/timeline.json';
import {ExtendedFilm} from './extended/ExtendedFilm';
import extendedTimeline from './extended/timeline.json';
import {MadmanFilm} from './madman/MadmanFilm';
import madmanTimeline from './madman/timeline.json';
import {MadmanVoicedFilm} from './madman/MadmanVoicedFilm';
import voicedTimeline from './madman/voiced-timeline.json';
import {MadmanHistoryStudy} from './madman/MadmanHistoryStudy';
import historyStudy from './madman/history-study-v3.json';
import {MadmanEnhancedFilm} from './madman/MadmanEnhancedFilm';
import fullV4Timeline from './madman/full-v4-timeline.json';
import {MadmanSuspenseFilm} from './madman/MadmanSuspenseFilm';
import suspenseV5Timeline from './madman/suspense-v5-timeline.json';

export const RemotionRoot: React.FC = () => (
  <>
  <Composition
    id="Lanting"
    component={LantingFilm}
    width={1920}
    height={1080}
    fps={24}
    durationInFrames={timeline.durationInFrames}
  />
  <Composition id="LantingMuseum" component={MuseumFilm} width={1920} height={1080} fps={24} durationInFrames={museumTimeline.durationInFrames} />
  <Composition id="LantingMuseum4K" component={MuseumFilm} width={3840} height={2160} fps={24} durationInFrames={museumTimeline.durationInFrames} />
  <Composition id="LantingExtended" component={ExtendedFilm} width={1920} height={1080} fps={24} durationInFrames={extendedTimeline.durationInFrames} />
  <Composition id="LantingExtended4K" component={ExtendedFilm} width={3840} height={2160} fps={24} durationInFrames={extendedTimeline.durationInFrames} />
  <Composition id="MadmanDiary" component={MadmanFilm} width={1920} height={1080} fps={24} durationInFrames={madmanTimeline.durationInFrames} />
  <Composition id="MadmanDiaryVoiced" component={MadmanVoicedFilm} width={1920} height={1080} fps={24} durationInFrames={voicedTimeline.durationInFrames} />
  <Composition id="MadmanHistoryStudy" component={MadmanHistoryStudy} width={historyStudy.width} height={historyStudy.height} fps={historyStudy.fps} durationInFrames={historyStudy.durationInFrames} />
  <Composition id="MadmanDiaryEnhanced" component={MadmanEnhancedFilm} width={fullV4Timeline.width} height={fullV4Timeline.height} fps={fullV4Timeline.fps} durationInFrames={fullV4Timeline.durationInFrames} />
  <Composition id="MadmanDiarySuspense" component={MadmanSuspenseFilm} width={suspenseV5Timeline.width} height={suspenseV5Timeline.height} fps={suspenseV5Timeline.fps} durationInFrames={suspenseV5Timeline.durationInFrames} />
  </>
);
