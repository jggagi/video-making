import React from 'react';

type XY = {x: number; y: number};
type XYZ = {x: number; y: number; z: number};

const LATE_CX = 486;
const LATE_CY = 850;
const clamp = (value: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, value));
const smooth = (value: number) => {
  const t = clamp(value);
  return t * t * (3 - 2 * t);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const fmt = (value: number) => Number(value.toFixed(1));
const wrap = (value: number, period: number) => ((value % period) + period) % period;

// A moving pinhole camera wraps each lattice layer only after it has faded at
// the far and near planes. This keeps the camera in continuous motion without
// visible depth-pop or a planar-grid look.
const DEEP_PERIOD = 3680;
const DEEP_LAYERS = Array.from({length: 8}, (_, layer) => ({
  index: layer,
  z: layer * 460,
  tone: layer % 3,
}));

function deepDepth(z: number, frame: number): number {
  const travel = (frame - 2820) * 1.6;
  return 300 + wrap(z - travel, DEEP_PERIOD);
}

function deepLayerOpacity(depth: number): number {
  return smooth((depth - 310) / 260) * smooth((4050 - depth) / 760);
}

function projectDeep(point: XYZ, frame: number): XY {
  const elapsed = frame - 2820;
  const depth = deepDepth(point.z, frame);
  const yaw = 0.12 * Math.sin(elapsed * 0.0014);
  const pitch = 0.045 * Math.sin(elapsed * 0.0019);
  // Keep the depth axis centered on the lens: yaw changes perspective without
  // translating every far layer sideways out of frame.
  const xRotated = point.x * Math.cos(yaw);
  const zRotated = depth * Math.cos(yaw) - point.x * Math.sin(yaw);
  const yRotated = point.y * Math.cos(pitch) + (depth - 2100) * Math.sin(pitch);
  const viewDepth = Math.max(180, zRotated);
  const perspective = 760 / (760 + viewDepth);
  const cameraX = 24 * Math.sin(elapsed * 0.0031);
  const cameraY = 18 * Math.sin(elapsed * 0.0022 + 0.7);
  return {
    x: LATE_CX + (xRotated - cameraX) * perspective,
    y: LATE_CY + (yRotated - cameraY) * perspective,
  };
}

function deepCellPath(layer: number, frame: number): string {
  const z = DEEP_LAYERS[layer].z;
  const commands: string[] = [];
  const rows = 8;
  const cols = 10;
  const radius = 84;
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const cx = (col - (cols - 1) / 2) * 140 + (row % 2 ? 70 : -70);
      const cy = (row - (rows - 1) / 2) * 148;
      const vertices = Array.from({length: 6}, (_, vertex) => {
        const angle = (Math.PI / 3) * vertex + Math.PI / 6;
        return projectDeep({
          x: cx + Math.cos(angle) * radius,
          y: cy + Math.sin(angle) * radius,
          z,
        }, frame);
      });
      commands.push(`M${fmt(vertices[0].x)} ${fmt(vertices[0].y)}`);
      for (let i = 1; i < vertices.length; i++) {
        commands.push(`L${fmt(vertices[i].x)} ${fmt(vertices[i].y)}`);
      }
      commands.push('Z');
    }
  }
  return commands.join('');
}

function deepBridgePath(layer: number, frame: number): string {
  const commands: string[] = [];
  const z0 = DEEP_LAYERS[layer].z;
  const z1 = DEEP_LAYERS[(layer + 1) % DEEP_LAYERS.length].z;
  for (let row = 0; row < 8; row += 2) {
    for (let col = 0; col < 10; col += 2) {
      const x = (col - 4.5) * 140 + (row % 2 ? 70 : -70);
      const y = (row - 3.5) * 148;
      const a = projectDeep({x, y, z: z0}, frame);
      const b = projectDeep({x, y, z: z1}, frame);
      commands.push(`M${fmt(a.x)} ${fmt(a.y)}L${fmt(b.x)} ${fmt(b.y)}`);
    }
  }
  return commands.join('');
}

