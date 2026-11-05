/** Real player geometry, using the gallery's existing Edge/CDP harness. */
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { connect, evaluate, launch, openPage, serve } from './gallery_browser.mjs';
import { installGeometryProbe, pointerClick, pointerTouch, stable as galleryStable, visit } from './gallery_inspect_sheet.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
export const WIDTHS = [390, 840, 1080, 1280, 1440, 1840];
const dimensions = ['x', 'y', 'width', 'height'];
export const delta = (a, b) => !a || !b ? Infinity : Math.max(...dimensions.map(k => Math.abs(a[k] - b[k])));
const finite = r => r && dimensions.every(k => Number.isFinite(r[k])) && r.width > 0 && r.height > 0;

export function checkMorph(frames, mini, full, opening) {
  const samples = frames.filter(f => f.player);
  const rects = samples.map(f => f.player.visible);
  const start = opening ? mini : full, end = opening ? full : mini;
  const checks = [];
  const check = (name, pass, evidence) => checks.push({ name, pass: Boolean(pass), ...evidence });
  check('nonempty finite animation samples', rects.length >= 5 && rects.every(finite), { samples: rects.length });
  check('first visible rect at origin', delta(rects[0], start) <= 3, { delta: delta(rects[0], start), rect: rects[0], expected: start });
  const firstRaf = samples.find(f => f.source === 'raf')?.player.visible;
  // Unit comparator inputs may omit source, real captures always identify rAF explicitly.
  if (frames.some(f => f.source)) check('first rAF rect at origin', delta(firstRaf, start) <= 3, { delta: delta(firstRaf, start), rect: firstRaf });
  check('last visible rect at destination', delta(rects.at(-1), end) <= 0.5, { delta: delta(rects.at(-1), end), rect: rects.at(-1), expected: end });
  const intermediate = rects.filter(r => delta(r, start) > 3 && delta(r, end) > 3);
  check('geometric intermediate frames (no jump or fade only)', intermediate.length >= 3, { samples: intermediate.length });
  let worst = 0;
  for (let i = 1; i < rects.length; i++) {
    const a = rects[i - 1], b = rects[i];
    // Every edge travels toward its destination, including a mini bar above phone navigation.
    const edges = r => ({ ...r, right: r.x + r.width, bottom: r.y + r.height });
    const first = edges(start), last = edges(end), previous = edges(a), current = edges(b);
    for (const k of ['x', 'y', 'width', 'height', 'right', 'bottom']) {
      const direction = Math.sign(last[k] - first[k]);
      worst = Math.max(worst, direction ? -(current[k] - previous[k]) * direction : Math.abs(current[k] - previous[k]));
    }
  }
  check('monotonic rect growth/shrink', worst <= 0.5, { worstReversePx: worst });
  check('player stays opaque throughout geometric motion', samples.every(f => f.player.opacity >= 0.99),
    { minOpacity: Math.min(...samples.map(f => f.player.opacity)) });
  return checks;
}

export function checkUnderlay(frames, before, { vertical = true, closing = false } = {}) {
  const checks = [];
  let maxDelta = 0, missing = 0, worst;
  for (const f of frames) for (const [name, rect] of Object.entries(before)) {
    const d = delta(rect, f.anchors[name]);
    if (!finite(f.anchors[name])) missing++;
    if (d > maxDelta) { maxDelta = d; worst = { frame: f.t, name, before: rect, after: f.anchors[name] }; }
  }
  checks.push({ name: 'header/text/controls invariant on every frame', pass: frames.length >= 5 && Object.keys(before).length >= 5 && !missing && maxDelta <= 0.5, maxDelta, missing, worst });
  const surfaces = frames.map(f => f.surface).filter(Boolean);
  const boxes = surfaces.map(s => s.rect);
  const reference = boxes.at(-1);
  const drift = boxes.length ? Math.max(...boxes.map(r => Math.max(Math.abs(r.x - reference.x), Math.abs(r.width - reference.width), Math.abs(r.height - reference.height)))) : Infinity;
  checks.push({ name: 'surface sampled', pass: boxes.length >= 3, samples: boxes.length });
  checks.push({ name: 'surface x/width/height fixed (vertical motion only)', pass: !vertical || drift <= 0.5, maxDelta: drift, required: vertical });
  if (vertical) {
    const travel = boxes.length ? Math.max(...boxes.map(r => r.y)) - Math.min(...boxes.map(r => r.y)) : 0;
    const reversals = boxes.slice(1).map((r, i) => (r.y - boxes[i].y) * (closing ? -1 : 1));
    checks.push({ name: 'sheet slides vertically without reversing', pass: travel > 10 && Math.max(0, ...reversals) <= 0.5, travel, worstReversePx: Math.max(0, ...reversals) });
  }
  return checks;
}

