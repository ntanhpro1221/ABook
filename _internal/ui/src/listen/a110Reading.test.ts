import { afterEach, expect, it, vi } from "vitest";
import type { ListenBook, ListenChapter } from "./model";
import { latestReading, localReading, nextReadingRevision, newerReading, readingKey } from "./readingPosition";
import malformed from "../../../tests/fixtures/listening_revision/malformed.json";
import { bookProgress } from "@/android/progress";

afterEach(() => vi.unstubAllGlobals());

for (const row of malformed) it(`revision local: ${row.name}`, () => {
  const place = { chapterId: 1, index: 100, at: 200, rev: row.rev };
  vi.stubGlobal("localStorage", { getItem: () => JSON.stringify(place) });
  const local = localReading("b", "default");
  expect(local?.index).toBe(100);
  expect(local?.rev).toEqual(row.valid ? row.rev : undefined);
  const next = nextReadingRevision(undefined, local);
  expect(Number.isSafeInteger(next.counter)).toBe(true);
  expect(next.counter).toBeLessThanOrEqual(2 ** 40);
});

it("counter chạm trần tạo epoch mới, vẫn mới hơn bản trước", () => {
  const local = { chapterId: 1, index: 100, at: 200, rev: { counter: 2 ** 40, node: "reader" } };
  const next = nextReadingRevision(undefined, local);
  expect(next).toMatchObject({ epoch: "1", counter: 1 });
  expect(newerReading({ ...local, rev: next }, local)).toBe(true);
});

it("epoch có thể đổi tiếp mà không vướng một trần số thứ hai", () => {
  const local = { chapterId: 1, index: 100, at: 100, rev: { epoch: "111", counter: 2 ** 40, node: "reader" } };
  expect(nextReadingRevision(undefined, local)).toMatchObject({ epoch: "1111", counter: 1 });
});

it("revision hỏng của bản đang chờ gửi: giữ vị trí và tạo revision sau backend", () => {
  vi.stubGlobal("localStorage", { getItem: () => JSON.stringify({ chapterId: 1, index: 100, at: 200, pending: true, rev: { counter: 1e100, node: "peer" } }) });
  const book = { id: "b", chapters: [{ id: 1 }], state: { _clock: 2, reading: { chapterId: 1, index: 10, at: 100, rev: { counter: 2, node: "server" } } } } as unknown as ListenBook;
  expect(latestReading(book)).toMatchObject({ index: 100, rev: { counter: 3 } });
});

it("đồng hồ chỉnh lùi: bản local mới hơn vẫn dùng được khi chưa gửi xong", () => {
  const local = { chapterId: 1, index: 100, at: 100, pending: true, rev: { counter: 2, node: "reader" } };
  const book = { id: "b", chapters: [{ id: 1 }], state: { reading: { chapterId: 1, index: 10, at: 200, rev: { counter: 1, node: "reader" } } } } as unknown as ListenBook;
  vi.stubGlobal("localStorage", { getItem: (key: string) => key === readingKey("b", "default") ? JSON.stringify(local) : null });
  expect(latestReading(book)?.index).toBe(100);
});

it("bản đã đồng bộ mới hơn thắng bản dự phòng có giờ tương lai", () => {
  const local = { chapterId: 1, index: 10, at: 200, pending: false, rev: { counter: 1, node: "reader" } };
  const book = { id: "b", chapters: [{ id: 1 }], state: { reading: { chapterId: 1, index: 100, at: 100, rev: { counter: 2, node: "phone" } } } } as unknown as ListenBook;
  vi.stubGlobal("localStorage", { getItem: () => JSON.stringify(local) });
  expect(latestReading(book)?.index).toBe(100);
});

it("nghe lại sau khi chỉnh giờ lùi không bị kẹt ở đã nghe xong", () => {
  const state = { chapters: {}, bookmarks: [], finished: true, finishedAt: 200, _fieldRevs: { finished: { counter: 1, node: "desktop" } },
    last: { chapterId: 1, seconds: 10, at: 100, rev: { counter: 2, node: "desktop" } } };
  expect(bookProgress(state, [{ id: 1, duration: 1000 } as ListenChapter]).rewound).toBe(true);
});
