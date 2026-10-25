// @vitest-environment happy-dom
import { describe, expect, it, afterEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { createInspectorHelpers, inspectPage } from "./gallery_inspect_helpers.mjs";
import { cropClip, normalizeRule, gateRules, DEFAULT_FAIL_ON } from "./gallery_inspect.mjs";
import { deduplicate, inferSource } from "./gallery_inspect_report.mjs";

const h = createInspectorHelpers();
afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("hình học", () => {
  const a = { x: 10, y: 20, width: 20, height: 10 };
  it("không coi mép chạm / giao đúng 1 px là chồng", () => {
    expect(h.intersection(a, { x: 30, y: 20, width: 10, height: 10 })).toBeNull();
    expect(h.intersection(a, { x: 29, y: 20, width: 10, height: 10 })).toBeNull();
    expect(h.intersection(a, { x: 20, y: 29, width: 10, height: 10 })).toBeNull();
  });
  it("tìm vùng giao >1 px ở cả hai chiều", () => {
    expect(h.intersection(a, { x: 28, y: 25, width: 10, height: 10 })).toEqual({ x: 28, y: 25, width: 2, height: 5 });
    expect(h.intersection({ x: -4, y: -5, width: 8, height: 10 }, { x: 0, y: 0, width: 10, height: 10 }, 0)).toEqual({ x: 0, y: 0, width: 4, height: 5 });
  });
  it("hợp các rect và crop có lề, chặn theo viewport, scale 4", () => {
    const rects = [{ x: -2, y: 3, width: 12, height: 9 }, { x: 80, y: 70, width: 30, height: 40 }];
    expect(h.union(rects)).toEqual({ x: -2, y: 3, width: 112, height: 107 });
    expect(h.union([])).toBeNull();
    expect(cropClip(rects, { width: 100, height: 100 })).toEqual({ x: 0, y: 0, width: 100, height: 100, scale: 4 });
  });
});

describe("tương phản sRGB", () => {
  it("đen/trắng 21:1 và màu trùng 1:1", () => {
    expect(h.contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21);
    expect(h.contrastRatio([74, 92, 111], [74, 92, 111])).toBeCloseTo(1);
  });
  it("đúng tại biên 4.5:1 và bất biến khi đảo thứ tự", () => {
    expect(h.contrastRatio([119, 119, 119], [255, 255, 255])).toBeCloseTo(4.478, 3);
    expect(h.contrastRatio([118, 118, 118], [255, 255, 255])).toBeGreaterThan(4.5);
    expect(h.contrastRatio([255, 255, 255], [119, 119, 119])).toBeCloseTo(4.478, 3);
  });
  it("chồng alpha trước khi tính", () => {
    expect(h.composite([0, 0, 0, 0.5], [255, 255, 255, 1])).toEqual([127.5, 127.5, 127.5, 1]);
    expect(h.luminance([10, 10, 10])).toBeCloseTo(0.003035, 6);
  });
});

describe("chữ bị cắt", () => {
  const metrics = { scrollWidth: 120, clientWidth: 100, scrollHeight: 42, clientHeight: 40 };
  it("bắt hidden/clip và bỏ overflow cuộn", () => {
    expect(h.overflow(metrics, { overflowX: "hidden", overflowY: "clip" })).toEqual({ x: true, y: true });
    expect(h.overflow(metrics, { overflowX: "auto", overflowY: "scroll" })).toEqual({ x: false, y: false });
  });
  it("ellipsis chỉ miễn chiều ngang, line-clamp chỉ miễn chiều dọc", () => {
    expect(h.overflow(metrics, { overflowX: "hidden", overflowY: "hidden", textOverflow: "ellipsis" })).toEqual({ x: false, y: true });
    expect(h.overflow(metrics, { overflowX: "clip", overflowY: "hidden", webkitLineClamp: "2" })).toEqual({ x: true, y: false });
  });
  it("dung sai 1 px", () => {
    expect(h.overflow({ ...metrics, scrollWidth: 101, scrollHeight: 41 }, { overflowX: "hidden", overflowY: "hidden" })).toEqual({ x: false, y: false });
  });
});

describe("glyph và data-overlay trong DOM", () => {
  function load() { document.write(readFileSync("scripts/fixtures/skip-glyph.html", "utf8")); }
  const textRect = { x: 20, y: 20, width: 12, height: 12 }, graphicRect = { x: 10, y: 10, width: 28.8, height: 28.8 };
  it("TEXT-OVER-GRAPHIC bắt chữ HTML tuyệt đối của 0bec019f, cho qua chữ trong SVG mới", () => {
    load();
    const oldText = document.querySelector("#old-case .digits"), oldSvg = document.querySelector("#old-case svg");
    expect(h.graphicOverlap({ element: oldText, rect: textRect }, { element: oldSvg, rect: graphicRect })).not.toBeNull();
    const newText = document.querySelector("#new-case text"), newSvg = document.querySelector("#new-case svg");
    expect(h.graphicOverlap({ element: newText, rect: textRect }, { element: newSvg, rect: graphicRect })).toBeNull();
  });
  it("bộ soi hoàn chỉnh trả finding cho glyph cũ và không trả cho SVG mới (DOM giả chỉ cung cấp layout)", () => {
    load();
    const oldText = document.querySelector("#old-case .digits"), newText = document.querySelector("#new-case text");
    const box = (x) => ({ x, y: 10, width: 28.8, height: 28.8 });
    for (const el of document.body.querySelectorAll("*")) {
      vi.spyOn(el, "getBoundingClientRect").mockReturnValue(box(el.closest("#new-case") ? 110 : 10));
    }
    vi.spyOn(Range.prototype, "getClientRects").mockImplementation(function () {
      const el = this.startContainer.parentElement;
      return el === oldText ? [textRect] : el === newText ? [{ ...textRect, x: 120 }] : [];
    });
    vi.spyOn(document, "elementFromPoint").mockImplementation((x) => x < 100 ? oldText : newText);
    const computed = { display: "inline", visibility: "visible", opacity: "1", overflowX: "visible", overflowY: "visible", backgroundImage: "none", backgroundColor: "white", color: "black", fontSize: "12px", fontWeight: "400", transform: "none", scale: "none", content: "none", strokeWidth: "1.9px" };
    vi.stubGlobal("getComputedStyle", () => computed);
    vi.stubGlobal("DOMMatrix", class { c = 0; d = 1; });
    // Happy-dom không vẽ canvas; màu không ảnh hưởng đến quy tắc đang thử.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ clearRect() {}, fillRect() {}, getImageData: () => ({ data: [255, 255, 255, 255] }) });
    Object.defineProperty(document, "fonts", { configurable: true, value: [] });
    Object.defineProperty(document, "getAnimations", { configurable: true, value: () => [] });
    let result;
    try { result = inspectPage({}, h); } finally { Reflect.deleteProperty(document, "fonts"); Reflect.deleteProperty(document, "getAnimations"); }
    const overlaps = result.findings.filter((f) => f.rule === "TEXT-OVER-GRAPHIC");
    expect(overlaps).toHaveLength(1);
    expect(overlaps[0].selector).toMatch(/^#old-case/);
    expect(overlaps[0].text).toBe("15");
  });
  it("data-overlay chỉ miễn chữ và hình cùng nằm trong vùng được đánh dấu", () => {
    load();
    document.querySelector("#old-case .old").setAttribute("data-overlay", "fixture có chủ ý");
    const text = { element: document.querySelector("#old-case .digits"), rect: textRect };
    expect(h.graphicOverlap(text, { element: document.querySelector("#old-case svg"), rect: graphicRect })).toBeNull();
    expect(h.graphicOverlap(text, { element: document.querySelector("#new-case svg"), rect: graphicRect })).not.toBeNull();
  });
  it("hình chứa chữ (background ảnh bìa) được miễn", () => {
    load();
    expect(h.graphicOverlap({ element: document.querySelector("#old-case .digits"), rect: textRect }, { element: document.querySelector("#old-case"), rect: graphicRect })).toBeNull();
  });
  it("mã kiểm tra có thể nhúng nguyên vào CDP mà không có import/closure", () => {
    expect(() => new Function(`return (${inspectPage.toString()})({}, (${createInspectorHelpers.toString()})())`)).not.toThrow();
  });
});

describe("phần tử không được vẽ", () => {
  it("bỏ qua con cháu của content-visibility: hidden (trang dưới màn Đang nghe), vẫn bắt chữ bị cắt ở nơi được vẽ", () => {
    document.body.innerHTML = '<div id="covered"><p class="clip">Chương 7 · Giọng đọc của máy</p></div><div id="open"><p class="clip">Chương 7 · Giọng đọc của máy</p></div>';
    const covered = document.querySelector("#covered");
    const box = (el) => ({ x: 10, y: el.closest("#covered") ? 10 : 60, width: 100, height: 20 });
    for (const el of document.body.querySelectorAll("*")) {
      vi.spyOn(el, "getBoundingClientRect").mockReturnValue(box(el));
      if (el.matches(".clip")) for (const [key, value] of Object.entries({ scrollWidth: 160, clientWidth: 100, scrollHeight: 20, clientHeight: 20 })) Object.defineProperty(el, key, { configurable: true, value });
    }
    vi.spyOn(Range.prototype, "getClientRects").mockImplementation(function () {
      const el = this.startContainer.parentElement;
      return el?.matches(".clip") ? [{ x: 10, y: box(el).y, width: 160, height: 20 }] : [];
    });
    vi.spyOn(document, "elementFromPoint").mockImplementation((x, y) => document.querySelector(y < 40 ? "#covered .clip" : "#open .clip"));
    const base = { display: "block", visibility: "visible", opacity: "1", overflowX: "visible", overflowY: "visible", backgroundImage: "none", backgroundColor: "white", color: "black", fontSize: "14px", fontWeight: "400", transform: "none", scale: "none", content: "none", strokeWidth: "1.9px", contentVisibility: "visible" };
    vi.stubGlobal("getComputedStyle", (el) => el === covered ? { ...base, contentVisibility: "hidden" } : el.matches?.(".clip") ? { ...base, overflowX: "hidden" } : base);
    vi.stubGlobal("DOMMatrix", class { c = 0; d = 1; });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ clearRect() {}, fillRect() {}, getImageData: () => ({ data: [255, 255, 255, 255] }) });
    Object.defineProperty(document, "fonts", { configurable: true, value: [] });
    Object.defineProperty(document, "getAnimations", { configurable: true, value: () => [] });
    let result;
    try { result = inspectPage({}, h); } finally { Reflect.deleteProperty(document, "fonts"); Reflect.deleteProperty(document, "getAnimations"); }
    const clipped = result.findings.filter((f) => f.rule === "CLIPPED TEXT");
    expect(clipped.some((f) => f.selector.startsWith("#open"))).toBe(true);
    expect(clipped.filter((f) => f.selector.startsWith("#covered"))).toHaveLength(0);
  });
});