function ellipsoidCurves(cx: number, cy: number, z: number, rx: number, ry: number, rz: number, frame: number): {outline: string; meridians: string[]} {
  const sample = (latitude: number, longitude: number) => projectDeep({
    x: cx + rx * Math.cos(latitude) * Math.cos(longitude),
    y: cy + ry * Math.sin(latitude),
    z: z + rz * Math.cos(latitude) * Math.sin(longitude),
  }, frame);
  const outlinePoints = Array.from({length: 17}, (_, i) => {
    const angle = (Math.PI * 2 * i) / 16;
    return projectDeep({x: cx + rx * Math.cos(angle), y: cy + ry * Math.sin(angle), z}, frame);
  });
  const outline = `M${outlinePoints.map((point) => `${fmt(point.x)} ${fmt(point.y)}`).join('L')}Z`;
  const meridians = [-0.72, 0.72].map((longitude) => {
    const points = Array.from({length: 11}, (_, i) => sample(-Math.PI / 2 + (Math.PI * i) / 10, longitude));
    return `M${points.map((point) => `${fmt(point.x)} ${fmt(point.y)}`).join('L')}`;
  });
  return {outline, meridians};
}

function DeepCocoon({layer, pod, frame}: {layer: number; pod: number; frame: number}): React.ReactElement {
  const data = DEEP_LAYERS[layer];
  const depth = deepDepth(data.z, frame);
  const alpha = deepLayerOpacity(depth);
  const row = Math.floor(pod / 4);
  const col = pod % 4;
  const phase = (frame - 2820) * 0.004 + pod * 1.4 + layer * 0.7;
  const cx = (col - 1.5) * 410 + (row % 2 ? 24 : -24) + 7 * Math.sin(phase);
  const cy = (row - 1.5) * 285 + (col % 2 ? 18 : -18) + 5 * Math.cos(phase * 0.8);
  const z = data.z + 18 * Math.sin(phase * 0.6);
  const size = 760 / (760 + Math.max(180, depth));
  const ry = 60 + 90 * clamp(1 - depth / 4000);
  const curves = ellipsoidCurves(cx, cy, z, ry * 0.74, ry, ry * 0.42, frame);
  const warm = layer % 2 === 0;
  const color = warm ? '#ffd071' : '#73efff';
  const center = projectDeep({x: cx, y: cy, z}, frame);
  return (
    <g opacity={fmt(alpha * 0.9)}>
      <path d={curves.outline} fill={warm ? 'url(#lateDeepCocoonAmber)' : 'url(#lateDeepCocoonCyan)'} fillOpacity="0.5" stroke={color} strokeWidth={fmt(3.4 * size + 0.7)} />
      {curves.meridians.map((path, index) => (
        <path key={index} d={path} fill="none" stroke={index === 1 ? '#fff4db' : color} strokeWidth={fmt(1.4 * size + 0.45)} opacity={index === 1 ? 0.85 : 0.56} />
      ))}
      <circle cx={fmt(center.x)} cy={fmt(center.y)} r={fmt(2.5 + size * 5.5)} fill="#fff5d8" opacity={alpha * 0.92} />
    </g>
  );
}

function SuspendedCocoon({frame}: {frame: number}): React.ReactElement {
  const elapsed = frame - 2820;
  const contract = smooth(elapsed / 310);
  const fade = 1 - smooth((elapsed - 100) / 280);
  const scale = mix(1.02, 0.19, contract);
  const rotation = 2.2 * Math.sin(elapsed * 0.006);
  return (
    <g transform={`translate(${LATE_CX} ${LATE_CY}) rotate(${fmt(rotation)}) scale(${fmt(scale)})`} opacity={fmt(fade)}>
      <ellipse rx="280" ry="332" fill="url(#lateDeepHeroAura)" opacity="0.46" />
      <path d="M0 -296 C154 -276 246 -151 242 -8 C239 142 113 278 0 300 C-124 276 -244 142 -241 -7 C-237 -156 -156 -277 0 -296 Z" fill="url(#lateDeepHeroShell)" fillOpacity="0.72" stroke="#f4c879" strokeWidth="5" />
      <path d="M0 -328 C178 -295 277 -152 270 -6 C264 164 128 311 0 327 C-147 302 -275 153 -270 -5 C-267 -163 -176 -299 0 -328 Z" fill="none" stroke="#80edfa" strokeWidth="3" strokeDasharray="7 10" />
      <path d="M-176 -237 C-81 -104 69 -76 176 -235 M-214 -57 C-97 14 88 22 213 -53 M-173 129 C-73 67 80 87 174 157 M-105 247 C-40 184 50 185 107 253" fill="none" stroke="#ffdf9b" strokeWidth="3" opacity="0.65" />
      <ellipse rx="125" ry="181" fill="none" stroke="#ed8ff5" strokeWidth="3" strokeDasharray="3 11" />
      <ellipse rx="58" ry="87" fill="url(#lateDeepHeroCore)" />
      <circle cx="-19" cy="-36" r="10" fill="#fff9e4" opacity="0.92" />
    </g>
  );
}

