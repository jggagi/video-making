import React from 'react';
import {Audio, staticFile} from 'remotion';

/** The locally prepared, full-length mixed soundtrack for the voiced edition. */
export const Soundtrack: React.FC = () => (
  <Audio src={staticFile('audio-v3/soundtrack.wav')} />
);
