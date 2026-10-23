export type DiskPoint = {x: number; y: number};

export type DiskTriangle = {
	a: DiskPoint;
	b: DiskPoint;
	c: DiskPoint;
	depth: number;
};

export type DiskEdge = {a: DiskPoint; b: DiskPoint};

export type PoincareTiling = {
	triangles: DiskTriangle[];
	edges: DiskEdge[];
	maxRadius: number;
};

const TAU = Math.PI * 2;
const KEY_SCALE = 10000;

const length = (point: DiskPoint): number => Math.hypot(point.x, point.y);
const determinant = (a: DiskPoint, b: DiskPoint): number => a.x * b.y - a.y * b.x;
const dot = (a: DiskPoint, b: DiskPoint): number => a.x * b.x + a.y * b.y;
const sub = (a: DiskPoint, b: DiskPoint): DiskPoint => ({x: a.x - b.x, y: a.y - b.y});

const quantizedPointKey = (point: DiskPoint): string =>
	`${Math.round(point.x * KEY_SCALE)},${Math.round(point.y * KEY_SCALE)}`;

const orderedPointPairKey = (a: DiskPoint, b: DiskPoint): string => {
	const aKey = quantizedPointKey(a);
	const bKey = quantizedPointKey(b);
	return aKey < bKey ? `${aKey}|${bKey}` : `${bKey}|${aKey}`;
};

const triangleKey = (triangle: Omit<DiskTriangle, 'depth'>): string =>
	[quantizedPointKey(triangle.a), quantizedPointKey(triangle.b), quantizedPointKey(triangle.c)]
		.sort()
		.join('|');

const euclideanArea = (a: DiskPoint, b: DiskPoint, c: DiskPoint): number =>
	Math.abs(determinant(sub(b, a), sub(c, a))) / 2;

type Reflection = (point: DiskPoint) => DiskPoint;


const reflectionAcrossGeodesic = (a: DiskPoint, b: DiskPoint): Reflection => {
	const determinantAB = determinant(a, b);
	if (Math.abs(determinantAB) < 1e-8) {
		const direction = length(a) > 1e-10 ? a : b;
		const magnitude = length(direction);
		const ux = magnitude > 1e-10 ? direction.x / magnitude : 1;
		const uy = magnitude > 1e-10 ? direction.y / magnitude : 0;
		return (point) => {
			const projection = point.x * ux + point.y * uy;
			return {x: 2 * projection * ux - point.x, y: 2 * projection * uy - point.y};
		};
	}

	const rightA = (dot(a, a) + 1) / 2;
	const rightB = (dot(b, b) + 1) / 2;
	const center = {
		x: (rightA * b.y - a.y * rightB) / determinantAB,
		y: (a.x * rightB - rightA * b.x) / determinantAB,
	};
	const radiusSquared = Math.max(0, dot(center, center) - 1);

	return (point) => {
		const relative = sub(point, center);
		const distanceSquared = Math.max(1e-16, dot(relative, relative));
		const scale = radiusSquared / distanceSquared;
		return {x: center.x + scale * relative.x, y: center.y + scale * relative.y};
	};
};

const isUsableTriangle = (triangle: Omit<DiskTriangle, 'depth'>, maxRadius: number): boolean => {
	const centroid = {
		x: (triangle.a.x + triangle.b.x + triangle.c.x) / 3,
		y: (triangle.a.y + triangle.b.y + triangle.c.y) / 3,
	};
	return (
		length(centroid) <= maxRadius &&
		euclideanArea(triangle.a, triangle.b, triangle.c) >= 1e-11 &&
		length(triangle.a) < 1.00001 &&
		length(triangle.b) < 1.00001 &&
		length(triangle.c) < 1.00001
	);
};

/**
 * Build a Schwarz reflection tiling from the (π/3, π/2, π/7) right triangle.
 * Its mirrors are the sides of the fundamental chamber; direct reflection of a
 * regular {3, 7} face would overlap because a face is not a Coxeter chamber.
 */
