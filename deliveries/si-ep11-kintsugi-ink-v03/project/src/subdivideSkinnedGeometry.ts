import {
  Float32BufferAttribute,
  Uint16BufferAttribute,
  type BufferAttribute,
  type BufferGeometry,
  type InterleavedBufferAttribute,
} from 'three';

type Point3 = [number, number, number];
type Edge = {
  a: number;
  b: number;
  opposites: number[];
};

const POSITION_EPSILON = 1e-6;
const SUPPORTED_ATTRIBUTES = new Set([
  'position',
  'normal',
  'uv',
  'skinIndex',
  'skinWeight',
]);

/**
 * Apply one or more Loop subdivision steps to an indexed, skinned triangle
 * mesh. UV-split vertices remain split in the output, while coincident
 * positions are welded only for the subdivision neighborhood and normals.
 */
export function subdivideSkinnedGeometry(
  geometry: BufferGeometry,
  iterations = 1,
): BufferGeometry {
  if (!Number.isInteger(iterations) || iterations < 0) {
    throw new Error(`iterations must be a non-negative integer; received ${iterations}`);
  }

  if (iterations === 0) return geometry.clone();
  let result = geometry;
  for (let iteration = 0; iteration < iterations; iteration++) {
    result = subdivideOnce(result);
  }
  return result;
}

