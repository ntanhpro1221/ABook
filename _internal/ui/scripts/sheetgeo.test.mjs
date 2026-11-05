import { expect, it } from 'vitest';
import { checkMorph, checkUnderlay } from './sheetgeo.mjs';

const mini = { x: 0, y: 800, width: 390, height: 60 };
const full = { x: 0, y: 0, width: 390, height: 900 };
const frames = Array.from({ length: 11 }, (_, i) => ({ t: i * 16, player: { opacity: 1, visible: Object.fromEntries(Object.keys(mini).map(k => [k, mini[k] + (full[k] - mini[k]) * i / 10])) } }));
it('accepts geometric opening and reversed closing', () => {
  expect(checkMorph(frames, mini, full, true).every(c => c.pass)).toBe(true);
  expect(checkMorph([...frames].reverse(), mini, full, false).every(c => c.pass)).toBe(true);
});
it.each(['jump', 'fade', 'reverse', 'edge-reversal', 'missing', 'wrong-origin'])('rejects %s player animation', kind => {
  const broken = structuredClone(frames);
  if (kind === 'jump') broken.forEach(f => { f.player.visible = full; });
  if (kind === 'fade') broken[4].player.opacity = 0;
  if (kind === 'reverse') broken[5].player.visible.y = 790;
  if (kind === 'edge-reversal') broken[5].player.visible.y = 350;
  if (kind === 'missing') broken.length = 0;
  if (kind === 'wrong-origin') broken[0].player.visible = full;
  expect(checkMorph(broken, mini, full, true).some(c => !c.pass)).toBe(true);
});
const anchors = Object.fromEntries(['frame', 'header', 'text', 'transport', 'secondary'].map(k => [k, full]));
const sheetFrames = Array.from({ length: 11 }, (_, i) => ({ t: i * 16, anchors: structuredClone(anchors), surface: { rect: { x: 0, y: 900 - i * 30, width: 390, height: 300 } } }));
it('accepts vertical sheet over fixed underlay', () => expect(checkUnderlay(sheetFrames, anchors).every(c => c.pass)).toBe(true));
it.each(['push', 'missing', 'horizontal', 'resize', 'static', 'reversal'])('rejects %s sheet regression', kind => {
  const broken = structuredClone(sheetFrames);
  if (kind === 'push') broken[4].anchors.header.y += 0.6;
  if (kind === 'missing') broken[4].anchors.text = null;
  if (kind === 'horizontal') broken[4].surface.rect.x = 1;
  if (kind === 'resize') broken[4].surface.rect.height += 1;
  if (kind === 'static') broken.forEach(f => { f.surface.rect.y = 600; });
  if (kind === 'reversal') broken[5].surface.rect.y = 880;
  expect(checkUnderlay(broken, anchors).some(c => !c.pass)).toBe(true);
});
