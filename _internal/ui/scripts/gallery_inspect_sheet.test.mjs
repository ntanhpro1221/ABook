// @vitest-environment node
import { describe, expect, it } from "vitest";
import { compareGeometry, SHEET_RULE } from "./gallery_inspect_sheet.mjs";
import { DEFAULT_FAIL_ON, normalizeRule } from "./gallery_inspect.mjs";
import { createServer } from "node:http";
import { browserAvailable, launch, findBrowser, connect, openPage, evaluate } from "./gallery_browser.mjs";
import { installGeometryProbe, pointerClick } from "./gallery_inspect_sheet.mjs";

const snapshot = () => ({
  scrollTop: 350, scrollbarWidth: 15,
  styles: Object.fromEntries(["body", "html"].map(tag => [tag, { paddingLeft: "0px", marginRight: "0px", overflow: "auto" }])),
  anchors: [{ selector: "main", rect: { x: 12, y: -350, width: 900, height: 2000 }, scrollTop: 120, scrollLeft: 0 }],
});

it.skipIf(!browserAvailable)("isolated headless windows: native scrollbar, trusted pointer, clean and broken geometry", async () => {
  const server = createServer((_request, response) => response.end(`<!doctype html><meta charset="utf-8">
    <style>main{height:2600px}#open{position:fixed;top:12px;left:12px} [role=dialog]{position:fixed;top:100px;left:100px;width:240px;height:180px;background:white}</style>
    <main><h1>Underlying heading</h1><ul><li>One</li><li>Two</li><li>Three</li></ul></main>
    <section class="now-playing" data-state="closed" inert><h2>Closed player</h2></section>
    <button id="open" aria-haspopup="dialog">Open</button>
    <script>document.querySelector('#open').addEventListener('click', event => {
      window.trusted = event.isTrusted;
      const dialog = document.createElement('section'); dialog.setAttribute('role','dialog'); dialog.dataset.state='open';
      const close = document.createElement('button'); close.setAttribute('aria-label','Đóng'); close.textContent='Close';
      close.addEventListener('click', () => dialog.remove()); dialog.append(close); document.body.append(dialog);
    });</script>`));
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  let browser, cdp;
  try {
    browser = await launch(findBrowser(), { hideScrollbars: false });
    cdp = await connect(browser.endpoint);
    const options = { width: 1000, height: 700, scale: 1, mobile: false, theme: "light", newWindow: true, isolated: true };
    const a = await openPage(cdp, options), b = await openPage(cdp, options);
    expect(a.browserContextId).not.toBe(b.browserContextId);
    const url = `http://127.0.0.1:${server.address().port}`;
    for (const page of [a, b]) {
      await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: `(${installGeometryProbe.toString()})()` }, page.sessionId);
      await cdp.send("Page.navigate", { url }, page.sessionId);
      await evaluate(cdp, page.sessionId, "document.readyState === 'complete' ? true : new Promise(resolve => addEventListener('load',resolve,{once:true}))");
    }
    await evaluate(cdp, a.sessionId, "localStorage.setItem('m1-isolation','one')");
    expect(await evaluate(cdp, b.sessionId, "localStorage.getItem('m1-isolation')")).toBeNull();
    await evaluate(cdp, a.sessionId, "window.__sheetProbe.capture(true)");
    expect(await evaluate(cdp, a.sessionId, "window.__sheetProbe.anchors.some(a => a.el.closest('.now-playing'))")).toBe(false);
    await evaluate(cdp, a.sessionId, "document.querySelector('.now-playing').dataset.state='open'; window.__sheetProbe.capture(true)");
    expect(await evaluate(cdp, a.sessionId, "window.__sheetProbe.anchors.some(a => a.el.closest('.now-playing'))")).toBe(true);
    await evaluate(cdp, a.sessionId, "document.querySelector('.now-playing').remove()");
    await evaluate(cdp, a.sessionId, `(() => {
      const exiting = document.createElement('section'); exiting.className='now-playing'; exiting.dataset.state='closed';
      document.body.append(exiting); setTimeout(() => exiting.remove(), 180);
    })()`);
    const settled = await evaluate(cdp, a.sessionId, "window.__sheetProbe.stable()");
    expect(settled.stable).toBe(true);
    expect(settled.elapsed).toBeGreaterThanOrEqual(150);
    await evaluate(cdp, a.sessionId, `(() => {
      const hidden = document.createElement('div'); hidden.className='page-motion'; hidden.id='hidden-scroll';
      hidden.style.cssText='height:100px;overflow:hidden'; hidden.innerHTML='<div style="height:500px"></div>';
      document.body.append(hidden); window.__sheetProbe.position(true);
    })()`);
    expect(await evaluate(cdp, a.sessionId, "document.scrollingElement.scrollTop")).toBeGreaterThan(0);
    expect(await evaluate(cdp, a.sessionId, "document.querySelector('#hidden-scroll').scrollTop")).toBe(0);
    await evaluate(cdp, a.sessionId, "document.body.style.overflow='hidden'; document.scrollingElement.scrollTop=0; window.__sheetProbe.position(true)");
    expect(await evaluate(cdp, a.sessionId, "document.scrollingElement.scrollTop")).toBe(0);
    await evaluate(cdp, a.sessionId, "document.body.style.overflow=''; document.querySelector('#hidden-scroll').remove()");
    await evaluate(cdp, a.sessionId, "document.scrollingElement.scrollTop=450");
    const before = await evaluate(cdp, a.sessionId, "window.__sheetProbe.capture(true)");
    expect(before.scrollTop).toBe(450);
    expect(before.scrollbarWidth).toBeGreaterThan(0);
    await evaluate(cdp, a.sessionId, `(() => {
      const toast = document.createElement('div'); toast.dataset.sonnerToast='';
      toast.style.cssText='position:fixed;inset:0 auto auto 0;width:100px;height:100px;z-index:1000;background:white';
      document.body.append(toast); setTimeout(() => toast.remove(), 180);
    })()`);
    const clickStarted = Date.now();
    await pointerClick(cdp, a.sessionId, "#open");
    expect(Date.now() - clickStarted).toBeGreaterThanOrEqual(150);
    expect(await evaluate(cdp, a.sessionId, "window.trusted")).toBe(true);
    expect((await evaluate(cdp, a.sessionId, "window.__sheetProbe.stable()")).stable).toBe(true);
    expect(compareGeometry(before, await evaluate(cdp, a.sessionId, "window.__sheetProbe.capture()"))).toEqual([]);
    await evaluate(cdp, a.sessionId, "document.body.style.paddingRight='24px'");
    expect(compareGeometry(before, await evaluate(cdp, a.sessionId, "window.__sheetProbe.capture()"))).toEqual(expect.arrayContaining([expect.objectContaining({ metric: "body-paddingRight", delta: 24 })]));
    await evaluate(cdp, a.sessionId, "document.body.style.paddingRight=''");
    await pointerClick(cdp, a.sessionId, '[role="dialog"] button');
    expect(compareGeometry(before, await evaluate(cdp, a.sessionId, "window.__sheetProbe.capture()"), { closed: true })).toEqual([]);
  } finally {
    cdp?.close();
    try { await browser?.close(); } finally { server.close(); }
  }
}, 60000);
describe("sheet geometry comparison", () => {
  it("gates release runs, including numbered aliases", () => {
    expect(DEFAULT_FAIL_ON).toContain(SHEET_RULE);
    expect(normalizeRule("rule25")).toBe(SHEET_RULE);
  });
  it("accepts unchanged geometry and the inclusive 0.5px boundary", () => {
    const a = snapshot(), b = snapshot();
    b.anchors[0].rect.x += 0.5;
    expect(compareGeometry(a, b)).toEqual([]);
  });
  it("detects translation and reflow just above tolerance in either direction", () => {
    const a = snapshot(), b = snapshot();
    b.anchors[0].rect.x -= 0.501; b.anchors[0].rect.height += 1;
    expect(compareGeometry(a, b).map(f => f.metric)).toEqual(["anchor-x", "anchor-height"]);
  });
  it("does not round away document or nested-container scroll changes", () => {
    const a = snapshot(), b = snapshot(); b.scrollTop += 0.1; b.anchors[0].scrollTop -= 1; b.anchors[0].scrollLeft += 1;
    expect(compareGeometry(a, b).map(f => f.metric)).toEqual(["document-scrollTop", "container-scrollTop", "container-scrollLeft"]);
  });
  it("detects scrollbar removal and padding/margin compensation even without an anchor shift", () => {
    const a = snapshot(), b = snapshot(); b.scrollbarWidth = 0; b.styles.body.paddingLeft = "15px"; b.styles.html.marginRight = "-15px";
    expect(compareGeometry(a, b).map(f => f.metric)).toEqual(["scrollbar-width", "body-paddingLeft", "html-marginRight"]);
  });
  it("records intentional scroll locking but requires restoration on both close paths", () => {
    const a = snapshot(), b = snapshot(); b.styles.body.overflow = "hidden";
    expect(compareGeometry(a, b)).toEqual([]);
    expect(compareGeometry(a, b, { closed: true })[0].metric).toBe("body-overflow");
  });
  it("fails closed when an underlying anchor disappears or measurement is invalid", () => {
    const a = snapshot(), b = snapshot(); b.anchors = [];
    expect(compareGeometry(a, b)[0].metric).toBe("missing-anchor");
    b.anchors = snapshot().anchors; b.anchors[0].rect.width = NaN;
    expect(compareGeometry(a, b)[0].metric).toBe("anchor-width");
  });
});
