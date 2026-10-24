import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

// Các màu chữ đang dùng trên màn mới phải đạt AA ở cả hai chủ đề.
const css = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
function luminance(hex: string) {
  const rgb = hex.match(/[a-f\d]{2}/gi)!.map(value => parseInt(value, 16) / 255)
    .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
}
for (const theme of ["light", "dark"]) it(`mực, nguồn sách, trạng thái và nút chính đủ tương phản: ${theme}`, () => {
  const block = css.match(theme === "light" ? /:root\s*\{([^}]+)\}/ : /\[data-theme="dark"\]\s*\{([^}]+)\}/)![1];
  const tokens = Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[a-f\d]{6})/gi)].map(match => [match[1], match[2]]));
  const ratio = (a: string, b: string) => {
    const values = [luminance(tokens[a]), luminance(tokens[b])].sort((a, b) => b - a);
    return (values[0] + .05) / (values[1] + .05);
  };
  for (const ink of ["text", "text-2", "accent-text", "success", "danger"]) {
    for (const background of ["bg", "panel"]) expect(ratio(ink, background), `${ink}/${background}`).toBeGreaterThanOrEqual(4.5);
  }
  expect(ratio("accent-ink", "accent")).toBeGreaterThanOrEqual(4.5);
});
