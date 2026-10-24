#!/usr/bin/env node
// Đối chứng quy tắc 8–9 bằng layout thật; dùng nguyên bộ soi và ảnh cắt của gallery.
import assert from "node:assert/strict";
import { readFileSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs, serve, findBrowser, launch, connect, openPage, evaluate, escapeHtml as esc } from "./gallery_browser.mjs";
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
  const viewport = { width: 1250, height: 650 };
  const page = await openPage(cdp, { ...viewport, scale: 1, mobile: false, theme: "light" });
  await cdp.send("Page.navigate", { url: local.base }, page.sessionId);
  const stylesheet = readdirSync(path.join(args.dist, "assets")).find((name) => /^frame-.*\.css$/.test(name));
  const fixture = readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures/sibling-icons.html"), "utf8")
    .replace("<style>", `<link rel="stylesheet" href="${new URL(`assets/${stylesheet}`, local.base).href}"><style>`);
  const { frameTree } = await cdp.send("Page.getFrameTree", {}, page.sessionId);
  await cdp.send("Page.setDocumentContent", { frameId: frameTree.frame.id, html: fixture }, page.sessionId);
  await settle(cdp, page.sessionId, args.timeout);
  const result = await evaluate(cdp, page.sessionId, inspectionExpression(false));
  const crop = captureCrops(cdp, page.sessionId, out, "siblings", viewport);
  for (const finding of result.findings) finding.crop = await crop(finding.rects);
  for (const contact of result.contacts) contact.crop = await crop([contact.rect]);
  const at = (list, rule, metric) => result.findings.filter((f) => f.listSelector === `#${list}` && f.rule === rule && (!metric || f.metric === metric));
  const proof = {
    boxesRule8: at("unequal-boxes", "SIBLING CONSISTENCY", "text-left").some((f) => f.delta === -6),
    boxesRule9: at("unequal-boxes", "OPTICAL SIZE CONSISTENCY").some((f) => f.delta === -6),
    inkRule8: at("unequal-ink", "SIBLING CONSISTENCY", "icon-text-gap").some((f) => f.delta === 3),
    inkRule9: at("unequal-ink", "OPTICAL SIZE CONSISTENCY").some((f) => f.delta === -6),
    gap3_5: at("unequal-gap", "SIBLING CONSISTENCY", "icon-text-gap").some((f) => f.delta === 3.5),
    equalSilent: !result.findings.some((f) => f.listSelector === "#equal-icons"),
    negativeGap: at("overflow-icons", "SIBLING CONSISTENCY", "icon-text-overlap").some((f) => f.value < 0),
    differentGlyphsSilentRule9: at("overflow-icons", "OPTICAL SIZE CONSISTENCY").length === 0,
  };
  writeFileSync(path.join(out, "findings.json"), JSON.stringify({ proof, ...result }, null, 2));
  writeFileSync(path.join(out, "index.html"), `<!doctype html><html lang="vi"><meta charset="utf-8"><title>Đối chứng quy tắc 8–9</title><style>body{font:14px system-ui;margin:24px}figure{display:inline-block;vertical-align:top;max-width:95%;margin:12px}img{display:block;max-width:100%}code{display:block;overflow-wrap:anywhere}</style><h1>Đối chứng quy tắc 8–9</h1><pre>${esc(JSON.stringify(proof, null, 2))}</pre>${result.findings.map((f) => `<figure><a href="${f.crop}"><img src="${f.crop}"></a><figcaption>${esc(f.rule)} · hàng ${f.rowIndex ?? "—"} / mốc ${f.referenceRowIndex ?? "—"}<code>${esc(f.selector)}</code>${esc(f.metric)}: ${f.value} / ${f.referenceValue ?? "—"} px · Δ ${f.delta ?? "—"} px</figcaption></figure>`).join("")}</html>`);
  console.log(JSON.stringify(proof));
  for (const [name, passed] of Object.entries(proof)) assert(passed, name);
} finally {
  cdp?.close();
  try { await browser?.close(); } finally { local?.server.close(); }
}
