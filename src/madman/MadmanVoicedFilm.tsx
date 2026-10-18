import React from 'react';
import {MadmanFilm} from './MadmanFilm';
import voicedTimeline from './voiced-timeline.json';

export const MadmanVoicedFilm: React.FC = () => <MadmanFilm
  timelineData={voicedTimeline}
  audioSrc="madman/audio/voiced-v2.wav"
  voiced
/>;
