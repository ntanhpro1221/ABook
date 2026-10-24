#!/usr/bin/env node
// Đối chứng thật trên Edge: glyph cũ và glyph hiện hành, cùng phông app và cùng bộ soi dùng cho gallery.
import { readFileSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs, serve, findBrowser, launch, connect, openPage, evaluate, escapeHtml } from "./gallery_browser.mjs";
import { inspectionExpression, settle, captureCrops } from "./gallery_inspect.mjs";

const args = parseArgs(process.argv.slice(2));
if (!args.out) throw new Error("Cần --out DIR");
const out = path.resolve(args.out);
mkdirSync(path.join(out, "crops"), { recursive: true });
let local, browser, cdp;
try {
  local = await serve(args.dist);
  browser = await launch(findBrowser(args.browser), { preserveProfile: true });
  cdp = await connect(browser.endpoint);
  const page = await openPage(cdp, { width: 1000, height: 400, scale: 1, mobile: false, theme: "light" });
  await cdp.send("Page.navigate", { url: local.base }, page.sessionId);
  // Không dựng app: chỉ nạp stylesheet phát hành trong bản gallery để đo đúng font, không dùng fallback.
  const stylesheet = readdirSync(path.join(args.dist, "assets")).find((name) => /^frame-.*\.css$/.test(name));
  const fixture = readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures/skip-glyph.html"), "utf8")
    .replace("<style>", `<link rel="stylesheet" href="${new URL(`assets/${stylesheet}`, local.base).href}"><style>`);
  const { frameTree } = await cdp.send("Page.getFrameTree", {}, page.sessionId);
  await cdp.send("Page.setDocumentContent", { frameId: frameTree.frame.id, html: fixture }, page.sessionId);
  await settle(cdp, page.sessionId, args.timeout);
  const result = await evaluate(cdp, page.sessionId, inspectionExpression(false));
  const crop = captureCrops(cdp, page.sessionId, out, "skip-fixture", { width: 1000, height: 400 });
  for (const finding of result.findings) finding.crop = await crop(finding.rects);
  const controls = [];
  for (const contact of result.contacts) controls.push({ ...contact, crop: await crop([contact.rect]) });
  const old = result.findings.filter((f) => f.rule === "TEXT-OVER-GRAPHIC" && f.selector.startsWith("#old-case"));
  const current = result.findings.filter((f) => f.rule === "TEXT-OVER-GRAPHIC" && f.selector.startsWith("#new-case"));
  const report = { oldCommit: "0bec019f", newCommit: "398db035", oldFlagged: old.length > 0, newPassed: current.length === 0, ...result, controls };
  writeFileSync(path.join(out, "findings.json"), JSON.stringify(report, null, 2));
  writeFileSync(path.join(out, "index.html"), `<!doctype html><html lang="vi"><meta charset="utf-8"><title>Đối chứng glyph 15</title><style>body{font:16px system-ui;margin:24px}section{display:flex;flex-wrap:wrap;gap:24px}figure{margin:12px}img{display:block}code{display:block;font-size:12px;max-width:500px;overflow-wrap:anywhere}</style><h1>Glyph cũ: ${report.oldFlagged ? "bị bắt" : "BỎ SÓT"}; glyph mới: ${report.newPassed ? "qua quy tắc 1" : "LỖI"}</h1><h2>Phát hiện</h2><section>${result.findings.map((f) => `<figure><img src="${f.crop}"><figcaption>${escapeHtml(f.rule)} · ${escapeHtml(f.text)}<code>${escapeHtml(f.selector)}</code></figcaption></figure>`).join("")}</section><h2>Mọi điều khiển và SVG · 4×</h2><section>${controls.map((c) => `<figure><img src="${c.crop}"><figcaption>${escapeHtml(c.text)}<code>${escapeHtml(c.selector)}</code></figcaption></figure>`).join("")}</section></html>`);
  console.log(JSON.stringify({ oldFlagged: report.oldFlagged, newPassed: report.newPassed, rules: result.findings.map((f) => [f.rule, f.selector]) }));
  if (!report.oldFlagged || !report.newPassed) process.exitCode = 1;
} finally {
  cdp?.close();
  try { await browser?.close(); } finally { local?.server.close(); }
}
