// Chữ của người dùng không bao giờ bị cắt (luật cứng của chủ sách): tên sách, tên chương, tên hồ sơ, tên file đã chọn xuống dòng, không "…" (truncate) và không
// cắt sau N dòng (line-clamp). Máy quét mã giao diện máy tính / phần Nghe: mọi khối có truncate / line-clamp mà chữ bên trong là tên sách / chương.
import { readdirSync, readFileSync } from "node:fs";
import { cwd } from "node:process";
import { expect, it } from "vitest";

const root = `${cwd()}/src`;
/** Biểu thức trong JSX in tên sách / chương / tên do người dùng đặt. */
const USER_TEXT = /book\.title|bookTitle|chapterTitle|chapter\.(sub)?title|fullTitle|displayTitle\(|titleOf\(|labels\.get\(|item\.label|\{item\.name\}|active\.name|^\{(name|title|sub|where)\}$/;
/** Chỗ còn cắt có lý do (đã ghi trong báo cáo, chờ chủ sách quyết): thanh phát thu nhỏ cao cố định một dòng tên chương + một dòng tên sách (DESIGN 6),
 *  tên đầy đủ ở tooltip `title` của nút. */
const ALLOWED = new Set(["listen/PlayerViews.tsx:{track.chapterTitle}#mini"]);
/** Tên máy trong chỗ hẹp (ShortName): rút có chủ đích, tên đầy đủ ở tooltip - tên máy không phải chữ của sách. */
const ALLOWED_ANYWHERE = new Set(["shared/ShortName.tsx:{name}"]);

it("không khối nào cắt tên sách / tên chương / tên người dùng đặt bằng truncate hay line-clamp", () => {
  const clipped: string[] = [];
  for (const dir of ["listen", "desktop", "shared"]) {
    for (const file of readdirSync(`${root}/${dir}`)) {
      if (!file.endsWith(".tsx") || file.includes(".test.")) continue;
      const source = readFileSync(`${root}/${dir}/${file}`, "utf8");
      const tag = /className=(?:"[^"]*\b(?:truncate|line-clamp-\d)\b[^"]*"|\{[^}]*\b(?:truncate|line-clamp-\d)\b[^}]*\})[^>]*>\s*([^<]*)/g;
      for (const match of source.matchAll(tag)) {
        const inner = match[1].trim();
        const expression = inner.match(/\{[^{}]*\}/g)?.find((part) => USER_TEXT.test(part.slice(1, -1).trim()) || USER_TEXT.test(part));
        if (!expression) continue;
        const where = `${dir}/${file}:${expression}`;
        if (ALLOWED_ANYWHERE.has(where)) continue;
        // Thanh phát thu nhỏ: khối MotionRegion của tên chương ngay trong nút "Mở màn hình đang nghe".
        const before = source.slice(Math.max(0, (match.index ?? 0) - 900), match.index);
        if (ALLOWED.has(`${where}#mini`) && before.includes('aria-label="Mở màn hình đang nghe"')) continue;
        clipped.push(`${where} (dòng ${source.slice(0, match.index).split("\n").length})`);
      }
    }
  }
  expect(clipped).toEqual([]);
});
