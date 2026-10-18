import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {C, FONT} from '../lib/theme';
import {clamp, ease, seeded, smooth} from '../lib/math';
import {ActLabel} from './Visuals';

export const SEARCH_NODE_COUNT = 600;
export const PRUNED_NODE_COUNT = 576;
export const SEARCH_RADIUS = 350;

const CENTER_X = 960;
const CENTER_Y = 540;
const GOLDEN_ANGLE = (137.508 * Math.PI) / 180;
const RADIAL_SCALE = 0.97;
const EXPANSION_START = 24;
const EXPANSION_SPAN = 1780;
const PRUNE_DELAY_FRAMES = 45;
const PRUNE_FLASH_FRAMES = 45;
const PRUNE_FADE_FRAMES = 100;
const GOLD_REVEAL_START = 2020;
const GOLD_REVEAL_END = 2340;

export type SearchNode = {
  id: number;
  parentId: number | null;
  depth: number;
  angle: number;
  radius: number;
  x: number;
  y: number;
  spawnFrame: number;
  pruneFrame: number | null;
  survives: boolean;
};

const baseNodes: Omit<SearchNode, 'spawnFrame' | 'pruneFrame' | 'survives'>[] = [];
for (let id = 0; id < SEARCH_NODE_COUNT; id += 1) {
  const parentId = id === 0 ? null : Math.floor((id - 1) / 3);
  const depth = parentId === null ? 0 : baseNodes[parentId].depth + 1;
  const angle = id * GOLDEN_ANGLE;
  const radius = id === 0 ? 0 : SEARCH_RADIUS * RADIAL_SCALE * Math.sqrt(id / (SEARCH_NODE_COUNT - 1));
  baseNodes.push({
    id,
    parentId,
    depth,
    angle,
    radius,
    x: CENTER_X + Math.cos(angle) * radius,
    y: CENTER_Y + Math.sin(angle) * radius,
  });
}

const leafToRoot: number[] = [];
let goldCursor: number | null = SEARCH_NODE_COUNT - 1;
while (goldCursor !== null) {
  leafToRoot.push(goldCursor);
  goldCursor = baseNodes[goldCursor].parentId;
}

/** The sole highlighted root-to-leaf solution, ordered from root to leaf. */
export const GOLDEN_PATH: readonly number[] = [...leafToRoot].reverse();
const alternativeBranchRoot = 19;
const isInAlternativeBranch = (id: number): boolean => {
  let cursor: number | null = id;
  while (cursor !== null) {
    if (cursor === alternativeBranchRoot) return true;
    cursor = baseNodes[cursor].parentId;
  }
  return false;
};
const alternativeSurvivors = baseNodes
  .filter(({id}) => isInAlternativeBranch(id))
  .sort((a, b) => a.id - b.id)
  .slice(0, 17)
  .map(({id}) => id);
const survivorIds = new Set([...GOLDEN_PATH, ...alternativeSurvivors]);

const expansionOrder = [...baseNodes].sort((a, b) => {
  if (a.depth !== b.depth) return a.depth - b.depth;
  return seeded(a.id + 601) - seeded(b.id + 601);
});
const spawnFrameById = new Array<number>(SEARCH_NODE_COUNT);
expansionOrder.forEach(({id}, rank) => {
  spawnFrameById[id] = Math.round(EXPANSION_START + (rank / (SEARCH_NODE_COUNT - 1)) * EXPANSION_SPAN);
});

const prunedBaseNodes = baseNodes.filter(({id}) => !survivorIds.has(id));
const pruneFrameById = new Array<number | null>(SEARCH_NODE_COUNT).fill(null);
prunedBaseNodes.forEach(({id}) => {
  pruneFrameById[id] = spawnFrameById[id] + PRUNE_DELAY_FRAMES;
});

