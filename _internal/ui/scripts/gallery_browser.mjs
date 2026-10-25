import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Hạ tầng dùng chung cho ảnh toàn màn và bộ soi chi tiết; không cần thư viện trình duyệt.
const here = path.dirname(fileURLToPath(import.meta.url));

export function parseArgs(argv) {
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
    else if (flag === "--fail-on") args.failOn = value().split(",").map((item) => item.trim().toUpperCase());
    else if (flag === "--scale") args.scale = Number(value());
    else if (flag === "--timeout") args.timeout = Number(value());
    else if (flag === "--probe") args.probe = readFileSync(path.resolve(value()), "utf8");
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

export function findBrowser(given) {
  if (given) {
    if (!existsSync(given)) throw new Error(`Không thấy trình duyệt ở ${given}`);
    return given;
  }
  const found = CANDIDATES.find((candidate) => candidate && existsSync(candidate));
  if (!found) throw new Error("Không tìm thấy Chrome / Edge - đưa đường dẫn bằng --browser PATH");
  return found;
}

/** Máy không có Chrome / Edge (CI chỉ có Chromium riêng): bộ test fixture trình duyệt bỏ qua thay vì đỏ cả lượt vitest. */
export const browserAvailable = CANDIDATES.some((candidate) => candidate && existsSync(candidate));

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png",
  ".woff2": "font/woff2", ".woff": "font/woff", ".json": "application/json", ".mjs": "text/javascript", ".wasm": "application/wasm" };

/** Máy chủ tĩnh cho dist/gallery trên cổng ngẫu nhiên của 127.0.0.1. */
export function serve(root) {
  root = path.resolve(root);
  if (!existsSync(path.join(root, "gallery.html"))) throw new Error(`Chưa có ${path.join(root, "gallery.html")} - chạy "npm run gallery:build" trước, hoặc đưa --base`);
  const server = createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    let file;
    try { file = path.join(root, decodeURIComponent(url.pathname)); } catch { response.writeHead(400).end(); return; }
    const relative = path.relative(root, file);
    if (relative.startsWith("..") || path.isAbsolute(relative) || !existsSync(file)) {
      response.writeHead(404).end();
      return;
    }
    try {
      const data = readFileSync(file);
      response.writeHead(200, { "Content-Type": TYPES[path.extname(file)] ?? "application/octet-stream" });
      response.end(data);
    } catch { response.writeHead(404).end(); }
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, base: `http://127.0.0.1:${server.address().port}/gallery.html` })));
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Edge vừa tạo file nhưng Windows còn giữ khoá ghi; tồn tại chưa có nghĩa là đọc được ngay. */
export function readDevToolsPort(portFile, read = readFileSync) {
  try { return read(portFile, "utf8").trim().split("\n"); }
  catch (error) {
    if (["EBUSY", "EACCES", "EPERM", "ENOENT"].includes(error.code)) return [];
    throw error;
  }
}

