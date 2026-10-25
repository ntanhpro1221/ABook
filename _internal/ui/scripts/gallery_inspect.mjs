#!/usr/bin/env node
// Soi chi tiết mọi mục gallery bằng hình học DOM; ảnh cắt phóng 4 lần qua CDP, không thêm dependency.
// node scripts/gallery_inspect.mjs --out ../../inspect --theme both [--browser PATH] [--only phone/player]
// Cùng --browser --out --only --theme --base --dist --timeout với gallery_shots.
// --fail-on none is advisory; a list replaces the audited default gate.
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs, findBrowser, serve, launch, connect, evaluate, waitUntil, openPage, escapeHtml as esc } from "./gallery_browser.mjs";
import { createInspectorHelpers, inspectPage } from "./gallery_inspect_helpers.mjs";
import { sourceIndex, deduplicate } from "./gallery_inspect_report.mjs";
import { createLayoutHelpers, inspectLayout, crossFrameRhythm, crossFrameTitles } from "./gallery_inspect_layout.mjs";
import { inspectAlignment } from "./gallery_inspect_alignment.mjs";
import { inspectTapReach } from "./gallery_inspect_tap.mjs";
import { inspectEdges } from "./gallery_inspect_edges.mjs";
import { inspectFrames } from "./gallery_inspect_frames.mjs";

export const RULES = ["TEXT-OVER-GRAPHIC", "TEXT-OVER-TEXT", "CLIPPED TEXT", "SMALL TEXT", "TOUCH TARGET", "CONTRAST", "ICON SIZE MISMATCH", "SIBLING CONSISTENCY", "OPTICAL SIZE CONSISTENCY", "INK EDGE", "RHYTHM", "BASELINE", "CONTROL HEIGHT", "FILL INSET", "TAP REACH", "FOCUS RING CLIPPED", "CORNER MISMATCH", "LINE BREAK", "COVERED TEXT", "REPEATED LABEL", "STACKED LAYERS", "NESTED CARD"];
// Gate đã có fixture hai phía; quy tắc 16–17 dùng cả đối chứng gallery gốc (rules144).
export const DEFAULT_FAIL_ON = ["SMALL TEXT", "TOUCH TARGET", "CONTRAST", "SIBLING CONSISTENCY", "INK EDGE", "RHYTHM", "BASELINE", "CONTROL HEIGHT", "TAP REACH", "FOCUS RING CLIPPED", "CORNER MISMATCH", "LINE BREAK", "COVERED TEXT", "REPEATED LABEL", "STACKED LAYERS", "NESTED CARD"];
export function gateRules(value) {
  return value === undefined ? [...DEFAULT_FAIL_ON] : value.length === 1 && value[0].toUpperCase() === "NONE" ? [] : value.map(normalizeRule);
}
export function normalizeRule(value) {
  const key = value.trim().toUpperCase().replaceAll("_", " ");
  const numbered = /^RULE([1-9]|1[0-9]|2[0-2])$/.exec(key);
  const rule = numbered ? RULES[Number(numbered[1]) - 1] : RULES.find((r) => r === key || r.replaceAll(" ", "-") === key);
  if (!rule) throw new Error(`Quy tắc lạ: ${value}. Chọn ${RULES.join(", ")}`);
  return rule;
}

export const inspectionExpression = (phone) => `(${inspectPage.toString()})(${JSON.stringify({ phone })}, (${createInspectorHelpers.toString()})(), (context) => ({ ...(${inspectLayout.toString()})(context, (${createLayoutHelpers.toString()})()), ...(${inspectAlignment.toString()})(context), ...(${inspectTapReach.toString()})(context), ...(${inspectEdges.toString()})(context), ...(${inspectFrames.toString()})(context) }))`;

