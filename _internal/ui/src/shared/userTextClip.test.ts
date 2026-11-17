// Chữ của người dùng không bao giờ bị cắt (luật cứng của chủ sách): tên sách, tên chương, tên hồ sơ, tên file đã chọn xuống dòng, không "…" (truncate) và không
// cắt sau N dòng (line-clamp); ô một dòng cố định (thanh phát, màn Đang nghe) thì qua MarqueeLine - thu cỡ rồi chạy chữ. Máy quét mã giao diện máy tính / phần Nghe: mọi khối có truncate / line-clamp mà chữ bên trong là tên sách / chương.
import { readdirSync, readFileSync } from "node:fs";
import { cwd } from "node:process";
import { expect, it } from "vitest";

const root = `${cwd()}/src`;
/** Biểu thức trong JSX in tên sách / chương / tên do người dùng đặt. */
const USER_TEXT = /book\.title|bookTitle|chapterTitle|chapter\.(sub)?title|fullTitle|displayTitle\(|titleOf\(|labels\.get\(|item\.label|\{item\.name\}|active\.name|^\{(name|title|sub|where)\}$/;
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
        clipped.push(`${where} (dòng ${source.slice(0, match.index).split("\n").length})`);
      }
    }
  }
  expect(clipped).toEqual([]);
});

/** Biểu thức in tên giọng / tên nhân vật (cùng loại với tên giọng của điện thoại, TextCutScanTest). */
const NAME_TEXT = /spokenVoiceName\(|voiceName\(|cleanName\(|\bvoice\.name\b|\bperson\.(?:name|label)\b|\bpicked\.label\b|^\{shown\}$/;
/** Nhãn của nút giọng trên thanh phát rộng (`look` khác "row"): nút công cụ cao cố định, ẩn dưới 75rem; tên đầy đủ ở dòng đang chọn trong hộp giọng ngay khi bấm. */
const NAME_ALLOWED = new Set(["listen/PlayerViews.tsx:{current ? spokenVoiceName(current.name) : \"\"}#bar"]);

it("tên giọng / tên nhân vật không bị cắt \"…\": một dòng thì qua OneLineFit (thu cỡ, không vừa thì xuống dòng)", () => {
  const clipped: string[] = [];
  for (const dir of ["listen", "desktop", "shared", "studio"]) {
    for (const file of readdirSync(`${root}/${dir}`)) {
      if (!file.endsWith(".tsx") || file.includes(".test.")) continue;
      const source = readFileSync(`${root}/${dir}/${file}`, "utf8");
      const tag = /className=(?:"[^"]*\b(?:truncate|line-clamp-\d)\b[^"]*"|\{[^}]*\b(?:truncate|line-clamp-\d)\b[^}]*\})[^>]*>\s*([^<]*)/g;
      for (const match of source.matchAll(tag)) {
        const expression = match[1].trim().match(/\{(?:[^{}]|\{[^{}]*\})*\}/g)?.find((part) => NAME_TEXT.test(part.slice(1, -1).trim()) || NAME_TEXT.test(part));
        if (!expression) continue;
        const where = `${dir}/${file}:${expression}`;
        // Nút thanh phát rộng: lớp `max-w-24 truncate @max-[75rem]:hidden` (chỉ dạng nút công cụ, không phải dòng menu).
        if (NAME_ALLOWED.has(`${where}#bar`) && /max-w-24 truncate @max-\[75rem\]:hidden/.test(match[0])) continue;
        clipped.push(`${where} (dòng ${source.slice(0, match.index).split("\n").length})`);
      }
    }
  }
  expect(clipped).toEqual([]);
});

it("máy dò tên giọng bắt được chỗ cắt cũ (đối chứng: dòng giọng trước OneLineFit)", () => {
  const old = `<span className="min-w-0 truncate text-sm font-medium">{shown}</span>`;
  const match = /className="[^"]*\btruncate\b[^"]*"[^>]*>\s*([^<]*)/.exec(old);
  expect(match && NAME_TEXT.test(match[1].trim())).toBe(true);
});
