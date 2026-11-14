import { EASE, MOTION, prefersReducedMotion } from '../shared/motion';

/** Trim only token edges. Internal hyphens and apostrophes remain part of the word. */
export function wordInkRange(text: string): [number, number] {
  const edge = /[\p{P}\p{Z}\s]/u;
  let from = 0, until = text.length;
  while (from < until && edge.test(text[from])) from++;
  while (until > from && edge.test(text[until - 1])) until--;
  return [from, until];
}

export interface WordBox { x: number; y: number; width: number; height: number }
export function wordDuration(stepMs: number, rate: number): number {
  return Math.max(0, Math.min(MOTION.fast, Math.floor(stepMs / Math.max(0.1, rate))));
}

/** One independent ink element; animation never changes text layout. */
export function moveWordInk(ink: HTMLElement, box: WordBox, previous: WordBox | null, duration: number, sequential: boolean): void {
  const style = (r: WordBox) => ({ transform: `translate(${r.x}px, ${r.y}px)`, width: `${r.width}px`, height: `${r.height}px`, opacity: '1' });
  const current = getComputedStyle(ink);
  const before = { transform: current.transform, width: current.width, height: current.height, opacity: current.opacity };
  ink.getAnimations?.().forEach(a => a.cancel());
  Object.assign(ink.style, style(box));
  if (!previous || !sequential || prefersReducedMotion() || duration <= 0 || typeof ink.animate !== 'function') return;
  if (Math.abs(previous.y - box.y) > 4) {
    // A single element disappears before changing lines; no diagonal sweep across text.
    ink.animate([{ ...before, easing: EASE.standard }, { ...before, width: '0px', offset: 0.5 },
      { ...style(box), width: '0px', offset: 0.5, easing: EASE.standard }, style(box)], { duration, easing: 'linear' });
  } else ink.animate([before, style(box)], { duration, easing: EASE.standard });
}

const scrolls = new WeakMap<HTMLElement, number>();
/** Bounded scroll: move near a distant destination, then glide the final viewport. */
export function scrollReading(box: HTMLElement, top: number, animate: boolean): void {
  const old = scrolls.get(box);
  if (old !== undefined) cancelAnimationFrame(old);
  scrolls.delete(box);
  const target = Math.max(0, Math.min(Math.max(0, box.scrollHeight - box.clientHeight), top));
  if (!animate || prefersReducedMotion() || typeof requestAnimationFrame !== 'function') {
    box.scrollTo({ top, behavior: 'auto' });
    return;
  }
  if (Math.abs(target - box.scrollTop) > box.clientHeight * 2 && box.clientHeight > 0)
    box.scrollTo({ top: target - Math.sign(target - box.scrollTop) * box.clientHeight * 0.5, behavior: 'auto' });
  const from = box.scrollTop;
  let start: number | undefined;
  // Same cubic-bezier standard token as native clients (solve x, evaluate y).
  const [x1, y1, x2, y2] = EASE.standard.match(/[\d.]+/g)!.map(Number);
  const cubic = (t: number, a: number, b: number) => 3 * (1 - t) ** 2 * t * a + 3 * (1 - t) * t * t * b + t ** 3;
  const standard = (p: number) => {
    let lo = 0, hi = 1;
    for (let i = 0; i < 14; i++) {
      const t = (lo + hi) / 2;
      const x = cubic(t, x1, x2);
      if (x < p) lo = t; else hi = t;
    }
    const t = (lo + hi) / 2;
    return cubic(t, y1, y2);
  };
  const tick = (now: number) => {
    start ??= now;
    const p = prefersReducedMotion() ? 1 : Math.min(1, (now - start) / MOTION.slow);
    box.scrollTo({ top: p === 1 ? target : from + (target - from) * standard(p), behavior: 'auto' });
    if (p < 1) scrolls.set(box, requestAnimationFrame(tick)); else scrolls.delete(box);
  };
  scrolls.set(box, requestAnimationFrame(tick));
}

export function cancelReadingScroll(box: HTMLElement): void {
  const id = scrolls.get(box);
  if (id !== undefined) cancelAnimationFrame(id);
  scrolls.delete(box);
}