export async function settle(cdp, session, timeout) {
  await evaluate(cdp, session, `(async () => {
    await document.fonts.ready;
    for (const weight of [400,500,600,700]) {
      await document.fonts.load(weight + ' 14px "Be Vietnam Pro"', 'Tiếng Việt Đặng Ánh 0123456789');
      await document.fonts.load(weight + ' 14px "Be Vietnam Pro Digits"', '0123456789');
    }
    // Spinner/skeleton chạy vô hạn không bao giờ kết thúc: giữ khung hiện tại rồi huỷ chuyển động để đo tĩnh.
    window.__inspectFrozenAnimations ??= [];
    window.__inspectFreezeInfinite = () => { for (const a of document.getAnimations()) {
      if (a.effect?.getComputedTiming().endTime === Infinity) {
        window.__inspectFrozenAnimations.push({ name: a.animationName ?? a.id, time: a.currentTime });
        a.pause();
        try { a.commitStyles(); } catch { /* Hiệu ứng không hỗ trợ commitStyles vẫn có thể huỷ. */ }
        a.cancel();
      }
    } };
    window.__inspectFreezeInfinite();
    window.__inspectStillSince = 0;
    return true;
  })()`);
  await waitUntil(cdp, session, `(() => {
    // Dữ liệu giả có thể retry sau ready: spinner mới cũng phải đứng yên, không chỉ loạt đầu.
    window.__inspectFreezeInfinite();
    const still = document.fonts.status === "loaded" && document.getAnimations().every(a => a.playState === "finished" || a.playState === "idle");
    if (!still) { window.__inspectStillSince = 0; return false; }
    window.__inspectStillSince ||= performance.now();
    return performance.now() - window.__inspectStillSince >= 300;
  })()`, timeout, "phông chữ và chuyển động");
  await evaluate(cdp, session, "new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))");
}

export function cropClip(rects, viewport) {
  const area = createInspectorHelpers().union(rects);
  const x = Math.max(0, Math.floor(area.x - 8)), y = Math.max(0, Math.floor(area.y - 8));
  const right = Math.min(viewport.width, Math.ceil(area.x + area.width + 8));
  const bottom = Math.min(viewport.height, Math.ceil(area.y + area.height + 8));
  return { x, y, width: Math.max(1, right - x), height: Math.max(1, bottom - y), scale: 4 };
}

export function captureCrops(cdp, session, out, stem, viewport, { nearest = false } = {}) {
  const cache = new Map();
  return async (rects) => {
    const clip = cropClip(rects, viewport);
    clip.scale = (nearest ? 1 : clip.scale) / (viewport.deviceScale ?? 1);
    const key = JSON.stringify(clip);
    if (cache.has(key)) return cache.get(key);
    const file = `crops/${stem}-${String(cache.size + 1).padStart(4, "0")}.png`;
    cache.set(key, file);
    let data;
    try { ({ data } = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false, clip }, session)); }
    catch (error) { throw new Error(`${error.message} · clip ${key}`); }
    if (nearest) data = await evaluate(cdp, session, `(async () => {
      const img = new Image(); img.src = ${JSON.stringify(`data:image/png;base64,${data}`)}; await img.decode();
      const canvas = document.createElement('canvas'); canvas.width = img.width * 4; canvas.height = img.height * 4;
      const ctx = canvas.getContext('2d'); ctx.imageSmoothingEnabled = false; ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL('image/png').split(',')[1];
    })()`);
    writeFileSync(path.join(out, file), Buffer.from(data, "base64"));
    return file;
  };
}

const sheetStyle = `body{font:14px/1.5 system-ui;margin:20px;background:#eee;color:#181818}a{color:#174ba2}code{overflow-wrap:anywhere}img{display:block;max-width:100%;height:auto;image-rendering:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;align-items:start}figure{margin:0;padding:12px;background:white;border:1px solid #bbb;overflow:auto}figcaption{margin-top:10px;overflow-wrap:anywhere}.wide img{max-width:none}summary{cursor:pointer;font-weight:bold}`;
const html = (title, body) => `<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${esc(title)}</title><style>${sheetStyle}</style><body>${body}</body></html>`;

function writeSheet(out, story) {
  const toastDetails = (story.tapToastOcclusions ?? []).map(item => `<p>Thông báo tạm che trang (không tính phát hiện): ${esc(item.text)} <code>${esc(item.selector)}</code> · pe: ${esc(item.pointerEvents)} · trúng <code>${esc(item.hitSelector)}</code> · toast <code>${esc(item.toastSelector)}</code> · <a href="../${esc(item.crop)}">Ảnh 4×</a></p>`).join("");
  writeFileSync(path.join(out, story.sheet), html(`${story.id} · ${story.theme}`, `<a href="../index.html">← Phát hiện</a><h1>${esc(story.id)} · ${story.theme}</h1><p>${story.contacts.length} điều khiển / SVG · ảnh gốc phóng 4×; bấm ảnh để xem nguyên cỡ.</p>${toastDetails}<label><input type="checkbox" onchange="document.body.classList.toggle('wide',this.checked)"> Hiện nguyên cỡ phóng đại</label><div class="grid">${story.contacts.map((c) => `<figure><a href="../${c.crop}"><img loading="lazy" src="../${c.crop}" alt="${esc(c.text)}"></a><figcaption>${esc(c.text)} · ${c.kind}<br><code>${esc(c.selector)}</code><br>${c.rect.width.toFixed(1)}×${c.rect.height.toFixed(1)} CSS px</figcaption></figure>`).join("")}</div>`));
}

