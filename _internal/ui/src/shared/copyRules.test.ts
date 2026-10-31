import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

// "Không X được" là câu cụt khi đứng một mình ("Không mở được", "Không lưu được") - nói theo cái người nghe thấy: "Chưa X được" + việc nên làm.
// Cùng luật với app điện thoại (CopyRulesTest.kt). Chuỗi đến từ máy chủ (Python) và chữ của truyện nằm ngoài luật này; dòng ghi nhật ký (log) cũng bỏ.
const SRC = fileURLToPath(new URL("..", import.meta.url)).replaceAll("\\", "/").replace(/\/$/, "");

const RULE = /"[^"\n]*\bKhông [^"\n]{1,30} được\b[^"\n]*"|`[^`\n]*\bKhông [^`\n]{1,30} được\b[^`\n]*`/g;

export function cutCopyOffences(file: string, text: string): string[] {
  const found: string[] = [];
  text.split("\n").forEach((line, index) => {
    const t = line.trimStart();
    if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*") || /\b(?:console|log)\./.test(line) || line.includes("AppLog")) return;
    for (const m of line.matchAll(RULE)) found.push(`${file.slice(SRC.length + 1)}:${index + 1} ${m[0]}`);
  });
  return found;
}

function files(dir: string): string[] {
  return readdirSync(dir).flatMap(name => {
    const full = join(dir, name).replaceAll("\\", "/");
    if (statSync(full).isDirectory()) return files(full);
    // Test nhắc chữ máy chủ trả về (Python) để so khớp, không phải chữ giao diện.
    return /\.tsx?$/.test(name) && !/\.test\./.test(name) ? [full] : [];
  });
}

it("không còn câu cụt 'Không … được' trong chữ giao diện", () => {
  const all = files(SRC).flatMap(file => cutCopyOffences(file, readFileSync(file, "utf8")));
  expect(all).toEqual([]);
});

it("luật bắt đúng 'Không X được' và để câu nói rõ nguyên nhân đi qua", () => {
  const f = `${SRC}/x.tsx`;
  expect(cutCopyOffences(f, 'const a = "Không mở được sách";')).toHaveLength(1);
  expect(cutCopyOffences(f, "const a = `Không lưu được ${name}`;")).toHaveLength(1);
  expect(cutCopyOffences(f, 'const a = "Chưa mở được sách";')).toEqual([]);
  expect(cutCopyOffences(f, 'const a = "Không có sách nào";')).toEqual([]);
  expect(cutCopyOffences(f, '// "Không mở được" là chữ cũ')).toEqual([]);
});
