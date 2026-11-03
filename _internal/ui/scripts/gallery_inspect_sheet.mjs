import { evaluate, openPage, waitUntil } from "./gallery_browser.mjs";

export const SHEET_RULE = "SHEET GEOMETRY";
export const TOLERANCE = 0.5;

/** Comparison is deliberately independent of the browser and retains individual deltas. */
export function compareGeometry(before, after, { closed = false, tolerance = TOLERANCE } = {}) {
  const changes = [];
  const number = (metric, a, b, limit = tolerance, selector = "html", rect) => {
    if (!Number.isFinite(a) || !Number.isFinite(b) || Math.abs(b - a) > limit)
      changes.push({ metric, selector, referenceValue: a, value: b, delta: b - a, rects: rect ? [rect] : [] });
  };
  number("document-scrollTop", before.scrollTop, after.scrollTop, 0);
  number("scrollbar-width", before.scrollbarWidth, after.scrollbarWidth);
  for (const tag of ["body", "html"]) for (const [property, value] of Object.entries(before.styles[tag])) {
    const next = after.styles[tag][property];
    if (property.startsWith("overflow")) {
      // Scroll locking is allowed while open; its computed state must be restored on close.
      if (closed && value !== next) changes.push({ metric: `${tag}-${property}`, selector: tag, referenceValue: value, value: next, rects: [] });
    } else number(`${tag}-${property}`, parseFloat(value), parseFloat(next), tolerance, tag);
  }
  const current = new Map(after.anchors.map(a => [a.selector, a]));
  for (const anchor of before.anchors) {
    const next = current.get(anchor.selector);
    if (!next?.rect) {
      changes.push({ metric: "missing-anchor", selector: anchor.selector, rects: [anchor.rect] });
      continue;
    }
    for (const dimension of ["x", "y", "width", "height"]) number(`anchor-${dimension}`, anchor.rect[dimension], next.rect[dimension], tolerance, anchor.selector, anchor.rect);
    number("container-scrollTop", anchor.scrollTop, next.scrollTop, 0, anchor.selector, anchor.rect);
    number("container-scrollLeft", anchor.scrollLeft, next.scrollLeft, 0, anchor.selector, anchor.rect);
  }
  return changes;
}

