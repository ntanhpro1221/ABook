// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it } from "vitest";
import { installFocusModality } from "./focusModality";
let dispose: () => void;
beforeEach(() => { document.body.innerHTML = '<button>A</button><button>B</button><input />'; dispose = installFocusModality(document); });
afterEach(() => { dispose(); document.body.replaceChildren(); });
it("chạm rồi focus bằng mã chỉ đánh dấu nút hiện tại, không đổi html", () => {
  document.dispatchEvent(new PointerEvent("pointerdown"));
  const [a,b] = document.querySelectorAll("button");
  a.focus(); expect(a.hasAttribute("data-pointer-focus")).toBe(true);
  b.focus(); expect(a.hasAttribute("data-pointer-focus")).toBe(false); expect(b.hasAttribute("data-pointer-focus")).toBe(true);
  expect(document.documentElement.hasAttribute("data-input")).toBe(false);
});
it("bàn phím khôi phục vòng ngay cả khi không đổi phần tử focus", () => {
  document.dispatchEvent(new PointerEvent("pointerdown"));
  const button=document.querySelector("button")!; button.focus();
  document.dispatchEvent(new KeyboardEvent("keydown", {key:"Tab"}));
  expect(button.hasAttribute("data-pointer-focus")).toBe(false);
  document.querySelector("input")!.focus(); expect(document.querySelector("[data-pointer-focus]")).toBeNull();
});
it("bỏ focus và tháo listeners không để lại marker trên cây cũ", () => {
  document.dispatchEvent(new PointerEvent("pointerdown"));
  const button=document.querySelector("button")!; button.focus(); button.blur();
  expect(document.querySelector("[data-pointer-focus]")).toBeNull();
  button.focus(); dispose(); expect(button.hasAttribute("data-pointer-focus")).toBe(false);
});
