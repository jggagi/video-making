import React, { useLayoutEffect, useMemo } from 'react';
import * as THREE from 'three';
import {
  authoredChoicePath,
  choicePotential,
  integrateChoicePath,
  mix,
  smoothstep,
} from './math';
import { Floor, Tube } from './Stage';

const gold = '#d6ab61';
const coffeeFloorY = -0.32;
const choiceStartFrame = 1200;
const choiceTerrainBucket = 12;

const clampFrame = (frame: number, lastFrame: number): number =>
  Math.max(0, Math.min(lastFrame, Math.floor(frame)));

const handShape = (): THREE.Shape => {
  const shape = new THREE.Shape();
  shape.moveTo(-2.4, -0.32);
  shape.bezierCurveTo(-1.6, -0.3, -1.5, -0.35, -1.1, -0.29);
  shape.bezierCurveTo(-0.83, -0.64, -0.43, -0.8, -0.07, -0.77);
  shape.bezierCurveTo(0.25, -0.76, 0.23, -0.61, 0.04, -0.57);
  shape.lineTo(-0.35, -0.48);
  shape.bezierCurveTo(-0.04, -0.43, 0.43, -0.42, 0.8, -0.37);
  shape.bezierCurveTo(1.04, -0.33, 0.98, -0.18, 0.77, -0.18);
  shape.lineTo(0.08, -0.17);
  shape.lineTo(0.9, -0.07);
  shape.bezierCurveTo(1.13, -0.03, 1.08, 0.12, 0.85, 0.12);
  shape.lineTo(0.06, 0.05);
  shape.lineTo(0.71, 0.25);
  shape.bezierCurveTo(0.92, 0.31, 0.81, 0.46, 0.62, 0.41);
  shape.lineTo(-0.02, 0.26);
  shape.lineTo(0.38, 0.49);
  shape.bezierCurveTo(0.54, 0.6, 0.42, 0.71, 0.26, 0.62);
  shape.lineTo(-0.47, 0.31);
  shape.bezierCurveTo(-0.76, 0.3, -0.94, 0.22, -1.13, 0.13);
  shape.lineTo(-2.4, 0.2);
  shape.closePath();
  return shape;
};

type ReachPose = { x: number; z: number; lift: number; yaw: number };

const reachPoseAt = (frame: number): ReachPose => {
  const cycle = ((frame % 420) + 420) % 420;
  let progress = 0;
  if (cycle < 150) progress = smoothstep(cycle / 150);
  else if (cycle < 225) progress = 1;
  else if (cycle < 360) progress = 1 - smoothstep((cycle - 225) / 135);

  return {
    x: -0.45 + progress * 1.02 + Math.sin(progress * Math.PI) * 0.07,
    z: 2.25 - progress * 0.45,
    lift: 0.055 + Math.sin(progress * Math.PI) * 0.035,
    yaw: -0.25 + Math.sin(progress * Math.PI) * 0.055,
  };
};