/** Installed in each fresh page; no app state is read or modified. Catalog clicks rendezvous with CDP. */
export function installGeometryProbe() {
  const surfaceSelector = '[role="dialog"]:not([data-state="closed"]):not([inert]), .now-playing[data-state="open"]';
  const box = el => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; };
  const path = el => {
    const parts = [];
    for (let node = el; node && node !== document.body; node = node.parentElement) {
      parts.unshift(`${node.localName}:nth-of-type(${[...node.parentElement.children].filter(n => n.localName === node.localName).indexOf(node) + 1})`);
    }
    return `body > ${parts.join(' > ')}`;
  };
  const surfaces = () => [...document.querySelectorAll(surfaceSelector)].filter(el => el.getBoundingClientRect().width > 0);
  // A menu can itself be a phone Sheet and is replaced by its selected dialog. It is not stable page content.
  const excluded = el => el.closest('[role="dialog"], [role="menu"], [role="tooltip"], [data-sonner-toaster], [data-motion-ghost], .now-playing:not([data-state="open"])');
  let sequence = 0;
  window.__galleryPointer = element => new Promise(resolve => {
    const id = ++sequence;
    element.dataset.geometryPointer = String(id);
    window.__sheetProbe.pending = { id, selector: `[data-geometry-pointer="${id}"]`, label: element.getAttribute('aria-label') || element.textContent?.trim().slice(0, 100) };
    window.__sheetProbe.resume = () => { window.__sheetProbe.pending = null; resolve(); };
  });
  window.__sheetProbe = {
    documentId: crypto.randomUUID(),
    pending: null,
    surfaces: () => surfaces().map(el => ({ selector: path(el), title: el.querySelector('[data-surface-title]')?.textContent || el.getAttribute('aria-label') || '', rect: box(el) })),
    triggers: () => [...document.querySelectorAll('[aria-haspopup="dialog"], [aria-label="Mở màn hình đang nghe"]' + (innerWidth <= 640 ? ', [aria-haspopup="menu"]' : ''))]
      .filter(el => !el.closest('[inert], [aria-hidden="true"]') && !excluded(el) && !el.matches(':disabled, [aria-expanded="true"]') && box(el).width > 0)
      .map(el => ({ selector: path(el), label: el.getAttribute('aria-label') || el.textContent?.trim().slice(0, 100), menu: el.getAttribute('aria-haspopup') === 'menu' })),
    prepare: selector => {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`Missing pointer target ${selector}`);
      const r = box(el);
      const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      if (r.y < 0 || r.y + r.height > innerHeight || r.x < 0 || r.x + r.width > innerWidth || !hit || !el.contains(hit)) el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
    },
    position: middle => {
      // Scroll user-scrollable underlay containers, including the document when its viewport permits scrolling.
      const nodes = [document.scrollingElement, ...document.querySelectorAll('main, .page-motion, [data-list-edges], [data-reader-controls]')];
      for (const el of new Set(nodes)) {
        if (!el || excluded(el) || el.scrollHeight <= el.clientHeight + 1) continue;
        const overflow = getComputedStyle(el).overflowY;
        // Body overflow propagates to the viewport when html is visible. Hidden overflow can
        // still be scrolled by JS, but forcing it scrolls the entire shell offscreen unrealistically.
        const viewportOverflow = overflow === 'visible' ? getComputedStyle(document.body).overflowY : overflow;
        if (el === document.scrollingElement ? /hidden|clip/.test(viewportOverflow) : !/auto|scroll/.test(overflow)) continue;
        el.scrollTop = middle ? (el.scrollHeight - el.clientHeight) / 2 : 0;
      }
    },
    capture: (fresh = false) => {
      if (fresh) {
        const candidates = new Set(document.querySelectorAll('main, .page-motion, h1, h2'));
        for (const list of document.querySelectorAll('ul, ol, [role="list"], [data-list-edges]')) {
          for (const row of [...list.children].slice(0, 3)) candidates.add(row);
        }
        for (const el of document.querySelectorAll('*')) {
          if ([...el.attributes].some(a => /^data-(list-edges|section-title|surface-title|reader-controls|page|book|chapter|anchor|windowed)/.test(a.name))) candidates.add(el);
          if (el.scrollHeight > el.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(el).overflowY)) candidates.add(el);
        }
        window.__sheetProbe.anchors = [...candidates].filter(el => !excluded(el) && box(el).width > 0 && box(el).height > 0)
          .map(el => ({ el, selector: path(el) }));
      }
      const styles = {};
      for (const tag of ['html', 'body']) {
        const css = getComputedStyle(document[tag === 'html' ? 'documentElement' : 'body']);
        styles[tag] = Object.fromEntries(['paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginRight','marginBottom','marginLeft','overflow','overflowX','overflowY'].map(p => [p, css[p]]));
      }
      return { scrollTop: document.scrollingElement.scrollTop, scrollbarWidth: innerWidth - document.documentElement.clientWidth, styles,
        anchors: window.__sheetProbe.anchors.map(({ el, selector }) => ({ selector, rect: el.isConnected ? box(el) : null, scrollTop: el.scrollTop, scrollLeft: el.scrollLeft })) };
    },
    stable: () => new Promise(resolve => {
      const start = performance.now();
      let previous = '', frames = 0, done = false;
      const finish = stable => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        resolve({ stable, elapsed: performance.now() - start, visibility: document.visibilityState,
          moving: stable ? [] : document.getAnimations().filter(a => a.playState === 'running').map(a => ({ name: a.animationName || a.id, end: a.effect?.getComputedTiming().endTime })) });
      };
      const timer = setTimeout(() => finish(false), 2000);
      const tick = () => {
        if (done) return;
        const current = JSON.stringify(surfaces().map(el => box(el)));
        const moving = document.getAnimations().some(a => a.playState === 'running' && a.effect?.getComputedTiming().endTime !== Infinity);
        // WAAPI morphs finish before React's exit fallback removes their closed surface.
        // A still-mounted exit can briefly enlarge document overflow; it is not a closed-page baseline.
        const exiting = document.querySelector('[role="dialog"][data-state="closed"], .now-playing[data-state="closed"]');
        frames = current === previous && !moving && !exiting ? frames + 1 : 0;
        if (frames >= 3) return finish(true);
        previous = current;
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }),
    center: selector => {
      const el = document.querySelector(selector);
      if (!el) throw new Error(`Missing click target ${selector}`);
      const r = box(el), x = r.x + r.width / 2, y = r.y + r.height / 2;
      const hit = document.elementFromPoint(x, y);
      if (hit && !el.contains(hit) && hit.closest('[data-sonner-toast]')) return null;
      if (!hit || !el.contains(hit)) throw new Error(`Pointer target occluded: ${selector} by ${hit?.outerHTML.slice(0, 180)}`);
      return { x, y };
    },
    closeControl: () => {
      const el = surfaces().at(-1);
      // Non-modal desktop popovers close through their own toggle trigger (they have no X).
      const button = el?.querySelector('button[aria-label="Đóng"], button[aria-label^="Thu nhỏ"]')
        ?? (el?.id ? [...document.querySelectorAll('[aria-controls]')].find(button => button.getAttribute('aria-controls') === el.id && !el.contains(button)) : null);
      return button ? path(button) : null;
    },
  };
}

