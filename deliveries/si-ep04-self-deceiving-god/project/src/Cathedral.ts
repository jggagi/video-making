type Vec4 = [number, number, number, number];

type Curve = {
  points: Vec4[];
  group: number;
  layer: number;
};

type Face = {
  points: [Vec4, Vec4, Vec4, Vec4];
  shell: number;
};

type Scene = {
  curves: Curve[];
  faces: Face[];
  points: Vec4[];
};

type Projected = { x: number; y: number; z: number };
type Camera = {
  zw: number;
  xw: number;
  yaw: number;
  tilt: number;
  d4: number;
  d3: number;
};

const TAU = Math.PI * 2;
const U_STEPS = 24;
const V_STEPS = 12;
const LACE_LAYERS = 6;
const SHELL_COUNT = 5;
const ROSE_GOLD = "#facc15";
const ROSE_PINK = "#d946ef";

/** A closed R4 Klein embedding with the glide seam (u+2pi,v) = (u,-v). */
export function klein4(u: number, v: number): [number, number, number, number] {
  const cv = Math.cos(v);
  const sv = Math.sin(v);
  const radius = 2.45 + cv;
  return [
    radius * Math.cos(u),
    radius * Math.sin(u),
    sv * Math.cos(u * 0.5),
    sv * Math.sin(u * 0.5),
  ];
}

const GROUP_COUNT = 21;
const STYLE: ReadonlyArray<{ color: string; width: number; alpha: number }> = [
  { color: ROSE_PINK, width: 0.48, alpha: 0.72 },
  { color: ROSE_GOLD, width: 0.48, alpha: 0.70 },
  { color: ROSE_GOLD, width: 0.52, alpha: 0.72 },
  { color: ROSE_PINK, width: 0.52, alpha: 0.72 },
  { color: ROSE_PINK, width: 0.55, alpha: 0.69 },
  { color: ROSE_GOLD, width: 0.55, alpha: 0.69 },
  { color: ROSE_GOLD, width: 0.58, alpha: 0.67 },
  { color: ROSE_PINK, width: 0.58, alpha: 0.67 },
  { color: ROSE_PINK, width: 0.60, alpha: 0.64 },
  { color: ROSE_GOLD, width: 0.60, alpha: 0.64 },
  { color: ROSE_PINK, width: 0.95, alpha: 0.90 },
  { color: ROSE_GOLD, width: 0.90, alpha: 0.86 },
  { color: ROSE_GOLD, width: 0.76, alpha: 0.76 },
  { color: ROSE_PINK, width: 0.84, alpha: 0.78 },
  { color: ROSE_GOLD, width: 0.72, alpha: 0.77 },
  { color: ROSE_GOLD, width: 1.00, alpha: 0.84 },
  { color: ROSE_PINK, width: 0.92, alpha: 0.83 },
  { color: ROSE_GOLD, width: 0.82, alpha: 0.78 },
  { color: ROSE_PINK, width: 0.74, alpha: 0.74 },
  { color: ROSE_GOLD, width: 0.66, alpha: 0.70 },
  { color: ROSE_PINK, width: 0.58, alpha: 0.66 },
];

const FACE_COLORS: ReadonlyArray<ReadonlyArray<string>> = [
  ["#150819", "#1a0920", "#210a28", "#290c30", "#310f38", "#2c0e34", "#230b2b", "#1a091f"],
  ["#13081a", "#190a23", "#200c2b", "#280e33", "#30113b", "#2b1036", "#220d2e", "#190a22"],
  ["#12091b", "#180b24", "#1f0d2d", "#270f36", "#2f123e", "#2a1139", "#210e31", "#180b25"],
  ["#11091a", "#170b23", "#1e0d2c", "#260f35", "#2e123d", "#291138", "#200e30", "#170b24"],
  ["#100819", "#160a22", "#1d0c2b", "#250e34", "#2d113c", "#281037", "#1f0d2f", "#160a23"],
];

