// @vitest-environment node
// Đo thật trên Chromium (Edge/Chrome headless, cùng Tailwind + phông app): chữ tự đo không bao giờ tràn khỏi nút hay bìa (soát leftfix C1, L1, T3)
// và danh sách dài hàng content-visibility không kẹt ở "chưa đo" (T6). Trang đo: src/testing/fitFixture, dựng bằng vite vào thư mục tạm.
import { mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { buildFitFixture, openFixture } from "./fit_fixture.mjs";
import { browserAvailable, connect, evaluate, findBrowser, launch, serve } from "./gallery_browser.mjs";

describe.skipIf(!browserAvailable)("chữ tự đo trên Chromium thật", () => {
  let out, local, browser, cdp;
  beforeAll(async () => {
    out = mkdtempSync(path.join(tmpdir(), "abook-fit-"));
    await buildFitFixture(out);
    local = await serve(out);
    browser = await launch(findBrowser());
    cdp = await connect(browser.endpoint);
  }, 180000);
  afterAll(async () => {
    cdp?.close();
    try { await browser?.close(); } finally {
      local?.server.close();
      // Thư mục dựng tạm do chính test này tạo (mkdtemp), đường dẫn tuyệt đối dưới tmpdir.
      if (out && path.dirname(out) === path.resolve(tmpdir()) && path.basename(out).startsWith("abook-fit-")) rmSync(out, { recursive: true, force: true });
    }
  });

  it("nhãn nút dài không tràn khỏi nút ở bề ngang 320: thu cỡ hay xuống dòng, nút cao thêm, icon ở dòng đầu (C1, L1)", async () => {
    const page = await openFixture(cdp, local.base);
    const result = await evaluate(cdp, page.sessionId, `(() => [...document.querySelectorAll("[data-case]")].filter(b => b.tagName === "BUTTON").map(button => {
      const label = button.querySelector("[data-one-line-fit]");
      const b = button.getBoundingClientRect();
      const range = document.createRange(); range.selectNodeContents(label);
      const lines = [...range.getClientRects()];
      const text = range.getBoundingClientRect();
      const icon = button.querySelector("[data-state-icon]")?.getBoundingClientRect();
      const first = lines[0];
      return { name: button.dataset.case, fit: label.dataset.fit, white: getComputedStyle(label).whiteSpace,
        overflowX: button.scrollWidth - button.clientWidth, overflowY: button.scrollHeight - button.clientHeight,
        textLeft: text.left - b.left, textRight: b.right - text.right, textTop: text.top - b.top, textBottom: b.bottom - text.bottom,
        lineCount: new Set(lines.map(r => Math.round(r.top))).size, height: b.height, minHeight: parseFloat(getComputedStyle(button).minHeight),
        iconOffset: icon && first ? Math.abs((icon.top + icon.height / 2) - (first.top + first.height / 2)) : 0,
        fontSize: parseFloat(getComputedStyle(label).fontSize) };
    }))()`);
    const byName = Object.fromEntries(result.map((r) => [r.name, r]));
    for (const r of result) {
      expect(r.overflowX, r.name).toBeLessThanOrEqual(0);
      expect(r.overflowY, r.name).toBeLessThanOrEqual(0);
      // Chữ nằm trọn trong nút (sai số làm tròn 0,5 px).
      for (const side of ["textLeft", "textRight", "textTop", "textBottom"]) expect(r[side], `${r.name} ${side}`).toBeGreaterThanOrEqual(-0.5);
      expect(r.iconOffset, `${r.name}: icon canh dòng đầu`).toBeLessThanOrEqual(1.5);
    }
    expect(byName["primary-long"].fit).toBe("wrap");
    expect(byName["primary-long"].white).toBe("normal");
    expect(byName["primary-long"].lineCount).toBeGreaterThan(1);
    // Nút chung không có lớp nới của nơi gọi vẫn cao thêm theo chữ (has-[[data-fit=wrap]]:h-auto).
    expect(byName["plain-long"].fit).toBe("wrap");
    expect(byName["plain-long"].height).toBeGreaterThan(40);
    expect(byName["plain-slight"].fit).toMatch(/^(one|shrunk)$/);
    expect(byName["plain-slight"].lineCount).toBe(1);
    expect(byName["plain-short"].fit).toBe("one");
    // Chữ vừa một dòng: nút giữ đúng chiều cao chuẩn (min-height của cỡ nút; cảm ứng 48), không cao thêm.
    expect(byName["plain-short"].height).toBeCloseTo(byName["plain-short"].minHeight, 0);
    expect(byName["plain-long"].height).toBeGreaterThan(byName["plain-short"].height);
    await cdp.send("Target.closeTarget", { targetId: page.targetId });
  });

  it("tên sách trên bìa vẽ không cắt mà thu cỡ cho vừa trọn bìa (T3), bìa bo 12 theo DESIGN.md", async () => {
    const page = await openFixture(cdp, local.base);
    const result = await evaluate(cdp, page.sessionId, `(() => [...document.querySelectorAll("[data-case^=cover]")].map(box => {
      const cover = box.firstElementChild;
      const title = cover.querySelector("[data-fit-box]");
      const c = cover.getBoundingClientRect();
      const range = document.createRange(); range.selectNodeContents(title);
      const t = range.getBoundingClientRect();
      const style = getComputedStyle(title);
      return { name: box.dataset.case, fit: title.dataset.fit, text: title.textContent, clamp: style.webkitLineClamp, ellipsis: style.textOverflow,
        overX: title.scrollWidth - title.clientWidth, overY: title.scrollHeight - title.clientHeight,
        inside: t.left >= c.left - 0.5 && t.right <= c.right + 0.5 && t.top >= c.top - 0.5 && t.bottom <= c.bottom + 0.5,
        radius: getComputedStyle(cover).borderTopLeftRadius, fontSize: parseFloat(style.fontSize) };
    }))()`);
    for (const r of result) {
      expect(r.clamp === "none" || r.clamp === "", r.name).toBe(true);
      expect(r.ellipsis, r.name).not.toBe("ellipsis");
      expect(r.overX, r.name).toBeLessThanOrEqual(0);
      expect(r.overY, r.name).toBeLessThanOrEqual(0);
      expect(r.inside, r.name).toBe(true);
      expect(r.radius, r.name).toBe("12px");
    }
    const byName = Object.fromEntries(result.map((r) => [r.name, r]));
    expect(byName["cover-md"].fit).toBe("shrunk");
    expect(byName["cover-short"].fit).toBe("one");
    expect(byName["cover-short"].fontSize).toBeGreaterThan(byName["cover-md"].fontSize);
    await cdp.send("Target.closeTarget", { targetId: page.targetId });
  });

  it("2.000 hàng content-visibility: hàng cuộn vào được đo, không kẹt ở chưa đo / xuống dòng (T6)", async () => {
    const page = await openFixture(cdp, local.base, "#rows=2000");
    const measure = (from, to) => evaluate(cdp, page.sessionId, `(() => { const rows = [...document.querySelectorAll("[data-row]")].slice(${from}, ${to});
      return rows.flatMap(r => [...r.querySelectorAll("[data-one-line-fit]")].map(el => el.dataset.fit)); })()`);
    const top = await measure(0, 10);
    // Hàng giữa danh sách lúc gắn nằm ngoài màn (content-visibility bỏ qua dàn trang): chưa đo được - đúng ca kẹt mà soát T6 nêu.
    expect((await measure(1500, 1510)).every((fit) => fit === "unmeasured")).toBe(true);
    expect(top.every((fit) => fit === "one" || fit === "shrunk" || fit === "wrap")).toBe(true);
    // Cuộn tới giữa danh sách: hàng ngoài màn lúc gắn (bị bỏ qua dàn trang, bề ngang 0) phải được đo khi hiện ra.
    await evaluate(cdp, page.sessionId, `(async () => { document.querySelector("[data-row='1500']").scrollIntoView(); for (let i = 0; i < 6; i++) await new Promise(r => requestAnimationFrame(r)); return true; })()`);
    const middle = await measure(1500, 1510);
    expect(middle.filter((fit) => fit === "unmeasured" || fit === undefined)).toEqual([]);
    const ms = await evaluate(cdp, page.sessionId, "window.__mountMs");
    expect(ms).toBeGreaterThan(0);
    await cdp.send("Target.closeTarget", { targetId: page.targetId });
  });
});
