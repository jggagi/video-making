/** Deterministic mathematical models for the EP06 Canvas scenes.
 *
 * The readiness curve is a neutral schematic sample. Lorenz and delay
 * coordinates are a mathematical demonstration, not a biological predictor.
 * The choice field and shield rays are explicit toy visual models.
 */

export type Vec2 = { x: number; y: number };
export type Vec3 = { x: number; y: number; z: number };

export const LORENZ = Object.freeze({ sigma: 10, rho: 28, beta: 8 / 3 });
export const LORENZ_DT = 0.008;
export const LORENZ_STEPS_PER_FRAME = 2;
export const LORENZ_DELAY_FRAMES = 24;
export const LORENZ_WARMUP_STEPS = 2500;
export const CHOICE_BRANCH_COUNT = 10;
export const CHOSEN_BRANCH = 7;

export const clamp = (value: number, minimum: number, maximum: number): number =>
  Math.max(minimum, Math.min(maximum, value));

export const clamp01 = (value: number): number => clamp(value, 0, 1);

export const mix = (a: number, b: number, amount: number): number =>
  a + (b - a) * amount;

export const smoothstep = (amount: number): number => {
  const t = clamp01(amount);
  return t * t * (3 - 2 * t);
};

/** Frame/index-derived value in [0, 1), suitable for repeatable visual seeds. */
export function seededUnit(index: number, salt = 0): number {
  const value = Math.sin((index + 1) * 127.1 + (salt + 1) * 311.7) * 43758.5453123;
  return value - Math.floor(value);
}

/** Neutral synthetic readiness-potential sample in microvolts.
 *
 * The curve begins its shallow negative-going ramp at -550 ms, reaches a
 * schematic value at action, and recovers after 0 ms. Negative values are
 * intentionally retained so a renderer can place them upward on a negative-up
 * cortical-potential axis.
 */
export function readinessPotentialMicrovolts(milliseconds: number): number {
  if (milliseconds < -550) return 0;
  if (milliseconds <= 0) {
    const t = clamp01((milliseconds + 550) / 550);
    return -1.15 * (0.12 * t + 0.88 * t * t);
  }
  const recovery = clamp01(milliseconds / 200);
  return mix(-1.15, -0.12, smoothstep(recovery));
}

export function lorenzDerivative(point: Vec3): Vec3 {
  return {
    x: LORENZ.sigma * (point.y - point.x),
    y: point.x * (LORENZ.rho - point.z) - point.y,
    z: point.x * point.y - LORENZ.beta * point.z,
  };
}

const addScaled = (point: Vec3, delta: Vec3, scale: number): Vec3 => ({
  x: point.x + delta.x * scale,
  y: point.y + delta.y * scale,
  z: point.z + delta.z * scale,
});

/** One fourth-order Runge-Kutta step for the classic Lorenz system. */
export function rk4LorenzStep(point: Vec3, dt = LORENZ_DT): Vec3 {
  const k1 = lorenzDerivative(point);
  const k2 = lorenzDerivative(addScaled(point, k1, dt / 2));
  const k3 = lorenzDerivative(addScaled(point, k2, dt / 2));
  const k4 = lorenzDerivative(addScaled(point, k3, dt));
  return {
    x: point.x + (dt / 6) * (k1.x + 2 * k2.x + 2 * k3.x + k4.x),
    y: point.y + (dt / 6) * (k1.y + 2 * k2.y + 2 * k3.y + k4.y),
    z: point.z + (dt / 6) * (k1.z + 2 * k2.z + 2 * k3.z + k4.z),
  };
}

/** Build a deterministic Lorenz trace, with a settling interval before index 0. */
export function buildLorenzTrajectory(
  frameCount = 7200,
  stepsPerFrame = LORENZ_STEPS_PER_FRAME,
  warmupSteps = LORENZ_WARMUP_STEPS,
): Vec3[] {
  const totalSteps = warmupSteps + Math.max(1, Math.floor(frameCount)) * stepsPerFrame + 1;
  const points: Vec3[] = new Array(totalSteps);
  let current: Vec3 = { x: 0.11, y: 0, z: 0 };
  for (let i = 0; i < warmupSteps; i += 1) current = rk4LorenzStep(current);
  points[0] = current;
  for (let i = 1; i < totalSteps; i += 1) {
    current = rk4LorenzStep(current);
    points[i] = current;
  }
  return points;
}

const LORENZ_TRACE = buildLorenzTrajectory();

