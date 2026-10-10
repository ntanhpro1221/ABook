import { describe, expect, it } from "vitest";
import { isOpenWork, waitingChanges, type WorkItem } from "./WorkInbox";

const card = (over: Partial<WorkItem>): WorkItem =>
  ({ kind: "speaker", key: "k", title: "", problem: "", affected: 1, doubt: 0, score: 0, options: [], current: "", examples: [], ...over }) as WorkItem;

describe("số thay đổi đang chờ áp dụng", () => {
  it("hai thẻ cùng quyết một câu là một thay đổi", () => {
    const lines = [{ stableId: "a1", textSha256: "x" }];
    const decided = [card({ key: "s", requested: "Lucien", current: "Heidi", lines }), card({ key: "v", kind: "vocative", requested: "Lucien", current: "Heidi", lines })];
    expect(waitingChanges(decided)).toBe(1);
  });

  it("giữ nguyên cách đang đọc không phải thay đổi; thẻ không có câu đếm theo thẻ", () => {
    const decided = [card({ key: "p", kind: "pronunciation", requested: "A", current: "A" }), card({ key: "q", kind: "pronunciation", requested: "B", current: "A" })];
    expect(waitingChanges(decided)).toBe(1);
  });
});

describe("việc còn chờ người duyệt (số trên nhãn tab)", () => {
  it("thẻ chỉ áp khi làm lại phân tích không đếm, như việc đã quyết (soát UX a23 B2)", () => {
    expect(isOpenWork(card({ redoOnly: true }))).toBe(false);
    expect(isOpenWork(card({ requested: "Nam" }))).toBe(false);
    expect(isOpenWork(card({}))).toBe(true);
  });
});
