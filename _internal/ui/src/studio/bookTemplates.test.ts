import { describe, expect, it } from "vitest";
import {
  MAX_TEMPLATES,
  applyTemplate,
  isFull,
  isModified,
  nameProblem,
  removeTemplate,
  renameTemplate,
  templateFromDraft,
  templatesOf,
  upsertTemplate,
  type BookTemplate,
  type Profile,
  type TemplateFields,
} from "./bookTemplates";

const ln: BookTemplate = { name: "Light novel", narrator: "Đức Trí", profile: "balanced", analysisModel: "qwen3:8b", startNow: false };
const tienHiep: BookTemplate = { name: "Tiên hiệp", narrator: "", profile: "fast", analysisModel: "", startNow: true };

interface Draft extends TemplateFields {
  title: string;
  paths: string[];
  firstPerson: string;
  dropCredits?: boolean;
  limit?: number | null;
}

const draft = (changes: Partial<Draft> = {}): Draft => ({
  title: "Tên sách", paths: ["D:/truyen"], firstPerson: "Lucien", dropCredits: true, limit: 20,
  narrator: "Thục Anh", profile: "high_quality" as Profile, startNow: true, ...changes,
});

describe("applyTemplate", () => {
  it("sets the four choices and the template name, and nothing else", () => {
    const before = draft();
    const after = applyTemplate(before, ln);
    expect(after).toMatchObject({ narrator: "Đức Trí", profile: "balanced", analysisModel: "qwen3:8b", startNow: false, template: "Light novel" });
    expect({ ...after, narrator: 0, profile: 0, analysisModel: 0, startNow: 0, template: 0 })
      .toEqual({ ...before, narrator: 0, profile: 0, analysisModel: 0, startNow: 0, template: 0 });
    expect(after.dropCredits).toBe(true);
  });

  it("does not mutate the draft", () => {
    const before = draft();
    applyTemplate(before, ln);
    expect(before.narrator).toBe("Thục Anh");
    expect(before.template).toBeUndefined();
  });

  it("keeps the current narrator when the template has none, or its voice is gone", () => {
    expect(applyTemplate(draft(), tienHiep).narrator).toBe("Thục Anh");
    expect(applyTemplate(draft(), ln, ["Thục Anh"]).narrator).toBe("Thục Anh");
    expect(applyTemplate(draft(), ln, ["Thục Anh", "Đức Trí"]).narrator).toBe("Đức Trí");
  });

  it("clears the model when the template uses the app default", () => {
    expect(applyTemplate(draft({ analysisModel: "other" }), tienHiep).analysisModel).toBe("");
  });
});

describe("isModified", () => {
  it("is false right after applying, true after any change of the four choices", () => {
    const applied = applyTemplate(draft(), ln);
    expect(isModified(applied, ln)).toBe(false);
    expect(isModified({ ...applied, narrator: "Thục Anh" }, ln)).toBe(true);
    expect(isModified({ ...applied, profile: "fast" }, ln)).toBe(true);
    expect(isModified({ ...applied, analysisModel: "" }, ln)).toBe(true);
    expect(isModified({ ...applied, startNow: true }, ln)).toBe(true);
  });

  it("ignores everything the template does not carry", () => {
    const applied = applyTemplate(draft(), ln);
    const other = { ...applied, title: "Khác", paths: [], firstPerson: "", dropCredits: false, limit: null };
    expect(isModified(other, ln)).toBe(false);
  });

  it("treats a missing model as the default, and ignores the narrator of a template without one", () => {
    const applied = applyTemplate(draft({ narrator: "Bất kỳ" }), tienHiep);
    expect(isModified({ ...applied, analysisModel: undefined }, tienHiep)).toBe(false);
    expect(isModified({ ...applied, narrator: "Giọng khác" }, tienHiep)).toBe(false);
  });
});

describe("templateFromDraft", () => {
  it("captures only the plain choices and trims the name", () => {
    const source = draft({ analysisModel: undefined });
    const saved = templateFromDraft(source, "  Tiên   hiệp ");
    expect(saved).toEqual({ name: "Tiên hiệp", narrator: "Thục Anh", profile: "high_quality", analysisModel: "", startNow: true });
    expect(Object.keys(saved).sort()).toEqual(["analysisModel", "name", "narrator", "profile", "startNow"]);
  });
});

describe("nameProblem", () => {
  it("accepts a fresh name and rejects empty, long, reserved and duplicate ones", () => {
    expect(nameProblem([ln], "Truyện Hàn")).toBe("");
    expect(nameProblem([ln], "   ")).not.toBe("");
    expect(nameProblem([ln], "x".repeat(41))).not.toBe("");
    expect(nameProblem([ln], "x".repeat(40))).toBe("");
    expect(nameProblem([ln], "mặc định")).not.toBe("");
    expect(nameProblem([ln], "LIGHT  novel")).not.toBe("");
  });

  it("does not count the template being renamed as a duplicate of itself", () => {
    expect(nameProblem([ln, tienHiep], "light NOVEL", "Light novel")).toBe("");
    expect(nameProblem([ln, tienHiep], "Tiên hiệp", "Light novel")).not.toBe("");
  });
});

describe("list helpers", () => {
  it("upsert replaces a same-name template in place (any case) and appends a new one", () => {
    const replaced = upsertTemplate([ln, tienHiep], { ...ln, name: "light novel", profile: "fast" });
    expect(replaced.map((item) => item.name)).toEqual(["light novel", "Tiên hiệp"]);
    expect(replaced[0].profile).toBe("fast");
    expect(upsertTemplate([ln], tienHiep).map((item) => item.name)).toEqual(["Light novel", "Tiên hiệp"]);
  });

  it("remove and rename keep the order; a bad rename changes nothing", () => {
    expect(removeTemplate([ln, tienHiep], "LIGHT NOVEL")).toEqual([tienHiep]);
    expect(renameTemplate([ln, tienHiep], "Light novel", " Truyện Nhật ").map((item) => item.name)).toEqual(["Truyện Nhật", "Tiên hiệp"]);
    expect(renameTemplate([ln, tienHiep], "Light novel", "Tiên hiệp")).toEqual([ln, tienHiep]);
  });

  it("is full at the limit", () => {
    const many = Array.from({ length: MAX_TEMPLATES }, (_, index) => ({ ...ln, name: `Mẫu ${index}` }));
    expect(isFull(many)).toBe(true);
    expect(isFull(many.slice(1))).toBe(false);
  });
});

describe("templatesOf", () => {
  it("survives missing or broken preference data", () => {
    expect(templatesOf(undefined)).toEqual([]);
    expect(templatesOf("x")).toEqual([]);
    expect(templatesOf([null, 3, { name: "A", profile: "ultra" }, { profile: "fast" }])).toEqual([]);
  });

  it("fills the optional fields", () => {
    expect(templatesOf([{ name: "A", profile: "fast" }])).toEqual([{ name: "A", narrator: "", profile: "fast", analysisModel: "", startNow: true }]);
  });
});
