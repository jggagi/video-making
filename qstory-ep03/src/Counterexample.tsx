type Point = { x: number; y: number };

const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value));
const smooth = (value: number) => value * value * (3 - 2 * value);
const between = (time: number, start: number, end: number) => smooth(clamp((time - start) / (end - start)));

const nodes: Point[] = [
  { x: 1015, y: 300 }, { x: 1195, y: 245 }, { x: 1380, y: 310 }, { x: 1590, y: 260 },
  { x: 1110, y: 460 }, { x: 1305, y: 455 }, { x: 1515, y: 470 }, { x: 1690, y: 540 },
  { x: 1030, y: 650 }, { x: 1220, y: 720 }, { x: 1450, y: 680 }, { x: 1650, y: 735 },
];

const edges: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [0, 4], [1, 4], [1, 5], [2, 5], [2, 6], [3, 6], [3, 7],
  [4, 5], [5, 6], [6, 7], [4, 8], [5, 9], [6, 10], [7, 11], [8, 9], [9, 10], [10, 11],
];

const relatedNodes = new Set([0, 1, 2, 4, 5, 6]);
const arrivalTimes: Record<number, number> = { 0: 119.9, 1: 121.1, 2: 123.6, 4: 121.6, 5: 123.0, 6: 125.2 };

const pointAt = (points: Point[], progress: number): Point => {
  const scaled = clamp(progress) * (points.length - 1);
  const index = Math.min(Math.floor(scaled), points.length - 2);
  const mix = scaled >= points.length - 1 ? 1 : scaled - index;
  return {
    x: points[index].x + (points[index + 1].x - points[index].x) * mix,
    y: points[index].y + (points[index + 1].y - points[index].y) * mix,
  };
};

const traveledPath = (points: Point[], progress: number) => {
  const scaled = clamp(progress) * (points.length - 1);
  const index = Math.min(Math.floor(scaled), points.length - 2);
  const end = pointAt(points, progress);
  const startPoints = points.slice(0, index + 1);
  return `M ${startPoints.map((p) => `${p.x} ${p.y}`).join(" L ")} L ${end.x} ${end.y}`;
};

const brokenRingPath = (cx: number, cy: number, radius: number, gapDegrees: number) => {
  const radians = (degrees: number) => (degrees * Math.PI) / 180;
  const start = radians(gapDegrees);
  const end = radians(360 - gapDegrees);
  const sx = cx + radius * Math.cos(start);
  const sy = cy + radius * Math.sin(start);
  const ex = cx + radius * Math.cos(end);
  const ey = cy + radius * Math.sin(end);
  return `M ${sx} ${sy} A ${radius} ${radius} 0 1 1 ${ex} ${ey}`;
};

const diamond = (cx: number, cy: number, size: number) =>
  `M ${cx} ${cy - size} L ${cx + size} ${cy} L ${cx} ${cy + size} L ${cx - size} ${cy} Z`;

