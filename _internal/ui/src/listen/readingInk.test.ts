import { expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { sentenceOutline } from './readingInk';

it('draws one closed contour with 8 px corners and 4 px padding on Qt and web', () => {
  const lines = [{ left: -4, top: 0, right: 204, bottom: 32 }, { left: -4, top: 32, right: 94, bottom: 64 }];
  const path = sentenceOutline(lines);
  expect(path.match(/M/g)).toHaveLength(1);
  expect(path.endsWith(' Z')).toBe(true);
  expect(path).toContain('Q-4,0 4,0');
  const context = { sentenceOutline: (_rects: { x: number; y: number; width: number; height: number }[]): string => '' };
  vm.runInNewContext(readFileSync(new URL('../../../desktop_qt/qml/ReadingInk.js', import.meta.url), 'utf8'), context);
  const qt = context.sentenceOutline(lines.map(r => ({ x: r.left + 4, y: r.top, width: r.right - r.left - 8, height: r.bottom - r.top })));
  expect(qt).toBe(path);
  expect(sentenceOutline([])).toBe('');
});