describe("nhãn nối đuôi chữ trong hàng lặp", () => {
  function run(html, boxes) {
    document.body.innerHTML = html;
    for (const el of document.body.querySelectorAll("*")) vi.spyOn(el, "getBoundingClientRect").mockReturnValue(boxes(el));
    vi.spyOn(Range.prototype, "getClientRects").mockImplementation(function () { const el = this.startContainer.parentElement; return el?.matches("span") ? [boxes(el)] : []; });
    vi.spyOn(document, "elementFromPoint").mockImplementation((x, y) => [...document.querySelectorAll("span")].find((el) => { const b = boxes(el); return x >= b.x && x <= b.x + b.width && y >= b.y && y <= b.y + b.height; }) ?? document.body);
    const base = { display: "block", visibility: "visible", opacity: "1", overflowX: "visible", overflowY: "visible", backgroundImage: "none", backgroundColor: "white", color: "black", fontSize: "14px", fontWeight: "400", transform: "none", scale: "none", content: "none", strokeWidth: "1.9px", contentVisibility: "visible", textAlign: "start", flexDirection: "row", justifyContent: "normal", alignItems: "normal", flexGrow: "0" };
    vi.stubGlobal("getComputedStyle", (el) => el.matches?.(".row") ? { ...base, display: "flex" } : el.matches?.("span") ? { ...base, display: "inline" } : base);
    vi.stubGlobal("DOMMatrix", class { c = 0; d = 1; });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ clearRect() {}, fillRect() {}, getImageData: () => ({ data: [255, 255, 255, 255] }) });
    Object.defineProperty(document, "fonts", { configurable: true, value: [] });
    Object.defineProperty(document, "getAnimations", { configurable: true, value: () => [] });
    try { return inspectPage({}, h).findings.filter((f) => f.rule === "SIBLING CONSISTENCY" && f.metric === "text-left"); } finally { Reflect.deleteProperty(document, "fonts"); Reflect.deleteProperty(document, "getAnimations"); }
  }
  const html = '<ul><li><div class="row"><span class="name">Ông Tư</span><span class="tag">Nam</span></div></li><li><div class="row"><span class="name">Bà Ba Hoa</span><span class="tag">Nữ</span></div></li></ul>';
  const rowY = (el) => el.closest("li") === document.querySelectorAll("li")[0] ? 10 : 50;
  it("mép trái nhãn sau tên dài ngắn khác nhau không phải lỗi", () => {
    const boxes = (el) => el.matches(".tag") ? { x: el.closest("li") === document.querySelectorAll("li")[0] ? 70 : 100, y: rowY(el), width: 20, height: 16 } : el.matches(".name") ? { x: 10, y: rowY(el), width: el.textContent.length * 6, height: 16 } : el.matches("li,.row") ? { x: 0, y: rowY(el), width: 300, height: 30 } : { x: 0, y: 0, width: 400, height: 400 };
    expect(run(html, boxes)).toHaveLength(0);
  });
  it("chữ đầu hàng lệch cột vẫn bị bắt", () => {
    const boxes = (el) => el.matches(".name") ? { x: el.closest("li") === document.querySelectorAll("li")[0] ? 10 : 16, y: rowY(el), width: 40, height: 16 } : el.matches(".tag") ? { x: 90, y: rowY(el), width: 20, height: 16 } : el.matches("li,.row") ? { x: 0, y: rowY(el), width: 300, height: 30 } : { x: 0, y: 0, width: 400, height: 400 };
    expect(run(html, boxes).length).toBeGreaterThan(0);
  });
});

