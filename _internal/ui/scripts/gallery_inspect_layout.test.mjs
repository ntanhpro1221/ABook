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
      // Hàng cuối bị mép khung cắt ngang icon (nét phải khuất hẳn): không đo icon dở - từng báo nhầm hàng chương sát thanh phát.
      expect(at(result, "gap-clipped", "ink-icon-text-gap")).toHaveLength(0);
    }
  });
  it("mực icon bị cắt ở mép cuộn không tạo chênh gap giả; gap sai của icon nguyên vẹn vẫn bị bắt", () => {
    for (const result of results) {
      expect(at(result, "gap-clipped-row", "ink-icon-text-gap")).toHaveLength(0);
      expect(at(result, "gap", "ink-icon-text-gap")).toHaveLength(1);
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
  it("vạch chia trong khối lề âm thò ra ngoài cột khung chứa thì báo; thụt lại thì không", () => {
    for (const result of results) {
      expect(at(result, "hair", "hairline-overhang")).toHaveLength(1);
      expect(at(result, "hair", "hairline-overhang")[0].delta).toBeCloseTo(12, 0);
      expect(at(result, "hair-pass", "hairline-overhang")).toHaveLength(0);
    }
  });
  it("dấu nối · cuối dòng hay đầu dòng thì báo; giữa dòng thì không", () => {
    for (const result of results) {
      const dots = (id) => result.findings.filter((f) => f.rule === "LINE BREAK" && (f.selector === `#${id}` || f.selector.startsWith(`#${id} >`)));
      expect(dots("dots-end").map((f) => f.metric)).toEqual(["separator-ends-line"]);
      expect(dots("dots-start").map((f) => f.metric)).toEqual(["separator-starts-line"]);
      expect(dots("dots-pass")).toHaveLength(0);
      // Hộp phải là số thường: DOMRect qua returnByValue thành {} và ảnh cắt hỏng cả khung.
      for (const f of dots("dots-end")) {
        for (const r of f.rects) expect(Number.isFinite(r.x + r.y + r.width + r.height)).toBe(true);
        expect(Number.isFinite(f.delta)).toBe(true); // index.html in Δ cho mọi phát hiện có referenceValue
      }
    }
  });
  it("nút xếp dọc: biểu tượng lệch khỏi giữa nhãn thì báo; nằm giữa thì không", () => {
    for (const result of results) {
      const at2 = (id) => result.findings.filter((f) => f.selector.startsWith(`#${id} >`) && f.metric === "stacked-icon-center");
      expect(at2("stack")).toHaveLength(1);
      expect(at2("stack-pass")).toHaveLength(0);
    }
  });
  it("nhãn nền đặc đè chữ bìa (kể cả aria-hidden) thì báo; đặt chỗ trống hay vẽ dưới chữ thì không", () => {
    for (const result of results) {
      const covered = (id) => result.findings.filter((f) => f.rule === "COVERED TEXT" && f.selector.startsWith(`#${id} >`));
      expect(covered("cover")).toHaveLength(1);
      expect(covered("cover-pass")).toHaveLength(0);
      expect(covered("cover-under")).toHaveLength(0);
      expect(covered("cover-layer")).toHaveLength(0);
      expect(Number.isFinite(covered("cover")[0]?.value)).toBe(true); // index.html in value cho mọi phát hiện có metric
    }
  });
  it("nút canh giữa có dấu ẩn giữ chỗ đẩy chữ lệch tâm thì báo; dấu đặt tuyệt đối hay hiện thật thì không", () => {
    for (const result of results) {
      const off = (id) => result.findings.filter((f) => f.metric === "centred-ink-off-centre" && f.selector.startsWith(`#${id} >`));
      expect(off("centre-off")).toHaveLength(1);
      expect(off("centre-pass")).toHaveLength(0);
    }
  });
  it("tiêu đề trong tab lặp tên tab đang chọn thì báo; tiêu đề khác thì không", () => {
    for (const result of results) {
      const repeated = (id) => result.findings.filter((f) => f.rule === "REPEATED LABEL" && f.selector.startsWith(`#${id} >`));
      expect(repeated("tabs")).toHaveLength(1);
      expect(repeated("tabs-pass")).toHaveLength(0);
      expect(repeated("dup-action").map((f) => f.metric)).toEqual(["label-names-two-actions"]);
      expect(repeated("dup-action-pass")).toHaveLength(0);
      expect(repeated("dup-action-under")).toHaveLength(0);
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

describe.skipIf(!browserAvailable)("giá trị đang chọn trong popup", () => {
  let choiceResults;
  beforeAll(async () => { choiceResults = await layoutFixtures({ fixture: "selected-choice.html" }); }, 60000);
  it("chỉ cho phép nút mở lặp giá trị đang chọn trong popup có quan hệ ARIA của nó", () => {
    for (const result of choiceResults) {
      const repeated = (id) => result.findings.filter((f) => f.rule === "REPEATED LABEL" && f.selector.startsWith(`#${id} >`));
      expect(repeated("selected-popup")).toHaveLength(0);
      for (const id of ["unselected-popup", "closed-popup", "unrelated-popup", "plain-container"]) {
        expect(repeated(id).map((f) => f.metric)).toEqual(["label-names-two-actions"]);
      }
    }
  });
});

// Lớp nổi nằm ở file riêng: role="dialog" trong bộ mẫu chung làm các luật khác coi cả trang là lớp dưới.
describe.skipIf(!browserAvailable)("fixture lớp nổi chồng nhau", () => {
  let layerResults;
  beforeAll(async () => { layerResults = await layoutFixtures({ fixture: "layers.html" }); }, 60000);
  it("hộp thoại đè hộp thoại hay lớp đè menu thì báo; menu trong hộp thoại và menu con cạnh menu cha thì không", () => {
    for (const result of layerResults) {
      const stacked = (id) => result.findings.filter((f) => f.rule === "STACKED LAYERS" && f.selector.startsWith(`#${id} >`));
      expect(stacked("stacked").map((f) => f.metric)).toEqual(["dialog-over-dialog"]);
      expect(stacked("stacked-menu").map((f) => f.metric)).toEqual(["layer-over-menu"]);
      expect(stacked("stacked-pass")).toHaveLength(0);
    }
  });
});
