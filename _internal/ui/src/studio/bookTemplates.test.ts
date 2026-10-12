import { describe, expect, it } from "vitest";
import {
  MAX_TEMPLATES,
  applyTemplate,
  changedChoices,
  isFull,
  isModified,
  missingModel,
  missingModelNote,
  missingVoice,
  missingVoiceNote,
  nameProblem,
  removeTemplate,
  renameTemplate,
  templateChoices,
  templateFromDraft,
  templatesOf,
  upsertTemplate,
  type BookTemplate,
  type Profile,
  type TemplateFields,
} from "./bookTemplates";

const ln: BookTemplate = { name: "Light novel", narrator: "Đức Trí", profile: "balanced", analysisModel: "qwen3:8b", startNow: false, precastWait: true };
const tienHiep: BookTemplate = { name: "Tiên hiệp", narrator: "", profile: "fast", analysisModel: "", startNow: true, precastWait: false };

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
    expect(after).toMatchObject({ narrator: "Đức Trí", profile: "balanced", analysisModel: "qwen3:8b", startNow: false, precastWait: true, template: "Light novel" });
    expect({ ...after, narrator: 0, profile: 0, analysisModel: 0, startNow: 0, precastWait: 0, template: 0 })
      .toEqual({ ...before, narrator: 0, profile: 0, analysisModel: 0, startNow: 0, precastWait: 0, template: 0 });
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
    expect(isModified({ ...applied, precastWait: false }, ln)).toBe(true);
    expect(isModified({ ...applyTemplate(draft(), tienHiep), precastWait: undefined }, tienHiep)).toBe(false);
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
    expect(saved).toEqual({ name: "Tiên hiệp", narrator: "Thục Anh", profile: "high_quality", analysisModel: "", startNow: true, precastWait: false });
    expect(Object.keys(saved).sort()).toEqual(["analysisModel", "name", "narrator", "precastWait", "profile", "startNow"]);
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
    expect(templatesOf([{ name: "A", profile: "fast" }])).toEqual([{ name: "A", narrator: "", profile: "fast", analysisModel: "", startNow: true, precastWait: false }]);
  });
});

describe("precastWait", () => {
  it("is captured from the draft, applied by the template and replaces the draft's own", () => {
    expect(templateFromDraft(draft({ precastWait: true }), "A").precastWait).toBe(true);
    expect(applyTemplate(draft({ precastWait: false }), ln).precastWait).toBe(true);
    expect(applyTemplate(draft({ precastWait: true }), tienHiep).precastWait).toBe(false);
  });

  it("is read back from preferences as off unless exactly true", () => {
    expect(templatesOf([{ name: "A", profile: "fast", precastWait: true }])[0].precastWait).toBe(true);
    expect(templatesOf([{ name: "A", profile: "fast", precastWait: "yes" }])[0].precastWait).toBe(false);
  });
});

describe("a template model the machine no longer has", () => {
  const installed = ["qwen3.5:9b", "qwen3:8b:latest"];

  it("is found only when the model list is known and lacks it", () => {
    expect(missingModel(ln, ["qwen3.5:9b"])).toBe("qwen3:8b");
    expect(missingModel(ln, installed)).toBe("");
    expect(missingModel({ analysisModel: "qwen3:8b:latest" }, ["qwen3:8b"])).toBe("");
    expect(missingModel(tienHiep, ["qwen3.5:9b"])).toBe("");
    expect(missingModel(ln, undefined)).toBe("");
    expect(missingModel(ln, [])).toBe("");
  });

  it("is not applied: the draft keeps its own model, everything else still follows the template", () => {
    const after = applyTemplate(draft({ analysisModel: "chosen:1b" }), ln, undefined, ["qwen3.5:9b"]);
    expect(after.analysisModel).toBe("chosen:1b");
    expect(after).toMatchObject({ profile: "balanced", startNow: false, precastWait: true, template: "Light novel" });
    expect(applyTemplate(draft(), ln, undefined, ["qwen3.5:9b"]).analysisModel).toBe("");
  });

  it("is applied when the model is installed, or when the list is unknown", () => {
    expect(applyTemplate(draft(), ln, undefined, installed).analysisModel).toBe("qwen3:8b");
    expect(applyTemplate(draft(), ln).analysisModel).toBe("qwen3:8b");
  });

  it("does not make the template look modified, and the note names the model", () => {
    const applied = applyTemplate(draft(), ln, undefined, ["qwen3.5:9b"]);
    expect(isModified(applied, ln)).toBe(true);
    expect(isModified(applied, ln, ["qwen3.5:9b"])).toBe(false);
    expect(missingModelNote("qwen3:8b:latest")).toBe("Model qwen3:8b trong mẫu không còn trên máy - giữ model đang chọn.");
  });
});

describe("a narrator the machine picks", () => {
  it("is saved as an empty narrator, not the name the machine happened to pick", () => {
    expect(templateFromDraft(draft({ narrator: "Ngọc Linh" }), "A", true).narrator).toBe("");
    expect(templateFromDraft(draft({ narrator: "Ngọc Linh" }), "A", false).narrator).toBe("Ngọc Linh");
  });

  it("puts the voice back to the machine's when applied, so the old voice is no longer highlighted", () => {
    expect(applyTemplate(draft({ narrator: "Bấm tay" }), tienHiep, undefined, undefined, "Ngọc Linh").narrator).toBe("Ngọc Linh");
    expect(applyTemplate(draft({ narrator: "Bấm tay" }), tienHiep).narrator).toBe("Bấm tay");
    expect(applyTemplate(draft({ narrator: "Bấm tay" }), ln, undefined, undefined, "Ngọc Linh").narrator).toBe("Đức Trí");
  });
});

describe("a template voice the machine no longer has", () => {
  it("is found only when the voice list is known and lacks it", () => {
    expect(missingVoice(ln, ["Thục Anh"])).toBe("Đức Trí");
    expect(missingVoice(ln, ["Đức Trí"])).toBe("");
    expect(missingVoice(tienHiep, ["Thục Anh"])).toBe("");
    expect(missingVoice(ln, undefined)).toBe("");
    expect(missingVoiceNote("Đức Trí")).toBe("Giọng Đức Trí trong mẫu không còn trên máy - giữ giọng đang chọn.");
  });
});

describe("what applying a template changed", () => {
  it("names only the choices the person had already made and the template overwrote", () => {
    const before = draft({ narrator: "Bấm tay", profile: "high_quality", startNow: true });
    const after = applyTemplate(before, ln);
    expect(changedChoices(before, after)).toEqual(["giọng kể", "chất lượng", "model đọc hiểu", "bắt đầu ngay", "chờ bạn duyệt trước khi thu"]);
    expect(changedChoices(after, applyTemplate(after, ln))).toEqual([]);
  });

  it("is enough to put the previous choices back", () => {
    const before = draft({ narrator: "Bấm tay", analysisModel: "qwen3:8b" });
    const after = applyTemplate(before, tienHiep);
    expect({ ...after, ...templateChoices(before) }).toEqual({ ...before, analysisModel: "qwen3:8b", precastWait: false, template: undefined });
  });
});