function traceIndex(frame: number): number {
  const safeFrame = clamp(Math.floor(frame), 0, 7199);
  return LORENZ_WARMUP_STEPS + safeFrame * LORENZ_STEPS_PER_FRAME;
}

export function lorenzPoint(frame: number): Vec3 {
  return LORENZ_TRACE[traceIndex(frame)];
}

/** Exact delay coordinates sampled from the same scalar Lorenz x trace. */
export function lorenzDelayCoordinates(frame: number): Vec3 {
  const index = traceIndex(frame);
  const lag = LORENZ_DELAY_FRAMES * LORENZ_STEPS_PER_FRAME;
  return {
    x: LORENZ_TRACE[index].x,
    y: LORENZ_TRACE[index - lag].x,
    z: LORENZ_TRACE[index - 2 * lag].x,
  };
}

export function lorenzTracePoint(frame: number, useDelayCoordinates: boolean): Vec3 {
  return useDelayCoordinates ? lorenzDelayCoordinates(frame) : lorenzPoint(frame);
}

/** Synthetic animation metric; it is not an empirical free-will measure. */
export function syntheticTrajectoryResidualPercent(frame: number): number {
  if (frame >= 3120) return 0.001;
  if (frame <= 1800) return 64;
  const t = (frame - 1800) / (3120 - 1800);
  return 64 * (0.001 / 64) ** t;
}

/** Deterministic synthetic reconstruction offset, with norm proportional to residual. */
export function syntheticReconstructionCoordinates(frame: number, residualFrame = frame): Vec3 {
  const reference = lorenzDelayCoordinates(frame);
  const residualScale = syntheticTrajectoryResidualPercent(residualFrame) / 64;
  const phase = Math.floor(frame) * 0.071;
  const direction = normalize3({
    x: Math.sin(phase + 0.7),
    y: Math.cos(phase * 0.83 + 1.2),
    z: Math.sin(phase * 1.17 + 2.4),
  });
  const error = 30 * residualScale;
  return {
    x: reference.x + direction.x * error,
    y: reference.y + direction.y * error,
    z: reference.z + direction.z * error,
  };
}

type BranchWell = { x: number; z: number; sx: number; sz: number; depth: number };

function branchEndpoint(branch: number): number {
  const normalized = clamp(branch, 0, CHOICE_BRANCH_COUNT - 1) / (CHOICE_BRANCH_COUNT - 1);
  return mix(-4.5, 4.5, normalized);
}

function branchWells(branch: number, hidden: boolean, nudge: number): BranchWell[] {
  const endpoint = branchEndpoint(branch);
  const wells: BranchWell[] = [];
  const selected = branch === CHOSEN_BRANCH;
  const baseDepth = hidden
    ? mix(0.44, selected ? 1.18 : 0.12, clamp01(nudge))
    : 0.44;
  for (let step = 0; step < 8; step += 1) {
    const progress = step / 7;
    wells.push({
      x: endpoint * progress,
      z: 3.7 - 7.4 * progress,
      sx: 0.48,
      sz: 0.72,
      depth: baseDepth,
    });
  }
  return wells;
}

/**
 * Ten-branch toy landscape made from Gaussian valley samples. Increasing nudge
 * creates a strong quadratic cross-track groove around branch 7 and raises the
 * nine competing endpoints. Values are dimensionless, not a measured reward.
 */
export function choicePotential(x: number, z: number, hidden = false, nudge = 1): number {
  let value = 0.006 * x * x;
  for (let branch = 0; branch < CHOICE_BRANCH_COUNT; branch += 1) {
    for (const well of branchWells(branch, hidden, nudge)) {
      const dx = (x - well.x) / well.sx;
      const dz = (z - well.z) / well.sz;
      value -= well.depth * Math.exp(-0.5 * (dx * dx + dz * dz));
    }
    if (hidden && branch !== CHOSEN_BRANCH) {
      const amount = clamp01(nudge);
      const dx = (x - branchEndpoint(branch)) / 0.58;
      const dz = (z + 3.7) / 0.65;
      value += 1.35 * amount * Math.exp(-0.5 * (dx * dx + dz * dz));
    }
  }
  if (hidden) {
    const progress = clamp01((3.7 - z) / 7.4);
    const targetX = branchEndpoint(CHOSEN_BRANCH) * progress;
    const crossTrack = x - targetX;
    value += 1.8 * clamp01(nudge) * crossTrack * crossTrack;
  }
  return value;
}

