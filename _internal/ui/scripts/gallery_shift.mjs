// Máy dò dịch bố cục lúc tải (layout-shift) trên mọi mục gallery. Lớp lỗi 25-10: trang hay dữ liệu đầu tới thì thứ đi kèm (nút đầu trang,
// thẻ Nghe tiếp, thẻ buổi sáng, dòng danh sách) mọc cao dần đẩy lưới xuống - "giao diện hiện ra từ hư không" khi mở app.
// Chỉ tính dịch trong LOAD_MS đầu (lúc tải); thao tác do kịch bản gallery bấm sau đó (mở bảng, mở trình phát) không tính.
//   node scripts/gallery_shift.mjs [--dist dist/gallery] [--only a,b] [--max 0.15]
import path from "node:path";
import { connect, evaluate, findBrowser, launch, openPage, serve, waitUntil } from "./gallery_browser.mjs";

const LOAD_MS = 1000;
const args = { dist: path.resolve(import.meta.dirname, "../dist/gallery"), max: 0.15, only: null };
for (let index = 2; index < process.argv.length; index += 1) {
  const flag = process.argv[index];
  if (flag === "--dist") args.dist = path.resolve(process.argv[++index]);
  else if (flag === "--only") args.only = process.argv[++index].split(",");
  else if (flag === "--max") args.max = Number(process.argv[++index]);
  else throw new Error(`Tham số lạ: ${flag}`);
}

const read = `new Promise((resolve) => {
  const out = [];
  new PerformanceObserver((list) => out.push(...list.getEntries())).observe({ type: "layout-shift", buffered: true });
  setTimeout(() => {
    const load = out.filter((entry) => entry.startTime < ${LOAD_MS});
    const name = (node) => (node?.className && String(node.className).slice(0, 60)) || node?.nodeName || "?";
    resolve({
      cls: +load.reduce((sum, entry) => sum + entry.value, 0).toFixed(4),
      top: load.sort((a, b) => b.value - a.value).slice(0, 3).map((entry) => ({
        t: Math.round(entry.startTime), value: +entry.value.toFixed(4),
        sources: entry.sources.map((source) => [name(source.node), Math.round(source.previousRect.y), Math.round(source.currentRect.y), Math.round(source.previousRect.height), Math.round(source.currentRect.height)]),
      })),
    });
  }, 200);
})`;

const local = await serve(args.dist);
const browser = await launch(findBrowser());
const cdp = await connect(browser.endpoint);
const found = [];
try {
  const index = await openPage(cdp, { width: 1280, height: 800, scale: 1, mobile: false, theme: "light" });
  await cdp.send("Page.navigate", { url: `${local.base}#/` }, index.sessionId);
  await waitUntil(cdp, index.sessionId, "Array.isArray(window.__galleryEntries)", 20000, "danh mục");
  const entries = (await evaluate(cdp, index.sessionId, "window.__galleryEntries")).filter((entry) => !args.only || args.only.includes(entry.id));
  for (const entry of entries) {
    const mobile = entry.id.startsWith("phone/");
    const page = await openPage(cdp, { width: mobile ? 412 : 1440, height: mobile ? 915 : 900, scale: 1, mobile, theme: "dark" });
    try {
      await cdp.send("Page.navigate", { url: `${local.base}?frame=${encodeURIComponent(entry.id)}&theme=dark` }, page.sessionId);
      await waitUntil(cdp, page.sessionId, "Boolean(window.__gallery?.ready)", 20000, entry.id);
      await evaluate(cdp, page.sessionId, `new Promise((resolve) => setTimeout(resolve, Math.max(0, ${LOAD_MS} - performance.now())))`);
      const shift = await evaluate(cdp, page.sessionId, read);
      if (shift.cls > 0.005) found.push({ id: entry.id, ...shift });
    } catch (error) {
      found.push({ id: entry.id, cls: Infinity, error: String(error).slice(0, 160) });
    }
    await cdp.send("Target.closeTarget", { targetId: page.targetId });
  }
} finally {
  cdp.close?.();
  await browser.close?.();
  local.server.close();
}

found.sort((a, b) => b.cls - a.cls);
for (const item of found) {
  console.log(`${item.error ? "LỖI " : ""}${item.cls.toFixed(3)} ${item.id}${item.error ? ` ${item.error}` : ""}`);
  for (const shift of item.top ?? []) console.log(`    t=${shift.t} ${shift.value}  ${shift.sources.map((source) => `${source[0]} y ${source[1]}→${source[2]} h ${source[3]}→${source[4]}`).join(" | ")}`);
}
const over = found.filter((item) => item.cls > args.max);
console.log(`${found.length} mục có dịch lúc tải > 0.005; ${over.length} mục vượt ngưỡng ${args.max}`);
process.exitCode = over.length ? 1 : 0;
