// @vitest-environment node
// Soát chuyển động 139 (docs/reviews/motion139.md): quét mã tìm lại các LOẠI lỗi đã sửa, để chỗ mới viết không mắc lại. Chỉ những mẫu ít báo nhầm.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = fileURLToPath(new URL("..", import.meta.url));

function sources(dir: string, ext: RegExp): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path, ext);
    return ext.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : [];
  });
}

const lineOf = (text: string, index: number) => text.slice(0, index).split("\n").length;

describe("luật chuyển động (DESIGN nguyên tắc 6, mục 5.2)", () => {
  it("lỗi / trạng thái rỗng không bật tắt bằng `{điều kiện && <InlineError|LoadError|EmptyState>}`: truyền `open` hay bọc MotionPresence", () => {
    // Đổi bước trong một vùng MotionRegion (mỗi bước một nhánh `bước === … &&`): vùng đã mờ qua cả khối.
    const allowed = [/step === "done" && \(\s*<EmptyState/];
    const offenders: string[] = [];
    for (const file of sources(SRC, /\.tsx$/)) {
      const text = readFileSync(file, "utf-8");
      for (const match of text.matchAll(/&&\s*\(?\s*<(InlineError|LoadError|EmptyState)\b/g)) {
        const around = text.slice(Math.max(0, match.index - 40), match.index + match[0].length);
        if (allowed.some((rule) => rule.test(around))) continue;
        offenders.push(`${file.slice(SRC.length)}:${lineOf(text, match.index)} ${match[0].replace(/\s+/g, " ")}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("không đường cong vượt đích: mọi cubic-bezier giữ tung độ trong [0, 1] (không nảy, không vượt đích)", () => {
    const offenders: string[] = [];
    for (const file of sources(SRC, /\.(css|tsx?)$/)) {
      const text = readFileSync(file, "utf-8");
      for (const match of text.matchAll(/cubic-bezier\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)/g)) {
        const [y1, y2] = [Number(match[2]), Number(match[4])];
        if (y1 < 0 || y1 > 1 || y2 < 0 || y2 > 1) offenders.push(`${file.slice(SRC.length)}:${lineOf(text, match.index)} ${match[0]}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("dấu chọn không đổi `invisible` theo trạng thái (ẩn cứng): luôn dựng, đổi độ mờ có transition", () => {
    const offenders: string[] = [];
    for (const file of sources(SRC, /\.tsx$/)) {
      const text = readFileSync(file, "utf-8");
      for (const match of text.matchAll(/\?\s*"[^"]*"\s*:\s*"invisible"|\?\s*"invisible"\s*:/g)) offenders.push(`${file.slice(SRC.length)}:${lineOf(text, match.index)}`);
    }
    expect(offenders).toEqual([]);
  });
});