/** Center-difference gradient of the toy potential. */
export function choicePotentialGradient(
  x: number,
  z: number,
  hidden = false,
  nudge = 1,
  branchIndex: number | null = null,
  epsilon = 0.002,
): Vec2 {
  const withOptionChannel = (sampleX: number, sampleZ: number): number => {
    let value = choicePotential(sampleX, sampleZ, hidden, nudge);
    if (branchIndex !== null) {
      const progress = clamp01((3.7 - sampleZ) / 7.4);
      const targetBranch = hidden ? CHOSEN_BRANCH : branchIndex;
      const targetX = branchEndpoint(targetBranch) * progress;
      const strength = hidden ? 3.4 : 2.5;
      value += 0.5 * strength * (sampleX - targetX) ** 2;
    }
    return value;
  };
  return {
    x: (withOptionChannel(x + epsilon, z) - withOptionChannel(x - epsilon, z)) / (2 * epsilon),
    y: (withOptionChannel(x, z + epsilon) - withOptionChannel(x, z - epsilon)) / (2 * epsilon),
  };
}

/**
 * Integrate a driven gradient-flow toy with forward Euler steps. Lateral motion
 * follows negative dV/dx; a monotonic forward driver advances z so the scene
 * does not claim a freely descending energy trajectory.
 */
export function integrateChoicePath(
  branch: number,
  hidden = false,
  nudge = 1,
  steps = 140,
): Vec2[] {
  const endpoint = branchEndpoint(branch);
  const initialProgress = hidden ? 0.18 : 0;
  let x = endpoint * initialProgress;
  let z = 3.7 - 7.4 * initialProgress;
  const path: Vec2[] = [{ x, y: z }];
  for (let i = 0; i < steps; i += 1) {
    const gradient = choicePotentialGradient(x, z, hidden, nudge, hidden ? CHOSEN_BRANCH : branch);
    x -= clamp(gradient.x * 0.035, -0.24, 0.24);
    z = 3.7 - 7.4 * initialProgress - (7.4 * (i + 1) * (1 - initialProgress)) / steps;
    path.push({ x, y: z });
  }
  return path;
}

/** Authored option centerline: a visible hypothetical route, not an organism trajectory. */
export function authoredChoicePath(branch: number, steps = 140): Vec2[] {
  const endpoint = branchEndpoint(branch);
  return Array.from({ length: steps + 1 }, (_, index) => {
    const progress = index / steps;
    return { x: endpoint * progress, y: 3.7 - 7.4 * progress };
  });
}

const PHI = (1 + Math.sqrt(5)) / 2;

function normalize3(point: Vec3): Vec3 {
  const magnitude = Math.hypot(point.x, point.y, point.z) || 1;
  return { x: point.x / magnitude, y: point.y / magnitude, z: point.z / magnitude };
}

