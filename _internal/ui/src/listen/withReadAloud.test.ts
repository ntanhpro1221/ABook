import { describe, expect, it } from "vitest";
import type { ListenBook } from "./model";
import { withReadAloud, type ListenSource } from "./source";

// Thư viện không được chờ danh sách giọng (lõi đọc to khởi động, hỏi cả dịch vụ trực tuyến) khi không cuốn nào có chương chỉ-có-chữ:
// điện thoại mở app trống từng hiện skeleton cả chục giây trước "Chưa có sách" (soát UX a9).

function book(id: string, chapters?: ListenBook["chapters"]): ListenBook {
  return { id, chapters } as unknown as ListenBook;
}

function source(books: ListenBook[], voices: () => Promise<unknown[]>): ListenSource {
  return { kind: "android", library: async () => books, book: async (id: string) => books.find((item) => item.id === id)!, readAloudVoices: voices } as unknown as ListenSource;
}

describe("thư viện và danh sách giọng", () => {
  it("không hỏi giọng khi không cuốn nào có chương chỉ-có-chữ", async () => {
    let asked = 0;
    const wrapped = withReadAloud(source([book("a"), book("b", [])], async () => (asked++, [])));
    expect((await wrapped.library()).map((item) => item.id)).toEqual(["a", "b"]);
    expect(asked).toBe(0);
  });

  it("thư viện trống hiện ngay dù danh sách giọng không bao giờ về", async () => {
    const wrapped = withReadAloud(source([], () => new Promise(() => undefined)));
    expect(await wrapped.library()).toEqual([]);
  });

  it("có chương chỉ-có-chữ thì hỏi giọng và gắn speech", async () => {
    const text = book("t", [{ id: 1, state: "text" }] as ListenBook["chapters"]);
    const wrapped = withReadAloud(source([text], async () => [{ id: "v" }]));
    const [first] = await wrapped.library();
    expect(first.chapters?.[0].speech).toBe(true);
  });
});
