// Real Chromium hit-testing for the floating "Đang nghe thử" bar over the music list (gallery desktop/music-library-previewing).
// The DOM test (PreviewBar.dom.test.tsx) cannot lay anything out, so a click on the bar's padding there proves nothing; here the browser
// decides what is under each point. For every padding / gap point of the bar: elementFromPoint lands inside [data-preview-bar], a track row
// really lies under that point (elementsFromPoint), and a real mouse click there neither opens a track nor stops the preview.
// A click on the bar body opens the previewing track. The title line wraps (no ellipsis).
// node scripts/check_preview_bar.mjs --dist <gallery build> --out <evidence dir>
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
const id = "desktop/music-library-previewing";
try {
  browser = await launch(findBrowser(args.browser), { softwareRendering: true });
  cdp = await connect(browser.endpoint);
  for (const [width, height] of [[1280, 900], [420, 860]]) {
    for (const theme of ["light", "dark"]) {
      const page = await openPage(cdp, { width, height, scale: 2, mobile: false, theme });
      const sid = page.sessionId;
      try {
        await cdp.send("Page.navigate", { url: `${local.base}?frame=${id}&theme=${theme}` }, sid);
        await waitUntil(cdp, sid, "Boolean(window.__gallery?.ready && document.querySelector('[data-preview-bar]'))", 30000, id);
        await evaluate(cdp, sid, "document.fonts.ready");
        await evaluate(cdp, sid, STILL);
        const info = await evaluate(cdp, sid, `(() => {
          const bar = document.querySelector('[data-preview-bar]');
          const body = bar.querySelector('[data-preview-open]');
          const stop = [...bar.querySelectorAll('button')].find((b) => b !== body);
          const b = bar.getBoundingClientRect(), o = body.getBoundingClientRect(), s = stop.getBoundingClientRect();
          const cy = b.y + b.height / 2;
          // Phần đệm trái, phần đệm trên/dưới (giữa thân), khe giữa thân và nút dừng, phần đệm phải.
          const points = {
            padLeft: [b.x + (o.x - b.x) / 2, cy],
            padTop: [o.x + o.width / 2, b.y + (o.y - b.y) / 2],
            padBottom: [o.x + o.width / 2, o.bottom + (b.bottom - o.bottom) / 2],
            gap: [o.right + (s.x - o.right) / 2, cy],
            padRight: [s.right + (b.right - s.right) / 2, cy],
          };
          const out = {};
          for (const [name, [x, y]] of Object.entries(points)) {
            const hit = document.elementFromPoint(x, y);
            const under = document.elementsFromPoint(x, y).find((el) => !bar.contains(el) && el.closest('[role=listitem], li') && !el.closest('[data-preview-bar]'));
            out[name] = { x, y, inside: Boolean(hit && bar.contains(hit) && hit !== body && !body.contains(hit) && hit !== stop && !stop.contains(hit)),
              hit: hit ? hit.tagName + '.' + String(hit.className).slice(0, 40) : null, rowUnder: Boolean(under) };
          }
          const line = body.querySelector('span.text-sm') ?? body.querySelector('span');
          const style = getComputedStyle(line);
          return { points: out, body: [o.x + o.width / 2, o.y + o.height / 2], wrap: style.whiteSpace, overflow: style.textOverflow,
            label: body.getAttribute('aria-label'), description: body.getAttribute('aria-description'), text: body.textContent,
            errors: window.__gallery.errors, clip: { x: b.x - 6, y: b.y - 6, width: b.width + 12, height: b.height + 12, scale: 1 } };
        })()`);
        assert.deepEqual(info.errors, [], `${id}: gallery errors`);
        assert.equal(info.label, null, "the bar body is named by its own line (status · title), not a separate aria-label");
        assert.equal(info.description, "Mở", "the bar body describes its action as Mở");
        assert.match(info.text, /^(Đang nghe thử|Đang đệm|Đã tạm dừng)\s·\s./, `bar line: ${info.text}`);
        assert.notEqual(info.wrap, "nowrap", "the title line wraps instead of being cut");
        assert.notEqual(info.overflow, "ellipsis", "the title line is never cut with an ellipsis");
        for (const [name, point] of Object.entries(info.points)) {
          assert(point.inside, `${width}x${height} ${theme} ${name}: the point lands on ${point.hit}, not on the bar's own padding`);
        }
        assert(Object.values(info.points).some((p) => p.rowUnder), `${width}x${height}: no track row lies under the bar - the check would prove nothing`);
        const crop = await cdp.send("Page.captureScreenshot", { format: "png", clip: info.clip }, sid);
        const file = `${id.replaceAll("/", "__")}-${width}-${theme}-bar@2x.png`;
        writeFileSync(path.join(args.out, file), Buffer.from(crop.data, "base64"));
        const realClick = async ([x, y]) => {
          await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1, buttons: 1 }, sid);
          await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1, buttons: 0 }, sid);
        };
        const opened = "Boolean([...document.querySelectorAll('[role=dialog]')].find((d) => !d.closest('[aria-hidden=true]')))";
        for (const [name, point] of Object.entries(info.points)) {
          await realClick([point.x, point.y]);
          await evaluate(cdp, sid, "new Promise((r) => setTimeout(r, 150))");
          assert.equal(await evaluate(cdp, sid, opened), false, `${name}: a click on the bar's padding opened a track`);
          assert.equal(await evaluate(cdp, sid, "Boolean(document.querySelector('[data-preview-bar]'))"), true, `${name}: a click on the padding stopped the preview`);
        }
        await realClick(info.body);
        await waitUntil(cdp, sid, opened, 5000, "the bar body opens the previewing track");
        results.push({ width, height, theme, file, points: info.points, text: info.text });
        console.log(`PASS ${width}x${height} ${theme}: ${Object.keys(info.points).length} padding points stay in the bar, body opens the track`);
      } catch (error) {
        console.error(await evaluate(cdp, sid, "JSON.stringify({gallery:window.__gallery, text:document.body.innerText.slice(-1500)})"));
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
  writeFileSync(path.join(args.out, "preview-bar-checks.json"), JSON.stringify(results, null, 2));
}
