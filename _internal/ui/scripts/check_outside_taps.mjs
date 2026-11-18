// Real-Chromium (headless, CDP Input.dispatchMouseEvent / dispatchTouchEvent) check: a click / touch / right click / wheel / hover OUTSIDE an
// open floating layer only closes the TOP layer; the element under it receives nothing and a dialog under a popover stays open; a click on a
// button INSIDE the layer does its job. Same rule as Qt (Backdrop) and Android. The DOM tests (outsideShield.dom.test.tsx) cannot hit-test by
// coordinates, so the part of a press that the browser re-targets after the layer closed (click after a touch, contextmenu on release) is only
// visible here (soát Chromium thật 18-11).
// node scripts/check_outside_taps.mjs --dist dist/gallery --out <evidence>/outside-taps.json [--only id,id] [--discover]
//   (or --base http://127.0.0.1:<port>/gallery.html against a running gallery dev server). Exit 1 when any scenario fails.
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { serve, findBrowser, launch, connect, openPage, waitUntil, evaluate, STILL } from "./gallery_browser.mjs";

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--discover") opt.discover = true;
  else opt[a.replace(/^--/, "")] = argv[++i];
}
if (!opt.dist && !opt.base) throw new Error("--dist <gallery build> or --base <gallery url> is required");

// Page-side helpers. find(label, within): visible clickable whose aria-label/text matches (regex source, case-sensitive).
const PAGE = `window.__t = (() => {
  const CLICK = 'button,a[href],[role=button],[role=menuitem],[role=menuitemradio],[role=menuitemcheckbox],[role=option],[role=tab],[role=switch],[role=radio]';
  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !el.closest('[aria-hidden=true],[inert],[hidden]'); };
  // Painted on screen, ignoring aria-hidden / inert that a modal layer puts on the rest of the page.
  const shown = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && !el.closest("[hidden]"); };
  const name = (el) => (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\\s+/g, ' ');
  const find = (label, within) => { const re = new RegExp(label); const root = within ? document.querySelector(within) : document;
    if (!root) return null; return [...root.querySelectorAll(CLICK)].find((el) => visible(el) && re.test(name(el))) || null; };
  const center = (el) => { const r = el.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; };
  const log = []; let under = null;
  for (const type of ['pointerover','mouseover','pointerdown','mousedown','pointerup','mouseup','click','contextmenu','dblclick','touchstart','touchend','wheel'])
    window.addEventListener(type, (e) => { if (under && e.composedPath().includes(under)) log.push(type); }, true);
  window.addEventListener('contextmenu', (e) => { if (under && e.composedPath().includes(under)) log.push(e.defaultPrevented ? 'contextmenu:handled-by-app' : 'contextmenu:native-menu'); });
  const layers = (sel) => [...document.querySelectorAll(sel)].filter((el) => el.isConnected && el.getAttribute('data-state') !== 'closed' && visible(el));
  return { CLICK, visible, shown, name, find, center, log, layers,
    setUnder(el) { under = el; log.length = 0; },
    // Page signature without the layer under test (marked data-t-layer before the click): route, headings, other dialogs / menus.
    sig() { const own = (el) => el.closest('[data-t-layer]') || [...(el.closest('[data-radix-popper-content-wrapper]')?.children ?? [])].some((c) => c.hasAttribute('data-t-layer'));
      return JSON.stringify({ url: location.href, h1: [...document.querySelectorAll('h1,h2')].filter((h) => shown(h) && !own(h)).slice(0, 3).map((h) => h.textContent.trim()),
      dialogs: [...document.querySelectorAll('[role=dialog],[role=alertdialog],[role=menu]')].filter((d) => shown(d) && !own(d)).length }); },
  };
})(); true`;