function subdivideOnce(geometry: BufferGeometry): BufferGeometry {
  const position = geometry.getAttribute('position');
  const uv = geometry.getAttribute('uv');
  const skinIndex = geometry.getAttribute('skinIndex');
  const skinWeight = geometry.getAttribute('skinWeight');
  const index = geometry.getIndex();

  if (!position || !uv || !skinIndex || !skinWeight) {
    throw new Error('Skinned subdivision requires position, uv, skinIndex, and skinWeight attributes.');
  }
  if (!index) {
    throw new Error('Skinned subdivision requires indexed triangle geometry.');
  }
  if (position.itemSize !== 3 || uv.itemSize !== 2 || skinIndex.itemSize !== 4 || skinWeight.itemSize !== 4) {
    throw new Error('Expected position/uv/skinIndex/skinWeight item sizes of 3/2/4/4.');
  }
  if (index.count % 3 !== 0) {
    throw new Error(`Expected triangle indices; index count ${index.count} is not divisible by 3.`);
  }
  if (Object.values(geometry.morphAttributes).some((attributes) => attributes.length > 0)) {
    throw new Error('Morph attributes are unsupported by skinned subdivision.');
  }
  for (const [name, attribute] of Object.entries(geometry.attributes)) {
    if (!SUPPORTED_ATTRIBUTES.has(name)) {
      throw new Error(`Unsupported geometry attribute "${name}"; only position, normal, uv, skinIndex, and skinWeight are supported.`);
    }
    if (attribute.count !== position.count) {
      throw new Error(`Attribute "${name}" has ${attribute.count} vertices; expected ${position.count}.`);
    }
  }

  const vertexCount = position.count;
  const welded = new Array<number>(vertexCount);
  const weldPositions: Point3[] = [];
  const weldCounts: number[] = [];
  const weldMap = new Map<string, number>();
  for (let vertex = 0; vertex < vertexCount; vertex++) {
    const point: Point3 = [position.getX(vertex), position.getY(vertex), position.getZ(vertex)];
    if (!point.every(Number.isFinite)) {
      throw new Error(`Non-finite position at vertex ${vertex}.`);
    }
    const key = positionKey(point);
    let id = weldMap.get(key);
    if (id === undefined) {
      id = weldPositions.length;
      weldMap.set(key, id);
      weldPositions.push([0, 0, 0]);
      weldCounts.push(0);
    }
    welded[vertex] = id;
    weldPositions[id][0] += point[0];
    weldPositions[id][1] += point[1];
    weldPositions[id][2] += point[2];
    weldCounts[id]++;
  }
  for (let id = 0; id < weldPositions.length; id++) {
    const count = weldCounts[id];
    weldPositions[id][0] /= count;
    weldPositions[id][1] /= count;
    weldPositions[id][2] /= count;
  }

  const faceCount = index.count / 3;
  const edges = new Map<string, Edge>();
  const neighbors = Array.from({length: weldPositions.length}, () => new Set<number>());
  for (let face = 0; face < faceCount; face++) {
    const originals = [index.getX(face * 3), index.getX(face * 3 + 1), index.getX(face * 3 + 2)];
    if (originals.some((vertex) => !Number.isInteger(vertex) || vertex < 0 || vertex >= vertexCount)) {
      throw new Error(`Triangle ${face} references an invalid vertex index.`);
    }
    const triangle = originals.map((vertex) => welded[vertex]) as [number, number, number];
    if (new Set(triangle).size !== 3) {
      throw new Error(`Triangle ${face} collapses after welding coincident UV-seam positions.`);
    }
    for (let corner = 0; corner < 3; corner++) {
      const a = triangle[corner];
      const b = triangle[(corner + 1) % 3];
      const opposite = triangle[(corner + 2) % 3];
      const key = edgeKey(a, b);
      const existing = edges.get(key);
      if (existing) {
        existing.opposites.push(opposite);
        if (existing.opposites.length > 2) {
          throw new Error(`Non-manifold topology: edge ${key} belongs to more than two triangles.`);
        }
      } else {
        edges.set(key, {a: Math.min(a, b), b: Math.max(a, b), opposites: [opposite]});
      }
      neighbors[a].add(b);
      neighbors[b].add(a);
    }
  }

  const boundaryNeighbors = Array.from({length: weldPositions.length}, () => new Set<number>());
  for (const edge of edges.values()) {
    if (edge.opposites.length === 1) {
      boundaryNeighbors[edge.a].add(edge.b);
      boundaryNeighbors[edge.b].add(edge.a);
    }
  }

  const jointCount = readJointCount(skinIndex, skinWeight, vertexCount);
  const weldedWeights = new Float64Array(weldPositions.length * jointCount);
  for (let vertex = 0; vertex < vertexCount; vertex++) {
    const id = welded[vertex];
    const offset = id * jointCount;
    for (let influence = 0; influence < 4; influence++) {
      const joint = skinIndex.getComponent(vertex, influence);
      const weight = skinWeight.getComponent(vertex, influence);
      if (!Number.isInteger(joint) || joint < 0 || joint >= jointCount || !Number.isFinite(weight) || weight < 0) {
        throw new Error(`Invalid skin influence at vertex ${vertex}.`);
      }
      weldedWeights[offset + joint] += weight / weldCounts[id];
    }
  }
  normalizeInfluenceRows(weldedWeights, weldPositions.length, jointCount);

  const nextPositions = new Array<Point3>(weldPositions.length);
  const nextWeights = new Float64Array(weldedWeights.length);
  for (let vertex = 0; vertex < weldPositions.length; vertex++) {
    const boundary = boundaryNeighbors[vertex];
    let coefficients: Array<[number, number]>;
    if (boundary.size > 0) {
      if (boundary.size !== 2) {
        throw new Error(`Ambiguous boundary topology at welded vertex ${vertex}: expected two boundary neighbors, found ${boundary.size}.`);
      }
      const [first, second] = boundary;
      coefficients = [[vertex, 0.75], [first, 0.125], [second, 0.125]];
    } else {
      const valence = neighbors[vertex].size;
      if (valence < 3) {
        throw new Error(`Ambiguous interior topology at welded vertex ${vertex}: valence ${valence}.`);
      }
      const beta = valence > 3 ? 3 / (8 * valence) : 3 / 16;
      coefficients = [[vertex, 1 - valence * beta]];
      for (const neighbor of neighbors[vertex]) coefficients.push([neighbor, beta]);
    }
    nextPositions[vertex] = weightedPoint(weldPositions, coefficients);
    blendInfluences(weldedWeights, jointCount, coefficients, nextWeights, vertex * jointCount);
  }

  const edgePositions = new Map<string, Point3>();
  const edgeWeights = new Map<string, Float64Array>();
  for (const [key, edge] of edges) {
    let coefficients: Array<[number, number]>;
    if (edge.opposites.length === 1) {
      coefficients = [[edge.a, 0.5], [edge.b, 0.5]];
    } else {
      coefficients = [[edge.a, 3 / 8], [edge.b, 3 / 8], [edge.opposites[0], 1 / 8], [edge.opposites[1], 1 / 8]];
    }
    edgePositions.set(key, weightedPoint(weldPositions, coefficients));
    const weights = new Float64Array(jointCount);
    blendInfluences(weldedWeights, jointCount, coefficients, weights, 0);
    edgeWeights.set(key, weights);
  }

  const output = geometry.clone();
  const outputPositions: number[] = [];
  const outputUvs: number[] = [];
  const outputSkinIndices: number[] = [];
  const outputSkinWeights: number[] = [];
  const outputIndices: number[] = [];
  const appendVertex = (point: Point3, u: number, v: number, influences: ArrayLike<number>) => {
    const vertex = outputPositions.length / 3;
    outputPositions.push(point[0], point[1], point[2]);
    outputUvs.push(u, v);
    appendTopFour(influences, jointCount, outputSkinIndices, outputSkinWeights);
    return vertex;
  };

  const originalOutputVertices = new Array<number>(vertexCount);
  for (let vertex = 0; vertex < vertexCount; vertex++) {
    const id = welded[vertex];
    originalOutputVertices[vertex] = appendVertex(
      nextPositions[id],
      uv.getX(vertex),
      uv.getY(vertex),
      nextWeights.subarray(id * jointCount, (id + 1) * jointCount),
    );
  }

  const originalEdgeVertices = new Map<string, number>();
  const edgeVertex = (a: number, b: number): number => {
    const key = edgeKey(a, b);
    const known = originalEdgeVertices.get(key);
    if (known !== undefined) return known;
    const weldedA = welded[a];
    const weldedB = welded[b];
    const topologicalKey = edgeKey(weldedA, weldedB);
    const point = edgePositions.get(topologicalKey);
    const influences = edgeWeights.get(topologicalKey);
    if (!point || !influences) {
      throw new Error(`Missing welded edge data for original edge ${key}.`);
    }
    const created = appendVertex(
      point,
      (uv.getX(a) + uv.getX(b)) / 2,
      (uv.getY(a) + uv.getY(b)) / 2,
      influences,
    );
    originalEdgeVertices.set(key, created);
    return created;
  };

  for (let face = 0; face < faceCount; face++) {
    const a = index.getX(face * 3);
    const b = index.getX(face * 3 + 1);
    const c = index.getX(face * 3 + 2);
    const ab = edgeVertex(a, b);
    const bc = edgeVertex(b, c);
    const ca = edgeVertex(c, a);
    outputIndices.push(
      originalOutputVertices[a], ab, ca,
      ab, originalOutputVertices[b], bc,
      ca, bc, originalOutputVertices[c],
      ab, bc, ca,
    );
  }

  output.setAttribute('position', new Float32BufferAttribute(outputPositions, 3));
  output.setAttribute('uv', new Float32BufferAttribute(outputUvs, 2));
  output.setAttribute('skinIndex', new Uint16BufferAttribute(outputSkinIndices, 4));
  output.setAttribute('skinWeight', new Float32BufferAttribute(outputSkinWeights, 4));
  output.setIndex(outputIndices);
  output.setAttribute('normal', computeWeldedNormals(outputPositions, outputIndices));

  output.clearGroups();
  for (const group of geometry.groups) {
    if (group.start % 3 !== 0 || group.count % 3 !== 0) {
      throw new Error('Geometry groups must start and end on triangle boundaries.');
    }
    output.addGroup(group.start * 4, group.count * 4, group.materialIndex);
  }
  const drawRange = geometry.drawRange;
  output.setDrawRange(drawRange.start * 4, drawRange.count === Infinity ? outputIndices.length : drawRange.count * 4);
  output.computeBoundingBox();
  output.computeBoundingSphere();
  return output;
}

