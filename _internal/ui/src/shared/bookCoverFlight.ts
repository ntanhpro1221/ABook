import { EASE, MOTION, prefersReducedMotion } from "./motion";

type Flight = { key: string; clone: HTMLElement; from: DOMRect; restore: () => void };
let pending: Flight | undefined;
let finish: (() => void) | undefined;

const bookKey = (path: string) => /^\/book\/([^/]+)\/?$/.exec(path)?.[1];
function cover(key: string): HTMLElement | undefined {
  const candidates = [...document.querySelectorAll<HTMLElement>("[data-book-cover]")].filter(e => e.dataset.bookCover === key);
  const focused = document.activeElement?.closest("[data-book-tile], section");
  return candidates.find(e => focused?.contains(e)) ?? candidates.find(e => {
    const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight;
  });
}

/** Capture only the selected artwork before the router removes the old page. */
export function captureBookCover(from: string, to: string): void {
  const key = from === "/" ? bookKey(to) : to === "/" ? bookKey(from) : undefined;
  finish?.(); finish = undefined;
  pending?.restore(); pending = undefined;
  if (!key || prefersReducedMotion()) return;
  const source = cover(key);
  if (!source) return;
  const rect = source.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const clone = source.cloneNode(true) as HTMLElement;
  clone.removeAttribute("id"); clone.removeAttribute("data-book-cover");
  clone.querySelectorAll("[id]").forEach(e => e.removeAttribute("id"));
  clone.dataset.bookCoverFlight = key;
  clone.setAttribute("aria-hidden", "true"); clone.setAttribute("inert", "");
  Object.assign(clone.style, { position: "fixed", left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`,
    height: `${rect.height}px`, margin: "0", zIndex: "45", transform: "none", transformOrigin: "0 0", pointerEvents: "none", animation: "none" });
  const visibility = source.style.visibility;
  source.style.visibility = "hidden";
  document.body.append(clone);
  pending = { key, clone, from: rect, restore: () => { source.style.visibility = visibility; clone.remove(); } };
}

/** Called before the incoming page starts moving, so this is its final rectangle. */
export function landBookCover(back: boolean): void {
  const flight = pending;
  pending = undefined;
  if (!flight) return;
  let target: HTMLElement | undefined;
  let visibility = "";
  let cleaned = false;
  const clean = () => {
    if (cleaned) return;
    cleaned = true;
    flight.restore(); if (target) target.style.visibility = visibility;
    if (finish === clean) finish = undefined;
  };
  finish = clean;
  const started = performance.now();
  const land = () => {
    if (cleaned) return;
    // The route can commit a loading placeholder before its query publishes the
    // book. Keep the source artwork, rather than dropping the flight at that frame.
    target = cover(flight.key);
    if (!target) {
      if (performance.now() - started < 500) requestAnimationFrame(land);
      else clean();
      return;
    }
    const rect = target.getBoundingClientRect();
    if (!rect.width || !rect.height) { clean(); return; }
    let dx = 0, dy = 0;
    // An asynchronously mounted destination may arrive while its page is already
    // sliding. Its endpoint is the layout rectangle after those translations.
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      const transform = getComputedStyle(parent).transform;
      if (transform && transform !== "none") {
        const matrix = new DOMMatrixReadOnly(transform);
        dx += matrix.m41; dy += matrix.m42;
      }
    }
    const to = { left: rect.left - dx, top: rect.top - dy, width: rect.width, height: rect.height };
    visibility = target.style.visibility;
    target.style.visibility = "hidden";
    flight.clone.dataset.flightTo = JSON.stringify(to);
    const animation = flight.clone.animate([
      { transform: "none", opacity: 1 },
      { transform: `translate(${to.left - flight.from.left}px, ${to.top - flight.from.top}px) scale(${to.width / flight.from.width}, ${to.height / flight.from.height})`, opacity: 1 },
    ], { duration: back ? MOTION.slowOut : MOTION.slow, easing: back ? EASE.accelerate : EASE.decelerate, fill: "forwards" });
    void animation.finished.then(clean, clean);
  };
  land();
}
