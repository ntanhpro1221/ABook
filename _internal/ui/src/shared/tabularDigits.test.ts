// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Luật R2 (soát thiết kế 10-11, DESIGN.md 5.5): chữ số đều độ rộng làm "1" hở hai bên ("1 , 1 5×", "- 1 8 dB"). Chỉ dùng cho giá trị tự đổi tại chỗ
 * (TickingValue / data-motion-live, styles.css) và ô cột số của bảng (`.tabular-cell`, chỉ ở các file có tên dưới đây). Lớp `tabular` / `tabular-nums`
 * và `font-variant-numeric` viết tay bị cấm: chúng gắn số đều vào chữ chạy.
 */
const root = fileURLToPath(new URL("..", import.meta.url));
const CELLS: Record<string, string> = {
  "shared/ChapterPreview.tsx": "cột số thứ tự và số chữ của bảng chương",
  "studio/NewProjectScreen.tsx": "cột số thứ tự và số chữ của bảng tệp",
  "studio/ProjectScreen.tsx": "cột số chương, độ dài, đã xong của bảng chương; cột giờ nhật ký",
  "studio/ProjectsScreen.tsx": "cột 'cập nhật' của bảng dự án",
  "studio/MusicTab.tsx": "cột thời điểm của bảng cảnh nhạc",
};
const FORBIDDEN = /(?<![\w-])tabular(?:-nums)?(?![\w-])|fontVariantNumeric|font-variant-numeric|\[font-variant/;
const CELL = /(?<![\w-])tabular-cell(?![\w-])/;

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap(entry => statSync(join(dir, entry)).isDirectory()
    ? sources(join(dir, entry)) : /\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry) ? [join(dir, entry)] : []);
}

function offenders(name: string, source: string): string[] {
  return source.split("\n").flatMap((line, index) => {
    const code = line.replace(/\/\/.*$|\{\/\*.*?\*\/\}/g, "");
    if (FORBIDDEN.test(code)) return [`${name}:${index + 1}: ${line.trim().slice(0, 100)}`];
    if (CELL.test(code) && !(name in CELLS)) return [`${name}:${index + 1}: tabular-cell ngoài bảng có tên`];
    return [];
  });
}

describe("chữ số đều chỉ ở giá trị tự đổi và cột số của bảng", () => {
  it("không chỗ nào gắn số đều vào chữ chạy", () => {
    const found = sources(root).flatMap(path => offenders(path.slice(root.length).replaceAll("\\", "/"), readFileSync(path, "utf8")));
    expect(found).toEqual([]);
  });
  it("mỗi file có tên vẫn còn ô cột số", () => {
    for (const name of Object.keys(CELLS)) expect(CELL.test(readFileSync(join(root, name), "utf8")), name).toBe(true);
  });
  it("styles.css chỉ cho số đều qua ba cửa", () => {
    const css = readFileSync(join(root, "styles.css"), "utf8");
    const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(match => /font-variant-numeric:\s*tabular-nums/.test(match[2]))
      .map(match => match[1].replace(/\/\*[\s\S]*?\*\//g, "").trim());
    expect(rules).toEqual([".tabular-cell, .ticking-value, [data-motion-live]"]);
  });
  it("bắt lớp tabular, tabular-nums và style viết tay; bỏ qua chú thích", () => {
    expect(offenders("listen/X.tsx", '<span className="tabular text-xs">')).toHaveLength(1);
    expect(offenders("listen/X.tsx", 'cn("a tabular-nums", b)')).toHaveLength(1);
    expect(offenders("listen/X.tsx", 'style={{ fontVariantNumeric: "tabular-nums" }}')).toHaveLength(1);
    expect(offenders("listen/X.tsx", '<span className="tabular-cell">')).toHaveLength(1);
    expect(offenders("studio/ProjectsScreen.tsx", '<span className="tabular-cell">')).toEqual([]);
    expect(offenders("listen/X.tsx", "// không tabular ở đây\nconst tabularData = 1;")).toEqual([]);
  });
});