/** A mathematically subdivided icosahedron projected onto the unit sphere. */
export function createGeodesicMesh(subdivisionLevels = 2): { vertices: Vec3[]; faces: number[][]; edges: [number, number][] } {
  const vertices: Vec3[] = [
    { x: -1, y: PHI, z: 0 }, { x: 1, y: PHI, z: 0 }, { x: -1, y: -PHI, z: 0 }, { x: 1, y: -PHI, z: 0 },
    { x: 0, y: -1, z: PHI }, { x: 0, y: 1, z: PHI }, { x: 0, y: -1, z: -PHI }, { x: 0, y: 1, z: -PHI },
    { x: PHI, y: 0, z: -1 }, { x: PHI, y: 0, z: 1 }, { x: -PHI, y: 0, z: -1 }, { x: -PHI, y: 0, z: 1 },
  ].map(normalize3);
  let faces: number[][] = [
    [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
    [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
    [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
    [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
  ];

  for (let level = 0; level < Math.max(0, Math.floor(subdivisionLevels)); level += 1) {
    const midpointCache = new Map<string, number>();
    const midpoint = (a: number, b: number): number => {
      const key = a < b ? `${a}:${b}` : `${b}:${a}`;
      const cached = midpointCache.get(key);
      if (cached !== undefined) return cached;
      const point = normalize3({
        x: (vertices[a].x + vertices[b].x) / 2,
        y: (vertices[a].y + vertices[b].y) / 2,
        z: (vertices[a].z + vertices[b].z) / 2,
      });
      const index = vertices.push(point) - 1;
      midpointCache.set(key, index);
      return index;
    };
    const refined: number[][] = [];
    for (const [a, b, c] of faces) {
      const ab = midpoint(a, b);
      const bc = midpoint(b, c);
      const ca = midpoint(c, a);
      refined.push([a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]);
    }
    faces = refined;
  }

  const edgeSet = new Set<string>();
  for (const [a, b, c] of faces) {
    for (const [left, right] of [[a, b], [b, c], [c, a]]) {
      edgeSet.add(left < right ? `${left}:${right}` : `${right}:${left}`);
    }
  }
  const edges: [number, number][] = [...edgeSet].map((edge) => edge.split(':').map(Number) as [number, number]);
  return { vertices, faces, edges };
}

export const GEODESIC_MESH = createGeodesicMesh(2);

function normalizeDirection(point: Vec3): Vec3 {
  return normalize3(point);
}

function cross3(a: Vec3, b: Vec3): Vec3 {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}

function dot3(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function add3(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

function scale3(point: Vec3, scale: number): Vec3 {
  return { x: point.x * scale, y: point.y * scale, z: point.z * scale };
}

function sphereIntersection(origin: Vec3, direction: Vec3, radius: number): Vec3 | null {
  const b = 2 * dot3(origin, direction);
  const c = dot3(origin, origin) - radius * radius;
  const discriminant = b * b - 4 * c;
  if (discriminant < 0) return null;
  const t = (-b - Math.sqrt(discriminant)) / 2;
  return t >= 0 ? add3(origin, scale3(direction, t)) : null;
}

export type ShieldRay = {
  origin: Vec3;
  direction: Vec3;
  hit: Vec3 | null;
  tangent: Vec3 | null;
  arc: Vec3[];
  exit: Vec3 | null;
};

/** Deterministic incoming ray and seeded great-circle tangent deflection. */
export function computeShieldRay(index: number, radius = 1): ShieldRay {
  const angle = (index / 18) * Math.PI * 2 + seededUnit(index, 3) * 0.16;
  const elevation = (seededUnit(index, 7) - 0.5) * 1.05;
  const origin = { x: 4.5 * Math.cos(angle), y: 4.5 * Math.sin(angle), z: 4.5 * elevation };
  const aim = {
    x: 0.22 * Math.sin(angle * 2.1),
    y: 0.22 * Math.cos(angle * 1.7),
    z: 0.18 * Math.sin(angle * 3.2),
  };
  const direction = normalizeDirection({ x: aim.x - origin.x, y: aim.y - origin.y, z: aim.z - origin.z });
  const hit = sphereIntersection(origin, direction, radius);
  if (!hit) return { origin, direction, hit: null, tangent: null, arc: [], exit: null };
  const normal = normalizeDirection(hit);
  let tangent = normalizeDirection(cross3(normal, { x: 0, y: 0, z: 1 }));
  if (!Number.isFinite(tangent.x) || Math.hypot(tangent.x, tangent.y, tangent.z) < 1e-8) {
    tangent = normalizeDirection(cross3(normal, { x: 0, y: 1, z: 0 }));
  }
  const sign = seededUnit(index, 11) < 0.5 ? -1 : 1;
  tangent = scale3(tangent, sign);
  const arc: Vec3[] = [];
  const arcAngle = 0.72 + seededUnit(index, 17) * 0.38;
  for (let i = 0; i <= 8; i += 1) {
    const t = (arcAngle * i) / 8;
    arc.push(add3(scale3(normal, radius * Math.cos(t)), scale3(tangent, radius * Math.sin(t))));
  }
  const last = arc[arc.length - 1];
  const exitDirection = normalizeDirection(add3(scale3(tangent, 0.82), scale3(normal, 0.57)));
  return {
    origin,
    direction,
    hit,
    tangent,
    arc,
    exit: add3(last, scale3(exitDirection, 1.4)),
  };
}

export function rotatePoint3(point: Vec3, yaw: number, pitch: number, roll = 0): Vec3 {
  const cosY = Math.cos(yaw);
  const sinY = Math.sin(yaw);
  const cosP = Math.cos(pitch);
  const sinP = Math.sin(pitch);
  const cosR = Math.cos(roll);
  const sinR = Math.sin(roll);
  const x1 = point.x * cosY + point.z * sinY;
  const z1 = -point.x * sinY + point.z * cosY;
  const y2 = point.y * cosP - z1 * sinP;
  const z2 = point.y * sinP + z1 * cosP;
  return { x: x1 * cosR - y2 * sinR, y: x1 * sinR + y2 * cosR, z: z2 };
}

/** Inverse-CDF Laplace sample for a seeded visual DP mechanism only; not a secure RNG. */
export function laplaceQuantile(u:number, sensitivity=1, epsilon=1):number {
  const q=clamp(u,1e-9,1-1e-9)-0.5;
  return -(sensitivity/epsilon)*Math.sign(q)*Math.log(1-2*Math.abs(q));
}
