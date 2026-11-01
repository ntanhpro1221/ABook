import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { expect, it } from "vitest";
import { AutoPickNote } from "./AutoPickNote";
import type { LocalTrack } from "./musicLocal";

// 01-11: nhãn ("", "Có lời", "Chưa phân tích") đứng TRƯỚC công tắc nên mỗi hàng bài nhạc đặt "Tự chọn" ở một x. Công tắc phải đứng đầu dòng.

function html(track: Partial<LocalTrack>, canOverride = true) {
  const full = { link: "local:" + "a1".repeat(20), title: "Bài", ...track } as LocalTrack;
  return renderToString(<QueryClientProvider client={new QueryClient()}><AutoPickNote track={full} canOverride={canOverride} onView={() => undefined} /></QueryClientProvider>);
}

it.each([
  [{ analysed: false }, "Chưa phân tích"],
  [{ analysed: true, vocalsLikely: true }, "Có lời"],
])("the Tự chọn switch comes before the note %#, so it sits in one column on every row", (track, note) => {
  const out = html(track);
  expect(out).toContain(note);
  expect(out.indexOf('role="switch"')).toBeGreaterThan(-1);
  expect(out.indexOf('role="switch"')).toBeLessThan(out.indexOf(note));
});

it("a row with no note still starts with the switch; without the switch only the note shows", () => {
  expect(html({ analysed: true })).toContain('role="switch"');
  const phone = html({ analysed: false }, false);
  expect(phone).not.toContain('role="switch"');
  expect(phone).toContain("Chưa phân tích");
});