/** Runs in the real app, never substitutes a component or changes animation time. */
function installPlayerProbe() {
  const box = e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; };
  const player = () => document.querySelector('.now-playing:not([data-state="warm"])');
  const visible = e => {
    const r = box(e), clip = getComputedStyle(e).clipPath;
    if (clip === 'none') return r;
    const match = /^inset\(([^)]*)\)$/.exec(clip);
    if (!match) throw new Error('Unsupported player clip-path: ' + clip);
    const values = match[1].split('round')[0].trim().split(/\s+/);
    const expanded = values.length === 1 ? [values[0], values[0], values[0], values[0]] : values.length === 2 ? [values[0], values[1], values[0], values[1]] : values.length === 3 ? [...values, values[1]] : values;
    const v = expanded.map((n, i) => n.endsWith('%') ? parseFloat(n) / 100 * (i % 2 ? r.width : r.height) : parseFloat(n));
    return { x: r.x + v[3], y: r.y + v[0], width: r.width - v[1] - v[3], height: r.height - v[0] - v[2] };
  };
  const opacity = e => { let n = 1; for (let p = e; p; p = p.parentElement) { const s = getComputedStyle(p); if (s.visibility !== 'visible' || s.display === 'none') return 0; n *= Number(s.opacity); } return n; };
  let refs = {};
  window.__playerProbe = {
    pin() {
      const p = player(), aside = p.querySelector(':scope > aside');
      refs = { frame: p, header: aside.firstElementChild, textColumn: p.querySelector('[data-read-along], [role="tabpanel"]') || p.querySelector('[data-np-stage]'),
        stage: p.querySelector('[data-np-stage]'), transport: p.querySelector('[data-player-transport]'), secondary: p.querySelector('[data-player-secondary]') };
      return this.snapshot().anchors;
    },
    snapshot() {
      const p = player();
      const surface = [...document.querySelectorAll('[role="dialog"]')].at(-1);
      return { t: performance.now(), player: p ? { raw: box(p), visible: visible(p), clip: getComputedStyle(p).clipPath, opacity: opacity(p), state: p.dataset.state } : null,
        anchors: Object.fromEntries(Object.entries(refs).map(([k, e]) => [k, e?.isConnected ? box(e) : null])),
        surface: surface ? { rect: box(surface), sheet: surface.classList.contains('motion-sheet'), state: surface.dataset.state, title: surface.getAttribute('aria-label') || surface.querySelector('[data-surface-title]')?.textContent } : null };
    },
    arm() {
      this.frames = []; this.events = []; this.done = false;
      const begin = performance.now();
      let triggeredAt = null, previous = '', stableFrames = 0;
      // Keep the same-task prepaint sample too: React layout effects create WAAPI before the next rAF.
      let lastState = '';
      const record = source => {
        const snap = this.snapshot(); snap.source = source;
        const state = JSON.stringify([snap.player?.state, snap.surface?.state]);
        if (source === 'raf' || state !== lastState) this.frames.push(snap);
        lastState = state;
      };
      const observer = new MutationObserver(() => record('mutation'));
      observer.observe(document.body, { subtree: true, childList: true, attributes: true });
      const event = e => { this.events.push({ type: e.type, trusted: e.isTrusted }); if (e.isTrusted) { triggeredAt = performance.now(); stableFrames = 0; } };
      document.addEventListener('click', event, true);
      document.addEventListener('keydown', event, true);
      const tick = () => {
        record('raf');
        const snap = this.frames.at(-1);
        const current = JSON.stringify({ player: snap.player, anchors: snap.anchors, surface: snap.surface });
        stableFrames = current === previous ? stableFrames + 1 : 0; previous = current;
        // Word highlights / toasts can keep starting finite animations during playback.
        // Wait for the measured boxes (and the view-transition), not unrelated content.
        const targets = new Set([player(), ...Object.values(refs), ...document.querySelectorAll('[role="dialog"]')]);
        const moving = document.getAnimations().some(a => a.playState === 'running' && a.effect?.getComputedTiming().endTime !== Infinity
          && (targets.has(a.effect?.target) || a.effect?.pseudoElement?.startsWith('::view-transition')));
        const settled = triggeredAt !== null && performance.now() - triggeredAt >= 180 && stableFrames >= 3 && !moving;
        if (!settled && performance.now() - begin < 2500) requestAnimationFrame(tick);
        else { observer.disconnect(); document.removeEventListener('click', event, true); document.removeEventListener('keydown', event, true); this.timedOut = !settled; this.done = true; }
      };
      requestAnimationFrame(tick);
    },
  };
}

