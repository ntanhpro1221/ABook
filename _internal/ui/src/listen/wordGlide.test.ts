import { describe, expect, it } from 'vitest';
import { wordDuration, wordInkRange } from './wordGlide';
import { MOTION } from '../shared/motion';

describe('word display geometry', () => {
  it.each([
    ['văn,', 'văn'], ['“Nghĩ', 'Nghĩ'], ['chuyện.', 'chuyện'], ['...!?', ''],
    ['«(tự-nhiên)—', 'tự-nhiên'], ['‘nhẹ-nhàng’', 'nhẹ-nhàng'], ['…', ''],
  ])('trims only the edges of %s', (text, expected) => {
    const [from, until] = wordInkRange(text);
    expect(text.slice(from, until)).toBe(expected);
  });
  it('caps travel at both the shared fast token and the playback word interval', () => {
    expect(wordDuration(500, 1)).toBe(MOTION.fast);
    expect(wordDuration(120, 3)).toBe(40);
    expect(wordDuration(0, 1)).toBe(0);
  });
});