/** The pre-echo cup scene. All movement is derived from the act-local frame. */
export const CoffeeScene: React.FC<{ frame: number }> = ({ frame }) => {
  const currentFrame = clampFrame(frame, 1259);
  const cup = useMemo(
    () =>
      new THREE.LatheGeometry(
        [
          [0.04, 0.04], [0.55, 0.04], [0.61, 0.08], [0.64, 0.15], [0.69, 0.98], [0.68, 1.04],
          [0.65, 1.06], [0.62, 1.02], [0.59, 0.24], [0.54, 0.19], [0.04, 0.19],
        ].map(([x, y]) => new THREE.Vector2(x, y)),
        96,
      ),
    [],
  );
  const saucer = useMemo(
    () =>
      new THREE.LatheGeometry(
        [
          [0.03, 0], [0.68, 0], [1, 0.06], [1.08, 0.12], [1.08, 0.15], [1.01, 0.17], [0.7, 0.08], [0.03, 0.06],
        ].map(([x, y]) => new THREE.Vector2(x, y)),
        96,
      ),
    [],
  );
  const silhouette = useMemo(handShape, []);
  const shadowGeometry = useMemo(() => new THREE.ShapeGeometry(silhouette, 32), [silhouette]);
  const handGeometry = useMemo(
    () =>
      new THREE.ExtrudeGeometry(silhouette, {
        depth: 0.11,
        bevelEnabled: true,
        bevelSegments: 3,
        steps: 1,
        bevelSize: 0.045,
        bevelThickness: 0.035,
        curveSegments: 32,
      }),
    [silhouette],
  );
  const steam = useMemo(
    () =>
      Array.from({ length: 3 }, (_, i) =>
        Array.from({ length: 40 }, (_, j) => {
          const t = j / 39;
          return new THREE.Vector3(
            0.06 + Math.sin(t * 6 + i * 1.9) * 0.13,
            0.99 + t * 1.05,
            (i - 1) * 0.1 + Math.cos(t * 5) * 0.07,
          );
        }),
      ),
    [],
  );

  useLayoutEffect(
    () => () => {
      cup.dispose();
      saucer.dispose();
      shadowGeometry.dispose();
      handGeometry.dispose();
    },
    [cup, saucer, shadowGeometry, handGeometry],
  );

  const steamPhase = currentFrame * (Math.PI * 2 / 420);
  const cupYaw = -0.22 + Math.sin(currentFrame * (Math.PI * 2 / 680)) * 0.025;
  const handPose = reachPoseAt(currentFrame);
  const shadowPose = reachPoseAt(currentFrame + 30);

  return (
    <>
      <Floor y={coffeeFloorY} color="#25282b" />
      <group position={[1.2, -0.27, -0.2]} scale={1.55} rotation={[0, cupYaw, 0]}>
        <mesh geometry={saucer} castShadow receiveShadow>
          <meshPhysicalMaterial color="#e4ddd0" roughness={0.24} clearcoat={0.7} clearcoatRoughness={0.18} />
        </mesh>
        <group position={[0, 0.1, 0]}>
          <mesh geometry={cup} castShadow receiveShadow>
            <meshPhysicalMaterial color="#e5ded1" roughness={0.2} clearcoat={0.8} clearcoatRoughness={0.18} />
          </mesh>
          <mesh position={[0.86, 0.59, 0]} castShadow>
            <torusGeometry args={[0.36, 0.085, 20, 64]} />
            <meshPhysicalMaterial color="#e2dacd" roughness={0.22} clearcoat={0.8} />
          </mesh>
          <mesh position={[0, 0.96, 0]}>
            <cylinderGeometry args={[0.627, 0.627, 0.012, 96]} />
            <meshPhysicalMaterial color="#170a03" roughness={0.32} clearcoat={0.25} clearcoatRoughness={0.12} envMapIntensity={0.18} />
          </mesh>
          <mesh position={[0, 1.045, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.65, 0.009, 8, 96]} />
            <meshStandardMaterial color="#f4ede0" roughness={0.19} />
          </mesh>
          {steam.map((points, index) => {
            const phase = steamPhase + index * 1.9;
            return (
              <group
                key={index}
                position={[Math.sin(phase) * 0.045, 0, Math.cos(phase * 0.83) * 0.025]}
                rotation={[0, Math.sin(phase * 0.7) * 0.045, Math.sin(phase) * 0.035]}
              >
                <Tube points={points} radius={0.008} color="#d6d6ca" opacity={0.12} emission={0} />
              </group>
            );
          })}
        </group>
      </group>

      {/* Explicit thought-experiment projection, not a measured neural signal. */}
      <mesh
        geometry={shadowGeometry}
        rotation={[-Math.PI / 2, 0, shadowPose.yaw]}
        position={[shadowPose.x, coffeeFloorY + 0.009, shadowPose.z]}
        scale={1.12}
      >
        <meshBasicMaterial color="#5b9296" transparent opacity={0.32} depthWrite={false} />
      </mesh>
      <mesh
        geometry={handGeometry}
        rotation={[-Math.PI / 2, 0, handPose.yaw]}
        position={[handPose.x, coffeeFloorY + handPose.lift, handPose.z]}
        scale={1.12}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial color="#e6e1d6" roughness={0.72} metalness={0} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[1.1, -0.306, -0.1]}>
        <ringGeometry args={[1.72, 1.735, 128]} />
        <meshBasicMaterial color="#a4b0a9" transparent opacity={0.24} />
      </mesh>
    </>
  );
};

const heightAt = (x: number, z: number, nudge: number): number =>
  Math.atan(choicePotential(x, z, true, nudge) * 0.24) * 0.62;

const nudgeAt = (frame: number): number => smoothstep(frame / choiceStartFrame);

