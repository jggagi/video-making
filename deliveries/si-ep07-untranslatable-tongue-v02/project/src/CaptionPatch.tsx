import React from 'react';
import {AbsoluteFill, useVideoConfig} from 'remotion';
import {Film} from './Film';

type CaptionPatchProps = {portrait?: boolean};

/**
 * Render the complete native Film into its original coordinate space, then
 * expose only the unchanged subtitle band through a 360px-high composition.
 * The wrapper deliberately keeps the full native dimensions: Film derives its
 * logical scale from the composition width, and CanvasWorld's SVG uses 100%
 * sizing against this full-size box.
 */
export const CaptionPatch: React.FC<CaptionPatchProps> = ({portrait = false}) => {
  const {width, height} = useVideoConfig();
  const sourceHeight = portrait ? 3840 : 2160;
  const sourceTop = portrait ? 2700 : 1800;

  if (height !== 360 || width !== (portrait ? 2160 : 3840)) {
    throw new Error(`CaptionPatch requires ${portrait ? '2160' : '3840'}x360 composition; got ${width}x${height}`);
  }

  return <AbsoluteFill style={{overflow: 'hidden'}}>
    <div style={{position: 'absolute', left: 0, top: -sourceTop, width, height: sourceHeight, overflow: 'visible'}}>
      <Film portrait={portrait} silent/>
    </div>
  </AbsoluteFill>;
};
