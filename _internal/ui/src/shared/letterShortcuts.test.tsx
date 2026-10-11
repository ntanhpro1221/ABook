import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import { ShortcutList } from "@/listen/Shortcuts";
import { letterShortcutsOn, setLetterShortcuts } from "./letterShortcuts";

// WCAG 2.1.4 (soát a31): phím tắt một chữ cái tắt được ở Cài đặt › Phím tắt; hộp Phím tắt nói rõ phím nào đang tắt.

afterEach(() => setLetterShortcuts(true));

describe("phím tắt một chữ cái", () => {
  it("mặc định bật, như trước", () => {
    expect(letterShortcutsOn()).toBe(true);
    const html = renderToString(<ShortcutList />);
    expect(html).not.toContain("đang tắt");
    expect(html).toContain("tắt được ở Cài đặt › Phím tắt");
  });

  it("tắt: bộ bắt phím đọc cờ lúc có phím, hộp Phím tắt đánh dấu B / M / [ ] / ? là đang tắt", () => {
    setLetterShortcuts(false);
    expect(letterShortcutsOn()).toBe(false);
    const html = renderToString(<ShortcutList />);
    expect(html.match(/\(đang tắt\)/g)).toHaveLength(4);
    expect(html).toContain("Space, mũi tên và Esc vẫn dùng được");
  });
});
