import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { connect, evaluate, findBrowser, launch, openPage, serve, STILL, waitUntil } from "./gallery_browser.mjs";

// Inspect rendered text, including clipping inherited from an ancestor. Scrollable
// viewports are allowed; a hidden/clip ancestor cannot silently swallow text.
export async function textCuts() {
  const findings = [];
  const hidden = /^(hidden|clip)$/;
  for (const el of document.querySelectorAll("body *")) {
    if (!(el instanceof HTMLElement) || el.matches("script,style,option") || el.closest('[inert], [data-motion-snapshot], .sr-only')) continue;
    // The skip link deliberately lives above the viewport until keyboard focus.
    // Focus it so its full rendered label is checked, then restore focus below.
    const skip = el.matches("[data-skip-link]") && el !== document.activeElement;
    const previousFocus = document.activeElement;
    if (skip) {
      el.focus({ preventScroll: true });
      await Promise.all(el.getAnimations().filter(a => a.effect?.getComputedTiming().endTime !== Infinity).map(a => a.finished.catch(() => undefined)));
    }
    const ownStyle = getComputedStyle(el);
    // Accessible-only labels deliberately occupy a 1px clipped box; they have
    // a visible icon/control counterpart and are not rendered text.
    if (ownStyle.position === "absolute" && (ownStyle.clip === "rect(0px, 0px, 0px, 0px)" || ownStyle.clipPath === "inset(50%)") && el.clientWidth <= 1 && el.clientHeight <= 1) continue;
    const nodes = [...el.childNodes].filter(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
    if (!nodes.length || !el.getClientRects().length || getComputedStyle(el).visibility === "hidden") { if (skip) { el.blur(); previousFocus?.focus({ preventScroll: true }); } continue; }
    const range = document.createRange();
    const rects = nodes.flatMap(n => { range.selectNodeContents(n); return [...range.getClientRects()]; });
    for (let box = el; box; box = box.parentElement) {
      const style = getComputedStyle(box);
      const x = hidden.test(style.overflowX) && box.scrollWidth > box.clientWidth + 1;
      const y = hidden.test(style.overflowY) && box.scrollHeight > box.clientHeight + 1;
      if (!x && !y) continue;
      const r = box.getBoundingClientRect();
      const left = r.left + box.clientLeft, top = r.top + box.clientTop;
      // Text below a legitimate scroller is reachable by scrolling, even if an
      // outer app shell clips its viewport. Check the nearest scrolling plane.
      let scrollX = false, scrollY = false;
      for (let inner = el; inner !== box; inner = inner.parentElement) {
        const s = getComputedStyle(inner);
        scrollX ||= /^(auto|scroll)$/.test(s.overflowX);
        scrollY ||= /^(auto|scroll)$/.test(s.overflowY);
      }
      if (rects.some(t => (x && !scrollX && (t.left < left - 1 || t.right > left + box.clientWidth + 1)) ||
        (y && !scrollY && (t.top < top - 1 || t.bottom > top + box.clientHeight + 1)))) {
        findings.push({ text: nodes.map(n => n.textContent.trim()).join(" "), element: el.tagName.toLowerCase(),
          className: el.className, clip: box.className || box.tagName.toLowerCase(), x, y,
          scroll: [box.scrollWidth, box.scrollHeight], client: [box.clientWidth, box.clientHeight] });
        break;
      }
    }
    if (skip) { el.blur(); previousFocus?.focus({ preventScroll: true }); }
  }
  return findings;
}

export async function renderTextCheck({ widths = [360, 412, 1024, 1440], only, out, phase = "after", dist = path.resolve(import.meta.dirname, "../dist/gallery"), onResult = () => {} } = {}) {
  let local, browser, cdp;
  const results = [];
  try {
    local = await serve(dist);
    browser = await launch(findBrowser(), { preserveProfile: true });
    cdp = await connect(browser.endpoint);
    const index = await openPage(cdp, { width: 1440, height: 900, scale: 1, mobile: false, theme: "light" });
    await cdp.send("Page.navigate", { url: local.base }, index.sessionId);
    await waitUntil(cdp, index.sessionId, "Array.isArray(window.__galleryEntries)", 45000, "gallery index");
    const entries = (await evaluate(cdp, index.sessionId, "window.__galleryEntries")).filter(e => !only || only.includes(e.id));
    await cdp.send("Target.closeTarget", { targetId: index.targetId });
    if (!entries.length) throw new Error("No gallery screens found");
    if (out) mkdirSync(out, { recursive: true });
    for (const entry of entries) {
      await Promise.all(widths.map(async width => {
        // Each viewport needs independent localStorage/cookies: consent and
        // remembered UI settings must not leak between concurrent renders.
        const { browserContextId } = await cdp.send("Target.createBrowserContext");
        const page = await openPage(cdp, { width, height: 1000, scale: 1, mobile: entry.platform === "phone", theme: "light", browserContextId });
        const result = { id: entry.id, width, findings: [], errors: [] };
        try {
          await cdp.send("Page.navigate", { url: `${local.base}?frame=${entry.id}&longText=1` }, page.sessionId);
          await waitUntil(cdp, page.sessionId, "window.__gallery?.ready", 45000, entry.id);
          await evaluate(cdp, page.sessionId, "document.fonts.ready");
          await evaluate(cdp, page.sessionId, STILL);
          const state = await evaluate(cdp, page.sessionId, "window.__gallery");
          result.errors = [...state.errors, ...state.missing];
          result.findings = await evaluate(cdp, page.sessionId, `(${textCuts.toString()})()`);
          await evaluate(cdp, page.sessionId, STILL);
          if (out && ["desktop/studio-projects", "phone/player-full", "desktop/studio-script", "phone/library-full"].includes(entry.id) && width === (entry.platform === "phone" ? 360 : 1024)) {
            const shot = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, page.sessionId);
            writeFileSync(path.join(out, `${phase}-${entry.id.replaceAll("/", "-")}-${width}.png`), Buffer.from(shot.data, "base64"));
            if (entry.id === "desktop/studio-projects") {
              const clip = await evaluate(cdp, page.sessionId, `(() => { const r = document.querySelector('aside[aria-label="Thanh bên"]').getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, scale: 1 }; })()`);
              const sidebar = await cdp.send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: false }, page.sessionId);
              writeFileSync(path.join(out, `${phase}-sidebar-${width}.png`), Buffer.from(sidebar.data, "base64"));
            }
          }
        } catch (error) {
          result.errors.push(error.message);
          const state = await evaluate(cdp, page.sessionId, "window.__gallery").catch(() => undefined);
          if (state) result.errors.push(...state.errors, ...state.missing);
        }
        finally {
          await cdp.send("Target.closeTarget", { targetId: page.targetId });
          await cdp.send("Target.disposeBrowserContext", { browserContextId });
        }
        results.push(result);
        onResult(result);
        if (out) writeFileSync(path.join(out, `${phase}-render.json`), JSON.stringify(results, null, 2));
      }));
    }
  } finally {
    cdp?.close();
    try { await browser?.close(); } finally { local?.server.close(); }
  }
  return results;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const phase = process.argv[2] ?? "after";
  const only = process.argv[3]?.split(",");
  const results = await renderTextCheck({ phase, only, dist: process.argv[4], out: "D:/Novels/native_desk_proto/webcut_shots", onResult: r => console.log(`${r.id} ${r.width}: ${r.findings.length} cuts, ${r.errors.length} errors`) });
  const bad = results.filter(r => r.findings.length || r.errors.length);
  console.log(`${results.length} renders; ${bad.length} failed`);
  if (bad.length) process.exitCode = 1;
}
