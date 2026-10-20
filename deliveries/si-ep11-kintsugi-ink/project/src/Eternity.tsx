import React from 'react';

type Point3 = {x: number; y: number; z: number};
type Point2 = {x: number; y: number};

const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value));
const smooth = (value: number) => {
  const t = clamp(value);
  return t * t * (3 - 2 * t);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const fmt = (value: number) => value.toFixed(1);

const normalize = (v: Point3): Point3 => {
  const length = Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z) || 1;
  return {x: v.x / length, y: v.y / length, z: v.z / length};
};

const ribbonPoint = (t: number, u: number, frame: number): {screen: Point2; depth: number} => {
  const a = 292;
  const b = 275;
  const c = 138;
  const center: Point3 = {x: a * Math.sin(t), y: b * Math.sin(2 * t), z: c * Math.cos(t)};
  const tangent = normalize({x: a * Math.cos(t), y: 2 * b * Math.cos(2 * t), z: -c * Math.sin(t)});
  const normal = normalize({x: tangent.y, y: -tangent.x, z: 0});
  const binormal = normalize({
    x: tangent.y * normal.z - tangent.z * normal.y,
    y: tangent.z * normal.x - tangent.x * normal.z,
    z: tangent.x * normal.y - tangent.y * normal.x,
  });
  const twist = t / 2 + 0.035 * Math.sin(frame * 0.002);
  const width: Point3 = {
    x: Math.cos(twist) * normal.x + Math.sin(twist) * binormal.x,
    y: Math.cos(twist) * normal.y + Math.sin(twist) * binormal.y,
    z: Math.cos(twist) * normal.z + Math.sin(twist) * binormal.z,
  };
  const halfWidth = 29;
  const world = {
    x: 540 + center.x + u * halfWidth * width.x,
    y: 920 + center.y + u * halfWidth * width.y,
    z: center.z + u * halfWidth * width.z,
  };

  // A slow camera orbit keeps the foil alive while leaving its crossover readable.
  const yaw = (frame - 5040) * 0.00045;
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const rotatedX = (world.x - 540) * cosYaw + world.z * sinYaw;
  const rotatedZ = -(world.x - 540) * sinYaw + world.z * cosYaw;
  const perspective = 1400 / (1400 - rotatedZ);
  return {
    screen: {
      x: 540 + rotatedX * perspective,
      y: 920 + (world.y - 920) * perspective - rotatedZ * 0.14,
    },
    depth: rotatedZ,
  };
};

type RibbonCell = {
  key: string;
  points: string;
  depth: number;
  fill: string;
  fillOpacity: number;
  strokeOpacity: number;
};

const makeRibbonCells = (frame: number, visibleSections: number): RibbonCell[] => {
  const sections = 96;
  const lanes = 4;
  const cells: RibbonCell[] = [];
  for (let i = 0; i < visibleSections; i += 1) {
    const t0 = (i / sections) * Math.PI * 2;
    const t1 = ((i + 1) / sections) * Math.PI * 2;
    for (let lane = 0; lane < lanes; lane += 1) {
      const u0 = -1 + (2 * lane) / lanes;
      const u1 = -1 + (2 * (lane + 1)) / lanes;
      const corners = [
        ribbonPoint(t0, u0, frame),
        ribbonPoint(t1, u0, frame),
        ribbonPoint(t1, u1, frame),
        ribbonPoint(t0, u1, frame),
      ];
      const averageDepth = corners.reduce((sum, point) => sum + point.depth, 0) / corners.length;
      const middleT = (t0 + t1) / 2;
      const middleU = (u0 + u1) / 2;
      const light = clamp(0.55 + 0.25 * Math.cos(middleT * 1.7 - middleU * 1.8) + 0.2 * Math.sin(middleT / 2));
      cells.push({
        key: 'r-' + i + '-' + lane,
        points: corners.map((point) => fmt(point.screen.x) + ',' + fmt(point.screen.y)).join(' '),
        depth: averageDepth,
        fill: light > 0.67 ? '#FBBF24' : '#F59E0B',
        fillOpacity: 0.34 + light * 0.34,
        strokeOpacity: 0.2 + light * 0.35,
      });
    }
  }
  return cells.sort((left, right) => left.depth - right.depth);
};