const ev = (cdp, session, expression) => evaluate(cdp, session, expression);
const stable = (cdp, session) => galleryStable(cdp, session, { tolerance: 0.5, geometryOnly: true });
async function record(cdp, session, action) {
  await ev(cdp, session, '__playerProbe.arm()');
  await action();
  await ev(cdp, session, 'new Promise((resolve,reject)=>{const start=performance.now();const tick=()=>__playerProbe.done?resolve(true):performance.now()-start>3000?reject(Error("rAF sampling timeout")):requestAnimationFrame(tick);tick()})');
  const data = await ev(cdp, session, '({frames:__playerProbe.frames,events:__playerProbe.events,timedOut:__playerProbe.timedOut})');
  if (data.timedOut) {
    const moving = await ev(cdp, session, 'document.getAnimations().filter(a=>a.playState==="running").map(a=>({name:a.animationName||a.id,target:a.effect?.target?.outerHTML?.slice(0,180)}))');
    throw new Error('Measured geometry did not finish with three identical rAF samples within 2.5s: ' + JSON.stringify({ frames: data.frames.slice(-5), moving }));
  }
  if (!data.events.some(e => e.trusted)) throw new Error('No trusted input during capture');
  // arm() already waited for these exact boxes, finite frame animations and
  // three stable rAFs. A second whole-gallery wait can observe unrelated layers.
  return data;
}
async function key(cdp, session, key = 'Escape') {
  for (const type of ['keyDown', 'keyUp']) await cdp.send('Input.dispatchKeyEvent', { type, key, code: key, windowsVirtualKeyCode: 27 }, session);
}