function transformShellPoint(point: Vec4, layer: number): Vec4 {
  if (layer === 0) return point;
  const scale = 0.75 ** layer;
  const zw = layer * 0.61;
  const z1 = point[2] * Math.cos(zw) - point[3] * Math.sin(zw);
  const w1 = point[2] * Math.sin(zw) + point[3] * Math.cos(zw);
  const xw = layer * 0.37;
  const x1 = point[0] * Math.cos(xw) - w1 * Math.sin(xw);
  const w2 = point[0] * Math.sin(xw) + w1 * Math.cos(xw);
  const pitch = [0, 1.02, 0.76, 1.38, 0.89][layer];
  const y1 = point[1] * Math.cos(pitch) - z1 * Math.sin(pitch);
  const z2 = point[1] * Math.sin(pitch) + z1 * Math.cos(pitch);
  const yaw = [0, 0.48, 1.31, 2.18, 2.82][layer];
  const x2 = x1 * Math.cos(yaw) - y1 * Math.sin(yaw);
  const y2 = x1 * Math.sin(yaw) + y1 * Math.cos(yaw);
  return [x2 * scale, y2 * scale, z2 * scale, w2 * scale];
}

function buildScene(): Scene {
  const curves: Curve[] = [];
  const faces: Face[] = [];
  const points: Vec4[] = [];
  const seen = new Set<Vec4>();

  const remember = (point: Vec4): Vec4 => {
    if (!seen.has(point)) {
      seen.add(point);
      points.push(point);
    }
    return point;
  };
  const addCurve = (curvePoints: Vec4[], group: number, layer = 0) => {
    curvePoints.forEach(remember);
    curves.push({ points: curvePoints, group, layer });
  };

  // Five orthogonal copies form an outer shell and four nested shells at the
  // dyadic scale ratio .75^layer. Every shell starts from the same exact R4
  // embedding; its copy transform is a sequence of metric rotations plus scale.
  for (let layer = 0; layer < SHELL_COUNT; layer++) {
    const surface: Vec4[][] = [];
    for (let i = 0; i <= U_STEPS; i++) {
      const u = (TAU * i) / U_STEPS;
      const row: Vec4[] = [];
      for (let j = 0; j <= V_STEPS; j++) {
        const v = -Math.PI + (TAU * j) / V_STEPS;
        row.push(remember(transformShellPoint(klein4(u, v), layer)));
      }
      surface.push(row);
    }

    // The final u row is the same glide seam with v reversed. The wire loops
    // include it once, while cross-sections omit the duplicate seam boundary.
    for (let j = 0; j < V_STEPS; j++) {
      const wire: Vec4[] = [];
      for (let i = 0; i <= U_STEPS; i++) wire.push(surface[i][j]);
      addCurve(wire, layer * 2 + (j % 5 === 0 ? 1 : 0), layer);
    }
    for (let i = 0; i < U_STEPS; i++) {
      const wire: Vec4[] = [];
      for (let j = 0; j <= V_STEPS; j++) wire.push(surface[i][j]);
      addCurve(wire, layer * 2 + (i % 5 === 0 ? 1 : 0), layer);
    }

    for (let i = 0; i < U_STEPS; i++) {
      for (let j = 0; j < V_STEPS; j++) {
        faces.push({
          points: [surface[i][j], surface[i + 1][j], surface[i + 1][j + 1], surface[i][j + 1]],
          shell: layer,
        });
      }
    }
  }

  // Six dyadic lace levels: each level doubles the number of rose knots while
  // shrinking their chart radius. Their loops are sampled on the Klein surface.
  const golden = 0.6180339887498949;
  const silver = 0.7548776662466927;
  for (let layer = 0; layer < LACE_LAYERS; layer++) {
    const count = 8 * 2 ** layer;
    const radiusScale = 1 / 2 ** (layer * 0.64);
    for (let i = 0; i < count; i++) {
      const u0 = TAU * fract((i + 0.5) * golden + layer * 0.173);
      const v0 = -1.2 + 2.4 * fract(i * silver + layer * 0.119);
      const phase = TAU * fract(i * golden + layer * silver);
      const ru = 0.78 * radiusScale;
      const rv = 0.44 * radiusScale;
      const motif: Vec4[] = [];
      for (let k = 0; k <= 6; k++) {
        const t = (TAU * k) / 6;
        const u = u0 + ru * (Math.cos(t) + 0.28 * Math.cos(5 * t + phase));
        const v = v0 + rv * (Math.sin(t) - 0.28 * Math.sin(5 * t + phase));
        motif.push(transformShellPoint(klein4(u, v), 0));
      }
      addCurve(motif, 15 + layer, layer);
    }
  }

  // Sixteen paired needle spires rise at most one model unit above the shell.
  // Their splay is restrained so the connected nave remains the dominant mass.
  const towerCenters: Vec4[] = [];
  const towerCount = 16;
  for (let tower = 0; tower < towerCount; tower++) {
    const u = (TAU * tower) / towerCount;
    const v = 0.62 * Math.sin(u * 0.5 + 0.35);
    const base = klein4(u, v);
    const centerline: Vec4[] = [];
    for (let k = 0; k <= 12; k++) {
      const t = k / 12;
      const flare = 0.05 + 0.13 * t + 0.035 * Math.sin(Math.PI * t);
      centerline.push([
        base[0] + Math.cos(u) * flare,
        base[1] + Math.sin(u) * flare,
        base[2] + t,
        base[3] + 0.08 * Math.sin(Math.PI * t + u),
      ]);
    }
    const apex = centerline[centerline.length - 1];
    towerCenters.push(apex);
    addCurve(centerline, 10);

    for (const side of [-1, 1]) {
      const rib: Vec4[] = [];
      for (let k = 0; k <= 12; k++) {
        const t = k / 12;
        const flare = 0.07 + 0.15 * t + 0.04 * Math.sin(Math.PI * t);
        const lateral = side * 0.04 * Math.sin(Math.PI * t);
        rib.push([
          base[0] + Math.cos(u) * flare - Math.sin(u) * lateral,
          base[1] + Math.sin(u) * flare + Math.cos(u) * lateral,
          base[2] + 0.88 * t,
          base[3] + side * 0.06 * Math.sin(Math.PI * t + u),
        ]);
      }
      addCurve(rib, side < 0 ? 10 : 11);
    }
  }

  // Pointed arches join neighboring spire tips in twin rib paths.
  for (let i = 0; i < towerCount; i++) {
    const left = towerCenters[i];
    const right = towerCenters[(i + 1) % towerCount];
    const crown: Vec4 = [
      (left[0] + right[0]) * 0.5,
      (left[1] + right[1]) * 0.5,
      (left[2] + right[2]) * 0.5 - 0.08,
      (left[3] + right[3]) * 0.5 + 0.06,
    ];
    const arch: Vec4[] = [];
    for (let half = 0; half < 2; half++) {
      const a = half === 0 ? left : crown;
      const b = half === 0 ? crown : right;
      const control: Vec4 = [
        (left[0] + right[0]) * 0.5,
        (left[1] + right[1]) * 0.5,
        Math.max(left[2], right[2]) - 0.02,
        (left[3] + right[3]) * 0.5 - 0.10,
      ];
      for (let k = half === 0 ? 0 : 1; k <= 6; k++) {
        const t = k / 6;
        const q = 1 - t;
        arch.push([
          q * q * a[0] + 2 * q * t * control[0] + t * t * b[0],
          q * q * a[1] + 2 * q * t * control[1] + t * t * b[1],
          q * q * a[2] + 2 * q * t * control[2] + t * t * b[2],
          q * q * a[3] + 2 * q * t * control[3] + t * t * b[3],
        ]);
      }
    }
    addCurve(arch, 12);
  }

  // Six large self-intersecting rose trajectories make the nave devour itself.
  for (let rose = 0; rose < 6; rose++) {
    const loop: Vec4[] = [];
    const phase = (TAU * rose) / 6;
    for (let k = 0; k <= 48; k++) {
      const t = (TAU * k) / 48;
      const v = 0.92 * Math.sin(t * 0.5 + phase) + 0.26 * Math.sin(5 * t * 0.5 - phase);
      loop.push(klein4(t, v));
    }
    addCurve(loop, rose % 2 === 0 ? 13 : 14);
  }

  return { curves, faces, points };
}

