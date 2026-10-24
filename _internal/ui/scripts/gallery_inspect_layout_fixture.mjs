import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { launch, findBrowser, connect, openPage, evaluate, parseArgs } from "./gallery_browser.mjs";
import { inspectionExpression, captureCrops } from "./gallery_inspect.mjs";

export async function layoutFixtures({ browser: executable, out } = {}) {
  const browser = await launch(findBrowser(executable), { preserveProfile: true });
  let cdp;
  const results = [];
  try {
    cdp = await connect(browser.endpoint);
    for (const phone of [false, true]) for (const theme of ["light", "dark"]) {
      const viewport = { width: phone ? 412 : 1440, height: phone ? 915 : 900, deviceScale: phone ? 2 : 1 };
      const page = await openPage(cdp, { ...viewport, scale: viewport.deviceScale, mobile: phone, theme });
      const { frameTree } = await cdp.send("Page.getFrameTree", {}, page.sessionId);
      const html = readFileSync(new URL("./fixtures/ink-rhythm.html", import.meta.url), "utf8")
        .replace("</style>", `${theme === "dark" ? "body{background:#181818;color:white}svg{stroke:white}" : ""}</style>`);
      await cdp.send("Page.setDocumentContent", { frameId: frameTree.frame.id, html }, page.sessionId);
      await evaluate(cdp, page.sessionId, "document.fonts.ready.then(() => true)");
      const result = await evaluate(cdp, page.sessionId, inspectionExpression(phone));
      if (out) {
        mkdirSync(path.join(out, "crops"), { recursive: true });
        const crop = captureCrops(cdp, page.sessionId, out, `${phone ? "phone" : "desktop"}-${theme}`, viewport);
        for (const finding of result.findings) finding.crop = await crop(finding.rects);
      }
      results.push({ phone, theme, ...result });
      await cdp.send("Target.closeTarget", { targetId: page.targetId });
    }
    if (out) writeFileSync(path.join(out, "findings.json"), JSON.stringify(results, null, 2));
    return results;
  } finally { cdp?.close(); await browser.close(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const args = parseArgs(process.argv.slice(2));
  const results = await layoutFixtures(args);
  console.log(JSON.stringify(results.map((r) => ({ phone: r.phone, theme: r.theme, findings: r.findings.filter((f) => ["INK EDGE", "RHYTHM"].includes(f.rule)) })), null, 2));
}
