export type Cue = {text: string; from: number; duration: number};
export type Shot = {
  id: string;
  kind: 'title' | 'scene' | 'end';
  from: number;
  duration: number;
  image: 'landscape' | 'gathering' | 'stream' | 'study';
  chapter: string;
  hero: string[];
  mood: 'joy' | 'turn' | 'reflect';
  text: string;
  narration?: string;
  audio?: string;
  audioOffset?: number;
  cues: Cue[];
};
export type Timeline = {fps: number; durationInFrames: number; shots: Shot[]};