/** Three-dimensional perspective honeycomb for the isolated-islands passage. */
export const DeepField: React.FC<{frame: number}> = ({frame}) => {
  const reveal = smooth((frame - 2840) / 250);
  const drift = frame - 2820;
  return (
    <g>
      <defs>
        <radialGradient id="lateDeepCocoonAmber" cx="35%" cy="26%" r="78%">
          <stop offset="0%" stopColor="#fff7dd" stopOpacity="0.78" />
          <stop offset="42%" stopColor="#f4ad4e" stopOpacity="0.26" />
          <stop offset="100%" stopColor="#da57c6" stopOpacity="0.02" />
        </radialGradient>
        <radialGradient id="lateDeepCocoonCyan" cx="34%" cy="23%" r="82%">
          <stop offset="0%" stopColor="#efffff" stopOpacity="0.74" />
          <stop offset="45%" stopColor="#31d9ea" stopOpacity="0.23" />
          <stop offset="100%" stopColor="#7656ef" stopOpacity="0.02" />
        </radialGradient>
        <radialGradient id="lateDeepHeroAura" r="72%">
          <stop offset="0%" stopColor="#ffe7a4" stopOpacity="0.56" />
          <stop offset="62%" stopColor="#db76ec" stopOpacity="0.16" />
          <stop offset="100%" stopColor="#59e9f2" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="lateDeepHeroShell" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#fff1c5" stopOpacity="0.42" />
          <stop offset="48%" stopColor="#ad5eae" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#25c8da" stopOpacity="0.1" />
        </linearGradient>
        <radialGradient id="lateDeepHeroCore" r="68%">
          <stop offset="0%" stopColor="#fff9df" stopOpacity="0.96" />
          <stop offset="36%" stopColor="#f5c45d" stopOpacity="0.74" />
          <stop offset="100%" stopColor="#de52d1" stopOpacity="0.04" />
        </radialGradient>
      </defs>
      {DEEP_LAYERS.map((layer, index) => {
        const depth = deepDepth(layer.z, frame);
        const alpha = deepLayerOpacity(depth) * reveal;
        if (alpha < 0.008) return null;
        const color = layer.tone === 0 ? '#ffd178' : layer.tone === 1 ? '#6ce5f1' : '#e298ee';
        return (
          <g key={layer.index}>
            <path d={deepCellPath(index, frame)} fill="none" stroke={color} strokeWidth={fmt(1.25 + (1 - depth / 4200) * 0.9)} strokeOpacity={fmt(alpha * (0.025 + 0.025 * (1 - depth / 4200)))} />
            {index < DEEP_LAYERS.length - 1 && (
              <path d={deepBridgePath(index, frame)} fill="none" stroke={index % 2 ? '#e7b7f0' : '#9beaf3'} strokeWidth="1.1" strokeOpacity={fmt(Math.min(alpha, deepLayerOpacity(deepDepth(DEEP_LAYERS[index + 1].z, frame))) * 0.1)} />
            )}
            {Array.from({length: 16}, (_, pod) => <DeepCocoon key={pod} layer={index} pod={pod} frame={frame} />)}
          </g>
        );
      })}
      <SuspendedCocoon frame={frame} />
      <path d={`M${fmt(116 + 22 * Math.sin(drift * 0.003))} 851 Q486 ${fmt(627 + 15 * Math.sin(drift * 0.002))} ${fmt(856 - 20 * Math.sin(drift * 0.0027))} 864`} fill="none" stroke="#9ceff6" strokeWidth="1.3" strokeDasharray="2 15" opacity={reveal * 0.34} />
    </g>
  );
};