async function widthRun(cdp, base, width, injected, classes) {
  const page = await openPage(cdp, { width, height: 900, scale: 1, mobile: width < 768, theme: 'light', isolated: true });
  const session = page.sessionId;
  const report = { width, height: 900, trials: [], checks: [] };
  const add = (name, checks, evidence) => {
    const trial = { name, status: checks.every(c => c.pass) ? 'PASS' : 'FAIL', checks, ...evidence };
    report.trials.push(trial);
    return trial;
  };
  const click = selector => (width < 768 ? pointerTouch : pointerClick)(cdp, session, selector);
  const closeSurface = async () => {
    const handle = await ev(cdp, session, `(()=>{const e=[...document.querySelectorAll('[role="dialog"][data-state="open"] [data-sheet-handle]')].at(-1);if(!e)return null;e.dataset.sheetgeoClose='';return '[data-sheetgeo-close]'})()`);
    if (handle) await click(handle);
    else await key(cdp, session);
  };
  const sheetTrial = async (name, selector, mode) => {
    await stable(cdp, session);
    const before = await ev(cdp, session, '__playerProbe.pin()');
    const opened = await record(cdp, session, () => click(selector));
    const surface = await ev(cdp, session, '__playerProbe.snapshot().surface');
    const checks = checkUnderlay(opened.frames, before, { vertical: surface?.sheet });
    checks.push({ name: 'requested surface is open', pass: surface?.state === 'open' });
    add(`${mode}: ${name} open`, checks, { before, ...opened });
    const closed = await record(cdp, session, closeSurface);
    add(`${mode}: ${name} close`, checkUnderlay(closed.frames, before, { vertical: surface?.sheet, closing: true }), { before, ...closed });
  };
  try {
    await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: `(${installGeometryProbe.toString()})();(${installPlayerProbe.toString()})();` }, session);
    for (const story of ['desktop/player-playing', 'desktop/book-text']) {
      await visit(cdp, session, `${base}?frame=${story}&theme=light`, 30000, async pending => { await click(pending.selector); return false; });
      if (story === 'desktop/book-text') {
        const start = await ev(cdp, session, `(()=>{const e=[...document.querySelectorAll('main button')].find(e=>e.textContent.trim().startsWith('Nghe'));if(!e)throw Error('Text book play button missing');e.dataset.sheetgeoStart='';return '[data-sheetgeo-start]'})()`);
        await click(start); await stable(cdp, session);
        const consent = await ev(cdp, session, `(()=>{const e=[...document.querySelectorAll('[role=dialog] button')].find(e=>e.textContent.trim()==='Nghe');if(!e)throw Error('Speech consent missing');e.dataset.sheetgeoConsent='';return '[data-sheetgeo-consent]'})()`);
        await click(consent); await stable(cdp, session);
      }
      for (let i = 0; i < 4 && await ev(cdp, session, 'Boolean(document.querySelector("[role=dialog]"))'); i++) { await key(cdp, session); await stable(cdp, session); }
      if (await ev(cdp, session, 'Boolean(document.querySelector(".now-playing[data-state=open]"))')) {
        await click('.now-playing button[aria-label^="Thu nhỏ"]'); await stable(cdp, session);
      }
      const playback = await ev(cdp, session, `(()=>{const e=document.querySelector('[data-np-source] [data-np="play"]');return {label:e?.getAttribute('aria-label'),busy:e?.getAttribute('aria-busy')}})()`);
      const playing = playback.label?.startsWith('Tạm dừng');
      report.checks.push({ name: `${story}: ${story.endsWith('player-playing') ? 'book is playing' : 'fake speech playback requested'}`, pass: playing || (story.endsWith('book-text') && playback.busy === 'true'), playback });
      const contentWidth = await ev(cdp, session, 'document.querySelector(".desktop-content").getBoundingClientRect().width');
      report.contentWidth = contentWidth;
      report.widthClass = classes.filter(c => contentWidth >= c.from).at(-1).name;
      const mini = await ev(cdp, session, '(()=>{const r=document.querySelector("[data-np-source]").getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})()');
      const opening = await record(cdp, session, () => click('[data-np-source] [aria-label="Mở màn hình đang nghe"]'));
      const full = await ev(cdp, session, '__playerProbe.snapshot().player.raw');
      add(`${story}: mini → player`, checkMorph(opening.frames, mini, full, true), { mini, full, ...opening });
      const layout = await ev(cdp, session, `(()=>{const p=document.querySelector('.now-playing'),a=p.querySelector(':scope > aside'),panel=p.querySelector(':scope > div'),r=a.getBoundingClientRect(),s=getComputedStyle(a),left=parseFloat(s.marginLeft),right=parseFloat(s.marginRight);return {column:r.toJSON(),columnMarginBox:{x:r.x-left,width:r.width+left+right},panel:panel?.getBoundingClientRect().toJSON()??null,stacked:!!p.querySelector('[data-player-mode]')}})()`);
      const largeFrom = classes.find(c => c.name === 'large').from;
      const expectedStacked = contentWidth < largeFrom;
      const layoutMatches = expectedStacked
        ? Math.abs(layout.columnMarginBox.x - full.x) <= 0.5 && Math.abs(layout.columnMarginBox.width - full.width) <= 0.5
        : layout.panel && Math.abs(layout.panel.x - layout.column.right) <= 0.5 && Math.abs(layout.panel.right - (full.x + full.width)) <= 0.5;
      report.checks.push({ name: `${story}: DESIGN 5.5 player split starts at large content width`, pass: layout.stacked === expectedStacked && Boolean(layoutMatches), contentWidth, largeFrom, layout });
      if (injected) await ev(cdp, session, `(()=>{const s=document.createElement('style');s.textContent='body:has([role="dialog"][data-state="open"]) .now-playing > aside { translate: 0 -32px !important; transition: translate 220ms linear !important; }';document.head.append(s);return true})()`);
      const phone = await ev(cdp, session, 'Boolean(document.querySelector("[data-player-mode]"))');
      for (const mode of ['Nghe', 'Đọc theo']) {
        const before = await ev(cdp, session, '__playerProbe.snapshot().player.raw');
        const selector = phone ? `[data-player-mode] [data-mode="${mode === 'Nghe' ? 'listen' : 'read'}"]` : `#now-tab-${mode === 'Nghe' ? 'chapters' : 'text'}`;
        const switched = await record(cdp, session, () => click(selector));
        const modeDelta = Math.max(...switched.frames.map(f => delta(f.player?.raw, before)));
        const readingInside = await ev(cdp, session, 'Boolean(document.querySelector(".now-playing [data-read-along], .now-playing #now-panel-text"))');
        add(`${story}: switch to ${mode}`, [{ name: 'player frame fixed throughout mode switch', pass: modeDelta <= 0.5, maxDelta: modeDelta }, { name: 'read along is inside player', pass: mode !== 'Đọc theo' || readingInside }], switched);
        if (mode === 'Đọc theo') {
          const textWidth = await ev(cdp, session, 'document.querySelector(".now-playing .reading-surface .measure")?.getBoundingClientRect().width ?? null');
          report.checks.push({ name: `${story}: reading text column at most 640px`, pass: Number.isFinite(textWidth) && textWidth <= 640.5, textWidth });
        }
        await sheetTrial('Tốc độ', '.now-playing [data-player-secondary] button[aria-label^="Tốc độ"]', mode);
        await sheetTrial('Hẹn giờ', '.now-playing [data-player-secondary] button[aria-label^="Hẹn giờ"]', mode);
        if (phone) await sheetTrial('Chương', '.now-playing [data-player-secondary] button[aria-pressed]', mode);
        await sheetTrial('Thêm tuỳ chọn', '.now-playing button[aria-label="Thêm tuỳ chọn"]', mode);
        // Voice/music MenuShell sections live inside the shared More surface.
        // Inline expansion is measured independently; it may resize the sheet itself, never its underlay.
        await click('.now-playing button[aria-label="Thêm tuỳ chọn"]'); await stable(cdp, session);
        const inline = await ev(cdp, session, `(()=>{const root=document.querySelector('[data-player-more]');return [...root.querySelectorAll('[data-player-inline] > button')].map((e,i)=>{e.dataset.sheetgeoInline=String(i);return '[data-sheetgeo-inline="'+i+'"]'})})()`);
        for (const target of inline) {
          const label = await ev(cdp, session, `document.querySelector(${JSON.stringify(target)}).getAttribute('aria-label')`);
          const pinned = await ev(cdp, session, '__playerProbe.pin()');
          const expanded = await record(cdp, session, () => click(target));
          add(`${mode}: inline ${label}`, checkUnderlay(expanded.frames, pinned, { vertical: false }), { before: pinned, ...expanded });
          const collapsed = await record(cdp, session, () => click(target));
          add(`${mode}: inline ${label} close`, checkUnderlay(collapsed.frames, pinned, { vertical: false }), { before: pinned, ...collapsed });
        }
        await closeSurface(); await stable(cdp, session);
        if (await ev(cdp, session, 'Boolean(document.querySelector("[data-player-more]"))')) throw new Error('More surface did not close through its control');
      }
      if (phone) { await click('[data-player-mode] [data-mode="listen"]'); await stable(cdp, session); }
      const closing = await record(cdp, session, () => click('.now-playing button[aria-label^="Thu nhỏ"]'));
      add(`${story}: player → mini`, checkMorph(closing.frames, mini, full, false), { mini, full, ...closing });
      const diagnostics = await ev(cdp, session, 'window.__gallery');
      report.checks.push({ name: `${story}: no gallery errors/missing APIs`, pass: !diagnostics.errors.length && !diagnostics.missing.length, diagnostics });
    }
  } catch (error) { report.checks.push({ name: 'execution', pass: false, error: error.stack }); }
  finally { await cdp.send('Target.disposeBrowserContext', { browserContextId: page.browserContextId }); }
  report.status = report.checks.every(c => c.pass) && report.trials.length > 0 && report.trials.every(t => t.status === 'PASS') ? 'PASS' : 'FAIL';
  return report;
}

