import { describe, expect, it } from "vitest";
import type { ListenChapter, ListeningState } from "@/listen/model";
import { bookProgress } from "./progress";

const chapters = [
  { id: 1, duration: 600 },
  { id: 2, duration: 600 },
] as ListenChapter[];
const done = { "1": { heard: 600, done: true }, "2": { heard: 600, done: true } } as unknown as ListeningState["chapters"];
const state = (extra: Partial<ListeningState>): ListeningState => ({ chapters: done, bookmarks: [], ...extra });

describe("bookProgress", () => {
  it("nghe hết rồi quay lại nghe chương 1: đang nghe lại, tiến độ theo chỗ đang nghe", () => {
    const again = bookProgress(state({ last: { chapterId: 1, seconds: 164.8, at: 500 } }), chapters);
    expect(again.finished).toBe(false);
    expect(again.rewound).toBe(true);
    expect(again.heardSeconds).toBeCloseTo(164.8);
    expect(bookProgress(state({ last: { chapterId: 2, seconds: 300, at: 500 } }), chapters, false)).toMatchObject({ heardSeconds: 900, caughtUp: false });
  });

  it("dừng ở đuôi chương cuối, hay tự đánh dấu nghe xong sau lần nghe ấy, vẫn là nghe xong", () => {
    expect(bookProgress(state({ last: { chapterId: 2, seconds: 595, at: 500 } }), chapters).finished).toBe(true);
    expect(bookProgress(state({ last: { chapterId: 1, seconds: 30, at: 500 }, finished: true, finishedAt: 600 }), chapters).finished).toBe(true);
    expect(bookProgress(state({ last: { chapterId: 1, seconds: 30, at: 500 }, finished: true, finishedAt: 400 }), chapters).finished).toBe(false);
  });
});