type Vec2 = {x: number; y: number};
type Curve = {start: Vec2; control: Vec2; end: Vec2; radii: [number, number, number]};

const quad = (curve: Curve, t: number): Vec2 => {
  const oneMinusT = 1 - t;
  return {
    x: oneMinusT * oneMinusT * curve.start.x + 2 * oneMinusT * t * curve.control.x + t * t * curve.end.x,
    y: oneMinusT * oneMinusT * curve.start.y + 2 * oneMinusT * t * curve.control.y + t * t * curve.end.y,
  };
};

const curveTangent = (curve: Curve, t: number): Vec2 => ({
  x: 2 * (1 - t) * (curve.control.x - curve.start.x) + 2 * t * (curve.end.x - curve.control.x),
  y: 2 * (1 - t) * (curve.control.y - curve.start.y) + 2 * t * (curve.end.y - curve.control.y),
});

const curveRadius = (curve: Curve, t: number) => {
  if (t < 0.5) return mix(curve.radii[0], curve.radii[1], t * 2);
  return mix(curve.radii[1], curve.radii[2], (t - 0.5) * 2);
};

const tubeGeometry = (curve: Curve, steps = 22) => {
  const samples = Array.from({length: steps + 1}, (_, i) => {
    const t = i / steps;
    const center = quad(curve, t);
    const tangent = curveTangent(curve, t);
    const length = Math.sqrt(tangent.x * tangent.x + tangent.y * tangent.y) || 1;
    const normal = {x: -tangent.y / length, y: tangent.x / length};
    const radius = curveRadius(curve, t);
    return {
      t,
      center,
      plus: {x: center.x + normal.x * radius, y: center.y + normal.y * radius},
      minus: {x: center.x - normal.x * radius, y: center.y - normal.y * radius},
    };
  });
  const outline = samples.map((sample) => sample.plus).concat(samples.slice().reverse().map((sample) => sample.minus));
  const path = 'M ' + outline.map((point) => fmt(point.x) + ' ' + fmt(point.y)).join(' L ') + ' Z';
  return {samples, path};
};

const meshStroke = (opacity = 0.34) => ({
  fill: 'none',
  stroke: '#E7E1D4',
  strokeOpacity: opacity,
  strokeWidth: 0.8,
  strokeLinecap: 'round' as const,
});

const renderTube = (curve: Curve, key: string, opacity: number) => {
  const {samples, path} = tubeGeometry(curve);
  const ringIndexes = [2, 5, 8, 11, 14, 17, 20];
  const rings = ringIndexes.map((index) => {
    const sample = samples[index];
    const middle = sample.center;
    const dx = sample.minus.x - sample.plus.x;
    const dy = sample.minus.y - sample.plus.y;
    return (
      <path
        key={key + '-ring-' + index}
        d={'M ' + fmt(sample.plus.x) + ' ' + fmt(sample.plus.y) + ' Q ' + fmt(middle.x + dy * 0.025) + ' ' + fmt(middle.y - dx * 0.025) + ' ' + fmt(sample.minus.x) + ' ' + fmt(sample.minus.y)}
        {...meshStroke(0.3)}
        opacity={opacity}
      />
    );
  });
  const seam = samples.filter((_, index) => index % 3 === 0).map((sample) => fmt(sample.center.x) + ',' + fmt(sample.center.y)).join(' ');
  return (
    <g key={key} opacity={opacity}>
      <path d={path} fill="#E7E1D4" fillOpacity="0.065" stroke="#E7E1D4" strokeOpacity="0.43" strokeWidth="0.9" />
      {rings}
      <polyline points={seam} fill="none" stroke="#FBBF24" strokeOpacity="0.42" strokeWidth="0.7" />
    </g>
  );
};

const bodyWidthAt = (y: number) => {
  const profile: Array<[number, number]> = [
    [800, 37], [812, 52], [834, 49], [858, 42], [882, 36], [920, 33],
    [948, 35], [972, 43], [990, 51], [1008, 47], [1020, 31],
  ];
  for (let i = 0; i < profile.length - 1; i += 1) {
    const [y0, w0] = profile[i];
    const [y1, w1] = profile[i + 1];
    if (y >= y0 && y <= y1) return mix(w0, w1, (y - y0) / (y1 - y0));
  }
  return y < 800 ? profile[0][1] : profile[profile.length - 1][1];
};

