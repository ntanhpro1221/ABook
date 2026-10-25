// @vitest-environment node
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, it } from "vitest";

const src = path.resolve(import.meta.dirname, "../src");
function files(dir) { return readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? files(path.join(dir, entry.name)) : [path.join(dir, entry.name)]); }

// Đọc hết thẻ mở, kể cả dấu > trong onClick: không bỏ sót nút tự dựng ngoài Button.
function buttons(source) {
  const result = [];
  for (const match of source.matchAll(/<button\b|<MotionRegion\s+as="button"/g)) {
    let braces = 0, quote = "";
    for (let i = match.index + match[0].length; i < source.length; i++) {
      const c = source[i];
      if (quote) { if (c === "\\") i++; else if (c === quote) quote = ""; continue; }
      if (c === '"' || c === "'" || c === "`") quote = c;
      else if (c === "{") braces++;
      else if (c === "}") braces--;
      else if (c === ">" && !braces) { result.push(source.slice(match.index, i)); break; }
    }
  }
  return result;
}

it("toàn app không thêm lại nút viền hoặc nhóm segmented", () => {
  const offenders = [];
  for (const file of files(src).filter(file => file.endsWith(".tsx") && !file.includes(".test."))) {
    const source = readFileSync(file, "utf8");
    if (/\bSegmented\b|variant=[^\n]*"(?:secondary|outline)"|<SlidingIndicator\b[^>]*variant="pill"/.test(source)) offenders.push(path.relative(src, file));
    for (const button of buttons(source)) {
      let classes = button.match(/className=("[^"]*"|\{cn\([\s\S]*?\)\})/)?.[1] ?? "";
      const variable = button.match(/className=\{(?:cn\()?([A-Za-z_]\w*)/)?.[1];
      if (variable) for (const match of source.matchAll(new RegExp(`const ${variable} = "([^"]*)"`, "g"))) classes += ` ${match[1]}`;
      if (/(?:^|[\s"`])(?:border|ring-1)(?:\s|"|`)/.test(classes)) offenders.push(`${path.relative(src, file)}: ${classes}`);
    }
  }
  expect(offenders).toEqual([]);
});
