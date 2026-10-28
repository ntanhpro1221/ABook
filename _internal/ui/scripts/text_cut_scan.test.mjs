// @vitest-environment node
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, it } from "vitest";
import { scanTextCuts } from "./text_cut_scan.mjs";

// Each exception must identify a finding and explain why full text is available.
// Owner rule: aim for zero; currently no exceptions.
const ALLOWED = new Map();
export function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    const file = path.join(dir, e.name);
    return e.isDirectory() ? sourceFiles(file) : /\.(css|tsx?|jsx?)$/.test(e.name) && !/\.test\./.test(e.name) ? [file] : [];
  });
}

it("all web UI source keeps complete text, with zero unexplained exceptions", () => {
  const root = path.resolve(import.meta.dirname, "../src");
  const files = sourceFiles(root);
  expect(files.length).toBeGreaterThan(100);
  const findings = files.flatMap(file => scanTextCuts(path.relative(root, file).replaceAll("\\", "/"), readFileSync(file, "utf8")));
  for (const [key, reason] of ALLOWED) {
    expect(reason.trim().length, key).toBeGreaterThan(20);
    expect(findings.some(f => `${f.file}:${f.line}:${f.why}` === key), `stale exception: ${key}`).toBe(true);
  }
  expect(findings.filter(f => !ALLOWED.has(`${f.file}:${f.line}:${f.why}`))).toEqual([]);
});

it.each([
  ['x.css', '.title { text-overflow: ellipsis; }'],
  ['x.css', '.title { -webkit-line-clamp: 2; }'],
  ['x.css', '.title { line-clamp: 3; }'],
  ['x.css', '.title { white-space: nowrap; } .title { overflow: hidden; }'],
  ['x.tsx', '<p className="md:truncate" />'],
  ['x.tsx', '<p className={cn("line-clamp-2", active && "text-fg")} />'],
  ['x.tsx', '<p className={`line-clamp-${lines}`} />'],
  ['x.tsx', '<p style={{ textOverflow: "ellipsis" }} />'],
  ['x.tsx', 'const style = { WebkitLineClamp: 2 };'],
  ['x.tsx', '<p style={{ whiteSpace: "nowrap", overflow: "hidden" }} />'],
  ['x.tsx', '<p className="whitespace-nowrap overflow-hidden" />'],
  ['x.tsx', 'const row = cn("whitespace-nowrap", active && "overflow-hidden");'],
  ['x.tsx', '<p className="whitespace-nowrap" style={{ overflow: "hidden" }} />'],
  ['x.tsx', '<p className="overflow-clip" style={{ whiteSpace: "nowrap" }} />'],
  ['x.tsx', '<p className="[white-space:nowrap] [overflow:hidden]" />'],
  ['x.tsx', '<p style={{ webkitLineClamp: 2 }} />'],
])("scanner rejects clipping: %s %s", (file, code) => expect(scanTextCuts(file, code).length).toBeGreaterThan(0));

it("allows wrapping, decorative cropping, scroll regions and comments", () => {
  expect(scanTextCuts('x.tsx', '// truncate\n<><p className="break-words whitespace-normal" /><div className="overflow-hidden" /></>')).toEqual([]);
  expect(scanTextCuts('x.css', '/* line-clamp: 2 */ .title { white-space: normal; overflow-wrap: anywhere; }')).toEqual([]);
});