function positionKey(point: Point3): string {
  return `${Math.round(point[0] / POSITION_EPSILON)},${Math.round(point[1] / POSITION_EPSILON)},${Math.round(point[2] / POSITION_EPSILON)}`;
}

function edgeKey(a: number, b: number): string {
  return a < b ? `${a}:${b}` : `${b}:${a}`;
}

function weightedPoint(points: Point3[], coefficients: Array<[number, number]>): Point3 {
  const result: Point3 = [0, 0, 0];
  for (const [vertex, weight] of coefficients) {
    result[0] += points[vertex][0] * weight;
    result[1] += points[vertex][1] * weight;
    result[2] += points[vertex][2] * weight;
  }
  return result;
}

function readJointCount(
  skinIndex: BufferAttribute | InterleavedBufferAttribute,
  skinWeight: BufferAttribute | InterleavedBufferAttribute,
  vertexCount: number,
): number {
  if (skinIndex.count !== vertexCount || skinWeight.count !== vertexCount) {
    throw new Error('Skin attribute counts must match the position count.');
  }
  let jointCount = 0;
  for (let vertex = 0; vertex < vertexCount; vertex++) {
    for (let influence = 0; influence < 4; influence++) {
      const joint = skinIndex.getComponent(vertex, influence);
      if (!Number.isInteger(joint) || joint < 0) throw new Error(`Invalid skin index at vertex ${vertex}.`);
      jointCount = Math.max(jointCount, joint + 1);
    }
  }
  return jointCount;
}