export const buildPoincareTiling = (options: {
	maxTriangles?: number;
	maxRadius?: number;
} = {}): PoincareTiling => {
	const maxTriangles = Math.max(1, Math.floor(options.maxTriangles ?? 2200));
	const maxRadius = Math.min(0.9999, Math.max(0.5, options.maxRadius ?? 0.998));
	const angleAtOrigin = Math.PI / 3;
	const angleAtVertex = Math.PI / 7;
	const coshOriginMirror = Math.cos(angleAtVertex) / Math.sin(angleAtOrigin);
	const originMirrorDistance = Math.acosh(coshOriginMirror);
	const mirrorRadius = Math.tanh(originMirrorDistance / 2);
	const coshOriginVertex = (1 / Math.sqrt(3)) * (Math.cos(angleAtVertex) / Math.sin(angleAtVertex));
	const originVertexDistance = Math.acosh(coshOriginVertex);
	const vertexRadius = Math.tanh(originVertexDistance / 2);
	const seed: Omit<DiskTriangle, 'depth'> = {
		a: {x: 0, y: 0},
		b: {x: mirrorRadius, y: 0},
		c: {x: vertexRadius * Math.cos(angleAtOrigin), y: vertexRadius * Math.sin(angleAtOrigin)},
	};

	const triangles: DiskTriangle[] = [{...seed, depth: 0}];
	const visited = new Set<string>([triangleKey(seed)]);
	for (let cursor = 0; cursor < triangles.length && triangles.length < maxTriangles; cursor += 1) {
		const current = triangles[cursor];
		const vertices = [current.a, current.b, current.c] as const;
		for (let side = 0; side < 3 && triangles.length < maxTriangles; side += 1) {
			const a = vertices[side];
			const b = vertices[(side + 1) % 3];
			const opposite = vertices[(side + 2) % 3];
			const reflected = reflectionAcrossGeodesic(a, b)(opposite);
			const candidate = {a, b, c: reflected};
			if (!isUsableTriangle(candidate, maxRadius)) continue;
			const key = triangleKey(candidate);
			if (visited.has(key)) continue;
			visited.add(key);
			triangles.push({...candidate, depth: current.depth + 1});
		}
	}

	const edges: DiskEdge[] = [];
	const seenEdges = new Set<string>();
	for (const triangle of triangles) {
		const vertices = [triangle.a, triangle.b, triangle.c] as const;
		for (let side = 0; side < 3; side += 1) {
			const a = vertices[side];
			const b = vertices[(side + 1) % 3];
			const key = orderedPointPairKey(a, b);
			if (seenEdges.has(key)) continue;
			seenEdges.add(key);
			edges.push({a, b});
		}
	}

	return {triangles, edges, maxRadius};
};

const normalizePositiveAngle = (angle: number): number => ((angle % TAU) + TAU) % TAU;

/** Append the true circular-arc geodesic between two points in the unit disk. */
export const appendPoincareGeodesic = (
	context: CanvasRenderingContext2D,
	from: DiskPoint,
	to: DiskPoint,
): void => {
	context.moveTo(from.x, from.y);
	const chordDeterminant = determinant(from, to);
	if (Math.abs(chordDeterminant) < 1e-8) {
		context.lineTo(to.x, to.y);
		return;
	}

	const rightFrom = (dot(from, from) + 1) / 2;
	const rightTo = (dot(to, to) + 1) / 2;
	const center = {
		x: (rightFrom * to.y - from.y * rightTo) / chordDeterminant,
		y: (from.x * rightTo - rightFrom * to.x) / chordDeterminant,
	};
	const radius = Math.sqrt(Math.max(0, dot(center, center) - 1));
	if (!Number.isFinite(radius) || radius > 1e6 || radius < 1e-9) {
		context.lineTo(to.x, to.y);
		return;
	}

	const start = Math.atan2(from.y - center.y, from.x - center.x);
	const end = Math.atan2(to.y - center.y, to.x - center.x);
	const positiveDelta = normalizePositiveAngle(end - start);
	const positiveMid = start + positiveDelta / 2;
	const negativeMid = start + (positiveDelta - TAU) / 2;
	const positiveRadius = Math.hypot(center.x + radius * Math.cos(positiveMid), center.y + radius * Math.sin(positiveMid));
	const negativeRadius = Math.hypot(center.x + radius * Math.cos(negativeMid), center.y + radius * Math.sin(negativeMid));
	context.arc(center.x, center.y, radius, start, end, negativeRadius < positiveRadius);
};

/** A disk-preserving Mobius transform plus an optional in-plane rotation. */
export const mobiusDiskPoint = (point: DiskPoint, shift: DiskPoint, rotation = 0): DiskPoint => {
	const denominatorReal = 1 + shift.x * point.x + shift.y * point.y;
	const denominatorImaginary = shift.x * point.y - shift.y * point.x;
	const denominatorMagnitude = denominatorReal * denominatorReal + denominatorImaginary * denominatorImaginary;
	const numeratorReal = point.x + shift.x;
	const numeratorImaginary = point.y + shift.y;
	const transformed = {
		x: (numeratorReal * denominatorReal + numeratorImaginary * denominatorImaginary) / denominatorMagnitude,
		y: (numeratorImaginary * denominatorReal - numeratorReal * denominatorImaginary) / denominatorMagnitude,
	};
	const cos = Math.cos(rotation);
	const sin = Math.sin(rotation);
	return {x: transformed.x * cos - transformed.y * sin, y: transformed.x * sin + transformed.y * cos};
};
