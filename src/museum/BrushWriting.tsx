import React, {useId} from 'react';
import {staticFile} from 'remotion';
import strokeJson from './strokes.json';

type StrokeRecord = {
  strokes: string[];
  medians: number[][][];
};

type StrokeStep = {
  characterIndex: number;
  strokeIndex: number;
  outline: string;
  median: number[][];
  medianPath: string;
  medianLength: number;
  weight: number;
  start: number;
  end: number;
};

type PauseStep = {
  start: number;
  end: number;
};

type TimelineStep =
  | ({kind: 'stroke'} & StrokeStep)
  | ({kind: 'pause'} & PauseStep);

const strokeData = strokeJson as Record<string, StrokeRecord>;
const CANVAS_SIZE = 1024;
const SOURCE_HEIGHT = 900;
const MASK_WIDTH = 170;
const MIN_WEIGHT = 55;
const MAX_WEIGHT = 1800;
const BRUSH_WIDTH = 320;
const BRUSH_HEIGHT = 512;
// The brush cutout leaves a small transparent margin below its visible tip.
// Keep these ratios together so the asset anchor can be tuned from its canvas.
const BRUSH_TIP_X = 0.5;
const BRUSH_TIP_Y = 0.98;
const BRUSH_ANGLE = -24;
// Close framing lets the shaft enter from beyond the top edge on high strokes;
// the nib and every written glyph remain visible in the composition.

const polylineLength = (points: number[][]) => {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    length += Math.hypot(current[0] - previous[0], current[1] - previous[1]);
  }
  return length;
};

const pathFromMedian = (points: number[][]) =>
  points
    .map(([x, y], index) => `${index === 0 ? 'M' : 'L'} ${x} ${y}`)
    .join(' ');

const pointAtProgress = (points: number[][], progress: number) => {
  const totalLength = polylineLength(points);
  if (totalLength <= 0 || points.length === 0) {
    return [0, 0];
  }

  let remaining = Math.max(0, Math.min(1, progress)) * totalLength;
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const segmentLength = Math.hypot(
      current[0] - previous[0],
      current[1] - previous[1],
    );
    if (remaining <= segmentLength || index === points.length - 1) {
      const amount = segmentLength === 0 ? 0 : remaining / segmentLength;
      return [
        previous[0] + (current[0] - previous[0]) * amount,
        previous[1] + (current[1] - previous[1]) * amount,
      ];
    }
    remaining -= segmentLength;
  }
  return points[points.length - 1];
};

const buildTimeline = (text: string, duration: number): TimelineStep[] => {
  const characters = Array.from(text);
  const characterStrokes = characters.map((character, characterIndex) => {
    const record = strokeData[character];
    if (!record) {
      return [];
    }

    return record.strokes.map((outline, strokeIndex) => {
      const median = record.medians[strokeIndex];
      const medianLength = polylineLength(median);
      return {
        characterIndex,
        strokeIndex,
        outline,
        median,
        medianPath: pathFromMedian(median),
        medianLength,
        weight: Math.max(MIN_WEIGHT, Math.min(MAX_WEIGHT, medianLength)),
      };
    });
  });
  const nonemptyCharacters = characterStrokes
    .map((strokes, index) => (strokes.length > 0 ? index : -1))
    .filter((index) => index >= 0);
  const pauseCount = characterStrokes.reduce(
    (count, strokes) => count + Math.max(0, strokes.length - 1),
    0,
  );
  const characterPauseCount = Math.max(0, nonemptyCharacters.length - 1);
  const requestedPauseFrames = pauseCount + characterPauseCount * 2;
  const safeDuration = Math.max(0, duration);
  const pauseScale =
    requestedPauseFrames === 0
      ? 1
      : Math.min(1, safeDuration / requestedPauseFrames);
  const actualPauseFrames = requestedPauseFrames * pauseScale;
  const strokeFrames = Math.max(0, safeDuration - actualPauseFrames);
  const allStrokes = characterStrokes.flat();
  const totalWeight = allStrokes.reduce((sum, stroke) => sum + stroke.weight, 0);
  const result: TimelineStep[] = [];
  let cursor = 0;

  for (const characterIndex of nonemptyCharacters) {
    const strokes = characterStrokes[characterIndex];
    for (let index = 0; index < strokes.length; index += 1) {
      const stroke = strokes[index];
      const strokeDuration =
        totalWeight === 0 ? 0 : (strokeFrames * stroke.weight) / totalWeight;
      result.push({
        kind: 'stroke',
        ...stroke,
        start: cursor,
        end: cursor + strokeDuration,
      });
      cursor += strokeDuration;

      const isLastStroke = index === strokes.length - 1;
      const isLastCharacter =
        characterIndex === nonemptyCharacters[nonemptyCharacters.length - 1];
      if (!isLastStroke) {
        const pauseDuration = pauseScale;
        result.push({kind: 'pause', start: cursor, end: cursor + pauseDuration});
        cursor += pauseDuration;
      } else if (!isLastCharacter) {
        const pauseDuration = 2 * pauseScale;
        result.push({kind: 'pause', start: cursor, end: cursor + pauseDuration});
        cursor += pauseDuration;
      }
    }
  }

  return result;
};

