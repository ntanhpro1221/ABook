import { describe, expect, it } from "vitest";
import type { ListenChapter, ListeningState } from "@/listen/model";
import { bookProgress, textBookProgress } from "./progress";

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

describe("textBookProgress", () => {
  const text = [{ id: 1, duration: 0 }, { id: 2, duration: 0 }, { id: 3, duration: 0 }, { id: 4, duration: 0 }] as ListenChapter[];
  const record = (chapters: Record<string, unknown>) => ({ chapters, bookmarks: [] }) as unknown as ListeningState;

  it("sách chữ chưa nghe gì: 0; nghe xong chương và đang đọc dở chương kế: có tiến độ theo chương", () => {
    expect(textBookProgress(record({}), text).fraction).toBe(0);
    const some = textBookProgress(record({ "1": { heard: 300, done: true }, "2": { heard: 100, done: false, duration: 400 } }), text);
    expect(some.fraction).toBeCloseTo((1 + 0.25) / 4);
    expect(some.chaptersDone).toBe(1);
    expect(some.finished).toBe(false);
  });

  it("nghe xong mọi chương hay tự đánh dấu nghe xong là đầy; không vượt 1", () => {
    const all = Object.fromEntries(text.map((chapter) => [String(chapter.id), { heard: 10, done: true }]));
    expect(textBookProgress(record(all), text)).toMatchObject({ fraction: 1, finished: true });
    expect(textBookProgress({ ...record({}), finished: true }, text)).toMatchObject({ fraction: 1, finished: true });
    expect(textBookProgress(record({ "1": { heard: 900, done: false, duration: 400 } }), text).fraction).toBeCloseTo(0.25);
  });
});