const SCENE = buildScene();

// A recognizable vaulted silhouette gives the abstract Klein nave physical
// scale. These glass buttresses are scenery, not part of the Klein embedding.
function vaultedSilhouette(ctx:CanvasRenderingContext2D,frame:number,box:{x:number;y:number;w:number;h:number},alpha:number){
 const cx=box.x+box.w*.5,base=box.y+box.h*.89;
 const breadth=Math.min(box.w*.82,box.h*1.24),height=box.h*.7;
 const turn=Math.sin(frame*.0007)*.10;
 ctx.save();ctx.globalAlpha=alpha;ctx.lineJoin='round';
 for(let i=-5;i<=5;i++){
  const side=i/5,xx=cx+side*breadth*.46+turn*height*(1-Math.abs(side));
  const hh=height*(.47+.53*(1-Math.abs(side)));
  const yy=base-hh,ww=breadth*(.023+.009*(1-Math.abs(side)));
  const g=ctx.createLinearGradient(xx,yy,xx,base);g.addColorStop(0,'#e45bff44');g.addColorStop(.4,'#71178180');g.addColorStop(1,'#0d081b');
  ctx.fillStyle=g;ctx.strokeStyle=i%2?'#d946ef99':'#facc1577';ctx.lineWidth=1.2;
  ctx.beginPath();ctx.moveTo(xx-ww,base);ctx.lineTo(xx-ww,yy+hh*.24);ctx.lineTo(xx,yy-hh*.14);ctx.lineTo(xx+ww,yy+hh*.24);ctx.lineTo(xx+ww,base);ctx.closePath();ctx.fill();ctx.stroke();
  for(let level=0;level<5;level++){
   const by=base-level*hh*.15,tip=by-hh*.23;
   ctx.beginPath();ctx.moveTo(xx-ww*.65,by);ctx.bezierCurveTo(xx-ww*.7,by-hh*.15,xx-ww*.35,tip,xx,tip);ctx.bezierCurveTo(xx+ww*.35,tip,xx+ww*.7,by-hh*.15,xx+ww*.65,by);ctx.stroke();
  }
  if(i<5){const nx=cx+(i+1)/5*breadth*.46+turn*height*(1-Math.abs((i+1)/5));const archY=base-hh*.62;
   ctx.beginPath();ctx.moveTo(xx,base-hh*.12);ctx.bezierCurveTo(xx,archY,(xx+nx)*.5,archY-hh*.14,(xx+nx)*.5,archY-hh*.21);ctx.bezierCurveTo((xx+nx)*.5,archY-hh*.14,nx,archY,nx,base-hh*.12);ctx.stroke();}
 }
 ctx.restore();
}

