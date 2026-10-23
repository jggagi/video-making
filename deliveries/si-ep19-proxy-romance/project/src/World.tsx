import * as React from "react";

const GOLD = "#D97706";
const SILVER = "#E2E8F0";
const INK = "#18181B";
const INK_LIGHT = "#3F3F46";
const VOID = "#07090C";

const clamp = (value: number, low = 0, high = 1): number =>
  Math.min(high, Math.max(low, value));
const mix = (a: number, b: number, amount: number): number =>
  a + (b - a) * amount;
const smooth = (value: number): number => {
  const t = clamp(value);
  return t * t * (3 - 2 * t);
};
const wave = (frame: number, rate: number, phase = 0): number =>
  Math.sin(frame * rate + phase);

type SeatedPersonProps = {
  x: number;
  y: number;
  mirror: 1 | -1;
  stroke: string;
  opacity: number;
  breath?: number;
  hand?: number;
  lineWidth?: number;
};

function SeatedPerson({
  x,
  y,
  mirror,
  stroke,
  opacity,
  breath = 0,
  hand = 0,
  lineWidth = 0.75,
}: SeatedPersonProps) {
  return (
    <g
      transform={`translate(${x} ${y + breath}) scale(${mirror} 1)`}
      fill="none"
      stroke={stroke}
      strokeWidth={lineWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      opacity={opacity}
    >
      {/* A quiet profile, shoulder, and curved seated spine. */}
      <ellipse cx="13" cy="-294" rx="26" ry="35" />
      <path d="M 34 -300 Q 42 -295 38 -287 Q 34 -283 41 -279 Q 35 -272 30 -270" />
      <path d="M -7 -260 Q -13 -249 -14 -237" />
      <path d="M 25 -260 Q 34 -251 35 -238" />
      <path d="M -12 -251 C -31 -231 -40 -206 -43 -177 Q -47 -146 -26 -125 Q -7 -105 22 -106" />
      <path d="M 30 -250 C 47 -227 49 -203 41 -180 Q 34 -159 51 -137" />
      <path d="M -31 -218 Q -8 -230 21 -218 Q 37 -212 44 -198" />
      <path d="M -35 -181 Q -8 -167 34 -176" opacity="0.62" />
      <path d="M -30 -128 Q -4 -140 24 -125" opacity="0.64" />

      {/* Bent legs and soft, grounded feet keep the pose readable as seated. */}
      <path d="M -25 -119 Q -5 -105 24 -105 Q 53 -102 67 -83 Q 77 -69 62 -57 Q 48 -47 23 -56 L -14 -71" />
      <path d="M -25 -116 Q -52 -112 -80 -91 Q -104 -74 -99 -58 Q -94 -45 -76 -51 L -46 -70" />
      <path d="M 62 -59 Q 68 -36 83 -15 Q 94 -5 119 -8 Q 126 -9 126 -3 Q 124 3 112 4 L 78 2 Q 65 1 61 -11 L 41 -58" />
      <path d="M -77 -51 Q -89 -31 -94 -9 Q -98 1 -119 3 Q -127 4 -125 10 Q -122 15 -108 14 L -78 12 Q -67 10 -64 0 L -48 -48" />
      <path d="M -11 -70 Q 15 -75 37 -63" opacity="0.6" />

      {/* Two bent arms meet around a small device; the hand has a live micro-shift. */}
      <g transform={`translate(0 ${hand})`}>
        <path d="M -29 -218 Q -7 -221 9 -200 L 20 -178 Q 22 -171 16 -168 L 8 -170" />
        <path d="M 8 -218 Q 29 -215 42 -198 L 26 -178 Q 20 -171 13 -174" />
        <path d="M 13 -177 L 20 -171 M 8 -173 L 16 -167" />
        <rect x="5" y="-198" width="23" height="34" rx="3" />
        <path d="M 10 -192 L 23 -192 M 14 -169 L 19 -169" strokeWidth={lineWidth * 0.65} />
      </g>

      {/* A few fine seams make the figure feel drawn rather than diagrammatic. */}
      <path d="M -20 -205 Q -7 -190 -5 -177" opacity="0.5" />
      <path d="M -55 -101 Q -61 -88 -62 -77" opacity="0.42" />
    </g>
  );
}

type DancerProps = {
  x: number;
  y: number;
  tone: string;
  echo: string;
  opacity: number;
  mirror?: 1 | -1;
  lean?: number;
  twitch?: number;
  fine?: boolean;
};

function Dancer({
  x,
  y,
  tone,
  echo,
  opacity,
  mirror = 1,
  lean = 0,
  twitch = 0,
  fine = true,
}: DancerProps) {
  const outline =
    "M -10 62 C -30 83 -34 111 -29 141 Q -22 172 -29 198 Q -32 211 -19 219 Q -1 227 17 216 Q 31 206 27 189 Q 20 157 30 133 Q 40 105 13 76";
  const arms =
    "M -8 83 C 15 91 34 113 57 128 Q 73 137 84 124 Q 91 115 78 105 L 48 84 Q 34 75 19 77 M 4 87 C 27 105 44 130 66 153 Q 78 165 89 153 Q 95 145 83 135 L 53 112";
  const legs =
    "M -21 211 Q -44 238 -48 267 Q -52 290 -77 308 Q -87 319 -77 325 Q -65 330 -49 320 L -10 300 Q 3 289 1 269 L 6 224 M 12 215 Q 36 238 55 264 Q 68 283 50 305 L 32 318 Q 24 326 36 328 Q 49 331 62 320 L 88 305 Q 101 290 87 265 Q 70 236 28 210";
  const torso =
    "M -12 70 Q 3 81 17 72 M -26 139 Q -2 151 29 137 M -25 183 Q -4 195 25 183 M -19 218 Q 0 227 17 216";
  const renderLines = (stroke: string, width: number, opacityScale = 1) => (
    <g
      fill="none"
      stroke={stroke}
      strokeWidth={width}
      strokeLinecap="round"
      strokeLinejoin="round"
      opacity={opacityScale}
    >
      <ellipse cx="0" cy="37" rx="24" ry="30" />
      <path d="M 21 34 Q 30 39 24 45 Q 20 48 27 52 Q 21 58 15 59" />
      <path d="M -10 63 Q -13 70 -12 78 M 10 63 Q 11 71 14 77" />
      <path d={outline} />
      <path d={arms} transform={`translate(0 ${twitch})`} />
      <path d={legs} />
      <path d={torso} />
      <path d="M -4 101 Q -19 119 -13 145 M 8 104 Q 22 119 18 137" opacity="0.65" />
      <path d="M -45 281 Q -26 284 -10 273 M 54 282 Q 72 282 85 270" opacity="0.56" />
    </g>
  );

  return (
    <g transform={`translate(${x} ${y})`} opacity={opacity}>
      <g transform={`rotate(${lean} 0 170) scale(${mirror} 1)`}>
        {fine && renderLines(echo, 2.35, 0.55)}
        {renderLines(tone, 1.05, 0.98)}
        <path
          d="M -21 92 Q -1 117 25 134"
          fill="none"
          stroke={tone}
          strokeWidth="0.7"
          strokeLinecap="round"
          opacity="0.74"
          transform={`translate(0 ${twitch})`}
        />
      </g>
    </g>
  );
}

type ThreadProps = {
  frame: number;
  amount: number;
  leftX: number;
  rightX: number;
  topY: number;
  mechanical: number;
};

function Threads({ frame, amount, leftX, rightX, topY, mechanical }: ThreadProps) {
  const strands: Array<{ from: number; to: number; color: string; phase: number }> = [
    { from: 0, to: 0, color: GOLD, phase: 0.2 },
    { from: -16, to: 18, color: SILVER, phase: 1.1 },
    { from: 22, to: -12, color: GOLD, phase: 2.3 },
    { from: 4, to: 26, color: SILVER, phase: 3.2 },
    { from: -28, to: -24, color: GOLD, phase: 4.4 },
    { from: 34, to: 5, color: SILVER, phase: 5.6 },
  ];
  const lowerY = 1201 + wave(frame, 0.017) * 2.5;

  return (
    <g fill="none" strokeLinecap="round" strokeLinejoin="round" opacity={amount}>
      {strands.map((strand, index) => {
        const sway = wave(frame, 0.025, strand.phase) * (4 + mechanical * 2);
        const startX = index % 2 === 0 ? 365 : 650;
        const endX = index % 2 === 0 ? leftX + 7 : rightX - 7;
        const startY = lowerY + strand.from * 0.35;
        const endY = topY + 126 + strand.to;
        const width = 0.52 + (0.5 + 0.5 * wave(frame, 0.031, strand.phase)) * 0.92;
        const d = `M ${startX + strand.from} ${startY} C ${startX + 112 + sway} ${startY - 105}, ${endX - 84 - sway} ${endY + 118}, ${endX + strand.to} ${endY}`;
        return (
          <g key={`strand-${index}`}>
            <path d={d} stroke={strand.color} strokeWidth={width + 0.9} opacity="0.16" />
            <path d={d} stroke={strand.color} strokeWidth={width} opacity="0.77" />
          </g>
        );
      })}

      {mechanical > 0 &&
        [
          { x: leftX - 5, y: topY + 48, lower: 1287, color: GOLD, phase: 0.6 },
          { x: rightX + 5, y: topY + 48, lower: 1280, color: SILVER, phase: 1.8 },
          { x: leftX + 57, y: topY + 157, lower: 1174, color: GOLD, phase: 2.9 },
          { x: rightX - 57, y: topY + 157, lower: 1178, color: SILVER, phase: 4.1 },
        ].map((line, index) => {
          const twitch = wave(frame, 0.14, line.phase) * (1.2 + mechanical * 2.1);
          const d = `M ${line.x + twitch} ${line.y} C ${line.x + 74} ${line.y + 120}, ${line.x - 76} ${line.lower - 92}, ${line.x + twitch * 0.4} ${line.lower}`;
          return (
            <path
              key={`control-${index}`}
              d={d}
              stroke={line.color}
              strokeWidth={0.42 + Math.abs(twitch) * 0.16}
              opacity="0.68"
            />
          );
        })}
    </g>
  );
}

export function World({ frame }: { frame: number }): React.ReactElement {
  const f = Number.isFinite(frame) ? clamp(frame, 0, 5399) : 0;
  const breath = wave(f, 0.037) * 1.25;
  const hand = wave(f, 0.061, 0.8) * 1.7;
  const ripple = wave(f, 0.019) * 1.9;
  const post = f >= 4860 ? f - 4860 : 0;
  const waterDrop = 1 - smooth(post / 180);
  const hostFlip = smooth((f - 1320) / 780);
  const hostOpacity = mix(0.94, 0.78, hostFlip);
  const hostBreath = f < 4860 ? breath * (1 - smooth((f - 4380) / 480)) : 0;
  const hostHand = f < 4860 ? hand * (1 - smooth((f - 4380) / 480)) : 0;
  const reflectedLife =
    f < 1320
      ? 0.12
      : mix(0.2, 0.43, smooth((f - 1320) / 600)) * (1 - smooth((f - 2100) / 500));

  const crossing = smooth((f - 1320) / 780);
  const settle = smooth((f - 2100) / 720);
  const riseY = mix(969, 760, crossing) - 140 * settle;
  const spiritOpacity = f < 1320 ? 0 : smooth((f - 1320) / 130);

  const embrace = smooth((f - 2820) / 780);
  const leftEmbraceX = f < 2820 ? 365 : mix(365, 490, embrace);
  const rightEmbraceX = f < 2820 ? 650 : mix(650, 590, embrace);
  const embraceY = f < 2820 ? riseY : mix(620, 603, embrace);
  const threadPull = smooth((f - 2220) / 600);
  const act4 = smooth((f - 4380) / 480);
  const mechanical = smooth((f - 3600) / 160) * (1 - smooth((f - 4380) / 160));
  const threadsVisible = f >= 2220 && f < 4860 ? 1 : 0;

  const walkLeft = leftEmbraceX - 840 * act4;
  const walkRight = rightEmbraceX + 840 * act4;
  const finalY = embraceY + wave(f, 0.09) * 1.3 * mechanical;
  const actorTwitchLeft = wave(f, 0.024, 0) * 1.2 + wave(f, 0.13, 0.4) * mechanical * 2.1;
  const actorTwitchRight = wave(f, 0.024, 1.2) * 1.2 + wave(f, 0.13, 1.8) * mechanical * 2.1;
  const reflectionLeft = f < 1320 ? INK_LIGHT : GOLD;
  const reflectionRight = f < 1320 ? INK_LIGHT : SILVER;
  const lineWave = ripple * waterDrop;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 1080 1920"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="A quiet two dimensional theatre of people, reflections, and threads"
    >
      <rect x="0" y="0" width="1080" height="1920" fill={VOID} />

      {/* The exact horizon stays still while a second, faint waterline breathes around it. */}
      <path d="M 92 960 H 900" fill="none" stroke={GOLD} strokeWidth="0.5" opacity="0.88" />
      <path
        d={`M 104 ${963 + lineWave} C 258 ${961 - lineWave}, 394 ${965 + lineWave}, 536 ${962} S 779 ${964 - lineWave}, 896 ${962 + lineWave}`}
        fill="none"
        stroke={GOLD}
        strokeWidth="0.55"
        opacity={0.22 + 0.12 * Math.abs(wave(f, 0.019))}
      />

      {/* Faint inverted copies sit directly beneath the horizon. */}
      <g transform="translate(0 1920) scale(1 -1)">
        <SeatedPerson x={365} y={930} mirror={-1} stroke={reflectionLeft} opacity={reflectedLife} breath={breath * 0.35} hand={hand * 0.3} lineWidth={0.75} />
        <SeatedPerson x={650} y={930} mirror={1} stroke={reflectionRight} opacity={reflectedLife * 0.84} breath={breath * 0.35} hand={hand * 0.3} lineWidth={0.75} />
      </g>

      {/* Original hosts fade and pass through a pure 2D vertical inversion below the horizon. */}
      <g transform={`translate(0 ${1920 * hostFlip}) scale(1 ${1 - 2 * hostFlip})`} opacity={hostOpacity}>
        <SeatedPerson x={365} y={930} mirror={-1} stroke={INK_LIGHT} opacity={1} breath={hostBreath} hand={hostHand} lineWidth={0.75} />
        <SeatedPerson x={650} y={930} mirror={1} stroke={INK_LIGHT} opacity={0.92} breath={hostBreath * 0.8} hand={-hostHand * 0.85} lineWidth={0.75} />
      </g>

      {/* The rising double-images cross the horizon in two-dimensional space. */}
      {f >= 1320 && f < 2820 && (
        <g>
          <Dancer x={365} y={riseY} tone={GOLD} echo={SILVER} opacity={spiritOpacity} mirror={1} lean={8 * embrace} twitch={actorTwitchLeft} />
          <Dancer x={650} y={riseY + 2} tone={SILVER} echo={GOLD} opacity={spiritOpacity * 0.92} mirror={-1} lean={-8 * embrace} twitch={actorTwitchRight} />
        </g>
      )}

      {/* Fine control threads bind the lower people to their dancing doubles. */}
      {threadsVisible > 0 && (
        <Threads
          frame={f}
          amount={threadsVisible * threadPull * (1 - 0.16 * act4)}
          leftX={f >= 4380 ? walkLeft : leftEmbraceX}
          rightX={f >= 4380 ? walkRight : rightEmbraceX}
          topY={embraceY}
          mechanical={mechanical}
        />
      )}

      {/* Lovers close the distance, turn toward one another, and interlace their arms. */}
      {f >= 2820 && f < 4380 && (
        <g>
          <Dancer
            x={leftEmbraceX}
            y={finalY}
            tone={GOLD}
            echo={SILVER}
            opacity={1}
            mirror={1}
            lean={8 * embrace}
            twitch={actorTwitchLeft}
          />
          <Dancer
            x={rightEmbraceX}
            y={finalY + 2}
            tone={SILVER}
            echo={GOLD}
            opacity={1}
            mirror={-1}
            lean={-8 * embrace}
            twitch={actorTwitchRight}
          />
        </g>
      )}

      {/* The lovers separate and leave while their taut threads remain. */}
      {f >= 4380 && f < 4860 && (
        <g>
          <Dancer x={walkLeft} y={embraceY} tone={GOLD} echo={SILVER} opacity={1 - 0.12 * act4} mirror={1} lean={8 * (1 - act4)} twitch={actorTwitchLeft} />
          <Dancer x={walkRight} y={embraceY + 2} tone={GOLD} echo={SILVER} opacity={1 - 0.12 * act4} mirror={-1} lean={-8 * (1 - act4)} twitch={actorTwitchRight} />
        </g>
      )}

      {/* Hollow reflected hosts remain after the stage empties, with two fine fractures. */}
      {f >= 4860 && (
        <g fill="none" stroke="#A1A1AA" strokeWidth="0.72" strokeLinecap="round" strokeLinejoin="round" opacity="0.72">
          <path d="M 350 1213 l 10 11 -7 10 12 13" />
          <path d="M 635 1214 l -9 11 8 9 -11 14" />
        </g>
      )}

      {/* A descending trace settles for three seconds after the figures stop. */}
      {f >= 4860 && post < 180 && (
        <path
          d={`M 158 ${968 + (1 - waterDrop) * 22} Q 334 ${971 + (1 - waterDrop) * 20}, 512 ${970 + (1 - waterDrop) * 23} T 886 ${969 + (1 - waterDrop) * 21}`}
          fill="none"
          stroke={GOLD}
          strokeWidth="0.42"
          opacity={0.11 * waterDrop}
        />
      )}
    </svg>
  );
}