type Bust = {cx: number; cy: number; side: 'left' | 'right'};
const BUSTS: Bust[] = [
  {cx: 300, cy: 740, side: 'left'},
  {cx: 672, cy: 740, side: 'right'},
];

function bustOutline(): string {
  return [
    'M0 -88',
    'C-45 -88 -70 -52 -72 -5',
    'C-75 47 -52 84 -25 96',
    'C-24 122 -39 136 -70 150',
    'C-127 174 -158 211 -166 274',
    'L-153 338 C-103 359 -55 369 0 369 C55 369 103 359 153 338',
    'L166 274 C158 211 127 174 70 150',
    'C39 136 24 122 25 96',
    'C52 84 75 47 72 -5',
    'C70 -52 45 -88 0 -88 Z',
  ].join(' ');
}

function bustWirePath(): {head: string[]; body: string[]} {
  const head: string[] = [];
  for (let meridian = -3; meridian <= 3; meridian++) {
    const x = meridian * 18;
    head.push(`M${x} -76 C${fmt(x * 1.55)} -31 ${fmt(x * 1.42)} 36 ${fmt(x * 0.42)} 91`);
  }
  const body: string[] = [];
  for (let line = -3; line <= 3; line++) {
    const x = line * 22;
    body.push(`M${fmt(x * 0.25)} 117 C${fmt(x * 0.66 - 74)} 181 ${fmt(x * 0.82 - 92)} 273 ${fmt(x * 0.92)} 354`);
  }
  for (const y of [170, 220, 275, 325]) {
    const half = y < 200 ? 112 : y < 260 ? 143 : y < 310 ? 152 : 137;
    body.push(`M${-half} ${y} Q0 ${y + 17} ${half} ${y}`);
  }
  return {head, body};
}

function bustNodes(frame: number): Array<{x: number; y: number; phase: number; strength: number}> {
  const nodes: Array<{x: number; y: number; phase: number; strength: number}> = [];
  for (let ring = 0; ring < 5; ring++) {
    const y = -66 + ring * 34;
    const width = 69 * Math.sqrt(Math.max(0.05, 1 - (y * y) / (88 * 88)));
    for (let i = 0; i < 12; i++) {
      const angle = (Math.PI * 2 * i) / 12 + ring * 0.17;
      nodes.push({x: Math.cos(angle) * width, y: y + Math.sin(angle) * 6, phase: i * 1.3 + ring, strength: 0.8});
    }
  }
  const rows = [142, 184, 226, 268, 310, 348];
  for (let row = 0; row < rows.length; row++) {
    const y = rows[row];
    const half = y < 190 ? 73 + (y - 142) * 0.85 : y < 270 ? 131 + (y - 190) * 0.24 : y < 324 ? 150 - (y - 270) * 0.18 : 140 - (y - 324) * 0.5;
    for (let col = 0; col < 9; col++) {
      const fraction = col / 8 * 2 - 1;
      nodes.push({x: fraction * half, y: y + 4 * Math.sin(col * 1.8 + row), phase: row * 4 + col * 0.8, strength: 0.66 + 0.26 * (1 - Math.abs(fraction))});
    }
  }
  return nodes.map((node) => ({...node, phase: node.phase + frame * 0.009}));
}