const makeTorsoPath = (cx: number) => [
  'M', fmt(cx - 39), '800',
  'Q', fmt(cx), '782', fmt(cx + 39), '800',
  'Q', fmt(cx + 53), '806', fmt(cx + 51), '826',
  'L', fmt(cx + 40), '862',
  'Q', fmt(cx + 31), '886', fmt(cx + 32), '917',
  'L', fmt(cx + 37), '950',
  'Q', fmt(cx + 45), '972', fmt(cx + 50), '989',
  'Q', fmt(cx + 52), '1005', fmt(cx + 43), '1011',
  'Q', fmt(cx), '1032', fmt(cx - 43), '1011',
  'Q', fmt(cx - 52), '1005', fmt(cx - 50), '989',
  'Q', fmt(cx - 45), '972', fmt(cx - 37), '950',
  'L', fmt(cx - 32), '917',
  'Q', fmt(cx - 31), '886', fmt(cx - 40), '862',
  'L', fmt(cx - 51), '826',
  'Q', fmt(cx - 53), '806', fmt(cx - 39), '800 Z',
].join(' ');

const legCurve = (cx: number, side: number): Curve => ({
  start: {x: cx + side * 22, y: 1006},
  control: {x: cx + side * 34, y: 1083},
  end: {x: cx + side * 33, y: 1177},
  radii: [22, 15, 10],
});

const footPath = (cx: number, side: number) => {
  const ankleX = cx + side * 33;
  const toeX = ankleX + side * 18;
  return [
    'M', fmt(ankleX - 9), '1170 Q', fmt(ankleX - 7), '1185', fmt(ankleX - 20), '1191',
    'Q', fmt(ankleX - 12), '1201', fmt(toeX + side * 4), '1195',
    'Q', fmt(toeX + side * 10), '1192', fmt(toeX), '1185',
    'L', fmt(ankleX + 9), '1171 Z',
  ].join(' ');
};