describe("so sánh hàng lặp với dung sai 1 CSS px", () => {
  it("ignores floating point residue but preserves a real >1 px drift", () => {
    expect(h.siblingDifferences([{ value: 18 }, { value: 16.999 }])).toEqual([]);
    expect(h.siblingDifferences([{ value: 18 }, { value: 16.98 }])).toHaveLength(1);
  });
  it("bắt hộp 18 / 12 và giữ hàng, mốc, độ lệch có dấu", () => {
    const samples = [{ rowIndex: 1, value: 18 }, { rowIndex: 2, value: 12 }];
    expect(h.siblingDifferences(samples)).toEqual([{ sample: samples[1], reference: samples[0], delta: -6 }]);
  });
  it("bắt khe lệch 3,5 px và chọn hàng đa số làm mốc", () => {
    const samples = [{ rowIndex: 1, value: 13.5 }, { rowIndex: 2, value: 10 }, { rowIndex: 3, value: 10 }];
    expect(h.siblingDifferences(samples)).toEqual([{ sample: samples[0], reference: samples[1], delta: 3.5 }]);
  });
  it("im lặng khi bằng nhau hoặc lệch đúng 1 px; bắt phần vượt rất nhỏ", () => {
    expect(h.siblingDifferences([])).toEqual([]);
    expect(h.siblingDifferences([{ value: 18 }, { value: 18 }, { value: 17 }])).toEqual([]);
    expect(h.siblingDifferences([{ value: 18 }, { value: 16.98 }])).toHaveLength(1);
  });
  it("không để mốc ở giữa che mất chênh lệch hai đầu", () => {
    expect(h.siblingDifferences([{ value: 1 }, { value: 0 }, { value: 2 }])).toHaveLength(1);
  });
});

