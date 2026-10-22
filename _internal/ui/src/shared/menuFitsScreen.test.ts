import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Điện thoại thật (OPPO A93, 22-10): menu "…" trang sách 11 mục cao 515 px mở ở y=350 trên màn 763 px - hai mục cuối
// ("Xuất sách nói (M4B)…", "Xoá khỏi điện thoại…") nằm ngoài màn, không cuộn tới được. Mọi menu thả xuống phải tự giới hạn
// chiều cao theo chỗ còn trên màn và cuộn được bên trong.
const SRC = fileURLToPath(new URL("..", import.meta.url));

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return path.endsWith(".tsx") && !path.endsWith(".test.tsx") ? [path] : [];
  });
}

describe("menu thả xuống vừa màn hình", () => {
  it("mọi DropdownMenu.Content giới hạn chiều cao theo chỗ còn trên màn và cuộn được", () => {
    const offenders: string[] = [];
    for (const file of sources(SRC)) {
      const text = readFileSync(file, "utf-8");
      for (const match of text.matchAll(/<DropdownMenu\.Content\b[^>]*>/g)) {
        const tag = match[0];
        if (!tag.includes("--radix-dropdown-menu-content-available-height") || !tag.includes("overflow-y-auto")) {
          offenders.push(`${file.slice(SRC.length)}: ${tag.slice(0, 80)}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