// pick: CSS selector of preferred candidates for the element under the outside click (falls back to any clickable).
const SCENARIOS = [
  { id: "library-sort-menu", kind: "DropdownMenu modal=false (Xếp theo)", frame: "desktop/library-full",
    open: [["^Xếp theo$"]], layer: "[role=menu]", pick: '[aria-label^="Mở "]',
    inside: { label: "^Tên", expect: `!__t.layers('[role=menu]').length && /Tên/.test(document.querySelector('[aria-label="Xếp theo"]').title)` } },
  { id: "music-chip-menu", kind: "DropdownMenu modal=false (chip Phong cách)", frame: "desktop/music-library",
    open: [["^Phong cách"]], layer: "[role=menu]", pick: "main li button, main [role=listitem] button",
    inside: { pickInside: "[role=menuitemradio]:not([data-state=checked])", expect: `!__t.layers('[role=menu]').length && !!__t.find('^Phong cách: ')` } },
  { id: "book-action-menu", kind: "ActionMenu (DropdownMenu modal) trang sách", frame: "desktop/book",
    open: [["^Thêm tuỳ chọn$", "main"]], layer: "[role=menu]", pick: "main button",
    inside: { label: "^Sửa thông tin", expect: `!!document.querySelector('[role=dialog]')` } },
  { id: "book-music-submenu", kind: "DropdownMenu SubContent (Nhạc nền)", frame: "desktop/book",
    route: "gac-xep", open: [["^Thêm tuỳ chọn$", "main"], ["^Nhạc nền"]], layer: "[role=menu]", pick: "main button", frameOverride: "desktop/book-text",
    inside: null },
  { id: "player-more-menu", kind: "Popover/menu \"…\" thanh phát", frame: "desktop/player-playing",
    open: [["^Thêm tuỳ chọn$", "[data-player-bar], footer, [aria-label*=phát]"]], layer: "[data-radix-popper-content-wrapper] > *", pick: '[aria-label^="Mở "]',
    inside: { label: "^Âm thanh", expect: `!!document.querySelector('[data-audio-fx]')` } },
  { id: "player-speed-popover", kind: "Popover (Tốc độ đọc)", frame: "desktop/player-playing",
    open: [["^Tốc độ đọc"]], layer: "[data-radix-popper-content-wrapper] > *", pick: '[aria-label^="Mở "]',
    inside: { label: "^1,5", expect: `/1,5/.test(__t.find('^Tốc độ đọc')?.textContent ?? '') || /1,5/.test(__t.name(__t.find('^Tốc độ đọc')))` } },
  { id: "player-sleep-popover", kind: "Popover (Hẹn giờ ngủ, trong menu …)", frame: "desktop/player-playing",
    open: [["^Thêm tuỳ chọn$", "[data-player-bar], footer, [aria-label*=phát]"], ["^Hẹn giờ ngủ"]], layer: "[data-radix-popper-content-wrapper] > *", pick: '[aria-label^="Mở "]',
    inside: null },
  { id: "reader-type-popover", kind: "Popover (Cỡ chữ, trang đọc theo)", frame: "desktop/reader",
    open: [["^Chữ và giãn dòng"]], layer: "[data-radix-popper-content-wrapper] > *", pick: "main button, main p, main [data-line]",
    inside: { pickInside: "button", expect: `true` } },
  { id: "studio-script-popover", kind: "Popover (Kịch bản · cách đọc câu)", frame: "desktop/studio-script",
    open: [], openPick: "main [aria-haspopup=dialog]", layer: "[data-radix-popper-content-wrapper] > *", pick: "main button",
    inside: null },
  { id: "book-dialog", kind: "Dialog modal (Sửa thông tin)", frame: "desktop/book",
    open: [["^Thêm tuỳ chọn$", "main"], ["^Sửa thông tin"]], layer: "[role=dialog]", pick: "main button, nav a, nav button, aside button",
    inside: { label: "^(Đóng|Huỷ)$", expect: `!__t.layers('[role=dialog]').length` } },
  { id: "confirm-dialog", kind: "Dialog xác nhận xoá", frame: "desktop/book-text",
    open: [["^Thêm tuỳ chọn$", "main"], ["^Xoá khỏi thư viện"]], layer: "[role=dialog],[role=alertdialog]", pick: "main button, nav a, nav button, aside button",
    inside: { label: "^(Để sau|Huỷ)$", expect: `!__t.layers('[role=dialog],[role=alertdialog]').length` } },
  { id: "sheet-narrow", kind: "Sheet (Dialog ở màn hẹp 420 px)", frame: "desktop/book", width: 420, height: 860,
    open: [["^Thêm tuỳ chọn$", "main"], ["^Sửa thông tin"]], layer: "[role=dialog]", pick: "main button, header button, nav button",
    inside: { label: "^(Đóng|Huỷ)$", expect: `!__t.layers('[role=dialog]').length` } },
  { id: "menu-narrow", kind: "Menu trang sách ở màn hẹp 420 px", frame: "desktop/book", width: 420, height: 860,
    open: [["^Thêm tuỳ chọn$", "main"]], layer: "[role=menu],[role=dialog]", pick: "main button, header button, nav button",
    inside: { label: "^Sửa thông tin", expect: `!!__t.layers('[role=dialog]').length` } },
  { id: "library-sort-narrow", kind: "Xếp theo ở màn hẹp 420 px", frame: "desktop/library-full", width: 420, height: 860,
    open: [["^Xếp theo$"]], layer: "[role=menu]", pick: '[aria-label^="Mở "]',
    inside: { label: "^Tên", expect: `!__t.layers('[role=menu]').length && /Tên/.test(document.querySelector('[aria-label="Xếp theo"]').title)` } },
  // Soát 18-11 T2: Popover nằm trong hộp thoại ("Phát trên" -> "Hẹn giờ" của loa): bấm ngoài bảng nhưng trong hộp chỉ đóng bảng, hộp còn mở.
  { id: "remote-sleep-in-dialog", kind: "Popover (Hẹn giờ của loa) trong Dialog \"Phát trên\"", frame: "desktop/remote-cast",
    open: [["^Hẹn giờ", "[role=dialog]"]], layer: "[data-radix-popper-content-wrapper] > *", pick: '[role=dialog] button[aria-label^="Tạm dừng"]', pickInDialog: true,
    inside: null },
];
for (const s of SCENARIOS) if (s.frameOverride) s.frame = s.frameOverride;
// Same layers, other inputs: right click (context menu), touch tap (touch emulation), mouse wheel.
const variant = (id, press, extra = {}) => ({ ...SCENARIOS.find((s) => s.id === id), id: `${id}-${press}`, press, inside: null, ...extra });
SCENARIOS.push(
  variant("library-sort-menu", "right"), variant("player-speed-popover", "right"), variant("book-action-menu", "right"),
  variant("library-sort-narrow", "touch"), variant("player-speed-popover", "touch"), variant("sheet-narrow", "touch"),
  variant("library-sort-menu", "wheel"), variant("player-speed-popover", "wheel"),
  variant("library-sort-menu", "touch"), variant("music-chip-menu", "touch"), variant("book-action-menu", "touch"), variant("reader-type-popover", "touch", { pick: "[data-sentence]", pickAny: true }),
  { ...SCENARIOS.find((s) => s.id === "reader-type-popover"), id: "reader-type-popover-sentence", pick: "[data-sentence]", pickAny: true, inside: null },
  variant("reader-type-popover", "right", { pick: "[data-sentence]", pickAny: true }),
  variant("remote-sleep-in-dialog", "touch"), variant("remote-sleep-in-dialog", "right"),
);
// Sum of scroll offsets of every scrolled box on the page (detects the page scrolling under a layer).
const SCROLLS = `[document.scrollingElement, ...document.querySelectorAll('*')].filter((e) => e && e.scrollHeight > e.clientHeight + 1).reduce((a, e) => a + e.scrollTop, 0)`;

