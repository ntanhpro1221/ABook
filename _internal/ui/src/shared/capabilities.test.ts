import { describe, expect, it } from "vitest";
import { canEditLayer, editBlockedNote, lineEditing, showsStudioOnly, studioNeed, syncsToComputer, type Capabilities } from "./capabilities";

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

describe("cuốn nghe thẳng từ máy khác", () => {
  it("sửa bị chặn kèm lý do, không bị giấu", () => {
    expect(editBlockedNote(caps({ link: true }))).toContain("sửa ở máy ấy");
  });
  it("không có lý do khi sửa được hay khi chưa biết khả năng", () => {
    expect(editBlockedNote(caps({}))).toBeNull();
    expect(editBlockedNote(caps({ link: true, workshop: true }))).toBeNull();
    expect(editBlockedNote(undefined)).toBeNull();
  });
});

describe("sửa một câu từ trang đọc", () => {
  it("cuốn không có xưởng: ghi ý muốn chờ Studio, trên cả máy có Studio lẫn điện thoại", () => {
    expect(lineEditing(caps({}))).toEqual({ mode: "wish" });
    expect(lineEditing(caps({ toolchain: true }))).toEqual({ mode: "wish" });
  });

  it("cuốn có xưởng và có Studio: sửa thật ở Studio", () => {
    expect(lineEditing(caps({ workshop: true, toolchain: true }))).toEqual({ mode: "studio" });
  });

  it("cuốn có xưởng mà chưa cài Studio: mờ, nói cần cài Studio", () => {
    expect(lineEditing(caps({ workshop: true }))).toEqual({ mode: "blocked", note: "cần cài Studio" });
  });

  it("cuốn nghe thẳng từ máy khác: mờ, nói sửa ở máy ấy; chưa biết khả năng: không có gì", () => {
    const blocked = lineEditing(caps({ link: true }));
    expect(blocked).toMatchObject({ mode: "blocked" });
    expect(blocked && "note" in blocked && blocked.note).toContain("sửa ở máy ấy");
    expect(lineEditing(undefined)).toBeNull();
  });
});

describe("cuốn tải từ máy tính chính (điện thoại)", () => {
  it("sửa được, và phần sửa gửi về máy tính", () => {
    expect(canEditLayer(caps({ sync: true }))).toBe(true);
    expect(syncsToComputer(caps({ sync: true }))).toBe(true);
    expect(editBlockedNote(caps({ sync: true }))).toBeNull();
  });

  it("cuốn nghe thẳng, cuốn của máy tính (workshop) và cuốn nhập từ file không gửi về đâu cả", () => {
    expect(syncsToComputer(caps({ link: true }))).toBe(false);
    expect(syncsToComputer(caps({ workshop: true, sync: true }))).toBe(false);
    expect(syncsToComputer(caps({}))).toBe(false);
    expect(syncsToComputer(undefined)).toBe(false);
  });
});
