// @vitest-environment node
import path from "node:path";
import { beforeAll, expect, it } from "vitest";
import { build } from "vite";
import { ENTRIES } from "../src/gallery/entries";
import { connect, evaluate, findBrowser, launch, openPage } from "./gallery_browser.mjs";
import { renderTextCheck, textCuts } from "./text_cut_render.mjs";

const widths = [360, 412, 1024, 1440];
let results;
beforeAll(async () => {
  // Always build current source; a stale gallery must never make this pass.
  // Vitest sets NODE_ENV=test; React's JSX transform and runtime must both be
  // built in production mode, just like `npm run gallery:build`.
  const nodeEnv = process.env.NODE_ENV;
  process.env.NODE_ENV = "production";
  try {
    await build({ configFile: path.resolve(import.meta.dirname, "../vite.gallery.config.ts"), mode: "production", logLevel: "silent" });
  } finally {
    if (nodeEnv === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = nodeEnv;
  }
  results = await renderTextCheck({ widths, out: path.resolve(import.meta.dirname, "../dist/text-cut"),
    onResult: r => { if (r.width === 1440) console.log(`Text visibility: ${r.id}`); } });
}, 1_800_000);

it.each(ENTRIES.flatMap(entry => widths.map(width => [entry.id, width])))("complete rendered text: %s at %i px", (id, width) => {
  const result = results.find(r => r.id === id && r.width === width);
  expect(result, "screen must be rendered, never silently skipped").toBeDefined();
  expect(result.errors).toEqual([]);
  expect(result.findings).toEqual([]);
});

it("render detector catches direct and ancestor clipping, allows wrapping, scrollable content and accessible-only labels", async () => {
  const browser = await launch(findBrowser(), { preserveProfile: true });
  const cdp = await connect(browser.endpoint);
  try {
    const page = await openPage(cdp, { width: 360, height: 800, scale: 1, mobile: false, theme: "light" });
    await evaluate(cdp, page.sessionId, `document.body.innerHTML = ${JSON.stringify(`<style>
      .cut { width: 80px; overflow: hidden; white-space: nowrap; }
      .ancestor { width: 80px; height: 18px; overflow: clip; }
      .wrap { width: 80px; overflow-wrap: anywhere; }
      .scroll { height: 20px; overflow-y: auto; width: 80px; }
      .screenreader { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
      </style><p class="cut">Tên sách dài bị cắt ngay ở đây</p>
      <div class="ancestor"><span>Tên sách dài bị khung cha cắt mất phần cuối</span></div>
      <p class="wrap">Tên sách dài vẫn xuống dòng đầy đủ</p>
      <div class="scroll"><p>Nội dung dài có thể cuộn để đọc trọn vẹn</p></div>
      <span class="screenreader">Nhãn trợ năng</span>`)}`);
    const cuts = await evaluate(cdp, page.sessionId, `(${textCuts.toString()})()`);
    expect(cuts.map(c => c.text)).toEqual(["Tên sách dài bị cắt ngay ở đây", "Tên sách dài bị khung cha cắt mất phần cuối"]);
  } finally { cdp.close(); await browser.close(); }
});
