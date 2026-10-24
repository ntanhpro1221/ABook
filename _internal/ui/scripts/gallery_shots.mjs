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

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

function parseArgs(argv) {
  const args = { theme: "light", dist: path.resolve(here, "../dist/gallery"), timeout: 45000 };
  for (let index = 0; index < argv.length; index += 1) {
    const [flag, inline] = argv[index].split(/=(.*)/s, 2);
    const value = () => inline ?? argv[++index];
    if (flag === "--browser") args.browser = value();
    else if (flag === "--out") args.out = value();
    else if (flag === "--base") args.base = value();
    else if (flag === "--dist") args.dist = path.resolve(value());
    else if (flag === "--only") args.only = value().split(",").map((item) => item.trim()).filter(Boolean);
    else if (flag === "--theme") args.theme = value();
    else if (flag === "--scale") args.scale = Number(value());
    else if (flag === "--timeout") args.timeout = Number(value());
    else if (flag === "--help" || flag === "-h") args.help = true;
    else throw new Error(`Tham số lạ: ${argv[index]}`);
  }
  return args;
}

const CANDIDATES = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/usr/bin/microsoft-edge",
];

function findBrowser(given) {
  if (given) {
    if (!existsSync(given)) throw new Error(`Không thấy trình duyệt ở ${given}`);
    return given;
  }
  const found = CANDIDATES.find((candidate) => candidate && existsSync(candidate));
  if (!found) throw new Error("Không tìm thấy Chrome / Edge - đưa đường dẫn bằng --browser PATH");
  return found;
}

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png",
  ".woff2": "font/woff2", ".woff": "font/woff", ".json": "application/json", ".mjs": "text/javascript", ".wasm": "application/wasm" };

/** Máy chủ tĩnh cho dist/gallery trên cổng ngẫu nhiên của 127.0.0.1. */
function serve(root) {
  if (!existsSync(path.join(root, "gallery.html"))) throw new Error(`Chưa có ${path.join(root, "gallery.html")} - chạy "npm run gallery:build" trước, hoặc đưa --base`);
  const server = createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const file = path.join(root, decodeURIComponent(url.pathname));
    if (!file.startsWith(root) || !existsSync(file)) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, { "Content-Type": TYPES[path.extname(file)] ?? "application/octet-stream" });
    response.end(readFileSync(file));
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, base: `http://127.0.0.1:${server.address().port}/gallery.html` })));
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Mở trình duyệt headless với cổng gỡ lỗi do nó tự chọn (đọc từ DevToolsActivePort trong thư mục hồ sơ tạm). */
async function launch(executable) {
  const profile = mkdtempSync(path.join(tmpdir(), "abook-gallery-"));
  const child = spawn(executable, [
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${profile}`,
    "--disable-extensions",
    "--remote-debugging-port=0",
    "--hide-scrollbars",
    "--mute-audio",
    // Chromium không chạy dưới root (máy ảo CI, container) nếu còn sandbox.
    ...(process.platform === "linux" && process.getuid?.() === 0 ? ["--no-sandbox"] : []),
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  let stderr = "";
  child.stderr.on("data", (chunk) => (stderr += chunk));
  const portFile = path.join(profile, "DevToolsActivePort");
  for (let waited = 0; !existsSync(portFile); waited += 100) {
    if (child.exitCode !== null || waited > 20000) {
      child.kill();
      throw new Error(`Trình duyệt không mở được cổng gỡ lỗi.\n${stderr.slice(-2000)}`);
    }
    await sleep(100);
  }
  let lines = [];
  while (lines.length < 2) {
    lines = readFileSync(portFile, "utf8").trim().split("\n");
    if (lines.length < 2) await sleep(50);
  }
  const endpoint = `ws://127.0.0.1:${lines[0].trim()}${lines[1].trim()}`;
  return {
    endpoint,
    close: async () => {
      child.kill();
      await sleep(300);
      try {
        rmSync(profile, { recursive: true, force: true });
      } catch {
        // Windows đôi khi còn giữ file hồ sơ vài giây: thư mục tạm, để hệ thống dọn.
      }
    },
  };
}

/** Kết nối CDP tối giản: lệnh có mã, phiên (flatten) theo sessionId. */
async function connect(endpoint) {
  if (typeof WebSocket !== "function") throw new Error("Node này chưa có WebSocket sẵn - cần Node 22 trở lên.");
  const socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", () => reject(new Error(`Không nối được ${endpoint}`)), { once: true });
  });
  let next = 1;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(typeof event.data === "string" ? event.data : Buffer.from(event.data).toString());
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(`${message.error.message} (${message.error.code})`));
      else resolve(message.result);
    }
  });
  const send = (method, params = {}, sessionId) =>
    new Promise((resolve, reject) => {
      const id = next++;
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  return { send, close: () => socket.close() };
}

async function evaluate(cdp, session, expression) {
  const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, session);
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}

async function waitUntil(cdp, session, expression, timeout, what) {
  const started = Date.now();
  for (;;) {
    try {
      if (await evaluate(cdp, session, expression)) return;
    } catch {
      // Trang đang chuyển (tải lại): thử lại.
    }
    if (Date.now() - started > timeout) throw new Error(`Hết giờ chờ ${what}`);
    await sleep(100);
  }
}

/** Mở một trang mới trong cùng trình duyệt, trả phiên (đã bật Page + Runtime). */
async function openPage(cdp, { width, height, scale, mobile, theme }) {
  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  await cdp.send("Page.enable", {}, sessionId);
  await cdp.send("Runtime.enable", {}, sessionId);
  await cdp.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile, screenWidth: width, screenHeight: height }, sessionId);
  // Điện thoại: màn cảm ứng thật cho CSS (@media (pointer: coarse)); trang còn tự giả matchMedia cho phần JS.
  await cdp.send("Emulation.setTouchEmulationEnabled", mobile ? { enabled: true, maxTouchPoints: 5 } : { enabled: false }, sessionId);
  await cdp.send("Emulation.setTimezoneOverride", { timezoneId: "Asia/Ho_Chi_Minh" }, sessionId);
  await cdp.send("Emulation.setLocaleOverride", { locale: "vi-VN" }, sessionId).catch(() => undefined);
  await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }, { name: "prefers-reduced-motion", value: "no-preference" }] }, sessionId);
  return { targetId, sessionId };
}

const STILL = `new Promise((resolve) => {
  const moving = () => document.getAnimations().some((a) => a.playState === "running" && a.effect && a.effect.getComputedTiming().endTime !== Infinity);
  const started = performance.now();
  const tick = () => (!moving() || performance.now() - started > 5000 ? requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))) : setTimeout(tick, 50));
  tick();
})`;

const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]);

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
  const local = args.base ? null : await serve(args.dist);
  const base = args.base ?? local.base;
  const browser = await launch(executable);
  const cdp = await connect(browser.endpoint);
  const shots = [];
  let failures = 0;
  try {
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
    cdp.close();
    await browser.close();
    local?.server.close();
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