const only = opt.only?.split(",");
const list = SCENARIOS.filter((s) => !only || only.includes(s.id));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --dist <gallery build>: serve a built gallery (npm run gallery:build) instead of a running dev server (--base).
const local = opt.dist ? await serve(opt.dist) : null;
if (local) opt.base = local.base;
if (opt.out) mkdirSync(path.dirname(path.resolve(opt.out)), { recursive: true });
const browser = await launch(findBrowser(opt.browser), { softwareRendering: true });
const cdp = await connect(browser.endpoint);
const results = [];
try {
  for (const s of list) {
    const res = { id: s.id, kind: s.kind, frame: s.frame };
    try {
      res.outside = await runOutside(s);
      if (s.inside && !opt.discover) res.inside = await runInside(s);
    } catch (error) { res.error = String(error.message ?? error).slice(0, 400); }
    results.push(res);
    console.log(JSON.stringify(res));
  }
} finally {
  cdp.close();
  await browser.close();
  local?.server.close();
  if (opt.out) writeFileSync(opt.out, JSON.stringify({ label: opt.label ?? null, base: opt.base, scenarios: list.map((s) => s.id), results }, null, 2));
}
{
  const failed = results.filter((r) => r.error || !r.outside?.pass || (r.inside && !r.inside.pass));
  console.log(`${results.length - failed.length}/${results.length} PASS` + (failed.length ? `; FAIL: ${failed.map((r) => r.id).join(", ")}` : ""));
  process.exitCode = failed.length ? 1 : 0;
}

async function fresh(s) {
  const page = await openPage(cdp, { width: s.width ?? 1440, height: s.height ?? 900, scale: 1, mobile: false, theme: "light" });
  const sid = page.sessionId;
  if (s.press === "touch") await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 }, sid);
  await cdp.send("Page.navigate", { url: `${opt.base}?frame=${s.frame}&theme=light` }, sid);
  await waitUntil(cdp, sid, "Boolean(window.__gallery?.ready)", 60000, s.frame);
  await evaluate(cdp, sid, STILL);
  await evaluate(cdp, sid, PAGE);
  return page;
}