function r4TorusProject(
  cx: number,
  cy: number,
  scale: number,
  u: number,
  v: number,
  elapsed: number,
  spin: number,
  orientation: number,
  screenRotation: number,
): XY {
  const diagonal = Math.SQRT1_2;
  let x = diagonal * Math.cos(u);
  let y = diagonal * Math.sin(u);
  let z = diagonal * Math.cos(v);
  let w = diagonal * Math.sin(v);

  const rotateXW = orientation + spin * elapsed * 0.012;
  const rotateYZ = -orientation * 0.72 - spin * elapsed * 0.0094;
  const oldX = x;
  x = oldX * Math.cos(rotateXW) - w * Math.sin(rotateXW);
  w = oldX * Math.sin(rotateXW) + w * Math.cos(rotateXW);
  const oldY = y;
  y = oldY * Math.cos(rotateYZ) - z * Math.sin(rotateYZ);
  z = oldY * Math.sin(rotateYZ) + z * Math.cos(rotateYZ);

  // S3 -> perspective R3 -> camera-rotated R2. The Clifford torus is the
  // product of two equal-radius circles in orthogonal R4 planes.
  const wDenom = Math.max(1.8, 3.05 - w);
  const x3 = x / wDenom;
  const y3 = y / wDenom;
  const z3 = z / wDenom;
  const cameraYaw = 0.54 + orientation * 0.32;
  const x3r = x3 * Math.cos(cameraYaw) + z3 * Math.sin(cameraYaw);
  const z3r = z3 * Math.cos(cameraYaw) - x3 * Math.sin(cameraYaw);
  const perspective = 3.25 / Math.max(2.2, 3.25 - z3r);
  const sx = x3r * scale * perspective;
  const sy = y3 * scale * perspective;
  return {
    x: cx + sx * Math.cos(screenRotation) - sy * Math.sin(screenRotation),
    y: cy + sx * Math.sin(screenRotation) + sy * Math.cos(screenRotation),
  };
}

function torusFamilyPath(bust: Bust, family: 0 | 1, curve: number, frame: number): string {
  const elapsed = frame - 3600;
  const spin = bust.side === 'left' ? 1 : -1;
  const orientation = bust.side === 'left' ? 0.12 : 0.86;
  const screenRotation = bust.side === 'left' ? -0.14 : Math.PI / 2 + 0.08;
  const fixed = (Math.PI * 2 * curve) / 8;
  const points = Array.from({length: 37}, (_, i) => {
    const varying = (Math.PI * 2 * i) / 36;
    return family === 0
      ? r4TorusProject(0, 0, 425, fixed, varying, elapsed, spin, orientation, screenRotation)
      : r4TorusProject(0, 0, 425, varying, fixed, elapsed, spin, orientation, screenRotation);
  });
  return `M${points.map((point) => `${fmt(point.x)} ${fmt(point.y)}`).join('L')}`;
}

