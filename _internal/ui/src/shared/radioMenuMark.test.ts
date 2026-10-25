import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

/** Mọi tệp .tsx của app (không test, không gallery). */
function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "gallery" ? [] : sources(path);
    return name.endsWith(".tsx") && !name.includes(".test.") ? [path] : [];
  });
}

// Danh sách chọn một (DESIGN 6, soát điện thoại 26-10: menu xếp Thư viện chỉ tô màu mục đang chọn): mục đang chọn có dấu chọn chung đứng đầu dòng,
// luôn giữ chỗ và mờ vào / ra - không chỉ đổi màu chữ, không ItemIndicator (gắn / gỡ cứng).
it("mọi DropdownMenu.RadioItem có SelectionMark, không dùng ItemIndicator", () => {
  const missing: string[] = [];
  for (const file of sources(fileURLToPath(new URL("..", import.meta.url)))) {
    const text = readFileSync(file, "utf8");
    if (text.includes("DropdownMenu.ItemIndicator")) missing.push(`${file}: ItemIndicator`);
    for (const match of text.matchAll(/<DropdownMenu\.RadioItem\b[\s\S]*?<\/DropdownMenu\.RadioItem>/g)) {
      if (!match[0].includes("<SelectionMark")) missing.push(`${file}: ${match[0].slice(0, 80)}`);
    }
  }
  expect(missing).toEqual([]);
});
