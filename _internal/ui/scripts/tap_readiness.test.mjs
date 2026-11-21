import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { expect, it } from 'vitest';

// Execute the exact browser predicate used by the CDP harness. No copy of its
// readiness algorithm, real browser, timers or machine-speed assumptions.
const source = readFileSync(new URL('../../scripts/tap_audit/ui_tap_audit.py', import.meta.url), 'utf8');
const predicate = source.match(/SETTLE_JS = r'''([\s\S]*?)'''/)[1];
const opening = source.match(/OPENING_JS = r'''([\s\S]*?)'''/)[1];

it.each([
  { pointerEvents: 'none', hit: false, disabled: false, blocked: true },
  { pointerEvents: 'auto', hit: false, disabled: false, blocked: true },
  { pointerEvents: 'auto', hit: true, disabled: false, blocked: false },
  { pointerEvents: 'none', hit: false, disabled: true, blocked: false },
])('samples the first visible frame without waiting away a pointer failure: %o', sample => {
  const window = {};
  let next;
  runInNewContext(opening, {
    window,
    requestAnimationFrame(callback) { next = callback; },
    tapAudit: {
      top: () => ({ querySelectorAll: () => [{}] }),
      controls: 'button', visible: () => true,
      inspect: () => ({ ...sample, blockedInLayer: sample.pointerEvents === 'none' ? ['BUTTON'] : [] }),
    },
  });
  next();
  expect(window.__toastFrames.count).toBe(1);
  expect(window.__toastFrames.pointerBlocked.length > 0).toBe(sample.blocked);
});
function sample({ moving = () => false, geometry = () => 0, fonts = () => 'loaded', frameMs = 500, infinite = false } = {}) {
  let frame = 0;
  const promise = runInNewContext(predicate, {
    performance: { now: () => frame * frameMs },
    requestAnimationFrame(callback) { queueMicrotask(() => { frame++; callback(); }); },
    document: {
      fonts: { get status() { return fonts(frame); } },
      querySelectorAll: () => [{ getBoundingClientRect: () => ({ x: geometry(frame), y: 0, width: 100, height: 40 }), getAttribute: () => 'open' }],
      getAnimations: () => moving(frame) ? [{ playState: 'running', effect: { getComputedTiming: () => ({ endTime: infinite ? Infinity : 5000 }) } }] : [],
    },
  });
  return { promise, frames: () => frame };
}

it('waits for animations mounted after the initial frame, including under load', async () => {
  const run = sample({ moving: frame => frame >= 2 && frame <= 7 });
  await run.promise;
  expect(run.frames()).toBe(10);
});

it('requires three consecutive stable geometry samples', async () => {
  const run = sample({ geometry: frame => Math.min(frame, 6) });
  await run.promise;
  expect(run.frames()).toBe(9);
});

it('waits for fonts before trusting stable control coordinates', async () => {
  const run = sample({ fonts: frame => frame < 8 ? 'loading' : 'loaded' });
  await run.promise;
  expect(run.frames()).toBe(10);
});

it('fails at the deadline rather than treating unfinished animation as ready', async () => {
  const run = sample({ moving: () => true, frameMs: 1000 });
  await expect(run.promise).rejects.toThrow('did not settle within 15s');
});

it('ignores infinite decorative animations', async () => {
  const run = sample({ moving: () => true, infinite: true });
  await run.promise;
  expect(run.frames()).toBe(4);
});

it('does not search the underlying page when the requested layer has not mounted', () => {
  const window = {};
  const helpers = source.match(/\bJS = r'''([\s\S]*?)'''/)[1].replace('CONTROLS', JSON.stringify('button'));
  runInNewContext(helpers, { window, document: { querySelectorAll() { throw Error('searched underlying page'); } } });
  expect(window.tapAudit.find({ selector: 'button' }, null)).toBeUndefined();
});