/** All 600 deterministic golden-angle nodes and their real ternary-tree parents. */
export const SEARCH_NODES: readonly SearchNode[] = baseNodes.map((node) => ({
  ...node,
  spawnFrame: spawnFrameById[node.id],
  pruneFrame: pruneFrameById[node.id],
  survives: survivorIds.has(node.id),
}));

const firstPruneFrame = Math.min(...prunedBaseNodes.map(({id}) => spawnFrameById[id] + PRUNE_DELAY_FRAMES));
const lastPruneFrame = Math.max(...prunedBaseNodes.map(({id}) => spawnFrameById[id] + PRUNE_DELAY_FRAMES));

export type SearchNodeVisualState = {
  spawned: boolean;
  pruned: boolean;
  flashing: boolean;
  finalized: boolean;
  fill: string;
  opacity: number;
  appearance: number;
  radiusScale: number;
};

/** Pure frame state for a node; pruned nodes start their red flash 45 frames after spawn. */
export const getSearchNodeVisualState = (node: SearchNode, frame: number): SearchNodeVisualState => {
  const sinceSpawn = frame - node.spawnFrame;
  const spawned = sinceSpawn >= 0;
  const appearance = smooth(clamp(sinceSpawn / 10));
  if (!spawned) {
    return {spawned, pruned: false, flashing: false, finalized: false, fill: C.cyan, opacity: 0, appearance, radiusScale: 1};
  }

  const pruneAge = node.pruneFrame === null ? -1 : frame - node.pruneFrame;
  const pruned = pruneAge >= 0;
  if (!pruned) {
    return {spawned, pruned, flashing: false, finalized: false, fill: C.cyan, opacity: appearance * 0.86, appearance, radiusScale: 1};
  }
  if (pruneAge < PRUNE_FLASH_FRAMES) {
    const flashT = pruneAge / PRUNE_FLASH_FRAMES;
    return {
      spawned,
      pruned,
      flashing: true,
      finalized: false,
      fill: C.red,
      opacity: 0.92 + Math.sin(flashT * Math.PI) * 0.08,
      appearance,
      radiusScale: 1 + 0.32 * Math.sin(flashT * Math.PI),
    };
  }

  const fadeT = smooth(clamp((pruneAge - PRUNE_FLASH_FRAMES) / PRUNE_FADE_FRAMES));
  const finalized = fadeT >= 1;
  return {
    spawned,
    pruned,
    flashing: false,
    finalized,
    fill: '#7f1d1d',
    opacity: finalized ? 0.06 : 0.72 - 0.66 * fadeT,
    appearance,
    radiusScale: 1,
  };
};

const goldRankById = new Map(GOLDEN_PATH.map((id, rank) => [id, rank]));
const goldEdgeIds = new Set(GOLDEN_PATH.slice(1).map((id) => {
  const parentId = SEARCH_NODES[id].parentId;
  return `${parentId}-${id}`;
}));
const goldPathD = GOLDEN_PATH.map((id, rank) => {
  const node = SEARCH_NODES[id];
  return `${rank === 0 ? 'M' : 'L'} ${node.x.toFixed(2)} ${node.y.toFixed(2)}`;
}).join(' ');
const goldPathLength = GOLDEN_PATH.slice(1).reduce((total, id, rank) => {
  const child = SEARCH_NODES[id];
  const parent = SEARCH_NODES[GOLDEN_PATH[rank]];
  return total + Math.hypot(child.x - parent.x, child.y - parent.y);
}, 0);

const metricLabel: React.CSSProperties = {
  fill: C.muted,
  fontFamily: FONT,
  fontSize: 11,
  letterSpacing: 1.7,
};

const MetricBar: React.FC<{x: number; y: number; width: number; value: number; color: string}> = ({x, y, width, value, color}) => (
  <g>
    <rect x={x} y={y} width={width} height={3} rx={1.5} fill="rgba(148,184,211,0.13)" />
    <rect x={x} y={y} width={width * clamp(value)} height={3} rx={1.5} fill={color} opacity={0.8} />
  </g>
);