const probe = (cdp, session, expression) => evaluate(cdp, session, `window.__sheetProbe.${expression}`);
async function pointerCenter(cdp, session, selector) {
  const started = Date.now();
  for (;;) {
    const point = await probe(cdp, session, `center(${JSON.stringify(selector)})`);
    if (point) return point;
    if (Date.now() - started >= 8000) throw new Error(`Toast still covers pointer target after 8 s: ${selector}`);
    await new Promise(resolve => setTimeout(resolve, 40));
  }
}
export async function pointerClick(cdp, session, selector) {
  const point = await pointerCenter(cdp, session, selector);
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...point }, session);
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point, button: "left", buttons: 1, clickCount: 1 }, session);
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point, button: "left", buttons: 0, clickCount: 1 }, session);
}

async function stable(cdp, session) {
  const result = await probe(cdp, session, "stable()");
  if (!result.stable) throw new Error(`Sheet geometry did not settle within 2 s (3 frames required): ${JSON.stringify(result)}`);
}

/** Replay catalog actions through CDP, pausing before a selected opener when requested. */
async function visit(cdp, session, url, timeout, onClick) {
  const previousDocument = await evaluate(cdp, session, "window.__sheetProbe?.documentId ?? null");
  await cdp.send("Page.navigate", { url }, session);
  // Page.navigate can return before commit: never replay a pending click or ready flag from the old document.
  await waitUntil(cdp, session, `Boolean(window.__sheetProbe && window.__gallery && window.__sheetProbe.documentId !== ${JSON.stringify(previousDocument)})`, timeout, "fresh geometry gallery");
  const start = Date.now();
  for (;;) {
    const state = await evaluate(cdp, session, "({ pending: window.__sheetProbe.pending, gallery: window.__gallery })");
    if (state.pending) {
      await probe(cdp, session, `prepare(${JSON.stringify(state.pending.selector)})`);
      await stable(cdp, session);
      if (await onClick(state.pending)) return;
      await probe(cdp, session, "resume()");
    } else if (state.gallery.ready) {
      if (state.gallery.errors.length || state.gallery.missing.length) throw new Error(JSON.stringify(state.gallery));
      await stable(cdp, session);
      return;
    } else await new Promise(resolve => setTimeout(resolve, 25));
    if (Date.now() - start > timeout) throw new Error("Timed out replaying geometry catalog actions");
  }
}

