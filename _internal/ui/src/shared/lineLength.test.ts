import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

// DESIGN 5.5 / 7: chữ đọc ≤ 68 ký tự mỗi dòng. `ch` là bề rộng chữ số "0" (≈ 0,615 em) nên `68ch` ra 87-90 ký tự thật (soát 25-10); bề rộng đo bằng em.
// Chữ Việt có dấu cách trung bình ≈ 0,46 em mỗi ký tự (đo thật: 33 em ra 71 ký tự).
const AVERAGE_EM_PER_CHAR = 0.46;
const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

it("lớp `measure` giữ dòng chữ đọc dưới 68 ký tự thật", () => {
  const width = Number(/@utility measure \{\s*max-width: ([\d.]+)em;/.exec(read("../styles.css"))?.[1]);
  expect(width).toBeGreaterThan(0);
  expect(width / AVERAGE_EM_PER_CHAR).toBeLessThanOrEqual(68);
  expect(width / AVERAGE_EM_PER_CHAR).toBeGreaterThan(60);
});

it("cột chữ của màn đọc đo bằng em (cùng cỡ chữ người đọc chọn), không bằng ch", () => {
  const reader = read("../listen/ReaderScreen.tsx");
  expect(reader).not.toMatch(/max-w-\[[^\]]*\dch/);
  const columns = [...reader.matchAll(/max-w-\[calc\(([\d.]+)em\+\d+px\)\]/g)].map((match) => Number(match[1]));
  expect(columns.length).toBeGreaterThan(0);
  for (const width of columns) expect(width / AVERAGE_EM_PER_CHAR).toBeLessThanOrEqual(68);
});

it("không chỗ nào của giao diện đặt độ rộng chữ bằng 68ch", () => {
  for (const file of ["../listen/ReaderScreen.tsx", "../listen/PlayerViews.tsx", "../shared/ui.tsx"]) expect(read(file)).not.toMatch(/\b6[0-9]ch\b/);
});