/** Mở trình duyệt headless với cổng gỡ lỗi do nó tự chọn (đọc từ DevToolsActivePort trong thư mục hồ sơ tạm). */
export async function launch(executable, { preserveProfile = false } = {}) {
  const profile = mkdtempSync(path.join(tmpdir(), "abook-gallery-"));
  const cleanProfile = () => {
    if (preserveProfile) return; // Inspector audits retain artifacts when deletion is forbidden.
    // Chỉ xoá hồ sơ vừa tạo, bằng Python và đường dẫn tuyệt đối; không đi theo junction/symlink.
    const cleaned = spawnSync(process.env.PYTHON ?? "python", ["-c", `
import os, sys, tempfile, time
root = os.path.abspath(sys.argv[1])
assert os.path.dirname(root) == os.path.abspath(tempfile.gettempdir())
assert os.path.basename(root).startswith('abook-gallery-') and not os.path.islink(root)
for attempt in range(60):
    try:
        if not os.path.exists(root): break
        for folder, dirs, files in os.walk(root, topdown=False, followlinks=False):
            for name in files: os.remove(os.path.abspath(os.path.join(folder, name)))
            for name in dirs:
                item = os.path.abspath(os.path.join(folder, name))
                if os.path.islink(item): os.remove(item)
                else: os.rmdir(item)
        os.rmdir(root)
        break
    except PermissionError:
        time.sleep(0.2)
else: raise RuntimeError('Hồ sơ trình duyệt vẫn bị khoá: ' + root)
`, profile], { encoding: "utf8", windowsHide: true });
    if (cleaned.status !== 0) throw new Error(cleaned.stderr || "Không xoá được hồ sơ trình duyệt");
  };
  const child = spawn(executable, [
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${profile}`,
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-component-update",
    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
    "--remote-debugging-port=0",
    "--hide-scrollbars",
    "--mute-audio",
    // Edge: hồ sơ mới tự đăng nhập tài khoản Microsoft và đồng bộ của máy - chụp ở cửa sổ riêng tư, tắt đồng bộ.
    ...(/msedge/i.test(path.basename(executable)) ? ["--inprivate", "--disable-sync"] : []),
    // Chromium không chạy dưới root (máy ảo CI, container) nếu còn sandbox.
    ...(process.platform === "linux" && process.getuid?.() === 0 ? ["--no-sandbox"] : []),
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  let stderr = "";
  child.stderr.on("data", (chunk) => (stderr += chunk));
  child.on("error", (error) => { stderr += error.message; });
  const portFile = path.join(profile, "DevToolsActivePort");
  try {
    for (let waited = 0; !existsSync(portFile); waited += 100) {
      if (child.exitCode !== null || waited > 20000) {
        throw new Error(`Trình duyệt không mở được cổng gỡ lỗi.\n${stderr.slice(-2000)}`);
      }
      await sleep(100);
    }
    let lines = [];
    const readingSince = Date.now();
    while (lines.length < 2) {
      if (child.exitCode !== null) throw new Error("Trình duyệt đóng trước khi ghi đủ cổng CDP");
      if (Date.now() - readingSince > 20000) throw new Error("Hết giờ đọc cổng CDP của trình duyệt");
      lines = readDevToolsPort(portFile);
      if (lines.length < 2) await sleep(50);
    }
    const endpoint = `ws://127.0.0.1:${lines[0].trim()}${lines[1].trim()}`;
    return {
      endpoint,
      close: async () => {
        let control;
        try {
          control = await connect(endpoint);
          await control.send("Browser.close").catch(() => undefined);
        } catch {
          // Nếu cổng đã đóng thì chỉ cần đợi tiến trình và dọn hồ sơ.
        } finally {
          control?.close();
        }
        for (let i = 0; child.exitCode === null && i < 50; i++) await sleep(100);
        if (child.exitCode === null) {
          if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true });
          else child.kill("SIGKILL");
          await sleep(300);
        }
        cleanProfile();
      },
    };
  } catch (error) {
    if (child.pid && child.exitCode === null) {
      if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true });
      else child.kill("SIGKILL");
    }
    cleanProfile();
    throw error;
  }
}

/** Kết nối CDP tối giản: lệnh có mã, phiên (flatten) theo sessionId. */
export async function connect(endpoint) {
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
  socket.addEventListener("close", () => {
    for (const item of pending.values()) item.reject(new Error("Kết nối CDP đã đóng"));
    pending.clear();
  });
  const send = (method, params = {}, sessionId) =>
    new Promise((resolve, reject) => {
      const id = next++;
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Hết giờ CDP: ${method}`)); }, 60000);
      pending.set(id, { resolve: (value) => { clearTimeout(timer); resolve(value); }, reject: (error) => { clearTimeout(timer); reject(error); } });
      socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  return { send, close: () => socket.close() };
}

export async function evaluate(cdp, session, expression) {
  const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, session);
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}

export async function waitUntil(cdp, session, expression, timeout, what) {
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
export async function openPage(cdp, { width, height, scale, mobile, theme }) {
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

export const STILL = `new Promise((resolve) => {
  const moving = () => document.getAnimations().some((a) => a.playState === "running" && a.effect && a.effect.getComputedTiming().endTime !== Infinity);
  const started = performance.now();
  const tick = () => (!moving() || performance.now() - started > 5000 ? requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))) : setTimeout(tick, 50));
  tick();
})`;

export const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]);