export async function inspectSheets(cdp, { base, entry, theme, timeout = 45000 }) {
  const result = { story: entry.id, theme, widths: [], trials: [], findings: [], errors: [], known: [] };
  for (const width of [1440, 400]) {
    const page = await openPage(cdp, { width, height: 900, scale: 1, mobile: false, theme, newWindow: true, isolated: true });
    // Headless still throttles rAF in background targets. This never creates a visible window.
    await cdp.send("Target.activateTarget", { targetId: page.targetId });
    const session = page.sessionId;
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: `(${installGeometryProbe.toString()})()` }, session);
    const url = `${base}?frame=${encodeURIComponent(entry.id)}&theme=${theme}`;
    const targets = [];
    try {
      // Discover *all* dialog/Now Playing transitions in the catalog's actual action sequence.
      await visit(cdp, session, url, timeout, async pending => {
        const before = await probe(cdp, session, "surfaces()");
        await pointerClick(cdp, session, pending.selector);
        await stable(cdp, session);
        const after = await probe(cdp, session, "surfaces()");
        if (after.some(a => !before.some(b => b.selector === a.selector && b.title === a.title))) targets.push({ step: pending.id, label: pending.label });
      });
      // Radix Dialog/Popover triggers and Now Playing can also be opened on ordinary gallery screens with no `act`.
      for (const trigger of await probe(cdp, session, "triggers()")) {
        if (trigger.menu) {
          // ActionMenu becomes a Sheet at phone width; plain dropdowns remain outside this rule.
          const before = await probe(cdp, session, "surfaces()");
          await probe(cdp, session, `prepare(${JSON.stringify(trigger.selector)})`);
          await stable(cdp, session);
          await pointerClick(cdp, session, trigger.selector);
          await stable(cdp, session);
          const after = await probe(cdp, session, "surfaces()");
          if (after.some(a => !before.some(b => b.selector === a.selector && b.title === a.title))) targets.push(trigger);
          await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }, session);
          await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }, session);
          await stable(cdp, session);
        } else targets.push(trigger);
      }
      result.known.push(...await evaluate(cdp, session, "window.__gallery.known"));
      result.widths.push({ width, targets });
      for (const target of targets) {
        let reusableSelector = null;
        for (const position of ["top", "middle"]) for (const dismissal of ["escape", "control"]) {
          const trial = { width, position, dismissal, target, before: null, open: null, closed: null };
          result.trials.push(trial);
          try {
            const exercise = async selector => {
              await probe(cdp, session, `position(${position === "middle"})`);
              // Only scroll the trigger into view if essential for a real click; the resulting position is the baseline.
              await probe(cdp, session, `prepare(${JSON.stringify(selector)})`);
              await stable(cdp, session);
              await pointerCenter(cdp, session, selector);
              trial.before = await probe(cdp, session, "capture(true)");
              trial.surfacesBefore = await probe(cdp, session, "surfaces()");
              await pointerClick(cdp, session, selector);
              await stable(cdp, session);
              trial.surfacesOpen = await probe(cdp, session, "surfaces()");
              if (!trial.surfacesOpen.some(a => !trial.surfacesBefore.some(b => b.selector === a.selector && b.title === a.title))) throw new Error("Pointer click did not open a new sheet/dialog/Now Playing");
              trial.open = await probe(cdp, session, "capture()");
              const record = phase => {
                for (const change of compareGeometry(trial.before, trial[phase], { closed: phase === "closed" })) {
                  result.findings.push({ rule: SHEET_RULE, story: entry.id, theme, width, position, dismissal, target: target.label, phase, ...change, text: `${width}px ${position} ${dismissal} ${target.label}: ${phase} ${change.metric}`, context: [] });
                }
              };
              record("open");
              if (dismissal === "escape") {
                // Start Escape at the surface, away from inputs with intentional local Escape handling.
                await evaluate(cdp, session, "document.querySelectorAll('[role=dialog]:not([inert]), .now-playing[data-state=open]').item(document.querySelectorAll('[role=dialog]:not([inert]), .now-playing[data-state=open]').length - 1)?.focus({preventScroll:true})");
                await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }, session);
                await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }, session);
              } else {
                const close = await probe(cdp, session, "closeControl()");
                if (!close) throw new Error("No close control found on opened surface");
                await pointerClick(cdp, session, close);
              }
              await stable(cdp, session);
              trial.surfacesClosed = await probe(cdp, session, "surfaces()");
              if (trial.surfacesClosed.some(a => !trial.surfacesBefore.some(b => b.selector === a.selector && b.title === a.title))) throw new Error("Dismissal did not close the opened surface");
              trial.closed = await probe(cdp, session, "capture()");
              record("closed");
              reusableSelector = selector;
            };
            if (reusableSelector && await evaluate(cdp, session, `Boolean(document.querySelector(${JSON.stringify(reusableSelector)}))`)) {
              await exercise(reusableSelector);
            } else {
              await visit(cdp, session, url, timeout, async pending => {
                if (pending.id === target.step) { await exercise(pending.selector); return true; }
                await pointerClick(cdp, session, pending.selector);
                await stable(cdp, session);
              });
              if (!target.step) await exercise(target.selector);
            }
            if (!trial.before) throw new Error("Catalog opener was not reached");
          } catch (error) {
            reusableSelector = null;
            trial.error = error.message;
            result.errors.push({ story: entry.id, theme, width, position, dismissal, target: target.label, error: error.message });
          }
        }
      }
    } catch (error) { result.errors.push({ story: entry.id, theme, width, error: error.message }); }
    finally { await cdp.send("Target.disposeBrowserContext", { browserContextId: page.browserContextId }); }
  }
  return result;
}
