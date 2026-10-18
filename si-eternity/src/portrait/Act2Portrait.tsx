import React from 'react';
import {useCurrentFrame} from 'remotion';
import {
  GOLDEN_PATH,
  PRUNED_NODE_COUNT,
  SEARCH_NODES,
  SEARCH_NODE_COUNT,
  SEARCH_RADIUS,
  getSearchNodeVisualState,
} from '../components/Act2BreadthMCTS';
import {C, FONT} from '../lib/theme';
import {clamp, ease, seeded} from '../lib/math';
import {PortraitHeading, PortraitPanel, PORTRAIT_FONT} from './PortraitElements';

const GRAPH_CENTER_X = 960;
const GRAPH_CENTER_Y = 540;
const PORTRAIT_CENTER_X = 520;
const PORTRAIT_CENTER_Y = 850;
const GRAPH_SCALE = 1.1;
const GOLD_REVEAL_START = 2020;
const GOLD_REVEAL_END = 2340;
const GRAPH_TRANSFORM = `translate(${PORTRAIT_CENTER_X} ${PORTRAIT_CENTER_Y}) scale(${GRAPH_SCALE}) translate(${-GRAPH_CENTER_X} ${-GRAPH_CENTER_Y})`;

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
const firstPruneFrame = Math.min(...SEARCH_NODES.flatMap((node) => node.pruneFrame === null ? [] : [node.pruneFrame]));
const lastPruneFrame = Math.max(...SEARCH_NODES.flatMap((node) => node.pruneFrame === null ? [] : [node.pruneFrame]));