const figure = (cx: number, inward: number, index: number, frame: number, opacity: number) => {
  const sway = Math.sin(frame * 0.009 + index * 1.3) * 1.5;
  const breathe = Math.sin(frame * 0.026 + index * 0.7) * 1.2;
  const center = cx + sway;
  const innerArm: Curve = {
    start: {x: center + inward * 39, y: 811 + breathe},
    control: {x: center + inward * 73, y: 835 + breathe},
    end: {x: center + inward * 96, y: 858 + breathe},
    radii: [17, 11, 7],
  };
  const outerArm: Curve = {
    start: {x: center - inward * 39, y: 811 + breathe},
    control: {x: center - inward * 70, y: 855 + breathe},
    end: {x: center - inward * 91, y: 960 + breathe},
    radii: [17, 11, 7],
  };
  const innerHandX = center + inward * 101;
  const outerHandX = center - inward * 97;
  const headY = 735 + breathe * 0.35;
  const torsoPath = makeTorsoPath(center);
  const torsoRings: React.ReactNode[] = [];
  for (let y = 812; y <= 1005; y += 12) {
    const width = bodyWidthAt(y);
    const arc = 2.4 + Math.sin(y * 0.028 + index) * 1.2;
    const isSeam = (Math.round((y - 812) / 12) + index) % 5 === 0;
    torsoRings.push(
      <path
        key={'torso-lat-' + index + '-' + y}
        d={'M ' + fmt(center - width) + ' ' + y + ' Q ' + fmt(center) + ' ' + fmt(y + arc) + ' ' + fmt(center + width) + ' ' + y}
        fill="none"
        stroke={isSeam ? '#FBBF24' : '#E7E1D4'}
        strokeOpacity={isSeam ? 0.38 : 0.32}
        strokeWidth={isSeam ? 0.95 : 0.72}
      />,
    );
  }
  const torsoLongitudes = [-0.76, -0.38, 0, 0.38, 0.76].map((ratio) => {
    const points: string[] = [];
    for (let y = 806; y <= 1014; y += 13) {
      points.push(fmt(center + bodyWidthAt(y) * ratio) + ',' + fmt(y));
    }
    return <polyline key={'torso-meridian-' + index + '-' + ratio} points={points.join(' ')} fill="none" stroke="#E7E1D4" strokeOpacity="0.2" strokeWidth="0.68" />;
  });
  const headLatitudes = Array.from({length: 9}, (_, row) => {
    const level = -0.78 + row * 0.195;
    const halfWidth = 29 * Math.sqrt(Math.max(0.04, 1 - level * level));
    const y = headY + level * 39;
    return (
      <path
        key={'head-lat-' + index + '-' + row}
        d={'M ' + fmt(center - halfWidth) + ' ' + fmt(y) + ' Q ' + fmt(center) + ' ' + fmt(y + 3) + ' ' + fmt(center + halfWidth) + ' ' + fmt(y)}
        fill="none"
        stroke="#E7E1D4"
        strokeOpacity="0.34"
        strokeWidth="0.72"
      />
    );
  });
  const headMeridians = [-0.72, -0.36, 0, 0.36, 0.72].map((meridian) => {
    const points = Array.from({length: 17}, (_, step) => {
      const angle = -Math.PI / 2 + (Math.PI * step) / 16;
      const x = center + 28 * meridian * Math.cos(angle);
      const y = headY + 39 * Math.sin(angle);
      return fmt(x) + ',' + fmt(y);
    });
    return <polyline key={'head-meridian-' + index + '-' + meridian} points={points.join(' ')} fill="none" stroke="#E7E1D4" strokeOpacity="0.22" strokeWidth="0.65" />;
  });
  const innerElbow = quad(innerArm, 0.53);
  const outerElbow = quad(outerArm, 0.53);

  return (
    <g key={'figure-' + index} opacity={opacity}>
      <ellipse cx={center} cy={headY} rx="31" ry="42" fill="#E7E1D4" fillOpacity="0.075" stroke="#E7E1D4" strokeOpacity="0.52" strokeWidth="1.05" />
      {headLatitudes}
      {headMeridians}
      <path d={'M ' + fmt(center - 14) + ' 774 Q ' + fmt(center) + ' 780 ' + fmt(center + 14) + ' 774 L ' + fmt(center + 17) + ' 807 Q ' + fmt(center) + ' 817 ' + fmt(center - 17) + ' 807 Z'} fill="#E7E1D4" fillOpacity="0.05" stroke="#E7E1D4" strokeOpacity="0.34" strokeWidth="0.8" />
      <path d={torsoPath} fill="#E7E1D4" fillOpacity="0.055" stroke="#E7E1D4" strokeOpacity="0.53" strokeWidth="1.05" />
      {torsoRings}
      {torsoLongitudes}
      {renderTube(innerArm, 'inner-arm-' + index, 1)}
      {renderTube(outerArm, 'outer-arm-' + index, 1)}
      {[1, -1].map((side) => {
        const leg = legCurve(center, side);
        const mesh = renderTube(leg, 'leg-' + index + '-' + side, 1);
        return (
          <g key={'leg-group-' + index + '-' + side}>
            {mesh}
            <path d={footPath(center, side)} fill="#E7E1D4" fillOpacity="0.07" stroke="#E7E1D4" strokeOpacity="0.46" strokeWidth="0.85" />
          </g>
        );
      })}
      <circle cx={innerElbow.x} cy={innerElbow.y} r="2.4" fill="#FBBF24" fillOpacity="0.82" />
      <circle cx={outerElbow.x} cy={outerElbow.y} r="2.1" fill="#FBBF24" fillOpacity="0.67" />
      <ellipse cx={innerHandX} cy={858 + breathe} rx="10" ry="6.5" fill="#E7E1D4" fillOpacity="0.16" stroke="#FBBF24" strokeOpacity="0.75" strokeWidth="0.9" />
      <ellipse cx={outerHandX} cy={960 + breathe} rx="7.5" ry="9" fill="#E7E1D4" fillOpacity="0.08" stroke="#E7E1D4" strokeOpacity="0.48" strokeWidth="0.8" />
      <path d={'M ' + fmt(center - 8) + ' 836 Q ' + fmt(center + 5) + ' 847 ' + fmt(center - 2) + ' 858 L ' + fmt(center + 5) + ' 874'} fill="none" stroke="#FBBF24" strokeOpacity={index === 0 ? 0.62 : 0.38} strokeWidth="1.05" strokeLinecap="round" />
      <circle cx={center - 2} cy="858" r="1.6" fill="#FBBF24" />
    </g>
  );
};

