/** Reflow the existing Chinese copy without changing characters or cue timing. */
export const portraitCaption = (text: string): string => {
  const chars = Array.from(text);
  if (chars.length <= 18) return text;
  const legal = Array.from({length: chars.length - 1}, (_, i) => i + 1)
    .filter((i) => i <= 18 && chars.length - i <= 18 && !/[，；。！？、—]/.test(chars[i]) && !(/[\dA-Za-z]/.test(chars[i - 1]) && /[\dA-Za-z]/.test(chars[i])));
  const semantic = legal.filter((i) => /[，；。！？—]/.test(chars[i - 1]));
  const candidates = semantic.length ? semantic : legal;
  const split = candidates.sort((a, b) => Math.abs(a - chars.length / 2) - Math.abs(b - chars.length / 2))[0] ?? Math.ceil(chars.length / 2);
  return chars.slice(0, split).join('') + '\n' + chars.slice(split).join('');
};
