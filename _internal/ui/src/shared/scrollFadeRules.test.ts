import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

// Mép cuộn (DESIGN.md 4.5, soát 26-10: dòng nhật ký đầu cắt ngang dưới câu "Có tên sách; khoá..."): khung cuộn dọc nào nằm dưới tiêu đề, trong
// bảng / hộp, hay dưới thanh cố định đều mờ mép 24px ở phía còn cuộn được (`useFadeScroller` / `useScrollFadeOn` của shared/scrollFade.ts),
// không bao giờ cắt cứng. Cùng luật với app điện thoại (ScrollFadeRulesTest.kt: LazyColumn / verticalScroll thiếu Modifier.fadeEdges là trượt).
const SRC = fileURLToPath(new URL("..", import.meta.url)).replaceAll("\\", "/").replace(/\/$/, "");

const SCROLLS = /\boverflow-(?:y-)?(?:auto|scroll)\b/g;
const FADED = /\bstyle=\{[^}]*fade/i;
// Menu / bảng nổi neo vào nút: không có tiêu đề cố định, tự co theo chỗ còn lại của màn và chỉ cuộn khi màn quá thấp.
const FLOATING = /^(?:DropdownMenu\.(?:Sub)?Content|Popover\.Content|PopoverPrimitive\.Content)$/;
// Ngoại lệ có lý do, theo file + đoạn đặc trưng của thẻ.
const EXEMPT: { file: string; tag: string; why: string }[] = [
  { file: "desktop/Shell.tsx", tag: "<main", why: "khung cuộn cả trang, không có gì cố định phía trên" },
  { file: "android/App.tsx", tag: "<main", why: "khung cuộn cả trang của bản WebView (thay bằng native ở P4); mặt nạ cả trang làm WebView khựng khi cuộn" },
  { file: "listen/PlayerViews.tsx", tag: "<ScrollHint", why: "tự vẽ mép trên mờ + dòng nhắc \"còn nữa\" ở mép dưới" },
  { file: "listen/PlayerViews.tsx", tag: "reading-surface", why: "lớp phủ màu nền đọc mờ cả hai mép (mặt nạ trên chương nghìn đoạn đắt hơn)" },
  { file: "listen/ReaderScreen.tsx", tag: "data-reader-scroll", why: "mép trên dính + mép dưới mờ riêng bằng màu nền đọc" },
];

/** Thẻ JSX mở chứa vị trí `at`: từ dấu `<` gần nhất phía trước (không phải kiểu generic như `querySelectorAll<HTMLElement>`) tới `>` đóng thẻ
 *  (bỏ qua `>` trong `{...}` và trong chuỗi). */
function openingTag(text: string, at: number): string {
  let start = at;
  while (start > 0 && !(text[start] === "<" && /[A-Za-z]/.test(text[start + 1] ?? "") && !/[\w.]/.test(text[start - 1] ?? ""))) start--;
  let depth = 0;
  let quote = "";
  for (let index = start; index < text.length; index++) {
    const char = text[index];
    if (quote) {
      if (char === quote && text[index - 1] !== "\\") quote = "";
    } else if (char === '"' || char === "'" || char === "`") quote = char;
    else if (char === "{") depth++;
    else if (char === "}") depth--;
    else if (char === ">" && depth === 0) return text.slice(start, index + 1);
  }
  return text.slice(start);
}

export function scrollFadeViolations(file: string, text: string): string[] {
  const found: string[] = [];
  for (const match of text.matchAll(SCROLLS)) {
    const tag = openingTag(text, match.index);
    const name = /^<([\w.]+)/.exec(tag)?.[1] ?? "";
    if (FADED.test(tag) || FLOATING.test(name)) continue;
    if (EXEMPT.some((rule) => rule.file === file && tag.includes(rule.tag))) continue;
    found.push(`${file}:${text.slice(0, match.index).split("\n").length} <${name}>`);
  }
  return found;
}

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name).replaceAll("\\", "/");
    if (statSync(full).isDirectory()) return name === "gallery" ? [] : files(full);
    return /\.tsx$/.test(name) && !/\.test\./.test(name) ? [full] : [];
  });
}

it("mọi khung cuộn dọc mờ mép ở phía còn cuộn được, không cắt cứng dưới tiêu đề / trong bảng", () => {
  const found = files(SRC).flatMap((full) => scrollFadeViolations(full.slice(SRC.length + 1), readFileSync(full, "utf8")));
  expect(found).toEqual([]);
});

it("máy dò bắt khung cuộn trần, để khung đã mờ mép, menu nổi và ngoại lệ có lý do đi qua", () => {
  expect(scrollFadeViolations("x.tsx", `<div className="max-h-72 overflow-y-auto">a</div>`)).toHaveLength(1);
  expect(scrollFadeViolations("x.tsx", `<pre ref={(node) => { if (node) node.scrollTop = 1; }} className="max-h-72 overflow-auto">a</pre>`)).toHaveLength(1);
  expect(scrollFadeViolations("x.tsx", `<ul className={cn("max-h-72 overflow-y-auto", on && "opacity-50")}>a</ul>`)).toHaveLength(1);
  expect(scrollFadeViolations("x.tsx", `<ul onKeyDown={(e) => e.currentTarget.querySelectorAll<HTMLElement>("button")} className="overflow-y-auto">a</ul>`)).toEqual(["x.tsx:1 <ul>"]);
  expect(scrollFadeViolations("x.tsx", `<div ref={fade.ref} style={fade.style} className="max-h-72 overflow-y-auto">a</div>`)).toEqual([]);
  expect(scrollFadeViolations("x.tsx", `<div ref={setBody} style={fade} className="dialog-body overflow-y-auto">a</div>`)).toEqual([]);
  expect(scrollFadeViolations("x.tsx", `<DropdownMenu.Content align="end" className="max-h-[var(--x)] overflow-y-auto">a</DropdownMenu.Content>`)).toEqual([]);
  expect(scrollFadeViolations("desktop/Shell.tsx", `<main ref={main} className="min-h-0 flex-1 overflow-y-auto">a</main>`)).toEqual([]);
});
