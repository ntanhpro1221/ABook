// Bảng màu "phòng nghe ấm" (DESIGN.md 5.1): mọi cặp chữ/nền đạt WCAG AA ở cả hai giao diện - 4,5:1 chữ thường, 3:1 cho --fg-3 (chỉ icon
// phụ / chữ lớn) và ranh giới điều khiển. Đọc thẳng styles.css, nên đổi một token là test này nói ngay.
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const css = readFileSync(new URL("../styles.css", import.meta.url), "utf8");

type Rgb = [number, number, number];
type Rgba = [number, number, number, number];

/** Khai báo `--x: ...;` của khối đầu tiên bắt đầu bằng `head`. */
function block(head: string): Record<string, string> {
  const start = css.indexOf(head);
  if (start < 0) throw new Error(`không thấy ${head}`);
  const body = css.slice(start, css.indexOf("\n}", start));
  const tokens: Record<string, string> = {};
  for (const match of body.matchAll(/^\s*(--[\w-]+):\s*([^;]+);/gm)) tokens[match[1]] ??= match[2].trim();
  return tokens;
}

function parse(value: string): Rgba {
  const hex = /^#([0-9a-f]{6})$/i.exec(value);
  if (hex) return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)).concat(1) as Rgba;
  const rgb = /^rgb\((\d+) (\d+) (\d+)(?: \/ ([\d.]+))?\)$/.exec(value);
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3]), rgb[4] === undefined ? 1 : Number(rgb[4])];
  throw new Error(`màu chưa hiểu: ${value}`);
}

const over = ([r, g, b, a]: Rgba, base: Rgb): Rgb => [r * a + base[0] * (1 - a), g * a + base[1] * (1 - a), b * a + base[2] * (1 - a)];

function luminance(rgb: Rgb): number {
  const [r, g, b] = rgb.map((c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const light = block(":root {");
const themes = { light, dark: { ...light, ...block('[data-theme="dark"] {') } };

// [chữ, [nền...], mức tối thiểu]. Nền trong suốt (rgb / a) tính chồng lên --bg.
const PAIRS: [string, string[], number][] = [
  ["--text", ["--bg", "--panel", "--bg-sunken", "--hover", "--accent-soft"], 4.5],
  ["--text-2", ["--bg", "--panel", "--bg-sunken", "--hover", "--accent-soft"], 4.5],
  ["--text-3", ["--bg", "--panel", "--bg-sunken", "--hover", "--accent-soft"], 4.5],
  ["--fg-3", ["--bg", "--panel", "--bg-sunken"], 3],
  ["--accent-ink", ["--accent", "--accent-hover"], 4.5],
  ["--accent-text", ["--bg", "--panel", "--bg-sunken", "--accent-soft"], 4.5],
  ["--success", ["--bg", "--panel", "--success-soft"], 4.5],
  ["--danger", ["--bg", "--panel", "--danger-soft"], 4.5],
  ["--control-line", ["--bg", "--panel", "--hover"], 3],
  ["--switch-off", ["--bg", "--panel"], 3],
  ["--focus", ["--bg", "--panel", "--hover", "--accent-soft"], 3],
];

for (const [name, tokens] of Object.entries(themes)) {
  const base = over(parse(tokens["--bg"]), [255, 255, 255]);
  const solid = (token: string): Rgb => over(parse(tokens[token]), base);
  for (const [fg, backgrounds, minimum] of PAIRS) {
    for (const bg of backgrounds) {
      it(`${name}: ${fg} trên ${bg} >= ${minimum}:1`, () => {
        expect(contrast(solid(fg), solid(bg))).toBeGreaterThanOrEqual(minimum);
      });
    }
  }
}

// Ba mặt đọc theo (+ "Tự động" của mỗi giao diện): mực, mực phụ, chữ nhấn trên nền mặt đọc.
const surfaces = {
  "tự động sáng": block(":root {\n  --read-bg"),
  "tự động tối": block('[data-theme="dark"] {\n  --read-bg'),
  giấy: block(':root[data-surface="paper"] {'),
  ngà: block(':root[data-surface="ivory"] {'),
  đêm: block(':root[data-surface="night"] {'),
};
for (const [name, tokens] of Object.entries(surfaces)) {
  for (const fg of ["--read-fg", "--read-fg-2", "--read-accent-text"]) {
    it(`mặt đọc ${name}: ${fg} >= 4.5:1`, () => {
      const bg = over(parse(tokens["--read-bg"]), [255, 255, 255]);
      expect(contrast(over(parse(tokens[fg]), bg), bg)).toBeGreaterThanOrEqual(4.5);
    });
  }
}

it("bảng trong DESIGN.md khớp styles.css", () => {
  const design = readFileSync(new URL("../../../docs/DESIGN.md", import.meta.url), "utf8");
  for (const token of ["--bg", "--panel", "--bg-sunken", "--line", "--text", "--text-2", "--text-3", "--fg-3", "--accent", "--accent-ink", "--accent-text", "--success-soft", "--warning", "--warning-soft", "--info-soft", "--focus", "--switch-off", "--switch-thumb"]) {
    const row = design.split("\n").find((line) => line.startsWith(`| \`${token}\``));
    expect(row, token).toBeDefined();
    expect(row, token).toContain(themes.light[token]);
    expect(row, token).toContain(themes.dark[token]);
  }
});
