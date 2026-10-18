import {SUBTITLES} from './timeline';

export const VOICED_SUBTITLES = [
  ...SUBTITLES.slice(0, 19),
  {from: 9780, to: 10080, zh: '人类在现实中试错千次；', en: 'Humans try a thousand times in reality.'},
  {from: 10080, to: 10500, zh: '超级智能在瞬间穷尽千万个宇宙，', en: 'A superintelligence exhausts ten million universes in an instant.'},
] as const;
