// @vitest-environment happy-dom
import { readdirSync, readFileSync, statSync } from "node:fs";
import { cwd } from "node:process";
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it } from "vitest";
import { lazyComponent } from "./lazyScreen";

let root: Root, host: HTMLDivElement;
let mounts = 0;
function Screen({ label }: { label: string }) {
  const [opened] = useState(() => ++mounts);
  return <button data-mount={opened}>{label}</button>;
}
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  mounts = 0;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); host.remove(); });

// Lần vẽ lại đầu tiên sau khi chunk về từng đổi hình cây (Suspense -> màn trần) và dựng lại cả màn: menu đang mở tự đóng.
it.each([false, true])("never remounts the screen once its chunk arrived, preloaded=%s", async (preloaded) => {
  const Lazy = lazyComponent(async () => Screen, <p>loading</p>);
  if (preloaded) await Lazy.preload();
  await act(async () => root.render(<Lazy label="a" />));
  await act(async () => { await Lazy.preload(); });
  const first = host.querySelector("button");
  expect(first?.textContent).toBe("a");
  for (const label of ["b", "c"]) await act(async () => root.render(<Lazy label={label} />));
  expect(host.querySelector("button")).toBe(first);
  expect(first?.textContent).toBe("c");
  expect(mounts).toBe(1);
  expect(host.textContent).not.toContain("loading");
});

// Máy dò: hình cây quanh màn nạp lười chỉ có MỘT chỗ giữ cho đúng. Suspense / React.lazy tự viết ở nơi khác dễ lặp lại lỗi trên.
it("lazy loading goes only through lazyComponent", () => {
  const root = `${cwd()}/src`;
  const sources = (dir: string): string[] => readdirSync(dir).flatMap((name) => {
    const path = `${dir}/${name}`;
    if (statSync(path).isDirectory()) return sources(path);
    return /\.tsx?$/.test(name) && !/\.test\./.test(name) && path !== `${root}/shared/lazyScreen.tsx` ? [path] : [];
  });
  const offenders = sources(root).filter((path) => /<Suspense|React\.lazy\(|lazy\(\s*\(\)\s*=>/.test(readFileSync(path, "utf8")));
  expect(offenders.map((path) => path.slice(root.length + 1))).toEqual([]);
});
