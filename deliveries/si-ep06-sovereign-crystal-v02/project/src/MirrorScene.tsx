import React, { useMemo } from 'react';
import * as THREE from 'three';
import {
  clamp,
  lorenzDelayCoordinates,
  smoothstep,
  syntheticReconstructionCoordinates,
} from './math';
import { Floor, Tube } from './Stage';

const GOLD = '#d6ab61';
const CYAN = '#76d7df';
const TRACE_POINTS = 421;
const HISTORY_FRAMES = 700;

type TraceSet = {
  reference: THREE.Vector3[];
  reconstruction: THREE.Vector3[];
};

const toWorld = (point: { x: number; y: number; z: number }, scale: number): THREE.Vector3 =>
  new THREE.Vector3(point.x * scale, point.y * scale, point.z * scale);

function buildTraces(globalFrame: number, reveal: number, worldScale: number): TraceSet {
  const available = Math.max(2, Math.round((TRACE_POINTS - 1) * reveal) + 1);
  const start = globalFrame - HISTORY_FRAMES;
  const reference: THREE.Vector3[] = [];
  const reconstruction: THREE.Vector3[] = [];

  for (let index = 0; index < available; index += 1) {
    const progress = index / (available - 1);
    const sampleFrame = Math.round(start + progress * HISTORY_FRAMES);
    reference.push(toWorld(lorenzDelayCoordinates(sampleFrame), worldScale));
    // Use this scene's current global frame for the error magnitude. Each
    // matching delay-coordinate sample then converges at global frame 3120.
    reconstruction.push(
      toWorld(syntheticReconstructionCoordinates(sampleFrame, globalFrame), worldScale),
    );
  }

  return { reference, reconstruction };
}

/** Paired delay-coordinate histories for local frames 0..1799 (global 1800..3599). */
export const MirrorScene: React.FC<{ frame: number }> = ({ frame }) => {
  const localFrame = Math.floor(clamp(frame, 0, 1799));
  const globalFrame = 1800 + localFrame;
  const reveal = 0.2 + 0.8 * smoothstep(localFrame / 108);
  // Shared presentation zoom fits the initially larger synthetic residual,
  // then lets both traces fill the glass. Their relative geometry is unchanged.
  const worldScale = 0.027 + 0.038 * smoothstep(localFrame / 180);

  const traces = useMemo(
    () => buildTraces(globalFrame, reveal, worldScale),
    [globalFrame, reveal, worldScale],
  );

  const referenceHead = traces.reference[traces.reference.length - 1];
  const reconstructionHead = traces.reconstruction[traces.reconstruction.length - 1];
  const gentleTurn = Math.sin(localFrame / 540) * 0.045;

  return (
    <>
      <Floor y={-1.72} color="#111820" />

      {/* One quiet glass volume holds both histories in the same space. */}
      <group position={[1.1, 0, 0]} rotation={[0, gentleTurn, 0]}>
        <mesh scale={[1.62, 1.62, 1.62]} renderOrder={1}>
          <sphereGeometry args={[1, 72, 48]} />
          <meshPhysicalMaterial
            color="#f6faf8"
            roughness={0.035}
            metalness={0}
            transmission={0.98}
            thickness={0.055}
            ior={1.38}
            envMapIntensity={0.45}
            clearcoat={0.2}
            clearcoatRoughness={0.12}
          />
        </mesh>

        <Tube points={traces.reference} radius={0.018} color={GOLD} emission={0.2} />
        <Tube points={traces.reconstruction} radius={0.014} color={CYAN} emission={0.22} />

        <mesh position={referenceHead}>
          <sphereGeometry args={[0.043, 20, 14]} />
          <meshPhysicalMaterial
            color="#f3d294"
            emissive="#b7833c"
            emissiveIntensity={0.24}
            metalness={0.62}
            roughness={0.2}
          />
        </mesh>
        <mesh position={reconstructionHead}>
          <sphereGeometry args={[0.036, 20, 14]} />
          <meshPhysicalMaterial
            color="#b6f0f1"
            emissive="#50b9c3"
            emissiveIntensity={0.27}
            metalness={0.28}
            roughness={0.18}
          />
        </mesh>
      </group>

      {/* A low fixed foot keeps the sculpture grounded without adding UI. */}
      <group position={[1.1, -1.67, 0]}>
        <mesh castShadow receiveShadow>
          <cylinderGeometry args={[1.48, 1.4, 0.1, 96]} />
          <meshStandardMaterial color="#313a42" metalness={0.63} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.052, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.28, 1.34, 96]} />
          <meshStandardMaterial
            color={GOLD}
            emissive={GOLD}
            emissiveIntensity={0.1}
            metalness={0.72}
            roughness={0.25}
          />
        </mesh>
      </group>
    </>
  );
};
