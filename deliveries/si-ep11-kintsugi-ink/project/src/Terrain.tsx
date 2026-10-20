import React from 'react';

type Point = {u: number; v: number};
type ScreenPoint = {x: number; y: number};
type Edge = {a: Point; b: Point; id: string};

const WIDTH = 1080;
const HEIGHT = 1920;
const GRID_COLS = 30;
const GRID_ROWS = 14;
const clamp = (n: number, low = 0, high = 1) => Math.max(low, Math.min(high, n));
const smooth = (n: number) => {
  const t = clamp(n);
  return t * t * (3 - 2 * t);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const bell = (n: number, center: number, spread: number) =>
  Math.exp(-Math.pow((n - center) / spread, 2));

function seededRandom(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function heightAt(u: number, v: number) {
  const summit = 0.91 * bell(u, -0.66, 0.27) * bell(v, 0.16, 0.22);
  const foldedRidge = 0.35 * bell(v, 0.32 + 0.12 * Math.sin(2.8 * u), 0.13);
  const crossRidge = 0.27 * bell(u, 0.16 + 0.08 * Math.sin(5 * v), 0.2) * bell(v, 0.55, 0.43);
  const distantShoulder = 0.28 * bell(u, 0.56, 0.22) * bell(v, 0.28, 0.19);
  const basin = 0.42 * bell(u, 0.36, 0.39) * bell(v, 0.84, 0.24);
  const channelOne = 0.17 * bell(v, 0.17 + 0.44 * (u + 0.86) + 0.045 * Math.sin(7 * u), 0.075);
  const channelTwo = 0.13 * bell(v, 0.52 - 0.2 * (u + 0.8) + 0.04 * Math.sin(5 * u + 1), 0.065);
  const paperFold = 0.055 * Math.sin(4.6 * u + 2.1 * v) + 0.035 * Math.cos(7.2 * v - 1.6 * u);
  return 0.1 + paperFold + summit + foldedRidge + crossRidge + distantShoulder - basin - channelOne - channelTwo;
}

function project(point: Point, height: number, frame: number): ScreenPoint {
  const orbit = Math.sin(frame * 0.00105) * 0.035;
  const tilt = Math.cos(frame * 0.00082) * 0.014;
  const unscaledY = 686 + point.v * 413 - height * 143 + point.u * orbit * 24 + (point.v - 0.5) * tilt * 52;
  return {
    x: 505 + point.u * 366 + (point.v - 0.5) * 65 + height * orbit * 18,
    y: 848 + (unscaledY - 848) * 1.2,
  };
}

function pointString(point: ScreenPoint) {
  return `${point.x.toFixed(1)},${point.y.toFixed(1)}`;
}

function rgb(hex: string): [number, number, number] {
  const value = hex.replace('#', '');
  return [parseInt(value.slice(0, 2), 16), parseInt(value.slice(2, 4), 16), parseInt(value.slice(4, 6), 16)];
}

function blendColor(a: string, b: string, amount: number) {
  const left = rgb(a);
  const right = rgb(b);
  const t = clamp(amount);
  return `rgb(${left.map((value, index) => Math.round(mix(value, right[index], t))).join(',')})`;
}

function porcelainTone(height: number) {
  const value = clamp((height + 0.22) / 1.25);
  if (value < 0.68) return blendColor('#242428', '#52525B', value / 0.68);
  return blendColor('#52525B', '#E7E1D4', (value - 0.68) / 0.32);
}

const grid: Point[] = Array.from({length: (GRID_COLS + 1) * (GRID_ROWS + 1)}, (_, index) => {
  const column = index % (GRID_COLS + 1);
  const row = Math.floor(index / (GRID_COLS + 1));
  return {u: mix(-0.98, 0.98, column / GRID_COLS), v: mix(0.02, 0.98, row / GRID_ROWS)};
});
const gridHeights = grid.map(({u, v}) => heightAt(u, v));
const facets: number[][] = [];
for (let row = 0; row < GRID_ROWS; row++) {
  for (let column = 0; column < GRID_COLS; column++) {
    const topLeft = row * (GRID_COLS + 1) + column;
    facets.push([topLeft, topLeft + 1, topLeft + GRID_COLS + 2, topLeft + GRID_COLS + 1]);
  }
}

const silhouetteWorld: Point[] = Array.from({length: 128}, (_, index) => {
  const angle = (index / 128) * Math.PI * 2;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  const ripple = 1 + 0.017 * Math.sin(5 * angle + 0.8) + 0.011 * Math.cos(9 * angle - 0.4) + 0.007 * Math.sin(17 * angle + 1.1);
  const roundedSquare = (value: number) => Math.sign(value) * Math.pow(Math.abs(value), 0.5);
  return {
    u: roundedSquare(cosine) * 0.95 * ripple,
    v: 0.5 + roundedSquare(sine) * 0.455 * ripple,
  };
});

function contourSegments(level: number) {
  const segments: Array<[Point, Point]> = [];
  const crossing = (a: Point, b: Point, va: number, vb: number): Point => {
    const t = clamp((level - va) / (vb - va));
    return {u: mix(a.u, b.u, t), v: mix(a.v, b.v, t)};
  };
  for (let row = 0; row < GRID_ROWS; row++) {
    for (let column = 0; column < GRID_COLS; column++) {
      const index = row * (GRID_COLS + 1) + column;
      const points = [grid[index], grid[index + 1], grid[index + GRID_COLS + 2], grid[index + GRID_COLS + 1]];
      const values = [gridHeights[index], gridHeights[index + 1], gridHeights[index + GRID_COLS + 2], gridHeights[index + GRID_COLS + 1]];
      const hits: Point[] = [];
      for (let edgeIndex = 0; edgeIndex < 4; edgeIndex++) {
        const next = (edgeIndex + 1) % 4;
        if ((values[edgeIndex] < level) !== (values[next] < level)) {
          hits.push(crossing(points[edgeIndex], points[next], values[edgeIndex], values[next]));
        }
      }
      for (let hit = 0; hit + 1 < hits.length; hit += 2) segments.push([hits[hit], hits[hit + 1]]);
    }
  }
  return segments;
}
const contours = [-0.08, 0.06, 0.2, 0.34, 0.48, 0.62, 0.76, 0.9, 1.04].map((level) => contourSegments(level));

function voronoiCells(): Array<{site: Point; polygon: Point[]}> {
  const random = seededRandom(0x51a11);
  const sites: Point[] = [];
  const columns = 6;
  const rows = 6;
  for (let row = 0; row < rows; row++) {
    for (let column = 0; column < columns; column++) {
      sites.push({
        u: -0.88 + ((column + 0.5) / columns) * 1.76 + (random() - 0.5) * 0.13,
        v: 0.045 + ((row + 0.5) / rows) * 0.91 + (random() - 0.5) * 0.065,
      });
    }
  }
  return sites.map((site, siteIndex) => {
    let polygon: Point[] = [{u: -0.98, v: 0.02}, {u: 0.98, v: 0.02}, {u: 0.98, v: 0.98}, {u: -0.98, v: 0.98}];
    for (let otherIndex = 0; otherIndex < sites.length && polygon.length; otherIndex++) {
      if (otherIndex === siteIndex) continue;
      const other = sites[otherIndex];
      const nx = other.u - site.u;
      const ny = other.v - site.v;
      const limit = other.u * other.u + other.v * other.v - site.u * site.u - site.v * site.v;
      const signed = (point: Point) => 2 * point.u * nx + 2 * point.v * ny - limit;
      const clipped: Point[] = [];
      for (let index = 0; index < polygon.length; index++) {
        const current = polygon[index];
        const next = polygon[(index + 1) % polygon.length];
        const currentValue = signed(current);
        const nextValue = signed(next);
        const currentInside = currentValue <= 1e-9;
        const nextInside = nextValue <= 1e-9;
        if (currentInside) clipped.push(current);
        if (currentInside !== nextInside) {
          const amount = currentValue / (currentValue - nextValue);
          clipped.push({u: mix(current.u, next.u, amount), v: mix(current.v, next.v, amount)});
        }
      }
      polygon = clipped;
    }
    return {site, polygon};
  }).filter(({polygon}) => polygon.length >= 3);
}

function key(point: Point) {
  return `${Math.round(point.u * 10000)}:${Math.round(point.v * 10000)}`;
}

function fractureEdges() {
  const edgeMap = new Map<string, Edge>();
  for (const {polygon} of voronoiCells()) {
    for (let index = 0; index < polygon.length; index++) {
      const first = polygon[index];
      const second = polygon[(index + 1) % polygon.length];
      const firstKey = key(first);
      const secondKey = key(second);
      if (firstKey === secondKey) continue;
      const id = firstKey < secondKey ? `${firstKey}|${secondKey}` : `${secondKey}|${firstKey}`;
      const isOuterBoundary =
        (Math.abs(first.u + 0.98) < 0.001 && Math.abs(second.u + 0.98) < 0.001) ||
        (Math.abs(first.u - 0.98) < 0.001 && Math.abs(second.u - 0.98) < 0.001) ||
        (Math.abs(first.v - 0.02) < 0.001 && Math.abs(second.v - 0.02) < 0.001) ||
        (Math.abs(first.v - 0.98) < 0.001 && Math.abs(second.v - 0.98) < 0.001);
      if (!isOuterBoundary && Math.hypot(first.u - second.u, first.v - second.v) > 0.006) {
        edgeMap.set(id, {a: first, b: second, id});
      }
    }
  }
  const edges = [...edgeMap.values()];
  const incident = new Map<string, number[]>();
  edges.forEach((edge, index) => {
    for (const endpoint of [key(edge.a), key(edge.b)]) {
      incident.set(endpoint, [...(incident.get(endpoint) ?? []), index]);
    }
  });
  const remaining = new Set(edges.map((_, index) => index));
  const ordered: Edge[] = [];
  const seed = {u: -0.76, v: 0.1};
  let currentVertex: string | undefined;
  while (remaining.size) {
    let selected = -1;
    let bestDistance = Infinity;
    for (const index of remaining) {
      const edge = edges[index];
      const center = {u: (edge.a.u + edge.b.u) / 2, v: (edge.a.v + edge.b.v) / 2};
      const connected = currentVertex ? key(edge.a) === currentVertex || key(edge.b) === currentVertex : false;
      const distance = currentVertex
        ? connected ? Math.hypot(center.u - seed.u, center.v - seed.v) * 0.12 + Math.hypot(center.u - (edge.a.u + edge.b.u) / 2, center.v - (edge.a.v + edge.b.v) / 2) : Infinity
        : Math.hypot(center.u - seed.u, center.v - seed.v);
      if (distance < bestDistance || (distance === bestDistance && edge.id < edges[selected]?.id)) {
        selected = index;
        bestDistance = distance;
      }
    }
    if (selected < 0 || !Number.isFinite(bestDistance)) {
      selected = Math.min(...remaining);
    }
    const edge = edges[selected];
    ordered.push(edge);
    remaining.delete(selected);
    const endpoints = [key(edge.a), key(edge.b)];
    const nextVertex = endpoints.find((endpoint) => endpoint !== currentVertex) ?? endpoints[0];
    currentVertex = nextVertex;
    if (!(incident.get(currentVertex)?.some((index) => remaining.has(index)))) currentVertex = undefined;
  }
  return ordered;
}
const cracks = fractureEdges();

const texture = (() => {
  const random = seededRandom(0xe11a5);
  return Array.from({length: 84}, (_, index) => ({
    point: {u: mix(-0.94, 0.94, random()), v: mix(0.045, 0.955, random())},
    radius: 0.6 + random() * 1.25,
    dark: index % 3 === 0,
    alpha: 0.1 + random() * 0.18,
  }));
})();

const flakeSeeds = (() => {
  const random = seededRandom(0xc05a1c);
  return Array.from({length: 46}, () => ({
    offset: random(),
    size: 4 + random() * 4,
    curl: random() * Math.PI * 2,
    angle: random() * Math.PI * 2,
  }));
})();

function bezier(a: Point, b: Point, c: Point, d: Point, t: number): Point {
  const inverse = 1 - t;
  return {
    u: inverse * inverse * inverse * a.u + 3 * inverse * inverse * t * b.u + 3 * inverse * t * t * c.u + t * t * t * d.u,
    v: inverse * inverse * inverse * a.v + 3 * inverse * inverse * t * b.v + 3 * inverse * t * t * c.v + t * t * t * d.v,
  };
}

function curlDrift(point: Point, frame: number, seed: number): Point {
  const phase = frame * 0.0017 + seed;
  const a = 3.3 * point.u + 2.5 * point.v + phase;
  const b = 4.4 * point.v - 1.8 * point.u - phase * 0.57;
  const amplitude = 0.026;
  const dPsiDu = amplitude * (3.3 * Math.cos(a) * Math.cos(b) + 1.8 * Math.sin(a) * Math.sin(b));
  const dPsiDv = amplitude * (2.5 * Math.cos(a) * Math.cos(b) - 4.4 * Math.sin(a) * Math.sin(b));
  return {u: dPsiDv * 0.34, v: -dPsiDu * 0.34};
}

function inkWashPath(index: number, frame: number) {
  const seed = index * 1.73 + 0.6;
  const centerV = 0.1 + index * 0.127;
  const points = Array.from({length: 42}, (_, sample) => {
    const t = sample / 41;
    const u = -0.97 + t * 1.94 + 0.045 * Math.sin(t * Math.PI * 2 + seed);
    const v = centerV + 0.055 * Math.sin(t * 7.2 + seed) + 0.023 * Math.sin(t * 17 + seed * 1.9);
    const flow = curlDrift({u, v}, frame, seed);
    const swept = {u: u + flow.u * 2.1, v: v + flow.v * 2.1};
    return project(swept, heightAt(swept.u, swept.v) + 0.022, frame);
  });
  return pathForPoints(points);
}

function routePoint(progress: number, rising: boolean, frame: number, seed: number) {
  const start = rising ? {u: 0.36, v: 0.86} : {u: -0.73, v: 0.12};
  const controlOne = rising ? {u: 0.48, v: 0.61} : {u: -0.34, v: 0.27};
  const controlTwo = rising ? {u: -0.42, v: 0.35} : {u: 0.47, v: 0.56};
  const end = rising ? {u: -0.73, v: 0.12} : {u: 0.36, v: 0.86};
  const point = bezier(start, controlOne, controlTwo, end, progress);
  const drift = curlDrift(point, frame, seed);
  const envelope = Math.sin(Math.PI * progress);
  return {
    u: point.u + drift.u * envelope,
    v: point.v + drift.v * envelope,
  };
}

function pathForPoints(points: ScreenPoint[]) {
  return points.map((point, index) => `${index ? 'L' : 'M'}${pointString(point)}`).join(' ');
}

function flakePolygon(center: ScreenPoint, size: number, angle: number) {
  const points = [
    [0, -size], [size * 0.62, -size * 0.1], [size * 0.14, size * 0.82], [-size * 0.46, size * 0.2],
  ];
  return points.map(([x, y], index) => {
    const rotatedX = x * Math.cos(angle) - y * Math.sin(angle);
    const rotatedY = x * Math.sin(angle) + y * Math.cos(angle);
    return `${index ? 'L' : 'M'}${(center.x + rotatedX).toFixed(1)},${(center.y + rotatedY).toFixed(1)}`;
  }).join(' ') + ' Z';
}

const Terrain: React.FC<{frame: number}> = ({frame}) => {
  const safeFrame = clamp(frame, 0, 4380);
  const projectedGrid = grid.map((point, index) => project(point, gridHeights[index], safeFrame));
  const silhouette = `${silhouetteWorld.map((point, index) => `${index ? 'L' : 'M'}${pointString(project(point, heightAt(point.u, point.v), safeFrame))}`).join(' ')} Z`;
  const inkWashes = Array.from({length: 7}, (_, index) => inkWashPath(index, safeFrame));
  const contourPaths = contours.map((segments) => segments.map(([start, end]) => {
    const a = project(start, heightAt(start.u, start.v), safeFrame);
    const b = project(end, heightAt(end.u, end.v), safeFrame);
    return `M${pointString(a)} L${pointString(b)}`;
  }).join(' '));
  const goldProgress = clamp((safeFrame - 1320) / 1500);
  const goldFront = goldProgress * cracks.length;
  const goldStarted = safeFrame >= 1320;
  const warm = smooth((safeFrame - 2940) / 600);
  const seal = smooth((safeFrame - 2820) / 720);
  const warning = clamp((safeFrame - 1530) / 75) * clamp((2050 - safeFrame) / 250);
  const descending = safeFrame < 1320;
  const rising = safeFrame >= 2820;

  const ridge = Array.from({length: 41}, (_, index) => {
    const u = mix(-0.94, 0.92, index / 40);
    let bestV = 0.04;
    let bestHeight = -Infinity;
    for (let sample = 0; sample <= 30; sample++) {
      const v = mix(0.04, 0.96, sample / 30);
      const height = heightAt(u, v);
      if (height > bestHeight) {
        bestHeight = height;
        bestV = v;
      }
    }
    return project({u, v: bestV}, bestHeight + 0.012, safeFrame);
  });
  const ridgePath = pathForPoints(ridge);

  const downParticles = descending ? flakeSeeds.map((seed, index) => {
    const progress = (safeFrame / (268 + seed.offset * 92) + seed.offset) % 1;
    const point = routePoint(progress, false, safeFrame, seed.curl);
    const screen = project(point, heightAt(point.u, point.v) + 0.025, safeFrame);
    const tailProgress = Math.max(0, progress - 0.055);
    const tailPoint = routePoint(tailProgress, false, safeFrame, seed.curl);
    const tail = project(tailPoint, heightAt(tailPoint.u, tailPoint.v) + 0.025, safeFrame);
    const opacity = 0.42 + 0.56 * Math.sin(Math.PI * progress);
    const color = index % 4 === 0 ? '#E7E1D4' : '#A1A1AA';
    return <g key={`down-${index}`} opacity={opacity}>
      <path d={`M${pointString(tail)} L${pointString(screen)}`} fill="none" stroke={color} strokeWidth={seed.size * 0.8} strokeLinecap="round" opacity="0.58" />
      <path d={flakePolygon(screen, seed.size, seed.angle + safeFrame * 0.012)} fill={color} />
    </g>;
  }) : null;

  const upParticles = rising ? flakeSeeds.map((seed, index) => {
    const elapsed = safeFrame - 2820;
    const phase = (elapsed / 390 + seed.offset * 1.7) % 1;
    const point = routePoint(phase, true, safeFrame, seed.curl);
    const screen = project(point, heightAt(point.u, point.v) + 0.04, safeFrame);
    const tailPhase = Math.max(0, phase - 0.075);
    const tailPoint = routePoint(tailPhase, true, safeFrame, seed.curl);
    const tail = project(tailPoint, heightAt(tailPoint.u, tailPoint.v) + 0.04, safeFrame);
    const tint = blendColor('#E7E1D4', '#FBBF24', seal);
    const shine = safeFrame >= 3540 ? '#FFF0BD' : tint;
    const opacity = 0.42 + 0.56 * Math.sin(Math.PI * phase);
    const rotation = seed.angle + safeFrame * (0.014 + index * 0.00012);
    return <g key={`up-${index}`} opacity={opacity}>
      <path d={`M${pointString(tail)} L${pointString(screen)}`} fill="none" stroke={tint} strokeWidth={seed.size * 0.95} strokeLinecap="round" opacity={0.68} />
      <path d={flakePolygon(screen, seed.size * (0.78 + 0.22 * seal), rotation)} fill={shine} />
    </g>;
  }) : null;

  const warningPath = (() => {
    const center = {u: 0.35, v: 0.84};
    const points = Array.from({length: 13}, (_, index) => {
      const angle = (index / 12) * Math.PI * 2;
      const radius = 0.105 * (0.82 + 0.12 * Math.sin(index * 2.4) + 0.07 * Math.cos(index * 4.1));
      const point = {u: center.u + Math.cos(angle) * radius, v: center.v + Math.sin(angle) * radius * 0.54};
      return project(point, heightAt(point.u, point.v) + 0.035, safeFrame);
    });
    return `${pathForPoints(points)} Z`;
  })();

  return <svg
    width={WIDTH}
    height={HEIGHT}
    viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
    preserveAspectRatio="none"
    style={{position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible'}}
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="ep11-porcelain-ground" x1="0" y1="0" x2="0.82" y2="1">
        <stop offset="0" stopColor="#68666A" stopOpacity="0.9" />
        <stop offset="0.55" stopColor="#38383E" stopOpacity="0.96" />
        <stop offset="1" stopColor="#1B1B1F" stopOpacity="0.98" />
      </linearGradient>
      <radialGradient id="ep11-gold-wash" cx="31%" cy="34%" r="76%">
        <stop offset="0" stopColor="#F59E0B" stopOpacity="0.28" />
        <stop offset="0.48" stopColor="#F59E0B" stopOpacity="0.09" />
        <stop offset="1" stopColor="#F59E0B" stopOpacity="0" />
      </radialGradient>
      <clipPath id="ep11-terrain-clip"><path d={silhouette} /></clipPath>
    </defs>

    <path d={silhouette} transform="translate(0 17)" fill="#08080A" opacity="0.48" />
    <path d={silhouette} fill="url(#ep11-porcelain-ground)" />
    <g clipPath="url(#ep11-terrain-clip)">
    {facets.map((indices, index) => {
      const average = indices.reduce((sum, pointIndex) => sum + gridHeights[pointIndex], 0) / indices.length;
      const highLight = clamp((average + 0.05) / 1.12);
      return <polygon
        key={`facet-${index}`}
        points={indices.map((pointIndex) => pointString(projectedGrid[pointIndex])).join(' ')}
        fill={porcelainTone(average)}
        opacity={0.045 + highLight * 0.14}
      />;
    })}

      {texture.map(({point, radius, dark, alpha}, index) => {
        const screen = project(point, heightAt(point.u, point.v) + 0.012, safeFrame);
        return <circle key={`grain-${index}`} cx={screen.x} cy={screen.y} r={radius} fill={dark ? '#111114' : '#F3EEE4'} opacity={alpha} />;
      })}
      {inkWashes.map((path, index) => <g key={`wash-${index}`} opacity={0.78 + (index % 3) * 0.08}>
        <path d={path} fill="none" stroke="#0B0B0E" strokeWidth={23 + (index % 3) * 5} strokeLinecap="round" opacity="0.045" />
        <path d={path} fill="none" stroke={index % 2 ? '#E7E1D4' : '#3F3F46'} strokeWidth={7 + (index % 2) * 3} strokeLinecap="round" opacity="0.055" />
        <path d={path} fill="none" stroke="#25252A" strokeWidth="1.2" strokeLinecap="round" opacity="0.11" />
      </g>)}
      {contourPaths.map((path, index) => <g key={`contour-${index}`}>
        <path d={path} fill="none" stroke="#121216" strokeWidth={index % 3 === 0 ? 10 : 6.2} strokeLinecap="round" opacity={0.034} />
        <path d={path} fill="none" stroke="#17171B" strokeWidth={index % 3 === 0 ? 1.15 : 0.75} strokeLinecap="round" opacity={0.29} />
      </g>)}
      <path d={silhouette} fill="url(#ep11-gold-wash)" opacity={warm * 0.84} />
      {warning > 0.001 && <g opacity={warning * 0.58}>
        <path d={warningPath} transform="translate(0 7)" fill="#571B18" opacity="0.82" />
        <path d={warningPath} fill="#B94A37" opacity="0.56" />
        <path d={warningPath} fill="none" stroke="#E07A54" strokeWidth="1.3" opacity="0.52" />
      </g>}

      {cracks.map((edge, index) => {
        const samples = Array.from({length: 8}, (_, sample) => {
          const amount = sample / 7;
          const point = {u: mix(edge.a.u, edge.b.u, amount), v: mix(edge.a.v, edge.b.v, amount)};
          return project(point, heightAt(point.u, point.v) + 0.018, safeFrame);
        });
        const d = pathForPoints(samples);
        const localGold = goldStarted ? clamp(goldFront - index) : 0;
        return <g key={`crack-${edge.id}`}>
          <path d={d} fill="none" stroke="#3F3F46" strokeWidth="1.05" strokeLinecap="round" strokeLinejoin="round" opacity="0.58" />
          {localGold > 0 && <path
            d={d}
            fill="none"
            stroke="#F59E0B"
            strokeWidth={6.2 + warm * 1.2}
            strokeLinecap="round"
            strokeLinejoin="round"
            pathLength={1}
            strokeDasharray="1 1"
            strokeDashoffset={1 - localGold}
            opacity={0.12 + warm * 0.05}
          />}
          {localGold > 0 && <path
            d={d}
            fill="none"
            stroke="#F59E0B"
            strokeWidth={2.05 + warm * 0.55}
            strokeLinecap="round"
            strokeLinejoin="round"
            pathLength={1}
            strokeDasharray="1 1"
            strokeDashoffset={1 - localGold}
            opacity={0.72 + seal * 0.2}
          />}
          {localGold > 0 && <path
            d={d}
            fill="none"
            stroke="#FBBF24"
            strokeWidth="0.72"
            strokeLinecap="round"
            strokeLinejoin="round"
            pathLength={1}
            strokeDasharray="1 1"
            strokeDashoffset={1 - localGold}
            opacity={0.64 + seal * 0.28}
          />}
          {safeFrame >= 3540 && <path d={d} fill="none" stroke="#FBBF24" strokeWidth="0.55" strokeLinecap="round" opacity="0.62" />}
        </g>;
      })}

      {goldProgress > 0.56 && <path d={ridgePath} fill="none" stroke="#F59E0B" strokeWidth="13" strokeLinecap="round" opacity={smooth((safeFrame - 2100) / 260) * 0.07} />}
      {goldProgress > 0.56 && <path d={ridgePath} fill="none" stroke="#FBBF24" strokeWidth="2.5" strokeLinecap="round" opacity={smooth((safeFrame - 2100) / 260) * 0.78} />}
      {goldProgress > 0.7 && <path d={ridgePath} fill="none" stroke="#FFF0BD" strokeWidth="0.7" strokeLinecap="round" opacity={smooth((safeFrame - 2280) / 300) * 0.72} />}
      {downParticles}
      {upParticles}
    </g>

    <path d={silhouette} fill="none" stroke="#C6C0B4" strokeWidth="1.3" opacity="0.34" />
    <path d={ridgePath} fill="none" stroke="#E7E1D4" strokeWidth="1.15" opacity={0.22 + warm * 0.22} />
  </svg>;
};

export {Terrain};
