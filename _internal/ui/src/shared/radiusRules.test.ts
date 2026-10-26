import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

// Bo góc chỉ có ba vai của docs/DESIGN.md 5.5 (control / cover / sheet, sinh vào shared/tokens.generated.css) + tròn + không bo.
// Cùng luật với app điện thoại (RadiusRulesTest.kt: RoundedCornerShape(<số>.dp) bị cấm ngoài theme/) - hai nền tảng không lệch bo góc.
const SRC = fileURLToPath(new URL("..", import.meta.url)).replaceAll("\\", "/").replace(/\/$/, "");
// Khung của thư viện mẫu (gallery.css) là đồ nghề của người làm, không phải giao diện app.
const SKIP = new Set([`${SRC}/gallery/gallery.css`, `${SRC}/shared/tokens.generated.css`]);

const TAILWIND = /(?<![\w-])rounded(-[^\s"'`,)}]*)?/g;
const ROLE = /^-(?:(?:t|b|l|r|s|e|tl|tr|bl|br|ss|se|es|ee)-)?(?:control|cover|sheet|full|none)$/;
const CSS_RADIUS = /border(?:-(?:top|bottom|start|end)-(?:left|right|start|end))?-radius\s*:\s*([^;}]+)/g;
const CSS_ALLOWED = /var\(--radius-(?:control|cover|sheet)\)|calc\(infinity \* 1px\)|\b0\b|50%|inherit|\s+/g;

function radiusViolations(file: string, text: string): string[] {
  const found: string[] = [];
  const lines = text.split("\n");
  lines.forEach((line, index) => {
    const at = `${file.slice(SRC.length + 1)}:${index + 1}`;
    if (/\.(tsx?)$/.test(file)) {
      for (const m of line.matchAll(TAILWIND)) if (!ROLE.test(m[1] ?? "")) found.push(`${at} ${m[0]}`);
      if (/\bborderRadius\b/.test(line)) found.push(`${at} borderRadius`);
    }
    for (const m of line.matchAll(CSS_RADIUS)) if (m[1].replace(CSS_ALLOWED, "").trim() !== "") found.push(`${at} border-radius: ${m[1].trim()}`);
  });
  return found;
}

function files(dir: string): string[] {
  return readdirSync(dir).flatMap(name => {
    const full = join(dir, name).replaceAll("\\", "/");
    if (statSync(full).isDirectory()) return files(full);
    // Test nhắc tên lớp trong biểu thức chính quy / bộ chọn nên không phải nơi dùng bo góc.
    return /\.(tsx?|css)$/.test(name) && !/\.test\./.test(name) && !SKIP.has(full) ? [full] : [];
  });
}

it("không còn bo góc ngoài ba vai control / cover / sheet, tròn và không bo", () => {
  const all = files(SRC).flatMap(file => radiusViolations(file, readFileSync(file, "utf8")));
  expect(all).toEqual([]);
});

it("luật bắt đúng: thang mặc định, giá trị tuỳ ý và border-radius lẻ đều bị chặn", () => {
  const ts = `${SRC}/x.tsx`;
  const css = `${SRC}/x.css`;
  expect(radiusViolations(ts, '<div className="rounded-lg md:rounded-xl rounded-[20px] rounded rounded-t-2xl" />').map(v => v.split(" ").pop()))
    .toEqual(["rounded-lg", "rounded-xl", "rounded-[20px]", "rounded", "rounded-t-2xl"]);
  expect(radiusViolations(ts, '<div className="rounded-control rounded-t-sheet rounded-full rounded-none rounded-cover" style={{ borderRadius: 3 }} />'))
    .toEqual(["x.tsx:1 borderRadius"]);
  expect(radiusViolations(css, ".a { border-radius: 3px; } .b { border-top-left-radius: 0.5rem }")).toHaveLength(2);
  expect(radiusViolations(css, ".a { border-radius: var(--radius-control); } .b { border-radius: 0; } .c { border-radius: calc(infinity * 1px); }")).toEqual([]);
});
