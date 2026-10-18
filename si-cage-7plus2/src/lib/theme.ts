import timeline from '../../timeline.json';

export const C = {bg: '#050811', amber: '#f59e0b', red: '#ef4444', cyan: '#06b6d4', white: '#ffffff', gold: '#facc15', muted: '#78899e', line: 'rgba(148,184,211,0.16)'} as const;
export const FONT = "'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Menlo, Consolas, monospace";
export const CN = "'PingFang SC', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif";
// All scene geometry stays in logical units. MainComposition applies this
// single vector/DOM scale before Chrome rasterizes the native UHD frame.
export const SCENE_WIDTH = timeline.logicalWidth;
export const SCENE_HEIGHT = timeline.logicalHeight;
export const RENDER_SCALE = timeline.renderScale;
export const GLOW = {
  cyan: 'drop-shadow(0 0 4px rgba(6, 182, 212, 0.65)) drop-shadow(0 0 20px rgba(6, 182, 212, 0.4))',
  gold: 'drop-shadow(0 0 4px rgba(250, 204, 21, 0.7)) drop-shadow(0 0 20px rgba(250, 204, 21, 0.4))',
} as const;
