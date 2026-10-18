export const clamp = (x: number, lo = 0, hi = 1): number => Math.min(hi, Math.max(lo, x));
export const mix = (a: number, b: number, t: number): number => a + (b - a) * t;
export const smooth = (x: number): number => { const t = clamp(x); return t * t * (3 - 2 * t); };
export const progress = (frame: number, from: number, to: number): number => clamp((frame - from) / (to - from));
export const seeded = (i: number): number => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453123; return x - Math.floor(x); };
export const ease = (frame: number, from: number, to: number): number => smooth(progress(frame, from, to));
export const fmt = (x: number): string => Math.floor(x).toLocaleString('en-US');
export type Vec3 = [number, number, number];
export type Vec4 = [number, number, number, number];
export const rotate4 = (v: Vec4, a: number, b: number, angle: number): Vec4 => {
  const out: Vec4 = [...v]; const c = Math.cos(angle); const s = Math.sin(angle);
  out[a] = v[a] * c - v[b] * s; out[b] = v[a] * s + v[b] * c;
  return out;
};
