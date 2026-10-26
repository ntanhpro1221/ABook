// @vitest-environment happy-dom
// Soát máy ảo 25-10 (V2-V8): hàng lựa chọn trong bảng trượt dùng chung cấu trúc, lưới / nút không lùi ra ngoài cột, chevron cuối dòng có ink-end.
import { renderToStaticMarkup } from "react-dom/server";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { cwd } from "node:process";
import { expect, it } from "vitest";
import { LevelButtons } from "./PlayerViews";
import { PlaylistOptionLabel } from "./PlaylistChoice";

const root = `${cwd()}/src`;
const css = readFileSync(`${root}/styles.css`, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
/** Mọi luật thường của styles.css: [bộ chọn, phần khai báo]. */
const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((match) => [match[1].trim(), match[2]] as const);
const sources = (dir = root): string[] => readdirSync(dir).flatMap((name) => {
  const path = `${dir}/${name}`;
  if (statSync(path).isDirectory()) return name === "gallery" ? [] : sources(path);
  return /\.tsx$/.test(name) && !/\.test\./.test(name) ? [path] : [];
});

it("V2 mức nhạc: mọi dòng là dòng lựa chọn của bảng (data-sheet-choice) với dấu ✓ là con trực tiếp, cùng cấu trúc danh sách nhạc", () => {
  const html = renderToStaticMarkup(<LevelButtons level={-12} disabled={false} onChange={() => undefined} />);
  const host = document.createElement("div");
  host.innerHTML = html;
  const rows = [...host.querySelectorAll("button")];
  expect(rows.length).toBeGreaterThan(1);
  for (const row of rows) {
    expect(row.hasAttribute("data-sheet-choice")).toBe(true);
    expect(row.firstElementChild?.tagName.toLowerCase()).toBe("svg"); // [data-sheet-choice] > svg: icon 20 px / khoảng 12 px của bảng trượt
    expect(row.className).toContain("min-h-9"); // cùng chiều cao tối thiểu với dòng danh sách nhạc
  }
});

it("V3 danh sách nhạc: mô tả luôn chừa hai dòng theo đơn vị lh (không cắt chữ), nên dòng mô tả ngắn / dài cao bằng nhau", () => {
  const short = renderToStaticMarkup(<PlaylistOptionLabel option={{ id: "a", label: "Một", hint: "", description: "Ngắn." }} chosen={false} />);
  const long = renderToStaticMarkup(<PlaylistOptionLabel option={{ id: "b", label: "Hai", hint: "", description: "Mô tả dài hơn nhiều, xuống dòng khi bảng hẹp." }} chosen />);
  for (const html of [short, long]) {
    expect(html).toMatch(/class="[^"]*min-h-\[2lh\][^"]*"[^>]*>(Ngắn\.|Mô tả dài)/);
    expect(html).not.toMatch(/truncate|line-clamp|overflow-hidden/);
  }
});

it("V4 bảng trượt: bỏ padding px-N thì bỏ cả margin âm -ml-N / -mx-N đi cùng", () => {
  const pair = rules.find(([selector]) => selector.includes(".player-sheet .sheet-body") && selector.includes('[class~="-ml-2"]'));
  expect(pair?.[0]).toContain('[class~="px-2"]');
  expect(pair?.[1]).toContain("margin-inline: 0");
  // Nút chân bảng Giọng đọc ("Làm trước…") đúng là cặp đó.
  const view = readFileSync(`${root}/listen/PlayerViews.tsx`, "utf8");
  expect(view).toMatch(/data-focus-next className="touch-hit -ml-2 rounded-control px-2/);
});

it("V4 loại lỗi: luật nào trong bảng trượt bỏ padding-inline của px-N thì cũng có luật bỏ margin âm cùng cỡ", () => {
  const zeroed = rules.filter(([selector, body]) => selector.includes(".player-sheet .sheet-body") && /\[class~="px-\d"\]/.test(selector) && /padding-inline: 0/.test(body));
  expect(zeroed.length).toBeGreaterThan(0);
  for (const [selector] of zeroed) {
    const size = selector.match(/\[class~="px-(\d)"\]/)![1];
    expect(css).toContain(`[class~="px-${size}"]:is([class~="-mx-${size}"]`);
  }
});

it("V8 lưới nút trong bảng trượt: một luật cho mọi mức bọc; bỏ padding-inline thì bỏ cả margin-inline âm (không lùi ra ngoài cột)", () => {
  const grids = rules.filter(([selector, body]) => selector.includes(".sheet-body") && /\.grid\b/.test(selector) && /padding-inline: 0/.test(body));
  expect(grids.length).toBe(1);
  expect(grids[0][1]).toContain("margin-inline: 0");
  // Không còn luật theo độ sâu bọc (> div > .grid) làm Hẹn giờ (MotionRegion) khác Tốc độ.
  expect(grids[0][0]).not.toContain(">");
  // Mọi luật sheet-body đặt margin-inline âm cho khung p-1 vẫn yếu hơn luật lưới.
  const grid = (html: string) => { const host = document.createElement("div"); host.innerHTML = html; return host.firstElementChild as HTMLElement; };
  const speed = grid('<div class="grid grid-cols-3 gap-1 p-1 -mx-1.5 px-1.5"></div>');
  expect(speed.matches(grids[0][0])).toBe(false); // ngoài .player-sheet .sheet-body thì không dính
  const sheet = document.createElement("div");
  sheet.className = "player-sheet";
  sheet.innerHTML = `<div class="sheet-body"><div>${speed.outerHTML}</div>${speed.outerHTML}</div>`;
  for (const cell of sheet.querySelectorAll(".grid")) expect(cell.matches(grids[0][0])).toBe(true); // cả khi bọc một div (MotionRegion) lẫn không
});

it("C1 hàng nút phụ: không luật nào kéo riêng biểu tượng đầu mút ra khỏi chỗ giữa trên nhãn", () => {
  // 25-10 V5 kéo biểu tượng "Đọc" / "Thêm" ra mép ngoài ô nút: mực lòi 9 px khỏi lề và tách khỏi nhãn (audit140 C1).
  const joined = rules.map(([selector, body]) => `${selector} {${body}}`).join("\n");
  expect(joined).not.toMatch(/\[data-(player|book)-secondary\]/);
});

it("V7 chevron cuối dòng: mọi ChevronRight đứng cuối dòng có ink-end (mực thẳng mép nội dung)", () => {
  const missing = sources().flatMap((file) => [...readFileSync(file, "utf8").matchAll(/<ChevronRight className="([^"]*)"/g)]
    .filter((match) => !match[1].includes("ink-end"))
    .map(() => file.slice(root.length + 1)));
  // Ngoại lệ: mũi tên cuộn tab trong nút tròn (shared/ui.tsx) - không phải icon cuối dòng.
  expect(missing).toEqual(["shared/ui.tsx"]);
});
