// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Cỡ file ghi bằng MỘT hàm: shared/format.ts formatSize (hệ 1024; bản Qt desktop_qt/qml/SizeFormat.js chép đúng hàm này). Trước 29-10 có
// thêm musicLocal.formatSize (hệ 10) và AnalysisModelPicker.gigabytes, nên cùng một file ghi "820 MB" ở thẻ giọng mà "782 MB" ở Cài đặt.
// Máy dò chặn bản tự tính mới: hàm cỡ file định nghĩa ngoài format.ts, hay phép chia cho 1e3 / 1e6 / 1e9 để ra KB / MB / GB.
const SHARED = "shared/format.ts";
const OWN_FORMATTER = /(function\s+|(const|let)\s+)(formatSize|formatBytes|gigabytes|megabytes)\b/;
const DECIMAL_UNITS = /\/\s*1e[369]\b/;

/** Mọi file .ts/.tsx (trừ test) dưới src, khoá là đường tương đối "studio/musicLocal.ts". */
function sources(root: string, prefix = ""): Record<string, string> {
  const files: Record<string, string> = {};
  for (const name of readdirSync(join(root, prefix))) {
    const rel = prefix ? `${prefix}/${name}` : name;
    if (statSync(join(root, rel)).isDirectory()) Object.assign(files, sources(root, rel));
    else if (/\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name)) files[rel] = readFileSync(join(root, rel), "utf8");
  }
  return files;
}

function ownSizeFormatters(files: Record<string, string>): string[] {
  const hits: string[] = [];
  for (const [name, text] of Object.entries(files)) {
    if (name === SHARED) continue;
    text.split("\n").forEach((line, index) => {
      if (OWN_FORMATTER.test(line) || DECIMAL_UNITS.test(line)) hits.push(`${name}:${index + 1}: ${line.trim()}`);
    });
  }
  return hits.sort();
}

describe("một hàm ghi cỡ file", () => {
  it("mọi nhãn cỡ file gọi shared/format.ts formatSize", () => {
    expect(ownSizeFormatters(sources(fileURLToPath(new URL("..", import.meta.url))))).toEqual([]);
  });
  it("máy dò thấy bản tự tính", () => {
    const hits = ownSizeFormatters({
      "studio/Old.ts": "export function formatSize(bytes: number) { return `${bytes / 1e9} GB`; }\n",
      "listen/Inline.tsx": "const gigabytes = (b: number) => b;\nconst label = `${(size / 1e6).toFixed(1)} MB`;\n",
      [SHARED]: "export function formatSize(bytes: number) { return `${bytes / 1e9}`; }\n",
    });
    expect(hits.map((hit) => hit.split(":").slice(0, 2).join(":"))).toEqual(["listen/Inline.tsx:1", "listen/Inline.tsx:2", "studio/Old.ts:1"]);
  });
});