function normalizeInfluenceRows(weights: Float64Array, rowCount: number, jointCount: number): void {
  for (let row = 0; row < rowCount; row++) {
    const start = row * jointCount;
    let sum = 0;
    for (let joint = 0; joint < jointCount; joint++) sum += weights[start + joint];
    if (!Number.isFinite(sum) || sum <= 0) throw new Error(`Skin weights for welded vertex ${row} sum to zero.`);
    for (let joint = 0; joint < jointCount; joint++) weights[start + joint] /= sum;
  }
}

function blendInfluences(
  source: Float64Array,
  jointCount: number,
  coefficients: Array<[number, number]>,
  destination: Float64Array,
  destinationOffset: number,
): void {
  destination.fill(0, destinationOffset, destinationOffset + jointCount);
  for (const [vertex, factor] of coefficients) {
    const sourceOffset = vertex * jointCount;
    for (let joint = 0; joint < jointCount; joint++) {
      destination[destinationOffset + joint] += source[sourceOffset + joint] * factor;
    }
  }
  let sum = 0;
  for (let joint = 0; joint < jointCount; joint++) sum += destination[destinationOffset + joint];
  if (!Number.isFinite(sum) || sum <= 0) throw new Error('Subdivision produced an empty skin-weight row.');
  for (let joint = 0; joint < jointCount; joint++) destination[destinationOffset + joint] /= sum;
}

function appendTopFour(
  influences: ArrayLike<number>,
  jointCount: number,
  indices: number[],
  weights: number[],
): void {
  const best: Array<[number, number]> = [];
  for (let joint = 0; joint < jointCount; joint++) {
    const weight = influences[joint];
    if (weight > 0) {
      best.push([joint, weight]);
      best.sort((a, b) => b[1] - a[1]);
      if (best.length > 4) best.pop();
    }
  }
  const total = best.reduce((sum, [, weight]) => sum + weight, 0);
  if (!Number.isFinite(total) || total <= 0) throw new Error('Subdivision produced an empty skin-weight row.');
  for (let influence = 0; influence < 4; influence++) {
    const selected = best[influence];
    indices.push(selected?.[0] ?? 0);
    weights.push(selected ? selected[1] / total : 0);
  }
}

function computeWeldedNormals(positions: number[], indices: number[]): Float32BufferAttribute {
  const vertexCount = positions.length / 3;
  const sums = new Float64Array(vertexCount * 3);
  for (let offset = 0; offset < indices.length; offset += 3) {
    const a = indices[offset] * 3;
    const b = indices[offset + 1] * 3;
    const c = indices[offset + 2] * 3;
    const abx = positions[b] - positions[a];
    const aby = positions[b + 1] - positions[a + 1];
    const abz = positions[b + 2] - positions[a + 2];
    const acx = positions[c] - positions[a];
    const acy = positions[c + 1] - positions[a + 1];
    const acz = positions[c + 2] - positions[a + 2];
    const nx = aby * acz - abz * acy;
    const ny = abz * acx - abx * acz;
    const nz = abx * acy - aby * acx;
    for (const vertex of [a, b, c]) {
      sums[vertex] += nx;
      sums[vertex + 1] += ny;
      sums[vertex + 2] += nz;
    }
  }

  const weldedSums = new Map<string, [number, number, number]>();
  const keys = new Array<string>(vertexCount);
  for (let vertex = 0; vertex < vertexCount; vertex++) {
    const offset = vertex * 3;
    const point: Point3 = [positions[offset], positions[offset + 1], positions[offset + 2]];
    const key = positionKey(point);
    keys[vertex] = key;
    const total = weldedSums.get(key) ?? [0, 0, 0];
    total[0] += sums[offset];
    total[1] += sums[offset + 1];
    total[2] += sums[offset + 2];
    weldedSums.set(key, total);
  }

  const normals = new Float32Array(vertexCount * 3);
  for (let vertex = 0; vertex < vertexCount; vertex++) {
    const sum = weldedSums.get(keys[vertex])!;
    const magnitude = Math.hypot(sum[0], sum[1], sum[2]);
    if (!Number.isFinite(magnitude) || magnitude <= 1e-20) {
      throw new Error(`Unable to compute a finite normal at subdivided vertex ${vertex}.`);
    }
    normals[vertex * 3] = sum[0] / magnitude;
    normals[vertex * 3 + 1] = sum[1] / magnitude;
    normals[vertex * 3 + 2] = sum[2] / magnitude;
  }
  return new Float32BufferAttribute(normals, 3);
}