function BustMesh({bust, frame}: {bust: Bust; frame: number}): React.ReactElement {
  const entering = smooth((frame - 3600) / 54);
  const leaving = 1 - smooth((frame - 4320) / 62);
  const opacity = entering * leaving;
  const pulse = 1 + 0.008 * Math.sin((frame - 3600) * 0.047 + (bust.side === 'right' ? 1.3 : 0));
  const isLeft = bust.side === 'left';
  const main = isLeft ? '#ffbf61' : '#ffc77d';
  const accent = isLeft ? '#fff1bd' : '#ff9f57';
  const nodes = bustNodes(frame);
  const wires = bustWirePath();
  const spin = isLeft ? 1 : -1;
  const orientation = isLeft ? 0.12 : 0.86;
  const screenRotation = isLeft ? -0.14 : Math.PI / 2 + 0.08;
  return (
    <g transform={`translate(${bust.cx} ${bust.cy}) scale(${fmt(pulse)})`} opacity={fmt(opacity)}>
      <path d={bustOutline()} fill={isLeft ? 'url(#lateNeuralAmberBody)' : 'url(#lateNeuralCopperBody)'} fillOpacity="0.48" stroke={main} strokeWidth="2.1" strokeOpacity="0.78" />
      <path d={wires.head.join('')} fill="none" stroke={accent} strokeWidth="1.2" strokeOpacity="0.42" />
      <path d={wires.body.join('')} fill="none" stroke={main} strokeWidth="1.25" strokeOpacity="0.38" />
      <path d="M-68 -10 C-50 -48 -28 -61 0 -66 C28 -61 50 -48 68 -10 M-105 176 Q0 212 105 176 M-145 282 Q0 310 145 282" fill="none" stroke="#fff3d2" strokeWidth="1.4" strokeOpacity="0.5" />
      {nodes.map((node, index) => {
        const glow = 0.54 + 0.42 * (0.5 + 0.5 * Math.sin(node.phase));
        const radius = 1.25 + node.strength * (0.9 + 0.7 * (0.5 + 0.5 * Math.sin(node.phase * 1.27)));
        return <circle key={index} cx={fmt(node.x)} cy={fmt(node.y)} r={fmt(radius)} fill={index % 7 === 0 ? '#fff6d9' : accent} opacity={fmt(glow)} />;
      })}
      {/* Counter-rotating great-circle families of a mathematically projected Clifford torus. */}
      {[0, 1].map((family) => (
        <g key={family} transform={`translate(0 -1)`} fill="none" strokeLinecap="round">
          {Array.from({length: 8}, (_, curve) => (
            <path
              key={curve}
              d={torusFamilyPath(bust, family as 0 | 1, curve, frame)}
              stroke={family === 0 ? (isLeft ? '#ee8aef' : '#4de7f5') : (isLeft ? '#ffd56e' : '#a3f4fa')}
              strokeWidth={curve % 3 === 0 ? 2.25 : 1.25}
              strokeOpacity={family === 0 ? 0.74 : 0.5}
            />
          ))}
        </g>
      ))}
      <ellipse cx="0" cy="0" rx="118" ry="148" fill="none" stroke={isLeft ? '#f093f0' : '#5fe8f4'} strokeWidth="1.4" strokeDasharray="4 9" strokeOpacity="0.44" transform={`rotate(${fmt((frame - 3600) * (isLeft ? 0.08 : -0.08))})`} />
    </g>
  );
}

/** Neural point-cloud busts and counter-rotating 4D Clifford-torus domains. */
export const NeuralIsolation: React.FC<{frame: number}> = ({frame}) => {
  const reveal = smooth((frame - 3600) / 46) * (1 - smooth((frame - 4326) / 52));
  const laserPulse = 0.72 + 0.2 * Math.sin((frame - 3600) * 0.09);
  return (
    <g>
      <defs>
        <linearGradient id="lateNeuralAmberBody" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffdfa0" stopOpacity="0.38" />
          <stop offset="48%" stopColor="#b97842" stopOpacity="0.16" />
          <stop offset="100%" stopColor="#302522" stopOpacity="0.06" />
        </linearGradient>
        <linearGradient id="lateNeuralCopperBody" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffd895" stopOpacity="0.34" />
          <stop offset="46%" stopColor="#c66a3a" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#28232a" stopOpacity="0.06" />
        </linearGradient>
        <linearGradient id="lateNeuralLaser" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#ffca72" stopOpacity="0" />
          <stop offset="24%" stopColor="#ffe5aa" stopOpacity="0.98" />
          <stop offset="76%" stopColor="#ffe5aa" stopOpacity="0.98" />
          <stop offset="100%" stopColor="#ffca72" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g opacity={fmt(reveal)}>
        {BUSTS.map((bust) => <BustMesh key={bust.side} bust={bust} frame={frame} />)}
        <path d="M463 1017 H509" fill="none" stroke="url(#lateNeuralLaser)" strokeWidth="3" opacity={laserPulse} />
        <path d="M463 1006 V1028 M509 1006 V1028" fill="none" stroke="#ffe0a0" strokeWidth="2" opacity={laserPulse} />
        <path d="M467 1017 H505" fill="none" stroke="#fff7dc" strokeWidth="0.9" strokeDasharray="2 8" opacity="0.88" />
        <text x="486" y="510" fill="#ffdc9b" fontFamily="Menlo, monospace" fontSize="30" letterSpacing="3.5" textAnchor="middle">PHYSICAL DISTANCE</text>
        <text x="486" y="550" fill="#fff0cb" fontFamily="Menlo, monospace" fontSize="36" fontWeight="700" letterSpacing="2" textAnchor="middle">10.0 CM</text>
      </g>
    </g>
  );
};

