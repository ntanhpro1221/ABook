import { describe, expect, it } from "vitest";
import { applyWhen } from "@/studio/decisions";
import {
  canReview,
  castItems,
  chapterRange,
  freeNote,
  isOpenWork,
  lineCount,
  lineItems,
  nameItems,
  precastInvites,
  precastKeys,
  type WorkItemLike,
} from "@/studio/precast";

const item = (kind: string, key: string, extra: Partial<WorkItemLike> = {}): WorkItemLike => ({
  kind,
  key,
  affected: 1,
  doubt: 0.5,
  ...extra,
});

describe("chọn thẻ cho từng bước", () => {
  const items = [
    item("speaker", "s1", { chapters: [1], affected: 1 }),
    item("turn", "t9", { chapters: [9], affected: 4 }),
    item("turn", "t2", { chapters: [2, 3], affected: 3 }),
    item("gender", "g", { chapters: [1, 9] }),
    item("alias", "a", { requested: "Gộp vào Krai" }),
    item("pronunciation", "p-sure", { doubt: 0.12, affected: 40 }),
    item("pronunciation", "p-unsure", { doubt: 0.5, affected: 2 }),
    item("pronunciation", "p-unsure-more", { doubt: 0.5, affected: 9 }),
    item("audio", "audio:1", { chapters: [1] }),
  ];

  it("bước nhân vật: giới, bí danh, chung giọng còn chờ quyết", () => {
    expect(castItems(items).map((entry) => entry.key)).toEqual(["g"]);
  });

  it("bước cách đọc tên: tên máy kém chắc trước, cùng mức thì tên nhiều câu trước", () => {
    expect(nameItems(items).map((entry) => entry.key)).toEqual(["p-unsure-more", "p-unsure", "p-sure"]);
  });

  it("bước ai nói: chỉ thẻ chạm các chương sắp thu, đếm số câu", () => {
    const lines = lineItems(items, [1, 2, 3]);
    expect(lines.map((entry) => entry.key)).toEqual(["s1", "t2"]);
    expect(lineCount(lines)).toBe(4);
    expect(lineItems(items, [])).toEqual([]);
  });
});

describe("lời trên màn", () => {
  it("dải chương sắp thu", () => {
    expect(chapterRange([])).toBe("");
    expect(chapterRange([{ title: "Chương 1" }])).toBe("Chương 1");
    expect(chapterRange([{ title: "Chương 1" }, { title: "Chương 2" }, { title: "Chương 3" }])).toBe("Chương 1 → Chương 3");
  });

  it("nói sửa tới đâu thì không phải thu lại", () => {
    expect(freeNote({ recordedThrough: null })).toContain("không phải thu lại câu nào");
    expect(freeNote({ recordedThrough: { id: 4, title: "Chương 4" } })).toContain("Đã thu tới Chương 4 - sửa ở chương sau đó không phải thu lại");
  });
});

describe("lời mời duyệt", () => {
  const book = (id: string, extra: Record<string, unknown> = {}) =>
    ({
      id,
      phase: "synthesis",
      chapters: { total: 10, completed: 0, failed: 0, working: 0 },
      precast: { ready: true, wait: false, announcedAt: 100, held: false },
      ...extra,
    }) as Parameters<typeof precastInvites>[0][number];

  it("mời một lần cho mỗi mốc Studio báo", () => {
    expect(precastInvites([book("a")], () => null).map((entry) => entry.id)).toEqual(["a"]);
    expect(precastInvites([book("a")], () => "100")).toEqual([]);
  });

  it("không mời khi đã thu chương rồi - trừ khi sách đang chờ duyệt", () => {
    const recording = { chapters: { total: 10, completed: 2, failed: 0, working: 1 } };
    expect(precastInvites([book("a", recording)], () => null)).toEqual([]);
    const held = { ...recording, precast: { ready: true, wait: true, announcedAt: 100, held: true } };
    expect(precastInvites([book("a", held)], () => null)).toHaveLength(1);
  });

  it("không mời khi chưa báo mốc hay sách đã xong", () => {
    expect(precastInvites([book("a", { precast: { ready: true, wait: false, announcedAt: null, held: false } })], () => null)).toEqual([]);
    expect(precastInvites([book("a", { phase: "done" })], () => null)).toEqual([]);
    expect(canReview({ phase: "analysis", precast: { ready: false, wait: false, announcedAt: null, held: false } })).toBe(false);
  });
});

describe("sửa lúc duyệt trước khi thu áp khi nào", () => {
  it("phân vai đã khoá thì không còn 'chờ phân vai xong'", () => {
    const book = { phase: "casting" as const, running: true, starting: false, paused: "listener" as const };
    expect(applyWhen({ ...book, castLocked: false })).toBe("cast");
    expect(applyWhen({ ...book, castLocked: true })).toBe("paused");
    expect(applyWhen({ ...book, paused: null, castLocked: true })).toBe("running");
  });
});

describe("số việc ở hai tab cộng lại đúng số điện thoại nhận (soát UX a24, A7)", () => {
  it("thẻ ở màn duyệt không đếm lại ở Việc cần duyệt, thẻ đã quyết / chỉ áp khi làm lại không đếm ở đâu", () => {
    const items = [
      item("speaker", "s1", { chapters: [1] }),
      item("turn", "t9", { chapters: [9] }),
      item("shared-voice", "v"),
      item("shared-voice", "v-done", { requested: "Giữ nguyên" }),
      item("pronunciation", "p"),
      item("narrator", "n", { redoOnly: true }),
      item("speaker", "s-redo", { chapters: [1], redoOnly: true }),
      item("audio", "w"),
    ];
    const inPrecast = precastKeys(items, [1, 2]);
    expect([...inPrecast].sort()).toEqual(["p", "s1", "v"]);
    const workTab = items.filter((card) => isOpenWork(card) && !inPrecast.has(card.key)).length;
    // Con số điện thoại = work_items.open_count = mọi thẻ isOpenWork.
    expect(inPrecast.size + workTab).toBe(items.filter(isOpenWork).length);
    expect(workTab).toBe(2);
  });
});
