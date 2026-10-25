// @vitest-environment node
import { beforeAll, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { layoutFixtures } from "./gallery_inspect_layout_fixture.mjs";
import { browserAvailable } from "./gallery_browser.mjs";
import { normalizeRule, DEFAULT_FAIL_ON } from "./gallery_inspect.mjs";

it("nhận tên và số 16–17; vòng chung là 2 px + 2 px", () => {
  expect(normalizeRule("rule16")).toBe("FOCUS RING CLIPPED");
  expect(normalizeRule("corner-mismatch")).toBe("CORNER MISMATCH");
  expect(normalizeRule("rule17")).toBe("CORNER MISMATCH");
  expect(DEFAULT_FAIL_ON).toContain("FOCUS RING CLIPPED");
  expect(DEFAULT_FAIL_ON).toContain("CORNER MISMATCH");
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  expect(css).toMatch(/:focus-visible\s*\{\s*outline: 2px solid var\(--focus\);\s*outline-offset: 2px;/);
});

describe.skipIf(!browserAvailable)("vòng tiêu điểm và góc bo trên Edge, hai theme và hai khổ", () => {
  let results;
  beforeAll(async () => { results = await layoutFixtures({ fixture: "focus-corners.html" }); }, 60000);
  const at = (r, id, rule) => r.findings.filter((f) => f.rule === rule && f.selector.startsWith(`#${id} >`));
  it("bắt overflow-x:auto, giữ đúng 4 px; padding bù và clip-margin đủ đều qua", () => {
    for (const r of results) {
      expect(at(r, "ring-cut", "FOCUS RING CLIPPED")).toHaveLength(1);
      expect(at(r, "ring-cut", "FOCUS RING CLIPPED")[0]).toMatchObject({ ring: 4, cut: ["left", "top", "bottom"] });
      for (const id of ["ring-room", "ring-clip", "ring-scroll", "ring-negative", "ring-disabled", "ring-border-box", "ring-border-out"]) expect(at(r, id, "FOCUS RING CLIPPED"), id).toHaveLength(0);
      expect(at(r, "ring-small-margin", "FOCUS RING CLIPPED")).toHaveLength(1);
    }
  });
  it("vùng cuộn còn cuộn tiếp về phía mép thì không báo; mép hết cuộn vẫn báo", () => {
    for (const r of results) {
      for (const id of ["ring-scrolled-top", "ring-scrolled-bottom"]) expect(at(r, id, "FOCUS RING CLIPPED"), id).toHaveLength(0);
      expect(at(r, "ring-edge-top", "FOCUS RING CLIPPED")).toHaveLength(1);
      expect(at(r, "ring-edge-top", "FOCUS RING CLIPPED")[0]).toMatchObject({ cut: ["top"] });
    }
  });
  it("clip-margin theo hộp được chỉ định và không áp dụng cho auto", () => {
    for (const r of results) {
      expect(at(r, "ring-content-box", "FOCUS RING CLIPPED")).toHaveLength(1);
      expect(at(r, "ring-auto-margin", "FOCUS RING CLIPPED")).toHaveLength(1);
    }
  });
  it("bắt thanh 4 px bo góc 8 px đã co còn 4 px; wrapper cắt theo bìa thì qua", () => {
    for (const r of results) {
      expect(at(r, "corner-old", "CORNER MISMATCH")).toHaveLength(2);
      expect(at(r, "corner-old", "CORNER MISMATCH")[0]).toMatchObject({ usedRadius: [4, 4], referenceRadius: [8, 8] });
      expect(at(r, "corner-new", "CORNER MISMATCH")).toHaveLength(0);
    }
  });
  it("so cả tổ tiên và góc elip; bỏ nền trong, góc không trùng và bán kính bằng nhau", () => {
    for (const r of results) {
      expect(at(r, "corner-ancestor", "CORNER MISMATCH")).toHaveLength(4);
      expect(at(r, "corner-ellipse", "CORNER MISMATCH")).toHaveLength(4);
      for (const id of ["corner-equal", "corner-transparent", "corner-offset", "corner-tolerance", "corner-hidden"]) expect(at(r, id, "CORNER MISMATCH"), id).toHaveLength(0);
    }
  });
});