describe("audited release gate and defect grouping", () => {
  it("gates reviewed rules and the two ink140 layout rules", () => {
    expect(gateRules()).toEqual(DEFAULT_FAIL_ON);
    expect(gateRules()).toContain("INK EDGE");
    expect(gateRules()).toContain("RHYTHM");
    expect(gateRules()).toContain("BASELINE");
    expect(gateRules()).toContain("CONTROL HEIGHT");
    expect(gateRules()).not.toContain("OPTICAL SIZE CONSISTENCY");
    expect(gateRules()).not.toContain("CLIPPED TEXT");
  });
  it("supports an advisory scan and an explicit rule override", () => {
    expect(gateRules(["NONE"])).toEqual([]);
    expect(gateRules(["rule9"])).toEqual(["OPTICAL SIZE CONSISTENCY"]);
    expect(() => gateRules(["typo"])).toThrow();
  });
  const finding = { id: "F1", story: "phone/a", theme: "light", rule: "SMALL TEXT", selector: "#one > svg > text", context: [{ tag: "text", classes: [], data: { "data-source": "Player.tsx" } }, { tag: "svg", classes: ["glyph-20"], data: {} }] };
  it("merges the same component across frames, themes and DOM indices", () => {
    const groups = deduplicate([finding, { ...finding, id: "F2", story: "desktop/b", theme: "dark", selector: "#two > svg:nth-of-type(2) > text" }]);
    expect(groups).toHaveLength(1);
    expect(groups[0].findingIds).toEqual(["F1", "F2"]);
    expect(groups[0].frames).toHaveLength(2);
  });
  it("does not merge distinct rules or source files", () => {
    expect(deduplicate([finding, { ...finding, rule: "CONTRAST" }, { ...finding, context: [{ tag: "svg", classes: ["glyph-20"], data: { "data-source": "Other.tsx" } }] }])).toHaveLength(3);
  });
  it("marks source guesses as likely and missing provenance as unknown", () => {
    expect(inferSource({ text: "Unique label", context: [] }, [{ file: "A.tsx", content: '<button>Unique label</button>' }]).confidence).toBe("likely");
    expect(inferSource({ text: "Unknown", context: [] }, []).file).toBeNull();
  });
  it("attributes matching buttons with a longer unique own class sequence", () => {
    const f = { text: "Dynamic voice name", rule: "TOUCH TARGET", context: [{ tag: "button", classes: ["grid", "size-9", "shrink-0", "place-items-center", "rounded-full", "border", "transition-colors", "border-line"], data: {} }] };
    const files = [{ file: "Book.tsx", content: '<button className="grid size-9 shrink-0 place-items-center rounded-full border transition-colors" />' }, { file: "Generic.tsx", content: '<button className="grid size-9 shrink-0 place-items-center rounded-full border disabled:opacity-50" />' }];
    expect(inferSource(f, files)).toMatchObject({ file: "Book.tsx", line: 1, confidence: "likely" });
    expect(deduplicate([f, { ...f, text: "Another voice" }], files)).toHaveLength(1);
  });
  it("uses ancestor evidence to disambiguate a shared button pattern", () => {
    const own = ["grid", "size-9", "shrink-0", "place-items-center", "rounded-full", "border", "transition-colors"];
    const ancestor = ["flex", "items-center", "gap-3", "rounded-2xl", "border", "border-line", "bg-panel", "p-4"];
    const f = { text: "Dynamic voice", rule: "TOUCH TARGET", context: [{ tag: "button", classes: own, data: {} }, { tag: "div", classes: ancestor, data: {} }] };
    const button = `<button className="${own.join(" ")}" />`;
    expect(inferSource(f, [{ file: "Book.tsx", content: `<div className="${ancestor.join(" ")}">${button}</div>` }, { file: "Voice.tsx", content: button }])).toMatchObject({ file: "Book.tsx", confidence: "likely" });
  });
  it("attributes SVG text to its renderer rather than a generic button wrapper", () => {
    const f = { text: "15", context: [{ tag: "text", classes: [], data: {} }, { tag: "svg", classes: ["glyph"], data: {} }] };
    expect(inferSource(f, [{ file: "Wrapper.tsx", content: '<button className="glyph" />' }, { file: "Player.tsx", content: '<svg><text>15</text></svg>' }])).toMatchObject({ file: "Player.tsx", confidence: "likely" });
  });
});