export const Counterexample = ({ t }: { t: number }) => {
  const time = Math.max(110, Math.min(145, t));
  const breakProgress = between(time, 110.9, 112.1);
  const gap = breakProgress * 24;
  const disturbanceProgress = clamp((time - 110.15) / 1.6);
  const disturbanceX = 190 + disturbanceProgress * 610;
  const disturbanceAlpha = 1 - between(time, 111.8, 112.5);
  const propagation = clamp((time - 118.45) / 8.1);
  const packetRoute: Point[] = [
    { x: 618, y: 480 }, nodes[0], nodes[4], nodes[5], nodes[6],
  ];
  const packet = pointAt(packetRoute, propagation);
  const packetVisible = clamp((time - 118.2) / 0.5) * (1 - between(time, 126.1, 127.3));
  const withdrawal = between(time, 129.3, 134.1);
  const reproduction = between(time, 127.0, 130.5);
  const alternative = between(time, 131.4, 135.7);
  const archive = between(time, 136.0, 137.1);
  const ringCenterX = 480 + reproduction * 190;
  const ringCenterY = 480;
  const ringRadius = 145 + reproduction * 34;
  const reproductionGap = Math.max(gap, reproduction * 23);
  const checkingLabel = between(time, 119.8, 120.4) * (1 - between(time, 126.9, 127.5));
  const withdrawalLabel = between(time, 130.0, 131.2) * (1 - between(time, 135.6, 136.4));

  const altPath = "M 1030 650 C 1095 594 1090 430 1192 365 C 1292 301 1402 372 1440 464 C 1477 554 1545 665 1650 735";
  const checkedPath = "M 1450 480 C 1490 570 1560 675 1650 735";

  return (
    <g aria-label="反例 C-17 传播、复核与证据留存">
      {/* The right-hand constellation is deliberately sparse: twelve readable workers and a few quiet satellites. */}
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        {edges.map(([a, b], index) => {
          const related = relatedNodes.has(a) || relatedNodes.has(b);
          const alpha = related ? 0.34 - withdrawal * 0.21 : 0.31;
          const color = related && time >= 118 && time < 127 &&
            time >= Math.max(arrivalTimes[a] ?? 200, arrivalTimes[b] ?? 200)
            ? "#eabc77"
            : related && withdrawal > 0.15 ? "#80909b" : "#8fb9dc";
          return (
            <line
              key={`edge-${index}`}
              x1={nodes[a].x}
              y1={nodes[a].y}
              x2={nodes[b].x}
              y2={nodes[b].y}
              stroke={color}
              strokeWidth={related && withdrawal > 0.15 ? 2 : 2.4}
              strokeDasharray={related && withdrawal > 0.15 ? "7 10" : undefined}
              opacity={alpha}
            />
          );
        })}
        <path d="M 913 236 L 952 218 L 982 249 L 1015 300" stroke="#92b8d7" strokeWidth="1.6" opacity="0.24" />
        <path d="M 1168 189 L 1218 173 L 1251 208 L 1195 245" stroke="#92b8d7" strokeWidth="1.6" opacity="0.23" />
        <path d="M 1421 253 L 1454 229 L 1488 268 L 1518 296" stroke="#92b8d7" strokeWidth="1.6" opacity="0.21" />
        <path d="M 985 701 L 957 741 L 1003 770 L 1030 650" stroke="#92b8d7" strokeWidth="1.6" opacity="0.22" />
        <path d="M 1580 782 L 1615 812 L 1662 786 L 1650 735" stroke="#92b8d7" strokeWidth="1.6" opacity="0.2" />
      </g>

      {[{ x: 913, y: 236 }, { x: 952, y: 218 }, { x: 982, y: 249 }, { x: 1168, y: 189 }, { x: 1218, y: 173 }, { x: 1251, y: 208 }, { x: 1421, y: 253 }, { x: 1454, y: 229 }, { x: 1488, y: 268 }, { x: 985, y: 701 }, { x: 957, y: 741 }, { x: 1003, y: 770 }, { x: 1580, y: 782 }, { x: 1615, y: 812 }, { x: 1662, y: 786 }].map((p, i) => (
        <circle key={`satellite-${i}`} cx={p.x} cy={p.y} r={i % 4 === 1 ? 3.2 : 2.5} fill="#a8c5dd" opacity="0.38" />
      ))}

      {/* The failed region remains visible while the surviving route bends around it. */}
      <g opacity={0.86 * Math.max(withdrawal, archive)}>
        <circle cx="1285" cy="520" r="104" fill="#65737c" opacity="0.16" />
        <circle cx="1285" cy="520" r="104" fill="none" stroke="#9aa4a9" strokeWidth="2.4" strokeDasharray="8 12" opacity="0.52" />
        <path d="M 1256 491 L 1314 549 M 1314 491 L 1256 549" stroke="#b1b8bb" strokeWidth="4" strokeLinecap="round" opacity="0.52" />
      </g>

      {/* The replacement route stays mostly blue; only its checked final leg turns muted gold. */}
      <path d={altPath} fill="none" stroke="#72b8ed" strokeWidth="6" strokeLinecap="round" opacity={alternative * 0.9} filter="url(#softGlow)" />
      <path d={checkedPath} fill="none" stroke="#d8c496" strokeWidth="5" strokeLinecap="round" opacity={alternative * 0.92} />
      {alternative > 0.2 && <circle cx="1572" cy="674" r="6" fill="#d8c496" opacity={0.75 * alternative} />}

      {/* A horizontal disturbance crosses the prototype; the opened gap holds through shot 15. */}
      <g opacity={1 - reproduction * 0.72}>
        <circle cx="480" cy="480" r="145" fill="none" stroke="#a8bdd1" strokeWidth="2" opacity="0.18" />
        {breakProgress < 0.08 ? (
          <circle cx="480" cy="480" r="145" fill="none" stroke="#c4d8e8" strokeWidth="9" opacity="0.9" filter="url(#softGlow)" />
        ) : (
          <path d={brokenRingPath(480, 480, 145, gap)} fill="none" stroke="#c4d8e8" strokeWidth="9" strokeLinecap="round" opacity="0.92" filter="url(#softGlow)" />
        )}
        {breakProgress > 0.5 && <path d="M 618 455 L 618 505" stroke="#ff625c" strokeWidth="4" strokeLinecap="round" opacity="0.8" />}
        <path d={`M ${Math.max(160, disturbanceX - 155)} 480 H ${Math.min(824, disturbanceX + 24)}`} stroke="#72b8ed" strokeWidth="1.5" strokeLinecap="round" opacity={0.48 * disturbanceAlpha} />
        <path d={`M ${Math.max(160, disturbanceX - 110)} 480 H ${Math.min(824, disturbanceX + 20)}`} stroke="#d1dfeb" strokeWidth="3.4" strokeLinecap="round" opacity={0.72 * disturbanceAlpha} />
        <path d={`M ${Math.max(160, disturbanceX - 13)} 480 H ${Math.min(824, disturbanceX + 19)}`} stroke="#ff625c" strokeWidth="4.4" strokeLinecap="round" opacity={0.92 * disturbanceAlpha} />
      </g>

      {/* A second, visibly enlarged copy repeats the same horizontal failure. */}
      {reproduction > 0 && (
        <g opacity={reproduction}>
          <circle cx={ringCenterX} cy={ringCenterY} r={ringRadius + 14} fill="none" stroke="#a8bdd1" strokeWidth="2" opacity="0.14" />
          <path d={brokenRingPath(ringCenterX, ringCenterY, ringRadius, reproductionGap)} fill="none" stroke="#d5e2ec" strokeWidth="10" strokeLinecap="round" opacity="0.94" filter="url(#softGlow)" />
          <path d={`M ${ringCenterX - ringRadius - 142} ${ringCenterY} H ${ringCenterX + ringRadius + 100}`} stroke="#d1dfeb" strokeWidth="3" strokeLinecap="round" opacity={0.62 * (1 - between(time, 132.2, 133.1))} />
          <path d={`M ${ringCenterX + ringRadius - 3} ${ringCenterY - 26} L ${ringCenterX + ringRadius + 14} ${ringCenterY} L ${ringCenterX + ringRadius - 3} ${ringCenterY + 26}`} fill="none" stroke="#ff625c" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" opacity={0.95 * reproduction} />
        </g>
      )}

      {/* C-17 follows the dependency chain while its original evidence marker stays in frame. */}
      <path d={traveledPath(packetRoute, propagation)} fill="none" stroke="#ff625c" strokeWidth="3" strokeLinecap="round" opacity={0.55 * packetVisible} />
      {packetVisible > 0.01 && (
        <path d={diamond(packet.x, packet.y, 13)} fill="#ff625c" stroke="#fff0ec" strokeWidth="2" opacity={packetVisible} filter="url(#glow)" />
      )}

      {nodes.map((node, index) => {
        const related = relatedNodes.has(index);
        const arrived = related && time >= (arrivalTimes[index] ?? 200);
        const faded = related ? withdrawal : 0;
        const activeBlue = !related || (arrived && time < 127);
        const color = related && faded > 0.15 ? "#9ba8ae" : arrived ? "#eabc77" : "#a7c9e7";
        const opacity = related ? 0.82 - 0.56 * faded : 0.76 + 0.1 * Math.sin(time * 1.4 + index);
        const radius = index % 3 === 0 ? 13 : index % 3 === 1 ? 10.5 : 12;
        return (
          <g key={`node-${index}`} opacity={opacity}>
            <circle cx={node.x} cy={node.y} r={radius + 11} fill={color} opacity={activeBlue ? 0.08 : 0.12} />
            <circle
              cx={node.x}
              cy={node.y}
              r={radius}
              fill="#0c1824"
              stroke={color}
              strokeWidth={related && faded > 0.15 ? 2.3 : 2.8}
              strokeDasharray={related && faded > 0.15 ? "5 6" : undefined}
            />
            <circle cx={node.x} cy={node.y} r="3.3" fill={color} opacity={0.95} />
            {!related && <circle cx={node.x} cy={node.y} r={radius + 5 + 2 * Math.sin(time * 1.7 + index)} fill="none" stroke="#7db7e6" strokeWidth="1.2" opacity="0.24" />}
          </g>
        );
      })}

      {/* Chinese status marks are short and held long enough to read. */}
      <g fontFamily="PingFang SC" fontSize="38" fontWeight="500" letterSpacing="2">
        <text x="1062" y="218" fill="#eabc77" opacity={checkingLabel}>已收到 → 复核中</text>
        <g fill="#e5e9ec" opacity={withdrawalLabel}>
          <text x="1060" y="218">复现失败</text>
          <text x="1060" y="267" fontSize="31" fill="#bbc3c8">相关结论已撤回</text>
        </g>
      </g>

      {/* Persistent archive source: the same C-17 diamond is visible from first discovery to final hold. */}
      <g>
        <rect x="137" y="718" width="388" height="124" rx="9" fill="#07121c" fillOpacity={0.08 * archive} stroke="#ff625c" strokeWidth="2" strokeDasharray="6 9" opacity={0.68 * archive} />
        <path d="M 151 739 V 728 H 182 M 510 739 V 728 H 479 M 151 821 V 832 H 182 M 510 821 V 832 H 479" fill="none" stroke="#ff625c" strokeWidth="3" strokeLinecap="round" opacity={archive} />
        <path d={diamond(205, 787, 16)} fill="#ff625c" stroke="#fff0ec" strokeWidth="2.2" filter="url(#glow)" />
        <text x="241" y="798" fill="#f1e2df" fontFamily="PingFang SC" fontSize="35" fontWeight="500" letterSpacing="2">反例 C-17</text>
        <text x="169" y="758" fill="#f0c3bd" fontFamily="PingFang SC" fontSize="32" fontWeight="500" letterSpacing="2" opacity={archive}>证据已保留</text>
      </g>
    </g>
  );
};
