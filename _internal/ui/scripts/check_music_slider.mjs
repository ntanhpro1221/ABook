// Real Chromium hit-testing and drag/release checks, using the existing gallery.
// node scripts/check_music_slider.mjs --dist <gallery build> --out <evidence dir>
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { parseArgs, findBrowser, serve, launch, connect, openPage, waitUntil, evaluate, STILL } from "./gallery_browser.mjs";

const args = parseArgs(process.argv.slice(2));
assert(args.out && args.dist, "--dist and --out are required");
mkdirSync(args.out, { recursive: true });
const local = await serve(args.dist);
let browser, cdp;
const results = [];
try {
  browser = await launch(findBrowser(args.browser), { softwareRendering: true });
  cdp = await connect(browser.endpoint);
  for (const id of ["desktop/studio-music", "desktop/book-edit-music-level", "desktop/player-music-level"]) {
    for (const theme of ["light", "dark"]) {
      const page = await openPage(cdp, { width: 1280, height: 900, scale: 2, mobile: false, theme });
      const sid = page.sessionId;
      try {
        await cdp.send("Page.navigate", { url: `${local.base}?frame=${id}&theme=${theme}` }, sid);
        await waitUntil(cdp, sid, "Boolean(window.__gallery?.ready && document.querySelector('[data-music-level] [role=slider]'))", 30000, id);
        await evaluate(cdp, sid, "document.fonts.ready");
        await evaluate(cdp, sid, STILL);
        const info = await evaluate(cdp, sid, `(() => {
          const thumb = document.querySelector('[data-music-level] [role=slider]');
          thumb.scrollIntoView({block:'center'});
          const box = thumb.getBoundingClientRect();
          const hit = document.elementFromPoint(box.x + box.width/2, box.y + box.height/2);
          const track = thumb.closest('[data-music-level]').querySelector('[data-orientation=horizontal]');
          const t = track.getBoundingClientRect();
          const h = thumb.closest('[data-music-level]').getBoundingClientRect();
          window.__levelWrites = [];
          const fetch = window.fetch;
          window.fetch = (url, init) => {
            if (init?.method === 'PUT' && String(url).includes('/music')) {
              window.__levelWrites.push(JSON.parse(init.body));
              return new Promise(() => {});
            }
            return fetch(url, init);
          };
          return {hit:hit === thumb || thumb.contains(hit), x:box.x+box.width/2, y:box.y+box.height/2,
            end:t.right+8, text:thumb.getAttribute('aria-valuetext'), errors:window.__gallery.errors,
            clip:{x:h.x-4,y:h.y-4,width:h.width+8,height:h.height+8,scale:1}};
        })()`);
        assert(info.hit, `${id}: thumb blocked at elementFromPoint`);
        assert.deepEqual(info.errors, [], `${id}: gallery errors`);
        const { data } = await cdp.send("Page.captureScreenshot", { format: "png" }, sid);
        const file = `${id.replaceAll("/", "__")}-${theme}@2x.png`;
        writeFileSync(path.join(args.out, file), Buffer.from(data, "base64"));
        const crop = await cdp.send("Page.captureScreenshot", { format: "png", clip: info.clip }, sid);
        writeFileSync(path.join(args.out, file.replace("@2x", "-slider@2x")), Buffer.from(crop.data, "base64"));
        await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: info.x, y: info.y, button: "left", clickCount: 1, buttons: 1 }, sid);
        await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: info.end, y: info.y, button: "left", buttons: 1 }, sid);
        await waitUntil(cdp, sid, "document.querySelector('[data-music-level] [role=slider]').getAttribute('aria-valuenow') === '-6'", 5000, "drag to maximum");
        assert.deepEqual(await evaluate(cdp, sid, "window.__levelWrites"), [], "drag must not save before release");
        await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: info.end, y: info.y, button: "left", clickCount: 1, buttons: 0 }, sid);
        await waitUntil(cdp, sid, "window.__levelWrites.length === 1", 5000, "release saves once");
        assert.equal((await evaluate(cdp, sid, "window.__levelWrites"))[0].levelDb, -6);
        await evaluate(cdp, sid, "window.__levelWrites = []; document.querySelector('[data-music-level] [role=slider]').focus()");
        await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "ArrowLeft", code: "ArrowLeft", windowsVirtualKeyCode: 37 }, sid);
        await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "ArrowLeft", code: "ArrowLeft", windowsVirtualKeyCode: 37 }, sid);
        await waitUntil(cdp, sid, "window.__levelWrites.length === 1", 5000, "keyboard saves once");
        assert.equal((await evaluate(cdp, sid, "window.__levelWrites"))[0].levelDb, -7);
        results.push({ id, theme, file, initial: info.text, hit: true, dragged: -6, saved: -6, keyboard: -7 });
        console.log(`PASS ${id} ${theme}: thumb hit, drag -6, one save on release, keyboard -7`);
      } catch (error) {
        console.error(await evaluate(cdp, sid, "JSON.stringify({gallery:window.__gallery, text:document.body.innerText.slice(-2500)})"));
        throw error;
      } finally {
        await cdp.send("Target.closeTarget", { targetId: page.targetId });
      }
    }
  }
} finally {
  cdp?.close();
  await browser?.close();
  local.server.close();
  writeFileSync(path.join(args.out, "slider-checks.json"), JSON.stringify(results, null, 2));
}