describe("quy tắc 8–9 trong bộ soi DOM hoàn chỉnh", () => {
  function inspectRows(options = {}) {
    const { width = 12, inkWidth = width, textShift = width - 18, progressShift = 0, labelShift = 0, separate = false, directTitle = false } = options;
    const row = () => `<li><button><svg viewBox="0 0 18 18"><rect width="18" height="18"/></svg>${directTitle ? "Tên sách" : "<span>Tên sách</span>"}<div role="progressbar"></div><span>50%</span></button></li>`;
    document.body.innerHTML = separate ? `<ul>${row()}</ul><ul>${row()}</ul>` : `<ul>${row()}${row()}</ul>`;
    const boxes = new Map(), textBoxes = new Map();
    [...document.querySelectorAll("li")].forEach((li, i) => {
      const y = 10 + i * 50, w = i ? width : 18;
      const box = (x, width) => ({ x, y, width, height: 20 });
      for (const el of [li, ...li.querySelectorAll("*")]) boxes.set(el, { x: 10, y, width: 250, height: 44 });
      const svg = li.querySelector("svg");
      boxes.set(svg, box(18, w));
      Object.defineProperty(svg, "getBBox", { value: () => ({ x: 0, y: 0, width: i ? inkWidth : 18, height: 18 }) });
      Object.defineProperty(svg, "getScreenCTM", { value: () => ({ a: 1, b: 0, c: 0, d: 1, e: 18, f: y }) });
      const spans = [...li.querySelectorAll("span")], label = spans.at(-1);
      if (directTitle) textBoxes.set([...li.querySelector("button").childNodes].find((n) => n.nodeType === Node.TEXT_NODE), box(46 + (i ? textShift : 0), 70));
      else boxes.set(spans[0], box(46 + (i ? textShift : 0), 70));
      boxes.set(li.querySelector('[role="progressbar"]'), box(130, 70 + (i ? progressShift : 0)));
      boxes.set(label, box(210 + (i ? labelShift : 0), 28));
    });
    const fallback = { x: 0, y: 0, width: 300, height: 150 };
    for (const el of document.body.querySelectorAll("*")) vi.spyOn(el, "getBoundingClientRect").mockImplementation(() => boxes.get(el) ?? fallback);
    vi.spyOn(Range.prototype, "getClientRects").mockImplementation(function () { return [textBoxes.get(this.startContainer) ?? boxes.get(this.startContainer.parentElement)]; });
    vi.spyOn(document, "elementFromPoint").mockReturnValue(document.body);
    vi.stubGlobal("getComputedStyle", (el) => ({ display: el.localName === "button" ? "flex" : "block", flexDirection: "row", flexGrow: el.matches('[role="progressbar"]') ? "1" : "0", visibility: "visible", opacity: "1", overflowX: "visible", overflowY: "visible", backgroundImage: "none", backgroundColor: "white", color: "black", fontSize: "14px", fontWeight: "400", transform: "none", scale: "none", content: "none", strokeWidth: "1px" }));
    vi.stubGlobal("DOMMatrix", class { c = 0; d = 1; });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ clearRect() {}, fillRect() {}, getImageData: () => ({ data: [255, 255, 255, 255] }) });
    Object.defineProperty(document, "fonts", { configurable: true, value: [] });
    Object.defineProperty(document, "getAnimations", { configurable: true, value: () => [] });
    try { return inspectPage({}, h).findings.filter((f) => ["SIBLING CONSISTENCY", "OPTICAL SIZE CONSISTENCY"].includes(f.rule)); }
    finally { Reflect.deleteProperty(document, "fonts"); Reflect.deleteProperty(document, "getAnimations"); }
  }
  it("hộp 18 / 12 px bị cả hai quy tắc bắt đúng hàng và delta", () => {
    const findings = inspectRows();
    expect(findings).toEqual(expect.arrayContaining([
      expect.objectContaining({ rule: "SIBLING CONSISTENCY", metric: "text-left", rowIndex: 2, referenceRowIndex: 1, delta: -6 }),
      expect.objectContaining({ rule: "OPTICAL SIZE CONSISTENCY", metric: "icon-width", rowIndex: 2, referenceRowIndex: 1, delta: -6 }),
    ]));
  });
  it("đo nét thật bên trong viewport SVG bằng nhau", () => {
    expect(inspectRows({ width: 18, inkWidth: 12 })).toEqual(expect.arrayContaining([
      expect.objectContaining({ metric: "icon-text-gap", delta: 6 }),
      expect.objectContaining({ rule: "OPTICAL SIZE CONSISTENCY", delta: -6 }),
    ]));
  });
  it("bắt cả nhãn text node trực tiếp sau SVG, không bắt buộc span bọc", () => {
    expect(inspectRows({ directTitle: true })).toEqual(expect.arrayContaining([
      expect.objectContaining({ metric: "text-left", delta: -6 }),
      expect.objectContaining({ rule: "OPTICAL SIZE CONSISTENCY", metric: "icon-width", delta: -6 }),
    ]));
  });
  it("không loại icon tràn sang chữ: khe âm vẫn được đối chiếu", () => {
    expect(inspectRows({ width: 18, inkWidth: 24, textShift: -6 })).toEqual(expect.arrayContaining([
      expect.objectContaining({ metric: "icon-text-gap", value: -2, delta: -12 }),
      expect.objectContaining({ rule: "OPTICAL SIZE CONSISTENCY", delta: 6 }),
    ]));
  });
  it("bắt khe 3,5 px, mép phải thanh tiến độ và nhãn tương ứng", () => {
    const findings = inspectRows({ width: 18, textShift: 3.5, progressShift: -4, labelShift: 2 });
    expect(findings).toEqual(expect.arrayContaining([
      expect.objectContaining({ metric: "icon-text-gap", delta: 3.5 }),
      expect.objectContaining({ metric: "progress-right", delta: -4 }),
      expect.objectContaining({ metric: "text-right", delta: 2 }),
    ]));
    expect(findings.some((f) => f.rule === "OPTICAL SIZE CONSISTENCY")).toBe(false);
  });
  it("hàng căn đều và chênh đúng 1 px không bị bắt", () => {
    expect(inspectRows({ width: 18 })).toEqual([]);
    vi.restoreAllMocks();
    expect(inspectRows({ width: 17 })).toEqual([]);
  });
  it("không so hàng khác danh sách", () => {
    expect(inspectRows({ separate: true })).toEqual([]);
  });
});

