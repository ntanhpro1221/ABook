// Chạy một biểu thức JS (file --js hoặc --expr) trên các mục của phòng trưng bày và in kết quả JSON: để ĐO (toạ độ, màu, khoảng cách), khác với
// `gallery_shots --probe` chỉ báo vấn đề. Dùng: node scripts/probes/measure.mjs --dist DIR --only id1,id2 [--theme light|dark] --probe file.js.
import { connect, evaluate, findBrowser, launch, openPage, parseArgs, serve, STILL, waitUntil } from "../gallery_browser.mjs";

const args = parseArgs(process.argv.slice(2));
const expression = args.probe;
if (!args.probe) {
  console.error("cần --probe file.js");
  process.exit(2);
}
const themes = args.theme === "both" ? ["light", "dark"] : [args.theme === "dark" ? "dark" : "light"];
const local = await serve(args.dist);
const browser = await launch(findBrowser(args.browser));
const cdp = await connect(browser.endpoint);
try {
  const index = await openPage(cdp, { width: 1280, height: 800, scale: 1, mobile: false, theme: "light" });
  await cdp.send("Page.navigate", { url: `${local.base}#/` }, index.sessionId);
  await waitUntil(cdp, index.sessionId, "Array.isArray(window.__galleryEntries)", 60000, "danh mục");
  const entries = (await evaluate(cdp, index.sessionId, "window.__galleryEntries")).filter((entry) => !args.only || args.only.some((part) => entry.id.includes(part)));
  await cdp.send("Target.closeTarget", { targetId: index.targetId });
  for (const entry of entries) {
    for (const theme of themes) {
      const mobile = entry.platform === "phone";
      const page = await openPage(cdp, { width: entry.width, height: entry.height, scale: mobile ? 2 : 1, mobile, theme });
      try {
        await cdp.send("Page.navigate", { url: `${local.base}?frame=${encodeURIComponent(entry.id).replace(/%2F/g, "/")}&theme=${theme}` }, page.sessionId);
        await waitUntil(cdp, page.sessionId, "Boolean(window.__gallery && window.__gallery.ready)", 60000, `mục ${entry.id}`);
        await evaluate(cdp, page.sessionId, "document.fonts ? document.fonts.ready.then(() => true) : true");
        await evaluate(cdp, page.sessionId, STILL);
        const result = await evaluate(cdp, page.sessionId, expression);
        console.log(`### ${entry.id} (${theme})`);
        console.log(typeof result === "string" ? result : JSON.stringify(result, null, 1));
      } catch (error) {
        console.log(`### ${entry.id} (${theme}) LỖI ${error.message}`);
      } finally {
        await cdp.send("Target.closeTarget", { targetId: page.targetId }).catch(() => undefined);
      }
    }
  }
} finally {
  cdp.close();
  try { await browser.close(); } finally { local.server.close(); }
}