// Một luật thiếu số không được làm đổ cả trang báo cáo (LINE BREAK/COVERED TEXT từng làm vậy ở lượt đầu).
const num = (value) => (Number.isFinite(value) ? value.toFixed(3) : "–");

export function writeOutputs(out, report) {
  writeFileSync(path.join(out, "findings.json"), JSON.stringify(report, null, 2));
  if (report.distinctDefects) writeFileSync(path.join(out, "distinct-defects.json"), JSON.stringify(report.distinctDefects, null, 2));
  const list = RULES.map((rule) => {
    const findings = report.findings.filter((f) => f.rule === rule);
    const groups = [...new Set(findings.map((f) => f.story))];
    return `<section><h2>${esc(rule)} (${findings.length})</h2>${groups.map((id) => `<details><summary>${esc(id)} (${findings.filter((f) => f.story === id).length})</summary><div class="grid">${findings.filter((f) => f.story === id).map((f) => `<figure id="${f.id}"><a href="${f.crop}"><img loading="lazy" src="${f.crop}" alt="${esc(f.text)}"></a><figcaption><b>${f.id} · ${f.theme}</b><br>${esc(f.text)}<br><code>${esc(f.selector)}</code>${f.rule === "TAP REACH" ? `<br>pe: ${esc(f.pointerEvents)} · trúng: <code>${esc(f.hitSelector ?? "null")}</code> · ${esc(f.hitText ?? "")}` : ""}${f.otherSelector || f.referenceSelector ? `<br>↔ <code>${esc(f.otherSelector ?? f.referenceSelector)}</code>` : ""}${f.fontSizes ? `<br>Cỡ chữ: ${f.fontSizes.join(" / ")} px` : ""}${f.topDelta !== undefined ? `<br>Δ trên / dưới: ${num(f.topDelta)} / ${num(f.bottomDelta)} px` : ""}${f.referenceValue !== undefined ? `<br>${f.rowIndex !== undefined ? `Hàng ${f.rowIndex} / mốc ${f.referenceRowIndex} · ` : ""}${esc(f.metric)}: ${num(f.value)} / ${num(f.referenceValue)} px · Δ ${num(f.delta)} px` : f.metric ? `<br>${esc(f.metric)}: ${num(f.value)} px` : ""}${f.referenceStory ? `<br>Mốc: <a href="${esc(f.referenceCrop)}">${esc(f.referenceStory)}</a>` : ""}${f.ratio ? `<br>Tương phản ${f.ratio}:1 / ${f.threshold}:1` : ""}<br><a href="${report.stories.find((s) => s.id === id && s.theme === f.theme)?.sheet}">Bảng chi tiết</a></figcaption></figure>`).join("")}</div></details>`).join("")}</section>`;
  }).join("");
  writeFileSync(path.join(out, "index.html"), html("ABook · soi chi tiết gallery", `<h1>ABook · soi chi tiết gallery</h1><p>${report.stories.length} lượt · ${report.findings.length} phát hiện · ${report.errors.length} lỗi chạy · ${esc(report.created)}</p><p>Ảnh cắt lề 8 CSS px: quy tắc cũ dùng CDP scale:4; INK EDGE/RHYTHM/BASELINE/CONTROL HEIGHT/FILL INSET phóng 4× nearest-neighbour từ raster CSS. Bấm ảnh để xem nguyên cỡ; phát hiện hình học cần được duyệt qua ảnh.</p><p>${RULES.map((r) => `${esc(r)}: ${report.counts[r]}`).join(" · ")}</p><details><summary>Bảng điều khiển / biểu tượng (${report.stories.length})</summary><ul>${report.stories.map((s) => `<li><a href="${s.sheet}">${esc(s.id)} · ${s.theme}</a> (${s.contacts.length})${s.error ? ` · ${esc(s.error)}` : ""}</li>`).join("")}</ul></details>${report.errors.length ? `<pre>${esc(JSON.stringify(report.errors, null, 2))}</pre>` : ""}${list}`));
}