export const Eternity: React.FC<{frame: number}> = ({frame}) => {
  if (frame < 4380 || frame >= 5400) return null;

  const reveal = smooth((frame - 4380) / 420);
  const visibleSections = Math.max(1, Math.min(96, Math.ceil(96 * reveal)));
  const fadeOut = 1 - smooth((frame - 4820) / 40);
  const fadeIn = smooth((frame - 4890) / 150);
  const handoffOpacity = frame < 4860 ? fadeOut : frame < 4890 ? 0 : fadeIn;
  const ribbonOpacity = handoffOpacity;
  const peopleOpacity = frame < 4890 ? 0 : fadeIn;
  const cells = makeRibbonCells(frame, visibleSections);

  const risingParticles = Array.from({length: 72}, (_, i) => {
    const angle = (i / 72) * Math.PI * 2;
    const stagger = (i % 18) * 3;
    const travel = smooth((frame - 4380 - stagger) / 390);
    const target = ribbonPoint(angle, Math.sin(i * 1.73) * 0.74, frame).screen;
    const startX = 540 + Math.sin(i * 2.399) * (86 + (i % 5) * 18);
    const startY = 1244 - (i % 13) * 7;
    const x = mix(startX, target.x, travel);
    const y = mix(startY, target.y, travel);
    const life = (1 - smooth((frame - 4660 - (i % 12) * 5) / 175)) * smooth((frame - 4380 - stagger) / 22);
    const radius = 0.75 + (i % 4) * 0.36;
    return <circle key={'rise-' + i} cx={fmt(x)} cy={fmt(y)} r={radius} fill={i % 4 === 0 ? '#FBBF24' : '#F59E0B'} opacity={life * (frame < 4860 ? fadeOut : 0)} />;
  });

  const orbitGlints = Array.from({length: 14}, (_, i) => {
    const t = frame * 0.0012 + (i / 14) * Math.PI * 2;
    const point = ribbonPoint(t, Math.sin(i * 2.4) * 0.8, frame).screen;
    const pulse = 0.42 + 0.32 * (0.5 + 0.5 * Math.sin(frame * 0.035 + i));
    return <circle key={'glint-' + i} cx={fmt(point.x)} cy={fmt(point.y)} r={i % 4 === 0 ? 1.8 : 1.15} fill="#FBBF24" opacity={pulse * ribbonOpacity} />;
  });

  return (
    <svg
      viewBox="0 0 1080 1920"
      width="1080"
      height="1920"
      aria-hidden="true"
      style={{position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible', pointerEvents: 'none'}}
    >
      <defs>
        <radialGradient id="eternity-warm-aura" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#F59E0B" stopOpacity="0.12" />
          <stop offset="55%" stopColor="#F59E0B" stopOpacity="0.045" />
          <stop offset="100%" stopColor="#0C0C0E" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="540" cy="920" rx="350" ry="350" fill="url(#eternity-warm-aura)" opacity={Math.max(ribbonOpacity, peopleOpacity)} />
      <g opacity={ribbonOpacity}>
        {cells.map((cell) => (
          <polygon
            key={cell.key}
            points={cell.points}
            fill={cell.fill}
            fillOpacity={cell.fillOpacity}
            stroke="#FBBF24"
            strokeOpacity={cell.strokeOpacity}
            strokeWidth="0.75"
            strokeLinejoin="round"
          />
        ))}
      </g>
      <g>{risingParticles}</g>
      <g opacity={peopleOpacity}>
        {figure(440, 1, 0, frame, 1)}
        {figure(640, -1, 1, frame, 1)}
        <path d="M 527 858 Q 535 851 541 858 Q 547 865 555 858" fill="none" stroke="#FBBF24" strokeOpacity="0.86" strokeWidth="1.2" strokeLinecap="round" />
        <circle cx="540" cy="858" r="2.5" fill="#FBBF24" opacity="0.92" />
      </g>
      <g>{orbitGlints}</g>
    </svg>
  );
};