export async function main(argv) {
  const args = Object.fromEntries(argv.filter(a => a.startsWith('--')).map((a, i) => [a.slice(2), argv[argv.indexOf(a) + 1]]));
  const root = path.resolve(here, '../../..');
  const classes = [...readFileSync(path.join(here, '../src/shared/widthClass.generated.ts'), 'utf8').matchAll(/^  (\w+): (\d+),$/gm)].map(m => ({ name: m[1], from: Number(m[2]) }));
  const report = { status: 'FAIL', injected: argv.includes('--inject-fault'), classes, results: [], cleanup: {} };
  let server, browser, cdp;
  try {
    ({ server, base: args.base } = await serve(path.join(here, '../dist/gallery')));
    browser = await launch(args.edge, { hideScrollbars: false, profileParent: args['task-dir'] || root, disableGpu: true });
    cdp = await connect(browser.endpoint);
    report.browser = await cdp.send('Browser.getVersion');
    report.profile = browser.profile;
    for (const width of WIDTHS) {
      const result = await widthRun(cdp, args.base, width, report.injected, classes);
      report.results.push(result);
      writeFileSync(args.output, JSON.stringify(report, null, 2) + '\n');
      console.log(`${result.status} | ${width}×900 | content=${result.contentWidth} ${result.widthClass} | ${result.trials.length} trials`);
      for (const t of result.trials.filter(t => t.status === 'FAIL')) console.log(`  FAIL | ${t.name} | ${JSON.stringify(t.checks.filter(c => !c.pass))}`);
      for (const c of result.checks.filter(c => !c.pass)) console.log(`  FAIL | ${JSON.stringify(c)}`);
    }
    const covered = new Set(report.results.map(r => r.widthClass));
    report.allWidthClassesCovered = classes.length === 5 && classes.every(c => covered.has(c.name));
    report.status = report.allWidthClassesCovered && report.results.length === WIDTHS.length && report.results.every(r => r.status === 'PASS') ? 'PASS' : 'FAIL';
  } catch (error) { report.error = error.stack; }
  finally {
    cdp?.close();
    if (browser) { await browser.close(); report.cleanup.profileRemoved = !existsSync(browser.profile); }
    if (server) await new Promise(resolve => server.close(resolve));
    report.cleanup.serverClosed = true;
  }
  if (!report.cleanup.profileRemoved) report.status = 'FAIL';
  writeFileSync(args.output, JSON.stringify(report, null, 2) + '\n');
  console.log(`${report.status} | sheetgeo | all width classes covered=${report.allWidthClassesCovered} | ${args.output}`);
  if (report.error) console.error(report.error);
  return report.status === 'PASS' ? 0 : 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main(process.argv.slice(2));