export const BrushWriting: React.FC<{
  text: string;
  frame: number;
  duration: number;
  x?: number;
  y?: number;
  size?: number;
  gap?: number;
  color?: string;
  showBrush?: boolean;
  vertical?: boolean;
}> = ({
  text,
  frame,
  duration,
  x = 350,
  y = 340,
  size = 240,
  gap = 25,
  color = '#242925',
  showBrush = true,
  vertical = false,
}) => {
  const reactId = useId();
  const componentId = reactId.replace(/[^A-Za-z0-9_-]/g, '') || 'brush-writing';
  const timeline = buildTimeline(text, duration);
  const complete = duration <= 0 ? frame > 0 : frame >= duration;
  const activeStep = showBrush && !complete && frame > 0
    ? timeline.filter(
        (step): step is Extract<TimelineStep, {kind: 'stroke'}> =>
          step.kind === 'stroke' && frame >= step.start,
      ).at(-1)
    : undefined;
  const activeBrush = activeStep
    ? (() => {
        const point = pointAtProgress(
          activeStep.median,
          (frame - activeStep.start) /
            Math.max(0.001, activeStep.end - activeStep.start),
        );
        const originX = vertical
          ? x
          : x + activeStep.characterIndex * (size + gap);
        const originY = vertical
          ? y + activeStep.characterIndex * (size + gap)
          : y;
        const scale = size / CANVAS_SIZE;
        return {
          tipX: originX + point[0] * scale,
          tipY: originY + (SOURCE_HEIGHT - point[1]) * scale,
          opacity: Math.min(1, Math.max(0, (duration - frame) / 8)),
        };
      })()
    : null;

  const visibleStrokes = timeline.flatMap((step) => {
    if (step.kind !== 'stroke') {
      return [];
    }
    if (frame <= 0 || frame < step.start) {
      return [];
    }

    const isComplete = complete || frame >= step.end;
    const isActive = !complete && frame >= step.start && frame < step.end;
    const progress = isComplete
      ? 1
      : isActive
        ? Math.max(0, Math.min(1, (frame - step.start) / Math.max(0.001, step.end - step.start)))
        : 0;
    const scale = size / CANVAS_SIZE;
    const glyphX = vertical
      ? x
      : x + step.characterIndex * (size + gap);
    const glyphY = vertical
      ? y + step.characterIndex * (size + gap)
      : y;
    const maskId = `${componentId}-c${step.characterIndex}-s${step.strokeIndex}`;

    return [
      <g
        key={`c${step.characterIndex}-s${step.strokeIndex}`}
        transform={`translate(${glyphX}, ${glyphY + (size * SOURCE_HEIGHT) / CANVAS_SIZE}) scale(${scale}, ${-scale})`}
      >
        {isComplete ? null : (
          <defs>
            <mask
              id={maskId}
              x={-MASK_WIDTH}
              y={-MASK_WIDTH}
              width={CANVAS_SIZE + MASK_WIDTH * 2}
              height={SOURCE_HEIGHT + MASK_WIDTH * 2}
              maskUnits="userSpaceOnUse"
              maskContentUnits="userSpaceOnUse"
            >
              <path
                d={step.medianPath}
                fill="none"
                stroke="white"
                strokeWidth={MASK_WIDTH}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={step.medianLength}
                strokeDashoffset={step.medianLength * (1 - progress)}
              />
            </mask>
          </defs>
        )}
        <path
          d={step.outline}
          fill={color}
          mask={isComplete ? undefined : `url(#${maskId})`}
        />
      </g>,
    ];
  });

  return (
    <svg
      width={1920}
      height={1080}
      viewBox="0 0 1920 1080"
      aria-hidden="true"
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'visible',
        pointerEvents: 'none',
      }}
    >
      {visibleStrokes}
      {activeBrush && activeBrush.opacity > 0 ? (
        <image
          href={staticFile('museum/brush.png')}
          x={activeBrush.tipX - BRUSH_WIDTH * BRUSH_TIP_X}
          y={activeBrush.tipY - BRUSH_HEIGHT * BRUSH_TIP_Y}
          width={BRUSH_WIDTH}
          height={BRUSH_HEIGHT}
          preserveAspectRatio="xMidYMid meet"
          transform={`rotate(${BRUSH_ANGLE}, ${activeBrush.tipX}, ${activeBrush.tipY})`}
          opacity={activeBrush.opacity}
        />
      ) : null}
    </svg>
  );
};