async function mouse(sid, [x, y], button = "left") {
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y, button: "none", buttons: 0 }, sid);
  await sleep(60);
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button, clickCount: 1, buttons: button === "left" ? 1 : 2 }, sid);
  await sleep(40);
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button, clickCount: 1, buttons: 0 }, sid);
}

async function openLayer(s, sid) {
  for (const [label, within] of s.open) {
    const at = await evaluate(cdp, sid, `(() => { const el = __t.find(${JSON.stringify(label)}, ${JSON.stringify(within ?? null)}) ?? (${JSON.stringify(within ?? null)} && __t.find(${JSON.stringify(label)})); if (!el) return null; el.scrollIntoView({block:'nearest'}); return __t.center(el); })()`);
    if (!at) throw new Error(`opener not found: ${label} (within ${within})`);
    await mouse(sid, at);
    await sleep(450);
    await evaluate(cdp, sid, STILL);
  }
  if (s.openPick) {
    const at = await evaluate(cdp, sid, `(() => { const el = [...document.querySelectorAll(${JSON.stringify(s.openPick)})].find(__t.visible); if (!el) return null; el.scrollIntoView({block:'center'}); return __t.center(el); })()`);
    if (!at) throw new Error(`opener not found: ${s.openPick}`);
    await mouse(sid, at);
    await sleep(450);
    await evaluate(cdp, sid, STILL);
  }
  const n = await evaluate(cdp, sid, `__t.layers(${JSON.stringify(s.layer)}).length`);
  if (!n) throw new Error(`layer did not open: ${s.layer}`);
}

