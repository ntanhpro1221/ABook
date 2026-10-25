// @vitest-environment node
import { beforeAll, describe, expect, it } from "vitest";
import { createLayoutHelpers, crossFrameRhythm, crossFrameTitles } from "./gallery_inspect_layout.mjs";
import { layoutFixtures } from "./gallery_inspect_layout_fixture.mjs";
import { browserAvailable } from "./gallery_browser.mjs";
import { normalizeRule } from "./gallery_inspect.mjs";

describe("đa số và nhịp giữa frame", () => {
  it("không đoán khi hai phía bằng nhau", () => {
    expect(createLayoutHelpers().majority([8, 8, 12, 12].map((value) => ({ value })), 1)).toBeNull();
    expect(createLayoutHelpers().majority([8, 8, 8, 12].map((value) => ({ value })), 1).value).toBe(8);
  });
  it("nhận tên và số 10–11", () => {
    expect(normalizeRule("rule10")).toBe("INK EDGE"); expect(normalizeRule("rhythm")).toBe("RHYTHM"); expect(normalizeRule("rule11")).toBe("RHYTHM");
  });
  it("chỉ so cùng platform, theme, nhóm và họ nội dung; dung sai 1 px", () => {
    const frame = (id, y, extra = {}) => ({ id, platform: "phone", theme: "light", group: "Cài đặt", layout: { firstBlock: { family: "settings-block", rect: { x: 20, y, width: 372, height: 100 }, selector: "section", context: [], text: "Nhóm", crop: `${id}.png` } }, ...extra });
    const result = crossFrameRhythm([frame("a", 95), frame("b", 95), frame("c", 96), frame("d", 103), frame("e", 120, { theme: "dark" }), frame("f", 99, { platform: "desktop" }), frame("g", 40, { group: "Studio" })]);
    expect(result).toHaveLength(1); expect(result[0]).toMatchObject({ story: "d", value: 103, referenceValue: 95, delta: 8, crop: "d.png", referenceCrop: "a.png" });
  });
});

describe("chân chữ tiêu đề màn giữa frame", () => {
  const frame = (id, baseline, extra = {}) => ({ id, platform: "phone", theme: "light", group: "Thư viện", layout: { screenTitle: { baseline, kind: "root", selector: "h1", rect: { x: 20, y: baseline - 24, width: 120, height: 32 }, context: [], text: id, crop: `${id}.png` } }, ...extra });
  it("so mọi màn cùng platform và theme, không theo nhóm gallery; dung sai 1 px", () => {
    const result = crossFrameTitles([frame("library", 45), frame("library-search", 45), frame("studio", 46, { group: "Studio" }), frame("settings", 40, { group: "Cài đặt" }),
      frame("dark", 54, { theme: "dark" }), frame("desktop", 64, { platform: "desktop" }), frame("broken", 30, { error: "x" })]);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ rule: "RHYTHM", metric: "screen-title-baseline", story: "settings", value: 40, referenceValue: 45, delta: -5, crop: "settings.png", referenceCrop: "library.png" });
  });
  it("không có đa số thì lấy trung vị làm mốc: ba màn gốc ba chân chữ đều bị bắt", () => {
    const result = crossFrameTitles([frame("library", 54, { group: "Thư viện" }), frame("studio", 46, { group: "Studio" }), frame("settings", 40, { group: "Cài đặt" })]);
    expect(result.map((f) => [f.story, f.referenceStory])).toEqual([["library", "studio"], ["settings", "studio"]]);
  });
  it("một khung thì không có gì để so", () => {
    expect(crossFrameTitles([frame("library", 54)])).toEqual([]);
  });
});

describe.skipIf(!browserAvailable)("fixture HTML trên Edge, hai theme và hai khổ", () => {
  let results;
  beforeAll(async () => { results = await layoutFixtures(); }, 60000);
  const at = (result, id, metric) => result.findings.filter((f) => f.selector.startsWith(`#${id} >`) && f.metric === metric);
  it("bắt padding trái/phải; -ml-3 px-3 và bù mép phải đều qua", () => {
    for (const result of results) {
      expect(at(result, "ghost", "ink-left")).toHaveLength(1);
      expect(at(result, "right", "ink-right")).toHaveLength(1);
      expect(at(result, "compensated", "ink-left")).toHaveLength(0);
      expect(at(result, "right-pass", "ink-right")).toHaveLength(0);
    }
  });
  it("đo path + nửa stroke, bỏ lề viewBox; icon đã bù qua", () => {
    for (const result of results) {
      expect(at(result, "inset-icon", "ink-left")[0]?.delta).toBeCloseTo(6, 1);
      expect(at(result, "inset-pass", "ink-left")).toHaveLength(0);
    }
  });
  it("bắt chênh gap 4 px dù khác glyph; hàng đều không báo", () => {
    for (const result of results) {
      expect(at(result, "gap", "ink-icon-text-gap")).toHaveLength(1);
      expect(at(result, "gap", "ink-icon-text-gap")[0].delta).toBeCloseTo(4, 1);
      expect(at(result, "gap-pass", "ink-icon-text-gap")).toHaveLength(0);
    }
  });
  it("bắt nhịp 20 / 8, bỏ đầu/cuối là header", () => {
    for (const result of results) {
      expect(at(result, "rhythm", "vertical-gap")).toHaveLength(1);
      expect(at(result, "rhythm", "vertical-gap")[0]).toMatchObject({ value: 20, referenceValue: 8, delta: 12 });
      expect(at(result, "rhythm-pass", "vertical-gap")).toHaveLength(0);
      expect(at(result, "fold-run", "vertical-gap")).toHaveLength(0);
    }
  });
  it("hàng nút chữ: hộp chạm căn giữa chữ ngắn làm lệch khoảng thì báo; gap đều hay tab chia đều thì không", () => {
    for (const result of results) {
      expect(at(result, "words", "horizontal-ink-gap")).toHaveLength(1);
      expect(at(result, "words", "horizontal-ink-gap")[0].values).toHaveLength(3);
      expect(at(result, "words-pass", "horizontal-ink-gap")).toHaveLength(0);
      expect(at(result, "words-even", "horizontal-ink-gap")).toHaveLength(0);
    }
  });
  it("tiêu đề màn: bỏ h1 trong nội dung, đo chân chữ của h1 đầu màn tính từ mép trên main (dải phía trên không tính)", () => {
    for (const result of results) {
      const title = result.layout.screenTitle;
      expect(title).toMatchObject({ text: "Thư viện", kind: "unmarked", fontSize: "24px", frameTop: 24 });
      // Arial / Liberation Sans 24/32: nửa khoảng dòng 2,6 + ascent 21,7 dưới mép trên dòng (đệm trên 12).
      expect(Math.abs(title.baseline - (title.rect.y - title.frameTop + 12 + 24.3))).toBeLessThan(1.5);
    }
  });
  it("thẻ có viền tạo cột riêng; nút giữa toàn hàng không phải cạnh cột", () => {
    for (const result of results) {
      expect(at(result, "panel", "ink-left")).toHaveLength(0);
      expect(at(result, "centered", "ink-left")).toHaveLength(0);
    }
  });
});
