#!/usr/bin/env node
// Chụp mọi mục của phòng trưng bày (src/gallery) bằng Chrome / Edge headless qua Chrome DevTools Protocol - không thêm thư viện nào:
// WebSocket có sẵn trong Node 22, máy chủ tĩnh bằng node:http.
//
//   npm run gallery:build                                   # dựng dist/gallery (hoặc: npm run gallery, rồi dùng --base)
//   node scripts/gallery_shots.mjs --browser "C:/Program Files/Google/Chrome/Application/chrome.exe" --out ../shots
//   node scripts/gallery_shots.mjs --browser /usr/bin/chromium --out /tmp/shots --only phone/library,desktop/studio --theme both
//
// Tham số:
//   --browser PATH   Chrome / Edge / Chromium (bắt buộc nếu không tự tìm được)
//   --out DIR        thư mục ảnh (tạo nếu chưa có) - kèm index.html lưới ảnh và report.json
//   --base URL       trang gallery.html đang chạy (vd http://localhost:5174/gallery.html từ `npm run gallery`); bỏ trống thì phục vụ --dist
//   --dist DIR       bản dựng của phòng trưng bày (mặc định dist/gallery)
//   --only A,B       chỉ mục có id chứa một trong các chuỗi này
//   --theme T        light | dark | both (mặc định light)
//   --scale N        tỉ lệ điểm ảnh (mặc định: điện thoại 2, máy tính 1)
//   --timeout MS     chờ một mục tối đa (mặc định 45000)
//   --probe FILE     biểu thức JS chạy trên từng màn đã đứng yên; trả mảng chuỗi, mỗi chuỗi là một vấn đề (vd scripts/probes/orphans.js)

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs, findBrowser, serve, launch, connect, evaluate, waitUntil, openPage, STILL, escapeHtml } from "./gallery_browser.mjs";

