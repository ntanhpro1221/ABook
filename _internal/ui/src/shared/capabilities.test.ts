import { describe, expect, it } from "vitest";
import { canEditLayer, showsStudioOnly, studioNeed, type Capabilities } from "./capabilities";

const caps = (over: Partial<Capabilities>): Capabilities => ({ toolchain: false, workshop: false, link: false, ...over });

describe("sửa áp ngay theo khả năng của máy", () => {
  it("làm được trên cuốn của máy này, có xưởng hay không", () => {
    expect(canEditLayer(caps({ workshop: true, toolchain: true }))).toBe(true);
    expect(canEditLayer(caps({}))).toBe(true); // cuốn nhập từ file trên điện thoại
    expect(canEditLayer(caps({ toolchain: true }))).toBe(true); // cuốn nhập từ file trên máy có Studio
  });

  it("không làm được trên cuốn nghe thẳng từ máy khác, hay khi chưa biết gì", () => {
    expect(canEditLayer(caps({ link: true }))).toBe(false);
    expect(canEditLayer(undefined)).toBe(false);
    expect(canEditLayer(null)).toBe(false);
  });
});

describe("việc cần Studio vẫn hiện, nói rõ thiếu gì", () => {
  it("điện thoại và máy chưa cài Studio: cần cài Studio", () => {
    expect(studioNeed(caps({}))).toBe("cần cài Studio");
    expect(studioNeed(caps({ workshop: true }))).toBe("cần cài Studio");
  });

  it("máy có Studio nhưng cuốn nhập từ file: cần dựng xưởng", () => {
    expect(studioNeed(caps({ toolchain: true }))).toMatch(/dựng xưởng/);
  });

  it("máy có Studio và cuốn có xưởng: làm được ngay, không có gì mờ", () => {
    expect(studioNeed(caps({ toolchain: true, workshop: true }))).toBeNull();
    expect(showsStudioOnly(caps({ toolchain: true, workshop: true }))).toBe(false);
  });

  it("cuốn của máy khác: không hiện gì (việc đó nằm ở máy kia)", () => {
    expect(showsStudioOnly(caps({ link: true }))).toBe(false);
    expect(showsStudioOnly(undefined)).toBe(false);
  });
});
