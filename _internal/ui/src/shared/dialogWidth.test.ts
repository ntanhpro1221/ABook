import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

// DESIGN §6: hộp giữa màn máy tính rộng ≤ 560. audit140 V9: chín hộp rộng 576-768 (max-w-xl/2xl/3xl), tìm ảnh bìa 768 đè hộp Sửa sách 576.
const TAILWIND: Record<string, number> = { xs: 320, sm: 384, md: 448, lg: 512, xl: 576, "2xl": 672, "3xl": 768, "4xl": 896, "5xl": 1024 };
const src = fileURLToPath(new URL("..", import.meta.url));
const files = (dir: string): string[] => readdirSync(dir).flatMap((name) => {
  const path = join(dir, name);
  return statSync(path).isDirectory() ? files(path) : /\.tsx$/.test(name) && !/\.test\.tsx$/.test(name) ? [path] : [];
});

it("mọi hộp thoại máy tính rộng không quá 560 px", () => {
  const wide = files(src).flatMap((path) => [...readFileSync(path, "utf8").matchAll(/width="max-w-(\[(\d+)px\]|[a-z0-9]+)"/g)]
    .map((match) => ({ at: `${path.slice(src.length)} ${match[0]}`, px: match[2] ? Number(match[2]) : TAILWIND[match[1]] ?? Infinity }))
    .filter(({ px }) => px > 560));
  expect(wide.map(({ at }) => at)).toEqual([]);
});