function fract(value: number): number {
  return value - Math.floor(value);
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function hasLayerOrnamentMotion(curve: Curve): boolean {
  return (curve.group >= 2 && curve.group < 10) || curve.group >= 15;
}

function layerOrnamentPhase(frame: number, curve: Curve): number {
  const direction = curve.layer % 2 === 0 ? 1 : -1;
  return direction * frame * 0.00008 * (1 + curve.layer * 0.15);
}

function smoothstep(a: number, b: number, x: number): number {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
}

function project4(point: Vec4, camera: Camera): Projected {
  const [x, y, z, w] = point;
  const cz = Math.cos(camera.zw);
  const sz = Math.sin(camera.zw);
  const z1 = z * cz - w * sz;
  const w1 = z * sz + w * cz;
  const cxw = Math.cos(camera.xw);
  const sxw = Math.sin(camera.xw);
  const x1 = x * cxw - w1 * sxw;
  const w2 = x * sxw + w1 * cxw;

  // Safe perspective from R4 to R3 after the two requested plane rotations.
  // d4 stays >= 10, so this never drives a surface through a near plane.
  const f4 = camera.d4 / (camera.d4 - w2);
  const x4 = x1 * f4;
  const y4 = y * f4;
  const z4 = z1 * f4;

  // Y is camera depth and Z remains the architectural vertical axis.
  const cy = Math.cos(camera.yaw);
  const sy = Math.sin(camera.yaw);
  const xYaw = x4 * cy - y4 * sy;
  const yDepth = x4 * sy + y4 * cy;
  const ct = Math.cos(camera.tilt);
  const st = Math.sin(camera.tilt);
  const y3 = z4 * ct - yDepth * st;
  const z3 = yDepth * ct + z4 * st;

  // Final 3D camera perspective; d3 stays >= 18 and z3 is painter depth.
  const f3 = camera.d3 / (camera.d3 - z3);
  return { x: xYaw * f3, y: y3 * f3, z: z3 };
}

function hash01(seed: number): number {
  let n = seed | 0;
  n = Math.imul(n ^ (n >>> 16), 0x7feb352d);
  n = Math.imul(n ^ (n >>> 15), 0x846ca68b);
  n ^= n >>> 16;
  return (n >>> 0) / 4294967296;
}

/**
 * Draw the impossible cathedral inside `box`. All geometry is immutable and
 * cached at module load; frame and collapse alone determine camera and reveal.
 */
export function drawCathedral(
  ctx: CanvasRenderingContext2D,
  frame: number,
  portrait: boolean,
  box: { x: number; y: number; w: number; h: number },
  collapse = 0,
): void {
  if (box.w <= 0 || box.h <= 0) return;
  const c = clamp01(collapse);
  const growth = smoothstep(0, 1, (frame - 3600) / 1800);
  const angle = frame;
  const camera: Camera = {
    zw: angle * 0.00113,
    xw: 0.24 + angle * 0.00079,
    yaw: 0.28 + angle * 0.00107 + (portrait ? 0.18 : 0),
    tilt: portrait
      ? 0.60 + 0.07 * Math.sin(angle * 0.00063)
      : 0.07 + 0.14 * Math.sin(angle * 0.00063),
    d4: 12.0 - growth * 0.46 + 0.12 * Math.sin(angle * 0.00131),
    d3: 22.0 - growth * 3.0 + 0.15 * Math.sin(angle * 0.00091),
  };

  const projected = new WeakMap<Vec4, Projected>();
  const project = (point: Vec4): Projected => {
    let value = projected.get(point);
    if (!value) {
      value = project4(point, camera);
      projected.set(point, value);
    }
    return value;
  };

  let minX = Infinity;
  let minY = Infinity;
  let minZ = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  let maxZ = -Infinity;
  for (const point of SCENE.points) {
    const p = project(point);
    minX = Math.min(minX, p.x);
    maxX = Math.max(maxX, p.x);
    minY = Math.min(minY, p.y);
    maxY = Math.max(maxY, p.y);
    minZ = Math.min(minZ, p.z);
    maxZ = Math.max(maxZ, p.z);
  }

  const sceneCenterX = (minX + maxX) * 0.5;
  const sceneCenterY = (minY + maxY) * 0.5;
  let fitMinX = minX;
  let fitMinY = minY;
  let fitMaxX = maxX;
  let fitMaxY = maxY;
  // Include the current image-space precession in the fit. Without this,
  // rotating inner wires could extend past the clipping box at some frames.
  for (const curve of SCENE.curves) {
    if (!hasLayerOrnamentMotion(curve)) continue;
    const phase = layerOrnamentPhase(frame, curve);
    const cos = Math.cos(phase);
    const sin = Math.sin(phase);
    for (const point of curve.points) {
      const p = project(point);
      const dx = p.x - sceneCenterX;
      const dy = p.y - sceneCenterY;
      const x = sceneCenterX + dx * cos - dy * sin;
      const y = sceneCenterY + dx * sin + dy * cos;
      fitMinX = Math.min(fitMinX, x);
      fitMaxX = Math.max(fitMaxX, x);
      fitMinY = Math.min(fitMinY, y);
      fitMaxY = Math.max(fitMaxY, y);
    }
  }
  const spanX = Math.max(0.001, fitMaxX - fitMinX);
  const spanY = Math.max(0.001, fitMaxY - fitMinY);
  const growthScale = 0.94 + 0.04 * growth;
  const metricScale = Math.min((box.w * 0.84) / spanX, (box.h * 0.82) / spanY) * growthScale;
  const sx = metricScale * (portrait ? 0.90 : 1);
  const sy = metricScale;
  const cx = box.x + box.w * 0.5;
  const cy = box.y + box.h * 0.56;
  const screen = (point: Vec4): Projected => {
    const p = project(point);
    return {
      x: cx + (p.x - sceneCenterX) * sx,
      y: cy - (p.y - sceneCenterY) * sy,
      z: p.z,
    };
  };
  // Secondary shell wires and lace knots precess as ornaments in image space.
  // This does not alter the cached Klein mesh or its glide-seam topology.
  const curveScreen = (point: Vec4, curve: Curve): Projected => {
    const p = screen(point);
    if (!hasLayerOrnamentMotion(curve)) return p;
    const phase = layerOrnamentPhase(frame, curve);
    const cos = Math.cos(phase);
    const sin = Math.sin(phase);
    const dx = p.x - cx;
    const dy = p.y - cy;
    return { x: cx + dx * cos - dy * sin, y: cy + dx * sin + dy * cos, z: p.z };
  };

  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x, box.y, box.w, box.h);
  ctx.clip();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.globalCompositeOperation = "source-over";

  if (c < 0.9999) {
    vaultedSilhouette(ctx,frame,box,(1-c)*(.58+.42*growth));
    const facePaths = Array.from({ length: SHELL_COUNT * 8 }, () => new Path2D());
    const depthSpan = Math.max(0.001, maxZ - minZ);
    for (const face of SCENE.faces) {
      const q = face.points.map((point) => screen(point));
      const depth = (q[0].z + q[1].z + q[2].z + q[3].z) * 0.25;
      const band = Math.max(0, Math.min(7, Math.floor(((depth - minZ) / depthSpan) * 8)));
      const path = facePaths[face.shell * 8 + band];
      let polygon = q;
      const area =
        q[0].x * q[1].y - q[1].x * q[0].y +
        q[1].x * q[2].y - q[2].x * q[1].y +
        q[2].x * q[3].y - q[3].x * q[2].y +
        q[3].x * q[0].y - q[0].x * q[3].y;
      if (area < 0) polygon = [q[0], q[3], q[2], q[1]];
      path.moveTo(polygon[0].x, polygon[0].y);
      path.lineTo(polygon[1].x, polygon[1].y);
      path.lineTo(polygon[2].x, polygon[2].y);
      path.lineTo(polygon[3].x, polygon[3].y);
      path.closePath();
    }
    for (let shell = 0; shell < SHELL_COUNT; shell++) {
      ctx.globalAlpha = (1 - c) * (0.68 + 0.20 * growth) * (1 - shell * 0.055);
      for (let band = 0; band < 8; band++) {
        ctx.fillStyle = FACE_COLORS[shell][band];
        ctx.fill(facePaths[shell * 8 + band]);
      }
    }

    const linePaths = Array.from({ length: GROUP_COUNT }, () => new Path2D());
    const layerAlpha = [0, 1, 2, 3, 4, 5].map((layer) =>
      smoothstep(0.08 + layer * 0.105, 0.38 + layer * 0.105, growth),
    );
    for (const curve of SCENE.curves) {
      const path = linePaths[curve.group];
      const first = curveScreen(curve.points[0], curve);
      path.moveTo(first.x, first.y);
      for (let i = 1; i < curve.points.length; i++) {
        const p = curveScreen(curve.points[i], curve);
        path.lineTo(p.x, p.y);
      }
    }

    const unit = Math.min(box.w, box.h) / 700;
    const glow = Math.min(12, 3.2 * unit);
    for (let group = 0; group < GROUP_COUNT; group++) {
      const style = STYLE[group];
      const layer = group >= 15 ? group - 15 : -1;
      const reveal = layer < 0 ? 1 : layerAlpha[layer];
      if (reveal <= 0.002) continue;
      ctx.strokeStyle = style.color;
      const strokeAlpha = (1 - c) * style.alpha * reveal * (group < 10 ? 0.82 + 0.18 * growth : 1);
      ctx.shadowColor = style.color;
      ctx.globalAlpha = strokeAlpha * 0.25;
      ctx.shadowBlur = Math.min(18, glow * 1.6);
      ctx.lineWidth = Math.max(1, style.width * unit * 4.1);
      ctx.stroke(linePaths[group]);
      ctx.globalAlpha = strokeAlpha;
      ctx.shadowBlur = 0;
      ctx.lineWidth = Math.max(0.45, style.width * unit * 0.88);
      ctx.stroke(linePaths[group]);
    }
  }

  // The 18-frame collapse proxy is continuous in `collapse`; shards are a pure
  // hash of stable sample indices and therefore identical at random-access frames.
  if (c > 0) {
    const radius = c * Math.hypot(box.w * 0.48, box.h * 0.48);
    ctx.globalAlpha = Math.sin(Math.PI * c) * 0.72;
    ctx.strokeStyle = ROSE_GOLD;
    ctx.shadowColor = ROSE_PINK;
    ctx.shadowBlur = 11;
    ctx.lineWidth = Math.max(1, Math.min(box.w, box.h) * 0.003 * (1 - c * 0.5));
    ctx.beginPath();
    ctx.ellipse(cx, cy, radius, radius * (portrait ? 1.12 : 0.72), angle * 0.0004, 0, TAU);
    ctx.stroke();
    ctx.shadowBlur = 0;

    const shardPaths = [new Path2D(), new Path2D(), new Path2D()];
    const shardColors = [ROSE_GOLD, ROSE_PINK, "#fff1fa"];
    const shardCount = 176;
    for (let i = 0; i < shardCount; i++) {
      const source = SCENE.points[(i * 73 + i * i * 19 + 17) % SCENE.points.length];
      const anchor = screen(source);
      let dx = anchor.x - cx;
      let dy = anchor.y - cy;
      const length = Math.hypot(dx, dy) || 1;
      const h1 = hash01(i * 29 + 7);
      const h2 = hash01(i * 131 + 53);
      const h3 = hash01(i * 313 + 101);
      const tangent = (h2 - 0.5) * 1.2;
      dx = (dx / length + tangent) * radius * (0.17 + h1 * 0.78) * c;
      dy = (dy / length - tangent * 0.55) * radius * (0.17 + h1 * 0.78) * c;
      const x = anchor.x + dx;
      const y = anchor.y + dy;
      const size = (0.55 + 4.8 * (1 - c)) * (0.45 + h3);
      const rotation = h2 * Math.PI + c * (4 + 12 * h1) + frame * 0.0017;
      const ux = Math.cos(rotation) * size;
      const uy = Math.sin(rotation) * size;
      const vx = -uy * (0.35 + 0.55 * h3);
      const vy = ux * (0.35 + 0.55 * h3);
      const path = shardPaths[i % shardPaths.length];
      path.moveTo(x + ux, y + uy);
      path.lineTo(x + vx, y + vy);
      path.lineTo(x - ux * 0.72, y - uy * 0.72);
      path.lineTo(x - vx, y - vy);
      path.closePath();
    }
    ctx.globalAlpha = 0.7 * c * (0.92 - 0.20 * c);
    for (let i = 0; i < shardPaths.length; i++) {
      ctx.fillStyle = shardColors[i];
      ctx.fill(shardPaths[i]);
    }
  }

  // Once the 18-frame collapse has completed, deterministic ash rises from
  // cached shell points from frame 5868 through 6000; it is independent of the
  // cathedral draw branch, so the architecture stays fully absent at c = 1.
  if (c >= 0.9999 && frame >= 5868 && frame <= 6000) {
    const riseProgress = clamp01((frame - 5868) / 132);
    ctx.globalAlpha = 0.15 + 0.28 * Math.sin(Math.PI * riseProgress);
    ctx.shadowBlur = 0;
    for (let i = 0; i < 144; i++) {
      const source = SCENE.points[(i * 137 + i * i * 11 + 29) % SCENE.points.length];
      const origin = screen(source);
      const h1 = hash01(i * 47 + 211);
      const h2 = hash01(i * 97 + 307);
      const h3 = hash01(i * 173 + 419);
      const x = origin.x + (h2 - 0.5) * box.w * 0.055 * riseProgress;
      const y = origin.y - box.h * (0.035 + h1 * 0.19) * riseProgress;
      const size = 0.55 + h3 * 1.15;
      ctx.fillStyle = i % 4 === 0 ? ROSE_GOLD : "#f7d6ff";
      ctx.fillRect(x, y, size, size);
    }
  }

  ctx.restore();
}