// A control laid out inside a clipping ancestor (collapsible/sheet opening with
// overflow hidden, MotionRegion clip-path slide) or straddling the viewport edge
// is not painted at its center, so a hit-test there proves nothing about the
// control. A fixed/absolute layer escapes clipping by ancestors that are not on
// its containing-block chain (Radix menus under a scroll-locked body).
function visibleIn({ overflow = 'visible', parentTop = 0, parentBottom = 900, top = 100, height = 40, innerHeight = 900,
  position = 'static', parentPosition = 'static', parentTransform = 'none', clipPath = 'none', parentIsBody = false }) {
  const window = {};
  const helpers = source.match(/\bJS = r'''([\s\S]*?)'''/)[1].replace('CONTROLS', JSON.stringify('button'));
  const style = extra => ({ opacity: '1', visibility: 'visible', display: 'block', overflowX: 'visible', overflowY: 'visible',
    position: 'static', transform: 'none', filter: 'none', perspective: 'none', contain: 'none', clipPath: 'none', ...extra });
  const parent = { parentElement: null, inert: false, offsetWidth: 400, offsetHeight: parentBottom - parentTop,
    style: style({ overflowY: overflow, position: parentPosition, transform: parentTransform, clipPath }),
    getBoundingClientRect: () => ({ left: 0, right: 400, top: parentTop, bottom: parentBottom, width: 400, height: parentBottom - parentTop }) };
  const button = { parentElement: parent, inert: false, offsetWidth: 100, offsetHeight: height, style: style({ position }),
    getBoundingClientRect: () => ({ left: 10, right: 110, top, bottom: top + height, width: 100, height }) };
  const document = { body: parentIsBody ? parent : {}, documentElement: {} };
  runInNewContext(helpers, { window, innerWidth: 400, innerHeight, getComputedStyle: e => e.style, document });
  return window.tapAudit.visible(button);
}

it.each([
  [{ overflow: 'hidden', parentBottom: 110 }, false],
  [{ overflow: 'clip', parentBottom: 110 }, false],
  [{ overflow: 'auto', parentBottom: 110 }, false],
  [{ overflow: 'hidden', parentBottom: 500 }, true],
  [{ overflow: 'visible', parentBottom: 110 }, true],
  [{ top: 894.6, height: 40, innerHeight: 915 }, false],
  [{ top: 870, height: 40, innerHeight: 915 }, true],
  [{ overflow: 'hidden', parentBottom: 110, position: 'fixed' }, true],
  [{ overflow: 'hidden', parentBottom: 110, position: 'fixed', parentTransform: 'translateX(0px)' }, false],
  [{ overflow: 'hidden', parentBottom: 110, position: 'absolute' }, true],
  [{ overflow: 'hidden', parentBottom: 110, position: 'absolute', parentPosition: 'relative' }, false],
  [{ overflow: 'hidden', parentBottom: 110, parentIsBody: true }, true],
  [{ clipPath: 'inset(0px 350px 0px 0px)' }, false],
  [{ clipPath: 'inset(0px 0px 0px 0px round 8px)' }, true],
  [{ clipPath: 'inset(100% 0px 0px)' }, false],
  [{ clipPath: 'inset(0px 0px 0px 300px)', position: 'fixed' }, false],
])('visibility follows painting (clipping chain, clip-path, viewport edge): %o', (layout, expected) => {
  expect(visibleIn(layout)).toBe(expected);
});

it.each([
  { surface: true, pointerEvents: 'auto', blocked: false },
  { surface: false, pointerEvents: 'auto', blocked: true },
  { surface: true, pointerEvents: 'none', blocked: true },
])('mid-motion hits on the layer\'s own surface are not tap-through, everything else is: %o', ({ surface, pointerEvents, blocked }) => {
  const window = {};
  let next;
  runInNewContext(opening, {
    window,
    requestAnimationFrame(callback) { next = callback; },
    tapAudit: {
      top: () => ({ querySelectorAll: () => [{}] }), controls: 'button', visible: () => true, surfaceHit: () => surface,
      inspect: () => ({ pointerEvents, hit: false, disabled: false, blockedInLayer: pointerEvents === 'none' ? ['BUTTON'] : [] }),
    },
  });
  next();
  expect(window.__toastFrames.pointerBlocked.length > 0).toBe(blocked);
});

it.each([
  ['layer surface', 'surface', true],
  ['the control itself', 'self', true],
  ['another control in the layer', 'other', false],
  ['the page below the layer', 'below', false],
  ['nothing', 'none', false],
])('surfaceHit accepts only %s when appropriate', (_name, target, expected) => {
  const window = {};
  const helpers = source.match(/\bJS = r'''([\s\S]*?)'''/)[1].replace('CONTROLS', JSON.stringify('button'));
  const node = (parent, isControl) => ({ parent, isControl, closest(sel) { for (let n = this; n; n = n.parent) if (n.isControl) return n; return null; } });
  const root = node(null, false), surface = node(root, false), control = node(surface, true), other = node(surface, true), page = node(null, false);
  root.contains = n => { for (let x = n; x; x = x.parent) if (x === root) return true; return false; };
  control.contains = n => n === control;
  const hit = { surface, self: control, other, below: page, none: null }[target];
  runInNewContext(helpers, { window, document: { elementFromPoint: () => hit } });
  expect(window.tapAudit.surfaceHit(control, { x: 1, y: 1 }, root)).toBe(expected);
});
