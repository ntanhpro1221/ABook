// @vitest-environment happy-dom
// Khung chờ chỉ hiện khi chờ lâu (máy ảo 25-10: tab Studio lần đầu chớp hai thanh xám ~200 ms rồi mới mờ sang nội dung).
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { LOADING_PATIENCE, LoadingCrossfade } from "./MotionPresence";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: Root | undefined;
let time = 1000;
afterEach(() => { act(() => root?.unmount()); root = undefined; document.body.innerHTML = ""; vi.restoreAllMocks(); });

function mount() {
  vi.spyOn(performance, "now").mockImplementation(() => time);
  const host = document.body.appendChild(document.createElement("div"));
  root = createRoot(host);
  const show = (loading: boolean) => act(() => root!.render(<LoadingCrossfade loading={loading} placeholder={<i>chờ</i>}><b>nội dung</b></LoadingCrossfade>));
  return { host, show, placeholder: () => host.querySelector(".motion-loading-placeholder") };
}

it("dữ liệu về trước LOADING_PATIENCE: khung chờ gỡ luôn, không mờ ra; nội dung hiện dần", () => {
  const { host, show, placeholder } = mount();
  show(true);
  expect(placeholder()?.getAttribute("data-state")).toBe("open");
  time += LOADING_PATIENCE - 50;
  show(false);
  expect(placeholder()).toBeNull();
  expect(host.querySelector(".motion-loading-content")?.classList).toContain("motion-reveal");
  // Vẽ lại sau đó (đồng hồ đã qua mốc) cũng không gọi khung chờ đang khép quay lại.
  time += 1000;
  show(false);
  expect(placeholder()).toBeNull();
});

it("chờ lâu: khung chờ đã hiện thì mờ ra đè lên nội dung như cũ; lượt chờ sau tính lại từ đầu", () => {
  const { show, placeholder } = mount();
  show(true);
  time += LOADING_PATIENCE + 100;
  show(false);
  expect(placeholder()?.getAttribute("data-state")).toBe("closed");
  show(true);
  expect(placeholder()?.getAttribute("data-state")).toBe("open");
  time += 20;
  show(false);
  expect(placeholder()).toBeNull();
});

it("khung chờ trễ đúng LOADING_PATIENCE trong CSS", () => {
  const css = readFileSync(`${cwd()}/src/styles.css`, "utf8");
  expect(css).toContain(`--loading-patience: ${LOADING_PATIENCE}ms;`);
  expect(css).toContain('.motion-loading-placeholder.motion-panel[data-state="open"] { animation-delay: var(--loading-patience); }');
  // Mọi khung chờ xám (Skeleton) cũng chờ đúng mốc ấy, kể cả bản không qua LoadingCrossfade.
  expect(css.match(/fade-in var\(--motion-medium\) linear var\(--loading-patience\) backwards/g)).toHaveLength(2);
});