export async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(["--theme", "both", ...argv]);
  if (args.help || !args.out) {
    console.log("node scripts/gallery_inspect.mjs --out DIR [--browser PATH] [--only A,B] [--theme light|dark|both] [--base URL] [--dist DIR] [--fail-on none|rule1,rule2,...,rule21]\nDefault --fail-on: rule4,rule5,rule6,rule8,rule10,rule11,rule12,rule13,rule15,rule16,rule17,rule18,rule19,rule20,rule21 (rules142/report.md; Studio included)\nrule10 INK EDGE: 2..20 px edges; >1 px icon/text gaps. rule11 RHYTHM: >2 px sibling gaps; >1 px first-block tops. rule12 BASELINE: >1 px alphabetic baseline delta. rule13 CONTROL HEIGHT: >1 px visible height/top/bottom or same-role menu-row delta. rule14 FILL INSET: <6 px ink padding, or selected fill ends >8 px before its row control. rule15 TAP REACH: enabled visible controls in the last leaf layer/main must restore pointer events and hit inside that layer. rule16 FOCUS RING CLIPPED: 4 px outline extent, 0.5 px tolerance; skip partially scrolled controls and honor overflow-clip-margin. rule17 CORNER MISMATCH: coincident corners within 1 px, CSS-scaled radius deficit >1 px, unless rounded ancestor clips. rule18 LINE BREAK: a middle-dot separator that ends or begins a line (half a font size of vertical offset). rule19 COVERED TEXT: a solid absolutely placed layer painted over text of the same frame, aria-hidden text included. rule20 REPEATED LABEL: a heading inside a tab panel that repeats the selected tab label. rule21 STACKED LAYERS: a dialog over another dialog, or any layer over a menu, overlapping by more than 8 px. Use --fail-on none for advisory output.");
    return !args.help ? 2 : 0;
  }
  if (!["light", "dark", "both"].includes(args.theme)) throw new Error("--theme phải là light, dark hoặc both");
  if (args.base && !["127.0.0.1", "localhost", "[::1]"].includes(new URL(args.base).hostname)) throw new Error("Chỉ được dùng --base cục bộ");
  const failOn = gateRules(args.failOn);
  const out = path.resolve(args.out);
  for (const dir of [out, path.join(out, "crops"), path.join(out, "contacts")]) mkdirSync(dir, { recursive: true });
  const report = { created: new Date().toISOString(), rules: RULES, counts: {}, settings: { phone: "412x915 @2x", desktop: "1440x900 @1x", cropScale: 4, themes: args.theme }, stories: [], findings: [], errors: [] };
  let local, browser, cdp;
  try {
    local = args.base ? null : await serve(args.dist);
    const base = args.base ?? local.base;
    const executable = findBrowser(args.browser);
    browser = await launch(executable, { preserveProfile: true });
    cdp = await connect(browser.endpoint);
    const index = await openPage(cdp, { width: 1280, height: 800, scale: 1, mobile: false, theme: "light" });
    await cdp.send("Page.navigate", { url: `${base}#/` }, index.sessionId);
    await waitUntil(cdp, index.sessionId, "Array.isArray(window.__galleryEntries)", args.timeout, "danh mục");
    const entries = (await evaluate(cdp, index.sessionId, "window.__galleryEntries")).filter((e) => !args.only || args.only.some((p) => e.id.includes(p)));
    if (!entries.length) throw new Error("Không có story khớp --only");
    await cdp.send("Target.closeTarget", { targetId: index.targetId });
    const themes = args.theme === "both" ? ["light", "dark"] : [args.theme];
    console.log(`${entries.length} mục × ${themes.length} chủ đề · ${executable}`);
    for (const entry of entries) for (const theme of themes) {
      const mobile = entry.platform === "phone";
      const width = mobile ? 412 : 1440, height = mobile ? 915 : 900;
      const page = await openPage(cdp, { width, height, scale: mobile ? 2 : 1, mobile, theme });
      const stem = `${entry.id.replaceAll("/", "__")}-${theme}`;
      const story = { ...entry, theme, sheet: `contacts/${stem}.html`, contacts: [], overlays: [] };
      const started = performance.now();
      try {
        await cdp.send("Page.navigate", { url: `${base}?frame=${encodeURIComponent(entry.id)}&theme=${theme}` }, page.sessionId);
        await waitUntil(cdp, page.sessionId, "Boolean(window.__gallery?.ready)", args.timeout, entry.id);
        await settle(cdp, page.sessionId, args.timeout);
        const gallery = await evaluate(cdp, page.sessionId, "window.__gallery");
        if (gallery.errors.length || gallery.missing.length) throw new Error(JSON.stringify(gallery));
        let result;
        for (let attempt = 0; attempt < 3; attempt++) {
          result = await evaluate(cdp, page.sessionId, inspectionExpression(mobile));
          if (result.metrics.animations.every((s) => s === "finished" || s === "idle")) break;
          await settle(cdp, page.sessionId, args.timeout);
        }
        if (result.metrics.animations.some((s) => s !== "finished" && s !== "idle")) throw new Error("Chuyển động vẫn chưa đứng yên lúc đo");
        story.metrics = result.metrics;
        story.siblingGroups = result.siblingGroups;
        story.layout = result.layout;
        story.tapToastOcclusions = result.layout?.tapToastOcclusions ?? [];
        story.frozenAnimations = await evaluate(cdp, page.sessionId, "window.__inspectFrozenAnimations");
        story.overlays = result.overlays;
        const crop = captureCrops(cdp, page.sessionId, out, stem, { width, height, deviceScale: mobile ? 2 : 1 });
        const inkCrop = captureCrops(cdp, page.sessionId, out, `${stem}-ink`, { width, height, deviceScale: mobile ? 2 : 1 }, { nearest: true });
        for (const item of story.tapToastOcclusions) item.crop = await crop([item.rect]);
        if (story.layout?.firstBlock) story.layout.firstBlock.crop = await inkCrop([story.layout.firstBlock.rect]);
        if (story.layout?.screenTitle) story.layout.screenTitle.crop = await inkCrop([story.layout.screenTitle.rect]);
        for (const finding of result.findings) {
          finding.id = `F${String(report.findings.length + 1).padStart(5, "0")}`;
          finding.story = entry.id; finding.theme = theme;
          finding.crop = await (["INK EDGE", "RHYTHM", "BASELINE", "CONTROL HEIGHT", "FILL INSET"].includes(finding.rule) ? inkCrop : crop)(finding.rects);
          report.findings.push(finding);
        }
        for (const contact of result.contacts) story.contacts.push({ ...contact, crop: await crop([contact.rect]) });
        story.findingCount = result.findings.length;
        console.log(`ok ${entry.id} (${theme}) · ${result.findings.length} phát hiện · ${story.contacts.length} chi tiết · ${((performance.now() - started) / 1000).toFixed(1)}s`);
      } catch (error) {
        story.error = error.message;
        report.errors.push({ story: entry.id, theme, error: error.message });
        console.error(`!! ${entry.id} (${theme}): ${error.message}`);
      } finally {
        await cdp.send("Target.closeTarget", { targetId: page.targetId }).catch(() => undefined);
        report.stories.push(story);
        writeSheet(out, story);
        report.counts = Object.fromEntries(RULES.map((r) => [r, report.findings.filter((f) => f.rule === r).length]));
        writeOutputs(out, report);
      }
    }
  } finally {
    cdp?.close();
    try { await browser?.close(); } finally { local?.server.close(); }
  }
  for (const finding of [...crossFrameRhythm(report.stories), ...crossFrameTitles(report.stories)]) {
    finding.id = `F${String(report.findings.length + 1).padStart(5, "0")}`;
    report.findings.push(finding);
    report.stories.find((s) => s.id === finding.story && s.theme === finding.theme).findingCount++;
  }
  report.counts = Object.fromEntries(RULES.map((r) => [r, report.findings.filter((f) => f.rule === r).length]));
  report.settings.failOn = failOn;
  report.settings.gateEvidence = "uicheck139c/result.md; ink140/report.md; rules142/report.md; rules144/result.md (full gallery including Studio, both themes; edge fixtures and baseline comparison)";
  report.distinctDefects = deduplicate(report.findings, sourceIndex(path.resolve(import.meta.dirname, "../src")));
  writeOutputs(out, report);
  console.log(`${report.findings.length} phát hiện; ${report.errors.length} lỗi chạy → ${path.join(out, "index.html")}`);
  return report.errors.length ? 2 : failOn.some((r) => report.counts[r] > 0) ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().then((code) => { process.exitCode = code; }).catch((error) => { console.error(error.stack); process.exitCode = 2; });
}