export const Act2BreadthMCTS: React.FC = () => {
  const frame = useCurrentFrame();
  const goldT = ease(frame, GOLD_REVEAL_START, GOLD_REVEAL_END);
  const orbit = (frame * 0.22) % 360;
  const nodeElements: React.ReactNode[] = [];
  let activeSimulations = 0;
  let branchesPruned = 0;
  let spawnedCount = 0;

  for (const node of SEARCH_NODES) {
    const visual = getSearchNodeVisualState(node, frame);
    if (!visual.spawned) continue;
    spawnedCount += 1;
    const appearance = visual.appearance;
    if (visual.pruned) branchesPruned += 1;
    else activeSimulations += 1;

    let fill: string = visual.fill;
    let nodeOpacity = visual.opacity;
    let nodeRadius = (node.id === 0 ? 7 : 2.15 + seeded(node.id + 901) * 1.2) * visual.radiusScale;
    let stroke: string = visual.pruned ? C.red : C.white;
    let strokeOpacity = visual.pruned ? visual.opacity : (node.id === 0 ? 0.72 : 0.22) * appearance;

    if (!visual.pruned && goldRankById.has(node.id)) {
      const rank = goldRankById.get(node.id) ?? 0;
      const nodeGoldT = ease(frame, GOLD_REVEAL_START + rank * 32, GOLD_REVEAL_START + rank * 32 + 48);
      if (nodeGoldT > 0.35) fill = C.gold;
      nodeRadius += nodeGoldT * (node.id === 0 ? 1.4 : 0.9);
      stroke = C.gold;
      strokeOpacity = 0.3 + 0.62 * nodeGoldT;
    }

    if (node.parentId !== null) {
      const parent = SEARCH_NODES[node.parentId];
      const edgeKey = `${parent.id}-${node.id}`;
      const isGoldEdge = goldEdgeIds.has(edgeKey);
      let edgeColor: string = C.cyan;
      let edgeOpacity = 0.105 * appearance;
      let edgeWidth = 0.8;
      if (visual.flashing) {
        edgeColor = C.red;
        edgeOpacity = 0.28 * appearance;
      } else if (visual.pruned) {
        edgeColor = '#8c2531';
        edgeOpacity = visual.opacity;
      }
      if (isGoldEdge && goldT > 0) {
        edgeColor = C.gold;
        edgeOpacity = 0.18 + goldT * 0.22;
        edgeWidth = 1.5;
      }
      nodeElements.push(
        <line
          key={`edge-${node.id}`}
          x1={parent.x}
          y1={parent.y}
          x2={node.x}
          y2={node.y}
          stroke={edgeColor}
          strokeWidth={edgeWidth}
          strokeOpacity={edgeOpacity}
        />,
      );
    }

    nodeElements.push(
      <circle
        key={`node-${node.id}`}
        cx={node.x}
        cy={node.y}
        r={nodeRadius}
        fill={fill}
        fillOpacity={nodeOpacity}
        stroke={stroke}
        strokeOpacity={strokeOpacity}
        strokeWidth={node.id === 0 ? 1.4 : 0.65}
      />,
    );
  }

  const hasPruningStarted = branchesPruned > 0;
  const expansionComplete = spawnedCount === SEARCH_NODE_COUNT;
  const pruningComplete = branchesPruned === PRUNED_NODE_COUNT && frame >= lastPruneFrame;
  const verifierConfidence = 0.2 + 0.76 * ease(frame, firstPruneFrame, GOLD_REVEAL_END);
  const phase = frame >= GOLD_REVEAL_END
    ? 'VERIFIED FUTURE'
    : frame >= GOLD_REVEAL_START
      ? 'RESOLVING GOLDEN PATH'
      : !hasPruningStarted
        ? 'EXPANDING SEARCH TREE'
        : !expansionComplete
          ? 'EXPANDING / PRUNING'
          : !pruningComplete
            ? 'PRUNING SEARCH SPACE'
            : 'VERIFYING SURVIVORS';
  const phaseColor = hasPruningStarted && !pruningComplete ? C.red : frame >= GOLD_REVEAL_START ? C.gold : C.cyan;
  const toastOne = ease(frame, 1110, 1130) * (1 - ease(frame, 1255, 1280));
  const toastTwo = ease(frame, 1480, 1500) * (1 - ease(frame, 1650, 1672));
  const expansionProgress = spawnedCount / SEARCH_NODE_COUNT;
  const normalizedPruned = branchesPruned / SEARCH_NODE_COUNT;

  return (
    <AbsoluteFill style={{backgroundColor: 'transparent', overflow: 'hidden'}}>
      <ActLabel number="02" title="A million possible futures." kicker="BREADTH / SEARCH SPACE" />
      <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
        <defs>
          <radialGradient id="act2-search-core">
            <stop offset="0" stopColor={C.cyan} stopOpacity="0.10" />
            <stop offset="1" stopColor={C.cyan} stopOpacity="0" />
          </radialGradient>
          <filter id="act2-gold-glow" x="-25%" y="-25%" width="150%" height="150%">
            <feGaussianBlur stdDeviation="4" />
          </filter>
        </defs>

        <circle cx={CENTER_X} cy={CENTER_Y} r={SEARCH_RADIUS * RADIAL_SCALE} fill="url(#act2-search-core)" />
        {[0.2, 0.4, 0.6, 0.8, 0.97].map((scale, index) => (
          <circle
            key={`ring-${index}`}
            cx={CENTER_X}
            cy={CENTER_Y}
            r={SEARCH_RADIUS * scale}
            fill="none"
            stroke={index === 4 ? C.cyan : C.white}
            strokeOpacity={index === 4 ? 0.16 : 0.055}
            strokeWidth={index === 4 ? 1 : 0.7}
            strokeDasharray={index === 4 ? '2 8' : undefined}
          />
        ))}
        <circle
          cx={CENTER_X}
          cy={CENTER_Y}
          r={SEARCH_RADIUS * RADIAL_SCALE}
          fill="none"
          stroke={C.cyan}
          strokeOpacity="0.18"
          strokeWidth="1"
          strokeDasharray="28 620"
          strokeDashoffset={-frame * 0.7}
          transform={`rotate(${orbit} ${CENTER_X} ${CENTER_Y})`}
        />
        <line x1={CENTER_X - 12} y1={CENTER_Y} x2={CENTER_X + 12} y2={CENTER_Y} stroke={C.white} strokeOpacity="0.3" />
        <line x1={CENTER_X} y1={CENTER_Y - 12} x2={CENTER_X} y2={CENTER_Y + 12} stroke={C.white} strokeOpacity="0.3" />

        <g>{nodeElements}</g>

        <path
          d={goldPathD}
          fill="none"
          stroke={C.gold}
          strokeWidth="9"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeOpacity={goldT * (0.24 + Math.sin(frame / 18) * 0.06)}
          strokeDasharray={`${goldPathLength} ${goldPathLength}`}
          strokeDashoffset={goldPathLength * (1 - goldT)}
          filter="url(#act2-gold-glow)"
        />
        <path
          d={goldPathD}
          fill="none"
          stroke={C.gold}
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeOpacity={goldT * (0.9 + Math.sin(frame / 18) * 0.1)}
          strokeDasharray={`${goldPathLength} ${goldPathLength}`}
          strokeDashoffset={goldPathLength * (1 - goldT)}
        />
        <circle cx={CENTER_X} cy={CENTER_Y} r="12" fill="none" stroke={C.cyan} strokeOpacity="0.24" strokeWidth="1" />
        <text x={CENTER_X + 20} y={CENTER_Y - 15} fill={C.white} opacity="0.56" fontFamily={FONT} fontSize="10" letterSpacing="1.4">ROOT / MCTS</text>
        <text x={CENTER_X + 269} y={CENTER_Y + 207} fill={C.muted} opacity="0.55" fontFamily={FONT} fontSize="9" letterSpacing="1.2">R = 350</text>

        <g opacity={toastOne} transform="translate(1110 362)">
          <rect width="276" height="27" rx="2" fill={C.red} fillOpacity="0.07" stroke={C.red} strokeOpacity="0.34" />
          <text x="12" y="18" fill={C.red} fontFamily={FONT} fontSize="9" letterSpacing="0.7">[PRUNED: THERMAL RUNAWAY]</text>
        </g>
        <g opacity={toastTwo} transform="translate(675 773)">
          <rect width="276" height="27" rx="2" fill={C.red} fillOpacity="0.07" stroke={C.red} strokeOpacity="0.34" />
          <text x="12" y="18" fill={C.red} fontFamily={FONT} fontSize="9" letterSpacing="0.7">[PRUNED: THERMAL RUNAWAY]</text>
        </g>

        <g transform="translate(1490 350)">
          <path d="M0 0H320 M0 0V480 M0 480H320" fill="none" stroke={C.line} strokeWidth="1" />
          <text x="0" y="24" fill={C.cyan} fontFamily={FONT} fontSize="11" letterSpacing="2">SEARCH TELEMETRY</text>
          <text x="320" y="24" textAnchor="end" fill={phaseColor} fontFamily={FONT} fontSize="9" letterSpacing="1">{phase}</text>
          <line x1="0" y1="42" x2="320" y2="42" stroke={C.line} />

          <text x="0" y="77" style={metricLabel}>ACTIVE SIMULATIONS</text>
          <text x="0" y="119" fill={C.white} fontFamily={FONT} fontSize="35" fontWeight="500">{activeSimulations.toString().padStart(3, '0')}</text>
          <text x="320" y="116" textAnchor="end" fill={C.muted} fontFamily={FONT} fontSize="10">LIVE / 600</text>
          <MetricBar x={0} y={136} width={320} value={activeSimulations / SEARCH_NODE_COUNT} color={C.cyan} />

          <text x="0" y="183" style={metricLabel}>BRANCHES PRUNED</text>
          <text x="0" y="225" fill={C.red} fontFamily={FONT} fontSize="35" fontWeight="500">{branchesPruned.toString().padStart(3, '0')}</text>
          <text x="320" y="222" textAnchor="end" fill={C.muted} fontFamily={FONT} fontSize="10">{Math.round(normalizedPruned * 100)}% / TARGET 96%</text>
          <MetricBar x={0} y={242} width={320} value={normalizedPruned} color={C.red} />

          <text x="0" y="289" style={metricLabel}>VERIFIER CONFIDENCE</text>
          <text x="0" y="331" fill={C.gold} fontFamily={FONT} fontSize="35" fontWeight="500">{Math.round(verifierConfidence * 100)}%</text>
          <text x="320" y="328" textAnchor="end" fill={C.muted} fontFamily={FONT} fontSize="10">{goldT > 0.9 ? 'PATH LOCKED' : 'INFERENCE'}</text>
          <MetricBar x={0} y={348} width={320} value={verifierConfidence} color={C.gold} />

          <line x1="0" y1="382" x2="320" y2="382" stroke={C.line} />
          <text x="0" y="407" fill={C.muted} fontFamily={FONT} fontSize="9" letterSpacing="1.3">TREE EXPANSION</text>
          <MetricBar x={0} y={419} width={320} value={expansionProgress} color={C.cyan} />
          <text x="0" y="452" fill={C.muted} fontFamily={FONT} fontSize="9" letterSpacing="1.3">BREADTH FIRST / TERNARY</text>
          <text x="320" y="452" textAnchor="end" fill={C.white} opacity="0.62" fontFamily={FONT} fontSize="9">{SEARCH_NODE_COUNT} NODES</text>
        </g>
      </svg>
    </AbsoluteFill>
  );
};

export default Act2BreadthMCTS;