function writeIndex(out, shots) {
  const groups = [];
  for (const shot of shots) {
    const key = `${shot.platform === "phone" ? "Điện thoại" : "Máy tính"} · ${shot.group}`;
    let group = groups.find((item) => item.key === key);
    if (!group) groups.push((group = { key, shots: [] }));
    group.shots.push(shot);
  }
  const html = `<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>ABook · ảnh phòng trưng bày</title>
<style>body{font:14px/1.4 system-ui,sans-serif;margin:16px;background:#f4f5f7;color:#1b1f24}h2{font-size:15px;margin:24px 0 8px}
.grid{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start}figure{margin:0;background:#fff;border:1px solid #d9dde3;border-radius:10px;padding:8px}
figure img{display:block;border-radius:6px;max-width:100%}figure.phone img{width:206px}figure.desktop img{width:480px}figcaption{margin-top:6px;max-width:480px}
code{color:#5d6673;font-size:12px}.bad{color:#b42318;font-size:12px;white-space:pre-wrap}</style></head><body>
<h1>ABook · ảnh phòng trưng bày</h1><p>${shots.length} ảnh · ${new Date().toISOString()}</p>
${groups.map((group) => `<h2>${escapeHtml(group.key)}</h2><div class="grid">${group.shots.map((shot) => `<figure class="${shot.platform}">
<a href="${encodeURI(shot.file)}"><img src="${encodeURI(shot.file)}" alt="${escapeHtml(shot.title)}" loading="lazy"></a>
<figcaption>${escapeHtml(shot.title)} <code>${escapeHtml(shot.id)} · ${shot.theme}</code>${shot.problems.length ? `<div class="bad">${escapeHtml(shot.problems.join("\n"))}</div>` : ""}</figcaption></figure>`).join("")}</div>`).join("\n")}
</body></html>`;
  writeFileSync(path.join(out, "index.html"), html);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.out) {
    console.log(readFileSync(fileURLToPath(import.meta.url), "utf8").split("\n").slice(1, 19).map((line) => line.replace(/^\/\/ ?/, "")).join("\n"));
    if (!args.out && !args.help) process.exitCode = 2;
    return;
  }
  const out = path.resolve(args.out);
  mkdirSync(out, { recursive: true });
  const themes = args.theme === "both" ? ["light", "dark"] : [args.theme === "dark" ? "dark" : "light"];
  const executable = findBrowser(args.browser);
  let local, browser, cdp;
  const shots = [];
  let failures = 0;
  try {
    local = args.base ? null : await serve(args.dist);
    const base = args.base ?? local.base;
    browser = await launch(executable, { preserveProfile: true });
    cdp = await connect(browser.endpoint);
    // Danh mục: trang mục lục đặt window.__galleryEntries.
    const index = await openPage(cdp, { width: 1280, height: 800, scale: 1, mobile: false, theme: "light" });
    await cdp.send("Page.navigate", { url: `${base}#/` }, index.sessionId);
    await waitUntil(cdp, index.sessionId, "Array.isArray(window.__galleryEntries)", args.timeout, "danh mục");
    const entries = (await evaluate(cdp, index.sessionId, "window.__galleryEntries")).filter((entry) => !args.only || args.only.some((part) => entry.id.includes(part)));
    await cdp.send("Target.closeTarget", { targetId: index.targetId });
    console.log(`${entries.length} mục × ${themes.length} chủ đề · ${executable}`);
    for (const entry of entries) {
      for (const theme of themes) {
        const mobile = entry.platform === "phone";
        const page = await openPage(cdp, { width: entry.width, height: entry.height, scale: args.scale ?? (mobile ? 2 : 1), mobile, theme });
        const file = `${entry.id.replace(/\//g, "__")}-${theme}.png`;
        const problems = [];
        const started = Date.now();
        try {
          await cdp.send("Page.navigate", { url: `${base}?frame=${encodeURIComponent(entry.id).replace(/%2F/g, "/")}&theme=${theme}` }, page.sessionId);
          await waitUntil(cdp, page.sessionId, "Boolean(window.__gallery && window.__gallery.ready)", args.timeout, `mục ${entry.id}`);
          await evaluate(cdp, page.sessionId, "document.fonts ? document.fonts.ready.then(() => true) : true");
          await evaluate(cdp, page.sessionId, STILL);
          const report = await evaluate(cdp, page.sessionId, "window.__gallery");
          // --probe <file.js>: biểu thức máy dò chạy trên màn đã đứng yên; mảng khác rỗng = vấn đề (vd chữ mồ côi).
          const probe = args.probe ? await evaluate(cdp, page.sessionId, args.probe) : [];
          problems.push(...(Array.isArray(probe) ? probe : [probe]).map((item) => `dò: ${item}`));
          problems.push(...report.errors.map((error) => `lỗi: ${error.split("\n")[0]}`), ...report.missing.map((name) => `chưa giả: ${name}`));
          const { data } = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, page.sessionId);
          writeFileSync(path.join(out, file), Buffer.from(data, "base64"));
        } catch (error) {
          problems.push(`không chụp được: ${error.message}`);
        } finally {
          await cdp.send("Target.closeTarget", { targetId: page.targetId }).catch(() => undefined);
        }
        if (problems.length) failures += 1;
        shots.push({ ...entry, theme, file, problems });
        console.log(`${problems.length ? "!!" : "ok"} ${entry.id} (${theme}) ${((Date.now() - started) / 1000).toFixed(1)}s${problems.length ? `\n   ${problems.join("\n   ")}` : ""}`);
      }
    }
  } finally {
    cdp?.close();
    try { await browser?.close(); } finally { local?.server.close(); }
  }
  writeIndex(out, shots);
  writeFileSync(path.join(out, "report.json"), JSON.stringify(shots, null, 2));
  console.log(`Xong: ${shots.length} ảnh, ${failures} mục có vấn đề -> ${path.join(out, "index.html")}`);
  if (failures) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