export const Act2Portrait: React.FC = () => {
  const frame = clamp(useCurrentFrame(), 0, 2699);
  const goldT = ease(frame, GOLD_REVEAL_START, GOLD_REVEAL_END);
  const orbit = (frame * 0.22) % 360;
  const edgeElements: React.ReactNode[] = [];
  const nodeElements: React.ReactNode[] = [];
  let spawnedCount = 0;
  let branchesPruned = 0;
  let survivorCount = 0;

  for (const node of SEARCH_NODES) {
    const visual = getSearchNodeVisualState(node, frame);
    if (!visual.spawned) continue;
    spawnedCount += 1;
    if (visual.pruned) branchesPruned += 1;
    else survivorCount += 1;

    let fill: string = visual.fill;
    let radius = (node.id === 0 ? 7 : 2.15 + seeded(node.id + 901) * 1.2) * visual.radiusScale;
    let stroke: string = visual.pruned ? C.red : C.white;
    let strokeOpacity = visual.pruned ? visual.opacity : (node.id === 0 ? 0.72 : 0.22) * visual.appearance;
    if (!visual.pruned && goldRankById.has(node.id)) {
      const rank = goldRankById.get(node.id) ?? 0;
      const nodeGoldT = ease(frame, GOLD_REVEAL_START + rank * 32, GOLD_REVEAL_START + rank * 32 + 48);
      if (nodeGoldT > 0.35) fill = C.gold;
      radius += nodeGoldT * (node.id === 0 ? 1.4 : 0.9);
      stroke = C.gold;
      strokeOpacity = 0.3 + 0.62 * nodeGoldT;
    }

    if (node.parentId !== null) {
      const parent = SEARCH_NODES[node.parentId];
      const isGoldEdge = goldEdgeIds.has(`${parent.id}-${node.id}`);
      let edgeColor: string = C.cyan;
      let edgeOpacity = 0.105 * visual.appearance;
      let edgeWidth = 0.8;
      if (visual.flashing) {
        edgeColor = C.red;
        edgeOpacity = 0.28 * visual.appearance;
      } else if (visual.pruned) {
        edgeColor = '#8c2531';
        edgeOpacity = visual.opacity;
      }
      if (isGoldEdge && goldT > 0) {
        edgeColor = C.gold;
        edgeOpacity = 0.18 + goldT * 0.22;
        edgeWidth = 1.5;
      }
      edgeElements.push(<line
        key={`edge-${node.id}`}
        x1={parent.x}
        y1={parent.y}
        x2={node.x}
        y2={node.y}
        stroke={edgeColor}
        strokeWidth={edgeWidth}
        strokeOpacity={edgeOpacity}
      />);
    }

    nodeElements.push(<circle
      key={`node-${node.id}`}
      cx={node.x}
      cy={node.y}
      r={radius}
      fill={fill}
      fillOpacity={visual.opacity}
      stroke={stroke}
      strokeOpacity={strokeOpacity}
      strokeWidth={node.id === 0 ? 1.4 : 0.65}
    />);
  }

  const expansionComplete = spawnedCount === SEARCH_NODE_COUNT;
  const pruningComplete = branchesPruned === PRUNED_NODE_COUNT && frame >= lastPruneFrame;
  const phase = frame >= GOLD_REVEAL_END
    ? '黄金路径已验证'
    : frame >= GOLD_REVEAL_START
      ? '收敛至黄金路径'
      : frame < firstPruneFrame
        ? '扩展搜索空间'
        : !expansionComplete
          ? '扩展与剪枝中'
          : !pruningComplete
            ? '淘汰低效分支'
            : '复核候选路径';
  const prunedPercent = Math.round((branchesPruned / SEARCH_NODE_COUNT) * 100);

  return <div style={{position: 'absolute', inset: 0, color: C.white, fontFamily: FONT}}>
    <PortraitHeading index="02" title="先穷尽可能，再选择" kicker="BREADTH / SEARCH" />

    <PortraitPanel top={460} height={780}>
      <svg width="880" height="780" viewBox="80 460 880 780" style={{position: 'absolute', inset: 0}} aria-hidden="true">
        <defs>
          <radialGradient id="portrait-search-core">
            <stop offset="0" stopColor={C.cyan} stopOpacity="0.12" />
            <stop offset="1" stopColor={C.cyan} stopOpacity="0" />
          </radialGradient>
          <filter id="portrait-gold-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" />
          </filter>
        </defs>
        <g transform={GRAPH_TRANSFORM}>
          <circle cx={GRAPH_CENTER_X} cy={GRAPH_CENTER_Y} r={SEARCH_RADIUS * 0.97} fill="url(#portrait-search-core)" />
          {[0.2, 0.4, 0.6, 0.8, 0.97].map((scale, index) => <circle
            key={`ring-${index}`}
            cx={GRAPH_CENTER_X}
            cy={GRAPH_CENTER_Y}
            r={SEARCH_RADIUS * scale}
            fill="none"
            stroke={index === 4 ? C.cyan : C.white}
            strokeOpacity={index === 4 ? 0.18 : 0.07}
            strokeWidth={index === 4 ? 1.2 : 0.8}
            strokeDasharray={index === 4 ? '2 8' : undefined}
          />)}
          <circle
            cx={GRAPH_CENTER_X}
            cy={GRAPH_CENTER_Y}
            r={SEARCH_RADIUS * 0.97}
            fill="none"
            stroke={C.cyan}
            strokeOpacity="0.2"
            strokeWidth="1"
            strokeDasharray="28 620"
            strokeDashoffset={-frame * 0.7}
            transform={`rotate(${orbit} ${GRAPH_CENTER_X} ${GRAPH_CENTER_Y})`}
          />
          <g>{edgeElements}{nodeElements}</g>
          <path
            d={goldPathD}
            fill="none"
            stroke={C.gold}
            strokeWidth="10"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeOpacity={goldT * 0.34}
            strokeDasharray={`${goldPathLength} ${goldPathLength}`}
            strokeDashoffset={goldPathLength * (1 - goldT)}
            filter="url(#portrait-gold-glow)"
          />
          <path
            d={goldPathD}
            fill="none"
            stroke={C.gold}
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeOpacity={goldT}
            strokeDasharray={`${goldPathLength} ${goldPathLength}`}
            strokeDashoffset={goldPathLength * (1 - goldT)}
          />
          <circle cx={GRAPH_CENTER_X} cy={GRAPH_CENTER_Y} r="10" fill="none" stroke={C.cyan} strokeOpacity="0.34" strokeWidth="1.4" />
        </g>
      </svg>
    </PortraitPanel>

    <div style={{position: 'absolute', left: 80, top: 1245, width: 880, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontFamily: PORTRAIT_FONT, fontSize: 25}}>
      <span style={{color: frame >= GOLD_REVEAL_START ? C.gold : C.cyan}}>{phase}</span>
      <span style={{color: C.red}}>剪枝 {prunedPercent}% <span style={{color: C.muted, fontSize: 20}}>／目标 96%</span></span>
    </div>

    <div style={{position: 'absolute', left: 80, top: 1280, width: 880, height: 100, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', borderTop: `1px solid ${C.line}`, paddingTop: 10}}>
      {[
        {label: '已生成', value: spawnedCount, color: C.cyan},
        {label: '已剪枝', value: branchesPruned, color: C.red},
        {label: '存活节点', value: survivorCount, color: C.gold},
      ].map((metric) => <div key={metric.label} style={{display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'center'}}>
        <span style={{fontFamily: FONT, color: metric.color, fontSize: 40, fontVariantNumeric: 'tabular-nums'}}>{metric.value}</span>
        <span style={{fontFamily: PORTRAIT_FONT, color: C.muted, fontSize: 22}}>{metric.label}</span>
      </div>)}
    </div>
  </div>;
};

export default Act2Portrait;
