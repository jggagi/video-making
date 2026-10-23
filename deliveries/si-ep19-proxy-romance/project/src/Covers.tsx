import React from 'react';
import { AbsoluteFill, Composition, Img, registerRoot, staticFile } from 'remotion';

export type CoverKind = 'A' | 'B';

const INK = '#07090C';
const GOLD = '#D97706';
const CHALK = '#E2E8F0';

export const Cover: React.FC<{ kind: CoverKind }> = ({ kind }) => {
  const background = kind === 'A' ? 'covers/frame-2100.png' : 'covers/frame-5040.png';

  return (
    <AbsoluteFill style={{ background: INK }}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          width: 1080,
          height: 1920,
          overflow: 'hidden',
          transform: 'scale(2)',
          transformOrigin: 'top left',
          background: INK,
          color: CHALK,
          fontFamily: '"PingFang SC", sans-serif',
        }}
      >
        <Img
          src={staticFile(background)}
          style={{ position: 'absolute', inset: 0, width: 1080, height: 1920, objectFit: 'cover' }}
        />

        {kind === 'B' && (
          <div
            aria-hidden
            style={{
              position: 'absolute',
              inset: '0 0 auto',
              height: 1000,
              background: `linear-gradient(to bottom, transparent 300px, ${INK} 410px, ${INK} 910px, transparent 950px)`,
            }}
          />
        )}

        <div
          style={{
            position: 'absolute',
            top: 350,
            left: 65,
            right: 173,
            zIndex: 2,
            fontSize: 60,
            fontWeight: 650,
            lineHeight: 1.45,
            letterSpacing: 1,
          }}
        >
          <span style={{ color: GOLD }}>我们派 AI 替身去谈恋爱，</span>
          <br />
          <span>最后却连怎么拥抱</span>
          <br />
          <span>都忘了</span>
        </div>

        <div
          aria-hidden
          style={{
            position: 'absolute',
            top: 1320,
            left: 0,
            right: 0,
            height: 600,
            background: `linear-gradient(to bottom, transparent 0, ${INK} 10px, ${INK} 100%)`,
            zIndex: 3,
          }}
        />

        <div
          style={{
            position: 'absolute',
            top: 1460,
            left: 65,
            zIndex: 4,
            color: '#A1A1AA',
            fontFamily: '"SFMono-Regular", Menlo, monospace',
            fontSize: 27,
            lineHeight: '32px',
            letterSpacing: 1.2,
          }}
        >
          一眼万年 S4 · EP19
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const RootCovers: React.FC = () => (
  <Composition
    id="CoverVertical"
    component={Cover}
    durationInFrames={1}
    fps={60}
    width={2160}
    height={3840}
    defaultProps={{ kind: 'A' }}
  />
);

registerRoot(RootCovers);
