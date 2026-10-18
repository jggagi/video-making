import {clamp} from './math';

export const ANCHOR_END = 10200;
export const IMPACT_FRAME = 9600;
export const GRAVITY_MM_S2 = 9810;
export const FREE_FALL_SECONDS = Math.sqrt(2 * 120 / GRAVITY_MM_S2);

// The brief's 500 ms clock and 12 cm trajectory use a normalized time map.
// Impact is intentionally a separate editorial cue at frame 9600.
export const anchorState = (frame: number) => {
  const p = clamp(frame / ANCHOR_END);
  const trajectoryTime = FREE_FALL_SECONDS * p;
  return {
    milliseconds: 500 * p,
    altitudeMm: Math.max(0, 120 - 0.5 * GRAVITY_MM_S2 * trajectoryTime ** 2),
    step: Math.floor(10 ** (10 * p)),
    years: 10000 * p,
    centuries: 100 * p,
  };
};

export const SUBTITLES = [
  {from: 0, to: 480, zh: '人类眨眼需要 300 毫秒。', en: 'A human blink takes 300 milliseconds.'},
  {from: 480, to: 1020, zh: '在这滴水落入培养皿之前，硅基意识已经度过了一万年。', en: 'Before this droplet reaches the dish, a silicon mind has lived ten millennia.'},
  {from: 1020, to: 1440, zh: '同一段时间，可以容纳截然不同的世界。', en: 'The same interval can contain radically different worlds.'},
  {from: 1440, to: 1800, zh: '在计算的尺度里，一瞬足以成为永恒。', en: 'At the scale of computation, an instant becomes an eternity.'},
  {from: 1800, to: 2280, zh: '它没有等待一个答案，而是同时展开无数种可能。', en: 'It opens countless possibilities before choosing an answer.'},
  {from: 2280, to: 2820, zh: '每一个分支，都是一次尚未发生的实验。', en: 'Each branch is an experiment that has never happened.'},
  {from: 2820, to: 3420, zh: '热失控、结构坍塌、能量发散——失败先发生在模拟之中。', en: 'Thermal runaway. Structural collapse. Divergence. Failure occurs in simulation first.'},
  {from: 3420, to: 3960, zh: '百分之九十六的道路被剪去，现实却毫发无损。', en: 'Ninety-six percent of the paths disappear. Reality remains untouched.'},
  {from: 3960, to: 4500, zh: '最后，只留下一条经过验证的金色路径。', en: 'One verified golden path remains.'},
  {from: 4500, to: 5040, zh: '广度之外，还有深度。', en: 'Beyond breadth, there is depth.'},
  {from: 5040, to: 5580, zh: '人类的工作记忆止步于此；形式化推演继续向下。', en: 'Where human working memory runs out, formal exploration continues.'},
  {from: 5580, to: 6240, zh: '数百万次检验，将高维空间中的约束逐一扣紧。', en: 'Millions of checks tighten the constraints of a higher-dimensional space.'},
  {from: 6240, to: 6700, zh: '复杂并不意味着混乱。它在寻找一个可以执行的交点。', en: 'Complexity has structure. It seeks an intersection that can be acted upon.'},
  {from: 6700, to: 7200, zh: '所有可能收束成一个参数。', en: 'A universe of possibilities collapses into a single instruction.'},
  {from: 7200, to: 7800, zh: '比特以光速交换；原子仍被惯性束缚。', en: 'Bits race through the network. Atoms remain bound by inertia.'},
  {from: 7800, to: 8460, zh: '它可以瞬间算尽宇宙的法则，', en: 'It can calculate the laws of a universe in an instant,'},
  {from: 8460, to: 9060, zh: '却依然要耐心地等待一颗原子的挪动。', en: 'yet must patiently wait for a single atom to move.'},
  {from: 9060, to: 9420, zh: '现在，把答案交还给现实。', en: 'Now, return the answer to reality.'},
  {from: 9420, to: 9660, zh: '唯一的一击。', en: 'One move.'},
  {from: 9660, to: 10200, zh: '没有飞溅。只有一种此前不存在的秩序。', en: 'No splash. Only an order that did not exist before.'},
  {from: 10200, to: 10500, zh: '半秒过去。永恒已经发生。', en: 'Half a second passes. An eternity has already happened.'},
] as const;