it("tên quy tắc cho --fail-on dùng được tên, dấu gạch và rule1..20; từ chối tên sai", () => {
  expect(normalizeRule("rule1")).toBe("TEXT-OVER-GRAPHIC");
  expect(normalizeRule("CLIPPED_TEXT")).toBe("CLIPPED TEXT");
  expect(normalizeRule("touch-target")).toBe("TOUCH TARGET");
  expect(normalizeRule("rule8")).toBe("SIBLING CONSISTENCY");
  expect(normalizeRule("rule9")).toBe("OPTICAL SIZE CONSISTENCY");
  expect(normalizeRule("optical-size-consistency")).toBe("OPTICAL SIZE CONSISTENCY");
  expect(normalizeRule("rule10")).toBe("INK EDGE");
  expect(normalizeRule("rule11")).toBe("RHYTHM");
  expect(normalizeRule("rule12")).toBe("BASELINE");
  expect(normalizeRule("rule13")).toBe("CONTROL HEIGHT");
  expect(normalizeRule("rule14")).toBe("FILL INSET");
  expect(normalizeRule("rule15")).toBe("TAP REACH");
  expect(normalizeRule("rule16")).toBe("FOCUS RING CLIPPED");
  expect(normalizeRule("rule17")).toBe("CORNER MISMATCH");
  expect(normalizeRule("rule18")).toBe("LINE BREAK");
  expect(normalizeRule("rule19")).toBe("COVERED TEXT");
  expect(normalizeRule("rule20")).toBe("REPEATED LABEL");
  expect(() => normalizeRule("rule21")).toThrow("Quy tắc lạ");
  expect(() => normalizeRule("typo")).toThrow("Quy tắc lạ");
});
