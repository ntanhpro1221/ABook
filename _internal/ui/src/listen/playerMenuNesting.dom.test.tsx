// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MenuShell } from "./PlayerViews";
import { dismissTopLayer } from "@/android/backLayers";
import * as Popover from "@radix-ui/react-popover";
import { TooltipProvider } from "@/shared/ui";

let root: Root;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("max-width"), addEventListener() {}, removeEventListener() {} }));
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
});

it("máy tính: lựa chọn trong mục con khép mục con, giữ bảng cha và một lớp nổi", async () => {
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  const pick = vi.fn();
  await act(() => root.render(<TooltipProvider><MenuShell label="Thêm tuỳ chọn" trigger="…"><MenuShell label="Nhạc nền" trigger="Tắt" look="row"><Popover.Close onClick={pick}>Tắt nhạc</Popover.Close></MenuShell></MenuShell></TooltipProvider>));
  await act(() => document.querySelector<HTMLButtonElement>('[aria-label="Thêm tuỳ chọn"]')!.click()); await wait();
  await act(() => document.querySelector<HTMLButtonElement>('[aria-label="Nhạc nền"]')!.click()); await wait();
  expect(document.querySelectorAll('[role="dialog"][data-state="open"]')).toHaveLength(1);
  await act(() => Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(button => button.textContent === "Tắt nhạc")!.click()); await wait();
  expect(pick).toHaveBeenCalledOnce();
  expect(document.querySelector('[aria-label="Nhạc nền"]')!.getAttribute("aria-expanded")).toBe("false");
  expect(document.querySelectorAll('[role="dialog"][data-state="open"]')).toHaveLength(1);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const wait = () => act(() => new Promise(resolve => setTimeout(resolve, 40)));
it.each([false, true])("nút mở giữ quan hệ ARIA do Radix cung cấp, điện thoại=%s", async (phone) => {
  vi.stubGlobal("matchMedia", () => ({ matches: phone, addEventListener() {}, removeEventListener() {} }));
  await act(() => root.render(<TooltipProvider><MenuShell label="Tốc độ đọc" trigger="1×"><button>Chọn tốc độ</button></MenuShell></TooltipProvider>));
  const trigger = document.querySelector<HTMLButtonElement>('[aria-label="Tốc độ đọc"]')!;
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  await act(() => trigger.click()); await wait();
  expect(trigger.getAttribute("aria-expanded")).toBe("true");
  const popup = document.getElementById(trigger.getAttribute("aria-controls")!);
  expect(popup?.getAttribute("role")).toBe("dialog");
  expect(popup?.textContent).toContain("Chọn tốc độ");
  await act(() => { expect(dismissTopLayer()).toBe(true); }); await wait();
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
});
it("mục con trong bảng trình phát mở tại chỗ; Back khép con rồi mới khép bảng", async () => {
  await act(() => root.render(<MenuShell label="Thêm tuỳ chọn" trigger="…"><MenuShell label="Nhạc nền" caption="Nhạc nền" trigger="Tắt" look="row"><button>Nhạc của tôi</button></MenuShell></MenuShell>));
  await act(() => document.querySelector<HTMLButtonElement>('[aria-label="Thêm tuỳ chọn"]')!.click()); await wait();
  await act(() => document.querySelector<HTMLButtonElement>('[aria-label="Nhạc nền"]')!.click()); await wait();
  expect(document.querySelectorAll('[role="dialog"][data-state="open"]')).toHaveLength(1);
  expect(document.querySelector('[aria-label="Nhạc nền"]')!.getAttribute("aria-expanded")).toBe("true");
  await act(() => { expect(dismissTopLayer()).toBe(true); }); await wait();
  expect(document.querySelector('[aria-label="Nhạc nền"]')!.getAttribute("aria-expanded")).toBe("false");
  expect(document.querySelectorAll('[role="dialog"][data-state="open"]')).toHaveLength(1);
  await act(() => { expect(dismissTopLayer()).toBe(true); }); await wait();
  expect(document.querySelectorAll('[role="dialog"][data-state="open"]')).toHaveLength(0);
});
