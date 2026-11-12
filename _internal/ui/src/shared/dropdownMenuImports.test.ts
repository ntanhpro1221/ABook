// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const SRC = fileURLToPath(new URL("..", import.meta.url));
const WRAPPER = "shared/DropdownMenu.tsx";
const RADIX = "@radix-ui/react-dropdown-menu";

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap(entry => statSync(join(dir, entry)).isDirectory()
    ? sources(join(dir, entry)) : /\.[cm]?[jt]sx?$/.test(entry) && !/\.test\.[cm]?[jt]sx?$/.test(entry) ? [join(dir, entry)] : []);
}

function directImports(source: string): number {
  return [...source.matchAll(/["'`]@radix-ui\/react-dropdown-menu["'`]/g)].length;
}

it("routes every dropdown through the shared opening-release guard", () => {
  const offenders = sources(SRC).filter(path => path.slice(SRC.length).replaceAll("\\", "/") !== WRAPPER
    && directImports(readFileSync(path, "utf8"))).map(path => path.slice(SRC.length));
  expect(offenders).toEqual([]);
});

it("catches imports, re-exports, require and dynamic imports", () => {
  for (const source of [`import * as Menu from '${RADIX}'`, `export * from "${RADIX}"`,
    `const menu = require('${RADIX}')`, `const menu = import('${RADIX}')`]) expect(directImports(source)).toBe(1);
});
