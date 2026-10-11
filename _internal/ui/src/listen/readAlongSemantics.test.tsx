import { renderToString } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";
import type { Script } from "./model";

// Soát a31 A5: mỗi câu của trình đọc chương là <span role="button"> - chương 22.000 câu thành 22.000 "nút", trình đọc màn hình đọc "nút"
// trước từng câu. Giờ: đoạn là <p>, câu là chữ thường; một câu nhận Tab (mũi tên đi tiếp) và mang lời chỉ cách dùng phím.

beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

const segment = (id: number, paragraph: number, text: string, kind = "narration") =>
  ({ id, paragraph, text, kind, speaker: "", start: id, end: id + 1, status: "verified" });
const script: Script = {
  chapterId: 1,
  title: "Chương 1",
  timed: true,
  duration: 6,
  segments: [segment(0, 0, "Chương 1", "heading"), segment(1, 1, "Câu một."), segment(2, 1, "Câu hai."), segment(3, 2, "Câu ba.")],
};

describe("trình đọc chương", () => {
  it("câu không là nút; đoạn là <p>; chỉ câu đang chọn nhận Tab và có lời chỉ phím", async () => {
    const { ReadAlongText } = await import("./ReadAlongText");
    const html = renderToString(<ReadAlongText script={script} playingIndex={-1} focusIndex={2} onTap={() => undefined} headingClassName="" />);
    expect(html).not.toContain('role="button"');
    expect(html.match(/<p class="text-pretty">/g)).toHaveLength(2);
    expect(html.match(/tabindex="0"/g)).toHaveLength(1);
    const stop = html.match(/<span[^>]*tabindex="0"[^>]*>/)?.[0] ?? "";
    expect(stop).toContain('data-index="2"');
    const hint = stop.match(/aria-describedby="([^"]+)"/)?.[1];
    expect(hint).toBeTruthy();
    expect(html).toContain(`id="${hint}" class="sr-only">Mũi tên lên, xuống`);
  });

  it("không bấm được (không có onTap) thì không có lời chỉ phím", async () => {
    const { ReadAlongText } = await import("./ReadAlongText");
    const html = renderToString(<ReadAlongText script={script} playingIndex={-1} focusIndex={1} headingClassName="" />);
    expect(html).not.toContain("aria-describedby");
    expect(html).not.toContain("sr-only");
  });
});
