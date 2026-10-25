import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const src = fileURLToPath(new URL("..", import.meta.url));
const files = (dir: string): string[] => readdirSync(dir).flatMap(name => {
  const path = join(dir, name);
  return statSync(path).isDirectory() ? files(path) : /\.tsx$/.test(name) && !/\.test\.tsx$/.test(name) ? [path] : [];
});

it("Select là nơi duy nhất dựng select gốc", () => {
  const raw = files(src).flatMap(path => [...readFileSync(path, "utf8").matchAll(/<select\b/g)].map(() => path.slice(src.length)));
  expect(raw).toEqual([join("shared", "ui.tsx")]);
});

// Chỉ chip, dấu tìm chữ, ô icon và đích thả file dùng nền nhấn. Thêm nền ở hàng / menu / panel phải làm test này đỏ.
const allowedSoft = (line: string) => {
  const prefix = line.slice(0, line.indexOf("bg-accent-soft"));
  const tag = [...prefix.matchAll(/<([a-z][\w-]*)\b/g)].at(-1)?.[1];
  return (tag === "span" || tag === "mark") && !/role=["'](?:row|option|listitem)/.test(line)
    || /grid size-\d+ (?:shrink-0 )?place-items-center/.test(line)
    || /accent: "bg-accent-soft/.test(line) || /dragging \? "border-accent bg-accent-soft/.test(line)
    || /border-dashed border-accent bg-accent-soft/.test(line);
};
it("hàng chọn không tô nền hổ phách, kể cả qua CSS", () => {
  const bad = files(src).flatMap(path => readFileSync(path, "utf8").split("\n").flatMap((line, index) =>
    line.includes("bg-accent-soft") && !allowedSoft(line) ? [`${path.slice(src.length)}:${index + 1}`] : []));
  expect(bad).toEqual([]);
  const css = readFileSync(join(src, "styles.css"), "utf8");
  expect(css).not.toMatch(/\[data-(?:sheet-current|selected|current)[^\]]*\][^{]*\{[^}]*background[^}]*accent-soft/);
  expect(allowedSoft('selected ? "bg-accent-soft" : "hover:bg-hover"')).toBe(false);
  expect(allowedSoft('<li className="bg-accent-soft">')).toBe(false);
  expect(allowedSoft('<li className="bg-accent-soft"><span>Tên</span></li>')).toBe(false);
  expect(allowedSoft('<span role="option" className="bg-accent-soft">Tên</span>')).toBe(false);
});

it("chân hộp dùng DialogActions thay vì tự bố trí", () => {
  const raw = files(src).filter(path => !path.endsWith(join("shared", "ui.tsx")))
    .filter(path => /className="[^"]*dialog-actions/.test(readFileSync(path, "utf8")));
  expect(raw).toEqual([]);
});
