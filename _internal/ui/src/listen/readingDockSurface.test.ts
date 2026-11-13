import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

// Dải neo cuối vùng Đọc theo (nút "Tới câu đang nghe" / thanh việc của câu) nằm ngay dưới chữ, nên nền của nó phải là nền MẶT ĐỌC (`--read-bg`, đổi theo
// Giấy / Ngà / Đêm) - đúng màu mà hai mép mờ phía trên nó cũng dùng. Tô `bg-bg` (nền chung của app) thì thành một mảng khác màu dưới chữ: soát điện thoại
// thật 13-11 thấy khối đen ở bản Android (NowPlayingSurfaceRulesTest.kt giữ luật bên đó).
const SRC = fileURLToPath(new URL("..", import.meta.url));
const FILES = ["listen/PlayerViews.tsx", "listen/ReaderScreen.tsx"];

function docks(text: string): string[] {
  return [...text.matchAll(/<[A-Za-z.]+[^>]*\bdata-reading-dock\b[^>]*>/g)].map((match) => match[0]);
}

it("every reading dock is painted with the reading surface, not the app ground", () => {
  const found = FILES.flatMap((file) => docks(readFileSync(SRC + file, "utf8")).map((tag) => ({ file, tag })));
  expect(found.length).toBe(FILES.length);
  for (const { file, tag } of found) {
    expect(`${file}: ${tag}`).toMatch(/bg-\[var\(--read-bg\)\]/);
    expect(`${file}: ${tag}`).not.toMatch(/\bbg-bg\b/);
  }
});

it("the rule catches a dock on the app ground", () => {
  const planted = '<div data-reading-dock className="flex h-12 shrink-0 bg-bg">';
  expect(docks(planted)).toHaveLength(1);
  expect(docks(planted)[0]).toMatch(/\bbg-bg\b/);
});
