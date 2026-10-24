#!/usr/bin/env node
// Real Chromium layout, paired negative/positive cases for precision and recall.
import assert from "node:assert/strict";
import { mkdirSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { parseArgs, serve, launch, findBrowser, connect, openPage, evaluate } from "./gallery_browser.mjs";
import { inspectionExpression, captureCrops, settle } from "./gallery_inspect.mjs";

const svg = (size = 18, shape = '<rect width="18" height="18"/>') => `<svg width="${size}" height="${size}" viewBox="0 0 18 18">${shape}</svg>`;
const rows = (a, b, styleA = "", styleB = "") => `<ul><li><button style="${styleA}">${a}</button></li><li><button style="${styleB}">${b}</button></li></ul>`;
const row = (size = 18, shape) => `${svg(size, shape)}<span>Label</span>`;
export const precisionCases = [
  { name: "overlay", rule: "TEXT-OVER-GRAPHIC", good: `<div data-overlay="art" class="layer">${svg()}<span>15</span></div>`, bad: `<div class="layer">${svg()}<span>15</span></div>` },
  { name: "scroll-fade", rule: "TEXT-OVER-GRAPHIC", good: '<div class="layer"><span>15</span><div aria-hidden="true" style="position:absolute;inset:0;pointer-events:none;background:linear-gradient(to top,#fff,transparent)"></div></div>', bad: '<div class="layer"><div style="position:absolute;inset:0;pointer-events:none;background:linear-gradient(to top,#fff,#888)"></div><span>15</span></div>' },
  { name: "hidden-zero-graphic", rule: "TEXT-OVER-GRAPHIC", good: `<div class="layer">${svg().replace('<svg ', '<svg style="display:none" ')}${svg(0)}<span>15</span></div>`, bad: `<div class="layer">${svg()}<span>15</span></div>` },
  { name: "font-padding", rule: "TEXT-OVER-TEXT", good: '<div class="line" style="top:20px">mmm</div><div class="line" style="top:33px">mmm</div>', bad: '<div class="line" style="top:20px">mmm</div><div class="line" style="top:23px">mmm</div>' },
  { name: "glyph-empty-corners", rule: "TEXT-OVER-TEXT", good: '<div class="line" style="left:24px;top:20px">O</div><div class="line" style="left:33px;top:29px">O</div>', bad: '<div class="line" style="left:24px;top:20px">O</div><div class="line" style="left:27px;top:23px">O</div>' },
  { name: "paused-status-eta", appFont: true, rule: "TEXT-OVER-TEXT", good: '<span class="line" style="left:24px;top:20px;font:500 12px Be Vietnam Pro">Tạm dừng · máy đang chạy pin</span><div class="line" style="left:188.75px;top:28.8125px;font:400 12px Be Vietnam Pro">pha thu âm còn khoảng 9 giờ</div>', bad: '<span class="line" style="left:24px;top:20px;font:500 12px Be Vietnam Pro">Tạm dừng · máy đang chạy pin</span><div class="line" style="left:188.75px;top:22px;font:400 12px Be Vietnam Pro">pha thu âm còn khoảng 9 giờ</div>' },
  { name: "one-element-text-nodes", rule: "TEXT-OVER-TEXT", good: '<div>some <!-- split -->more words</div>', bad: '<div class="line" style="top:20px">hello</div><div class="line" style="top:20px">world</div>' },
  { name: "skip-link", rule: "CLIPPED TEXT", good: '<a href="#main" style="position:absolute;top:-100px">Skip to content</a><main id="main">Content</main>', bad: '<a href="https://example.invalid" style="position:absolute;top:-100px">Lost content</a><main>Content</main>' },
  { name: "focus-revealed-control", rule: "CLIPPED TEXT", good: '<button class="focus:translate-y-0" style="position:fixed;top:-100px">Skip</button>', bad: '<button style="position:fixed;top:-100px">Lost control</button>' },
  { name: "truncation", rule: "CLIPPED TEXT", good: '<div style="width:30px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">Long visible sentence</div>', bad: '<div style="width:30px;overflow:hidden;white-space:nowrap">Long visible sentence</div>' },
  { name: "effective-font", rule: "SMALL TEXT", good: '<span style="display:inline-block;font-size:10px;transform:scale(1.2)">Transformed label</span>', bad: '<span style="font-size:8px">Tiny label</span>' },
  { name: "pseudo-hit", rule: "TOUCH TARGET", good: '<button class="hit" style="width:20px;height:20px;padding:0">X</button>', bad: '<button style="width:20px;height:20px;padding:0">X</button>' },
  { name: "label-hit", rule: "TOUCH TARGET", good: '<label style="display:flex;width:100px;height:48px;align-items:center"><input type="checkbox" style="width:14px;height:14px">Check</label>', bad: '<input type="checkbox" style="width:14px;height:14px">' },
  { name: "disabled-contrast", rule: "CONTRAST", good: '<button disabled style="color:#bbb">Unavailable</button>', bad: '<button style="color:#bbb">Available</button>' },
  { name: "aria-disabled-contrast", rule: "CONTRAST", good: '<button aria-disabled="true" style="color:#bbb">Unavailable</button>', bad: '<button style="color:#bbb">Available</button>' },
  { name: "icon-roles", rule: "ICON SIZE MISMATCH", good: `<div class="flex">${svg(18)}${svg(12, '<circle cx="9" cy="9" r="8"/>')}</div>`, bad: `<div class="flex">${svg(18)}${svg(12)}</div>` },
  { name: "decorative-labels", rule: "SIBLING CONSISTENCY", good: rows('<span aria-hidden="true" style="width:50px;text-align:center">AB</span><span>Label</span>', '<span aria-hidden="true" style="width:50px;text-align:center">WIDE</span><span>Label</span>'), bad: rows(row(), row(), '', 'padding-left:14px') },
  { name: "centered-labels", rule: "SIBLING CONSISTENCY", good: rows('<span>Short</span>', '<span>Much longer</span>', 'justify-content:center', 'justify-content:center'), bad: rows('<span>Short</span>', '<span>Much longer</span>', '', 'padding-left:14px') },
  { name: "fragmented-label", rule: "SIBLING CONSISTENCY", good: rows('<span>Chapter <!-- -->1<!-- --> · Short</span>', '<span>Chapter <!-- -->10<!-- --> · Longer words</span>'), bad: rows('<span>Chapter <!-- -->1<!-- --> · Short</span>', '<span>Chapter <!-- -->10<!-- --> · Longer words</span>', '', 'padding-left:14px') },
  { name: "different-states", rule: "SIBLING CONSISTENCY", good: '<ul><li><button aria-selected="false">Normal</button></li><li><button aria-selected="true" style="padding-left:14px">Selected</button></li></ul>', bad: rows(row(), row(), '', 'padding-left:14px') },
  { name: "row-origin", rule: "SIBLING CONSISTENCY", good: `<ul><li><button>${row()}</button></li><li style="margin-left:8px"><button>${row()}</button></li></ul>`, bad: rows(row(), row(), '', 'padding-left:14px') },
  { name: "subpixel-noise", rule: "SIBLING CONSISTENCY", good: rows(row(), row(), '', 'padding-left:9.001px'), bad: rows(row(), row(), '', 'padding-left:11.5px') },
  { name: "glyph-identity-gap", rule: "SIBLING CONSISTENCY", good: rows(row(18), row(18, '<rect x="3" y="3" width="12" height="12"/>').replace('<svg ', '<svg class="lucide-other" ')), bad: rows(row(), row(), '', 'gap:13.5px') },
  { name: "glyph-identity-ink", rule: "OPTICAL SIZE CONSISTENCY", good: rows(row(18), row(18, '<path d="M5 0L12 9L5 18Z"/>')), bad: rows(row(18), row(18, '<rect x="3" y="3" width="12" height="12"/>')) },
  { name: "hidden-row", rule: "OPTICAL SIZE CONSISTENCY", good: `<ul><li><button>${row()}</button></li><li hidden><button>${row(12)}</button></li></ul>`, bad: rows(row(), row(12)) },
];

async function main() {
  const args = parseArgs(process.argv.slice(2)), out = path.resolve(args.out);
  mkdirSync(path.join(out, "crops"), { recursive: true });
  const local = await serve(args.dist), browser = await launch(findBrowser(args.browser), { preserveProfile: true });
  const cdp = await connect(browser.endpoint), results = [];
  try {
    const viewport = { width: 1000, height: 650 };
    const page = await openPage(cdp, { ...viewport, scale: 1, mobile: false, theme: "light" });
    await cdp.send("Page.navigate", { url: local.base }, page.sessionId);
    const { frameTree } = await cdp.send("Page.getFrameTree", {}, page.sessionId);
    const stylesheet = readdirSync(path.join(args.dist, "assets")).find((name) => /^frame-.*\.css$/.test(name));
    for (const item of precisionCases) for (const variant of ["good", "bad"]) {
      const html = `<!doctype html><style>body{margin:24px;font:16px Arial;background:white;color:black}ul{padding:0;list-style:none}li{margin:0}button{display:flex;gap:10px;align-items:center;width:260px;height:44px;padding:8px;border:0;background:white;color:black;font:inherit;text-align:left}svg{flex-shrink:0;fill:currentColor} .flex{display:flex;gap:10px}.layer{position:relative;width:50px;height:50px}.layer svg,.layer span{position:absolute;top:0;left:0}.line{position:absolute;font:16px Arial}.hit{position:relative}.hit::after{content:"";position:absolute;left:50%;top:50%;width:44px;height:44px;transform:translate(-50%,-50%)}</style>${item[variant]}`;
      await cdp.send("Page.setDocumentContent", { frameId: frameTree.frame.id, html: item.appFont ? html.replace("<style>", `<link rel="stylesheet" href="${new URL(`assets/${stylesheet}`, local.base).href}"><style>`) : html }, page.sessionId);
      await evaluate(cdp, page.sessionId, 'document.fonts.ready.then(() => true)');
      if (item.appFont) await settle(cdp, page.sessionId, args.timeout);
      const result = await evaluate(cdp, page.sessionId, inspectionExpression(true));
      const findings = result.findings.filter((f) => f.rule === item.rule);
      const crop = captureCrops(cdp, page.sessionId, out, `${item.name}-${variant}`, viewport);
      for (const f of findings) f.crop = await crop(f.rects);
      const screenshot = await crop([{ x: 0, y: 0, width: 400, height: 200 }]);
      results.push({ name: item.name, variant, rule: item.rule, passed: variant === "good" ? findings.length === 0 : findings.length > 0, screenshot, findings });
    }
    writeFileSync(path.join(out, "findings.json"), JSON.stringify(results, null, 2));
    console.log(results.map((r) => `${r.passed ? "PASS" : "FAIL"} ${r.name} ${r.variant}: ${r.findings.length}`).join("\n"));
    assert(results.every((r) => r.passed), `${results.filter((r) => !r.passed).length} fixture checks failed`);
  } finally { cdp.close(); await browser.close(); local.server.close(); }
}
if (process.argv[1]?.endsWith("gallery_inspect_precision_fixture.mjs")) main().catch((e) => { console.error(e); process.exitCode = 1; });
