// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MotionRegion } from "./MotionRegion";

let root: ReturnType<typeof createRoot>;
let animation: Animation;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let index = 0; index < this.length; index++) yield this.item(index); } });
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  animation = { cancel: vi.fn(), onfinish: null } as unknown as Animation;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => animation);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const height = this.textContent ? 80 : 0;
    return { x: 0, y: 0, top: 0, left: 0, right: 240, bottom: height, width: 240, height, toJSON() {} };
  });
  const style = document.createElement("style"); style.textContent = readFileSync(`${cwd()}/src/styles.css`, "utf8"); document.head.append(style);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); document.head.replaceChildren(); vi.restoreAllMocks(); vi.useRealTimers(); });

it("V5 region rỗng giữ slot 80px qua exit, co về 0 rồi mới display:none", async () => {
  await act(() => root.render(<MotionRegion><p>Thông báo</p></MotionRegion>));
  const box = document.querySelector<HTMLElement>("[data-motion-region]")!;
  await act(() => root.render(<MotionRegion>{null}</MotionRegion>));
  expect(getComputedStyle(box).display).not.toBe("none");
  expect(box.style.height).toBe("80px");
  expect(HTMLElement.prototype.animate).toHaveBeenCalledWith(
    [{ opacity: 1, height: "80px" }, { opacity: 0, height: "0px" }], expect.any(Object),
  );
  await act(() => animation.onfinish?.(new Event("finish") as AnimationPlaybackEvent));
  expect(box.style.height).toBe("");
  expect(getComputedStyle(box).display).toBe("none");
});

it("V5 giữ cả margin cũ khi class bị bỏ, rồi co margin cùng slot", async () => {
  await act(() => root.render(<MotionRegion style={{ marginTop: "12px" }}><p>Thẻ</p></MotionRegion>));
  await act(() => root.render(<MotionRegion>{null}</MotionRegion>));
  const box = document.querySelector<HTMLElement>("[data-motion-region]")!;
  expect(box.style.marginTop).toBe("12px");
  expect(HTMLElement.prototype.animate).toHaveBeenLastCalledWith([
    { opacity: 1, height: "80px", marginTop: "12px" }, { opacity: 0, height: "0px", marginTop: "0px" },
  ], expect.any(Object));
});

it("V8 unmount region huỷ cả timer snapshot và timer giữ slot", async () => {
  vi.useFakeTimers();
  await act(() => root.render(<MotionRegion><p>Thẻ</p></MotionRegion>));
  await act(() => root.render(<MotionRegion>{null}</MotionRegion>));
  expect(vi.getTimerCount()).toBeGreaterThan(0);
  await act(() => root.render(null));
  expect(vi.getTimerCount()).toBe(0);
  expect(document.querySelector(".motion-snapshot")).toBeNull();
});

it("V5 reduced: giữ diện tích hết fade; mở lại giữa exit không bị callback cũ ẩn", async () => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: true } as MediaQueryList);
  await act(() => root.render(<MotionRegion><p>Thông báo</p></MotionRegion>));
  const box = document.querySelector<HTMLElement>("[data-motion-region]")!;
  await act(() => root.render(<MotionRegion>{null}</MotionRegion>));
  expect(box.style.height).toBe("80px");
  expect(HTMLElement.prototype.animate).toHaveBeenLastCalledWith([{ opacity: 1 }, { opacity: 0 }], expect.any(Object));
  const finish = animation.onfinish;
  await act(() => root.render(<MotionRegion><p>Nội dung mới</p></MotionRegion>));
  await act(() => finish?.call(animation, new Event("finish") as AnimationPlaybackEvent));
  expect(box.style.height).toBe("");
  expect(box.hasAttribute("data-motion-exit")).toBe(false);
  expect(box.textContent).toBe("Nội dung mới");
});