async function runOutside(s) {
  const page = await fresh(s);
  const sid = page.sessionId;
  try {
    await openLayer(s, sid);
    // Pick the element under: clickable, visible, outside the layer, its centre clear of every open layer box and of the openers.
    const pick = await evaluate(cdp, sid, `(() => {
      const layers = __t.layers(${JSON.stringify(s.layer)});
      const wrappers = [...document.querySelectorAll('[data-radix-popper-content-wrapper]')].filter(__t.visible);
      const boxes = [...layers, ...wrappers].map((el) => el.getBoundingClientRect());
      const inBox = ([x, y]) => boxes.some((r) => x >= r.left - 8 && x <= r.right + 8 && y >= r.top - 8 && y <= r.bottom + 8);
      const inLayer = (el) => layers.some((l) => l.contains(el)) || wrappers.some((w) => w.contains(el));
      const expanded = (el) => el.getAttribute('aria-expanded') === 'true' || el.getAttribute('data-state') === 'open';
      // Modal Radix layers set pointer-events:none on body, which hides everything from elementsFromPoint: lift it for this synchronous read only.
      const lift = document.createElement('style'); lift.textContent = '*{pointer-events:auto!important}';
      const modal = (el) => ${s.pickInDialog ? "el.closest('[role=alertdialog],[role=menu]')" : "el.closest('[role=dialog],[role=alertdialog],[role=menu]')"};
      const ok = (el) => { if (!__t.shown(el) || inLayer(el) || expanded(el) || modal(el)) return false; const c = __t.center(el);
        if (c[0] < 4 || c[1] < 4 || c[0] > innerWidth - 4 || c[1] > innerHeight - 4 || inBox(c)) return false;
        const stack = document.elementsFromPoint(...c);
        // Topmost non-layer element at that point must be el (or inside it): nothing else of the page covers it.
        const page = stack.find((x) => !inLayer(x) && !x.hasAttribute('data-outside-shield') && !/fixed/.test(getComputedStyle(x).position) || x === el || el.contains(x));
        return Boolean(page) && (page === el || el.contains(page)); };
      const prefer = ${s.pickAny ? "true" : "false"} ? [...document.querySelectorAll(${JSON.stringify(s.pick)})] : [...document.querySelectorAll(${JSON.stringify(s.pick)})].filter((el) => el.matches(__t.CLICK) || el.closest(__t.CLICK)).map((el) => el.matches(__t.CLICK) ? el : el.closest(__t.CLICK));
      const any = [...document.querySelectorAll(__t.CLICK)];
      document.head.append(lift);
      const el = prefer.find(ok) ?? any.find(ok);
      lift.remove();
      layers.forEach((l) => l.setAttribute('data-t-layer', ''));
      const inside = layers.flatMap((l) => [...l.querySelectorAll(__t.CLICK)]).filter(__t.visible).map(__t.name).slice(0, 25);
      if (!el) return { inside };
      __t.setUnder(el);
      const c = __t.center(el);
      const top = document.elementFromPoint(...c);
      return { at: c, under: el.tagName + ' "' + __t.name(el).slice(0, 50) + '"', topmost: top ? top.tagName + (top.hasAttribute('data-outside-shield') ? '[data-outside-shield]' : '') + '.' + String(top.className).slice(0, 40) : null, inside, sig: __t.sig() };
    })()`);
    if (!pick.at) return { pass: false, note: "no element under found", inside: pick.inside };
    // Phase 1: hover only (layer still open). Phase 2: press + release + wait.
    const [x, y] = pick.at;
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: x - 3, y: y - 3, button: "none", buttons: 0 }, sid);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y, button: "none", buttons: 0 }, sid);
    await sleep(250);
    const hover = await evaluate(cdp, sid, `({ log: [...__t.log], cursor: getComputedStyle(document.elementFromPoint(${x}, ${y})).cursor })`);
    await evaluate(cdp, sid, "__t.log.length = 0, true");
    const scrollBefore = await evaluate(cdp, sid, SCROLLS);
    if (s.press === "touch") {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] }, sid);
      await sleep(60);
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] }, sid);
    } else if (s.press === "wheel") {
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseWheel", x, y, deltaX: 0, deltaY: 300, button: "none", buttons: 0 }, sid);
    } else {
      const button = s.press === "right" ? "right" : "left";
      await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button, clickCount: 1, buttons: button === "left" ? 1 : 2 }, sid);
      await sleep(40);
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button, clickCount: 1, buttons: 0 }, sid);
    }
    await sleep(600);
    const scrollAfter = await evaluate(cdp, sid, SCROLLS);
    await evaluate(cdp, sid, STILL);
    const after = await evaluate(cdp, sid, `({ log: [...__t.log], open: __t.layers(${JSON.stringify(s.layer)}).length, sig: __t.sig(), shields: document.querySelectorAll('[data-outside-shield]').length })`);
    const PRESS = ["pointerdown", "mousedown", "click", "dblclick", "contextmenu"];
    const res = { under: pick.under, at: pick.at.map(Math.round), topmostBeforeClick: pick.topmost,
      hoverEventsWhileOpen: hover.log, cursorWhileOpen: hover.cursor, clickEvents: after.log, layerClosed: after.open === 0,
      pageUnchanged: after.sig === pick.sig, ...(after.sig !== pick.sig ? { sigBefore: pick.sig, sigAfter: after.sig } : {}), leftoverShields: after.shields };
    if (s.press) res.press = s.press;
    if (s.press === "wheel") {
      // Wheel outside: the page under must not scroll (layer may stay open - Radix does not close on wheel).
      res.pageScrolled = scrollBefore !== scrollAfter;
      res.leak = res.pageScrolled || after.log.some((t) => PRESS.includes(t));
      res.hoverLeak = hover.log.length > 0;
      res.pass = !res.leak && !res.hoverLeak;
      return res;
    }
    res.leak = after.log.some((t) => PRESS.includes(t)) || !res.pageUnchanged;
    res.hoverLeak = s.press === "touch" ? false : hover.log.length > 0;
    res.pass = !res.leak && res.layerClosed && !res.hoverLeak;
    if (opt.discover) res.insideButtons = pick.inside;
    return res;
  } finally {
    await cdp.send("Target.closeTarget", { targetId: page.targetId });
  }
}

async function runInside(s) {
  const page = await fresh(s);
  const sid = page.sessionId;
  try {
    await openLayer(s, sid);
    const at = await evaluate(cdp, sid, `(() => {
      const layers = __t.layers(${JSON.stringify(s.layer)});
      const all = layers.flatMap((l) => [...l.querySelectorAll(${JSON.stringify(s.inside.pickInside ?? "*")})]).filter((el) => __t.visible(el) && (el.matches(__t.CLICK)));
      const el = ${s.inside.label ? `all.find((el) => new RegExp(${JSON.stringify(s.inside.label)}).test(__t.name(el)))` : "all[0]"};
      if (!el) return null;
      return { at: __t.center(el), name: __t.name(el).slice(0, 60) };
    })()`);
    if (!at) return { pass: false, note: "inside button not found" };
    await mouse(sid, at.at);
    await sleep(600);
    await evaluate(cdp, sid, STILL);
    const ok = await evaluate(cdp, sid, `(() => { try { return Boolean(${s.inside.expect}); } catch (e) { return 'ERR ' + e.message; } })()`);
    const errors = await evaluate(cdp, sid, "window.__gallery?.errors ?? []");
    return { button: at.name, pass: ok === true, result: ok, errors: errors.slice(0, 3) };
  } finally {
    await cdp.send("Target.closeTarget", { targetId: page.targetId });
  }
}
