// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const SRC = fileURLToPath(new URL("..", import.meta.url));
// Mỗi lớp nổi của Radix đi qua một bọc chung: menu giữ cú nhả lúc mở (opening-release guard), và cả menu lẫn Popover bấm ra ngoài chỉ đóng
// (outsideShield.ts, soát 18-11 lần 4).
const WRAPPERS: Record<string, string> = {
  "@radix-ui/react-dropdown-menu": "shared/DropdownMenu.tsx",
  "@radix-ui/react-popover": "shared/Popover.tsx",
};

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap(entry => statSync(join(dir, entry)).isDirectory()
    ? sources(join(dir, entry)) : /\.[cm]?[jt]sx?$/.test(entry) && !/\.test\.[cm]?[jt]sx?$/.test(entry) ? [join(dir, entry)] : []);
}

function directImports(source: string, radix: string): number {
  return [...source.matchAll(new RegExp(`["'\`]${radix.replace(/[/.-]/g, "\$&")}["'\`]`, "g"))].length;
}

it("routes every dropdown and popover through its shared wrapper", () => {
  for (const [radix, wrapper] of Object.entries(WRAPPERS)) {
    const offenders = sources(SRC).filter(path => path.slice(SRC.length).replaceAll("\\", "/") !== wrapper
      && directImports(readFileSync(path, "utf8"), radix)).map(path => path.slice(SRC.length));
    expect(offenders, radix).toEqual([]);
  }
});

it("each wrapper's Content lays the outside shield", () => {
  for (const wrapper of Object.values(WRAPPERS)) {
    const source = readFileSync(join(SRC, wrapper), "utf8");
    expect(source, wrapper).toMatch(/export const Content = forwardRef[\s\S]*?\{\.\.\.useOutsideShield\(ref, props\.onInteractOutside\)\}/);
  }
});

it("catches imports, re-exports, require and dynamic imports", () => {
  for (const radix of Object.keys(WRAPPERS)) {
    for (const source of [`import * as Menu from '${radix}'`, `export * from "${radix}"`,
      `const menu = require('${radix}')`, `const menu = import('${radix}')`]) expect(directImports(source, radix)).toBe(1);
  }
});