const sampleSurface = (geometry: THREE.BufferGeometry, nudge: number): Float32Array => {
  const position = geometry.getAttribute('position') as THREE.BufferAttribute;
  const heights = new Float32Array(position.count);
  for (let i = 0; i < position.count; i += 1) {
    heights[i] = heightAt(position.getX(i), position.getZ(i), nudge);
  }
  return heights;
};

type SurfaceEdgeVertex = { index: number; x: number; z: number };

const makeSkirt = (): { geometry: THREE.BufferGeometry; edgeVertices: SurfaceEdgeVertex[] } => {
  const boundary: THREE.Vector3[] = [];
  for (let i = 0; i <= 110; i += 1) boundary.push(new THREE.Vector3(-4.4 + (i / 110) * 8.8, 0, -3.7));
  for (let i = 1; i <= 92; i += 1) boundary.push(new THREE.Vector3(4.4, 0, -3.7 + (i / 92) * 7.4));
  for (let i = 1; i <= 110; i += 1) boundary.push(new THREE.Vector3(4.4 - (i / 110) * 8.8, 0, 3.7));
  for (let i = 1; i <= 92; i += 1) boundary.push(new THREE.Vector3(-4.4, 0, 3.7 - (i / 92) * 7.4));

  const positions: number[] = [];
  const edgeVertices: SurfaceEdgeVertex[] = [];
  const pushPoint = (point: THREE.Vector3, movesWithSurface = false) => {
    const index = positions.length / 3;
    positions.push(point.x, point.y, point.z);
    if (movesWithSurface) edgeVertices.push({ index, x: point.x, z: point.z });
  };

  for (let i = 0; i < boundary.length - 1; i += 1) {
    const a = boundary[i];
    const b = boundary[i + 1];
    const lowA = new THREE.Vector3(a.x, -1.22, a.z);
    const lowB = new THREE.Vector3(b.x, -1.22, b.z);
    pushPoint(a, true);
    pushPoint(b, true);
    pushPoint(lowA);
    pushPoint(b, true);
    pushPoint(lowB);
    pushPoint(lowA);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  return { geometry, edgeVertices };
};

type HeightPair = { first: Float32Array; second: Float32Array };
type RoutePoint = { x: number; z: number; y: number };

const interpolatedPoints = (a: RoutePoint[], b: RoutePoint[], amount: number): THREE.Vector3[] =>
  a.map((point, index) => {
    const next = b[index];
    return new THREE.Vector3(
      mix(point.x, next.x, amount),
      mix(point.y, next.y, amount),
      mix(point.z, next.z, amount),
    );
  });

const sphereProgressAt = (frame: number): number => {
  const cycle = frame % 420;
  if (cycle < 180) return smoothstep(cycle / 180);
  if (cycle < 210) return 1;
  if (cycle < 390) return 1 - smoothstep((cycle - 210) / 180);
  return 0;
};

/** The choice landscape with a gradual preference nudge and a traversing toy path. */
export const ChoiceScene: React.FC<{ frame: number }> = ({ frame }) => {
  const currentFrame = clampFrame(frame, 1799);
  const bucketStart = Math.floor(currentFrame / choiceTerrainBucket) * choiceTerrainBucket;
  const bucketEnd = bucketStart + choiceTerrainBucket;
  const blend = (currentFrame - bucketStart) / choiceTerrainBucket;
  const firstNudge = nudgeAt(bucketStart);
  const secondNudge = nudgeAt(bucketEnd);

  const terrain = useMemo(() => {
    const geometry = new THREE.PlaneGeometry(8.8, 7.4, 110, 92);
    geometry.rotateX(-Math.PI / 2);
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(geometry.getAttribute('position').count * 3), 3));
    return geometry;
  }, []);
  const skirt = useMemo(makeSkirt, []);
  const terrainHeights = useMemo<HeightPair>(
    () => ({ first: sampleSurface(terrain, firstNudge), second: sampleSurface(terrain, secondNudge) }),
    [terrain, bucketStart],
  );
  const skirtHeights = useMemo<HeightPair>(
    () => ({
      first: Float32Array.from(skirt.edgeVertices, ({ x, z }) => heightAt(x, z, firstNudge)),
      second: Float32Array.from(skirt.edgeVertices, ({ x, z }) => heightAt(x, z, secondNudge)),
    }),
    [skirt, bucketStart],
  );
  const authoredBases = useMemo(
    () => Array.from({ length: 10 }, (_, branch) => authoredChoicePath(branch, 60).map(({ x, y }) => ({ x, z: y }))),
    [],
  );
  const authoredHeightPairs = useMemo(
    () =>
      authoredBases.map((path) => ({
        first: path.map(({ x, z }) => heightAt(x, z, firstNudge) + 0.025),
        second: path.map(({ x, z }) => heightAt(x, z, secondNudge) + 0.025),
      })),
    [authoredBases, bucketStart],
  );
  const drivenPathPairs = useMemo(() => {
    const createPath = (nudge: number): RoutePoint[] =>
      integrateChoicePath(1, true, nudge, 100).map(({ x, y }) => ({
        x,
        z: y,
        y: heightAt(x, y, nudge) + 0.06,
      }));
    return { first: createPath(firstNudge), second: createPath(secondNudge) };
  }, [bucketStart]);

  useLayoutEffect(() => {
    const position = terrain.getAttribute('position') as THREE.BufferAttribute;
    const color = terrain.getAttribute('color') as THREE.BufferAttribute;
    const base = new THREE.Color('#56636c');
    const peak = new THREE.Color('#c4c4b5');
    const sampleColor = new THREE.Color();

    for (let i = 0; i < position.count; i += 1) {
      const y = mix(terrainHeights.first[i], terrainHeights.second[i], blend);
      position.setY(i, y);
      sampleColor.copy(base).lerp(peak, (y + 1) / 2);
      color.setXYZ(i, sampleColor.r, sampleColor.g, sampleColor.b);
    }
    position.needsUpdate = true;
    color.needsUpdate = true;
    terrain.computeVertexNormals();

    const skirtPosition = skirt.geometry.getAttribute('position') as THREE.BufferAttribute;
    for (let i = 0; i < skirt.edgeVertices.length; i += 1) {
      const edge = skirt.edgeVertices[i];
      skirtPosition.setY(edge.index, mix(skirtHeights.first[i], skirtHeights.second[i], blend));
    }
    skirtPosition.needsUpdate = true;
    skirt.geometry.computeVertexNormals();
  }, [terrain, terrainHeights, skirt, skirtHeights, blend]);

  useLayoutEffect(
    () => () => {
      terrain.dispose();
      skirt.geometry.dispose();
    },
    [terrain, skirt],
  );

  const authoredPaths = authoredBases.map((path, branch) =>
    path.map(({ x, z }, index) =>
      new THREE.Vector3(x, mix(authoredHeightPairs[branch].first[index], authoredHeightPairs[branch].second[index], blend), z),
    ),
  );
  const drivenPath = interpolatedPoints(drivenPathPairs.first, drivenPathPairs.second, blend);
  const progress = sphereProgressAt(currentFrame);
  const drivenCurve = useMemo(() => new THREE.CatmullRomCurve3(drivenPath), [drivenPath]);
  const ball = drivenCurve.getPoint(progress);
  const groupYaw = -0.22 + Math.sin(currentFrame * 0.001) * 0.035;

  return (
    <>
      <Floor y={-1.65} />
      <group position={[1.1, -0.5, 0]} rotation={[0, groupYaw, 0]} scale={0.59}>
        <mesh geometry={terrain} castShadow receiveShadow>
          <meshStandardMaterial vertexColors roughness={0.53} metalness={0.28} side={THREE.DoubleSide} />
        </mesh>
        <mesh geometry={skirt.geometry} castShadow receiveShadow>
          <meshStandardMaterial color="#313b43" metalness={0.25} roughness={0.55} side={THREE.DoubleSide} />
        </mesh>
        {authoredPaths.map((points, index) => (
          <Tube key={index} points={points} radius={0.009} color="#a1b0ae" emission={0} opacity={0.35} />
        ))}
        <Tube points={drivenPath} radius={0.031} color={gold} emission={0.32} />
        <mesh position={ball} castShadow>
          <sphereGeometry args={[0.18, 48, 32]} />
          <meshPhysicalMaterial color="#c68b31" metalness={0.8} roughness={0.19} clearcoat={0.8} />
        </mesh>
        <pointLight position={[ball.x, ball.y + 0.4, ball.z]} intensity={0.32} color="#e8b967" distance={2} />
      </group>
    </>
  );
};
