// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Button } from "./ui";
import { useDestructiveConfirm } from "./DestructiveConfirm";

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); document.body.innerHTML = ""; });

it("locks a returned promise in the first frame, delays its spinner and releases on settlement", async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  let finish!: () => void;
  const work = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(<Button onClick={work}>Lưu</Button>));
  const button = host.querySelector("button")!;
  await act(async () => { button.click(); button.click(); });
  expect(work).toHaveBeenCalledTimes(1);
  expect(button.getAttribute("aria-busy")).toBe("true");
  expect(button.querySelector(".animate-spin")).toBeNull();
  await act(async () => vi.advanceTimersByTime(180));
  expect(button.querySelector(".animate-spin")).not.toBeNull();
  expect(button.querySelector(".animate-spin")!.parentElement!.classList.contains("hidden")).toBe(false);
  await act(async () => finish());
  expect(button.getAttribute("aria-busy")).toBeNull();
  await act(async () => root.unmount());
});

it("cancel and Escape never execute the destructive callback; acceptance executes once", async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const work = vi.fn();
  function Panel() {
    const { confirm, dialog } = useDestructiveConfirm();
    return <><Button onClick={() => confirm({title: "Xoá bài?", description: "Tên bài sẽ bị xoá.", run: work})}>Mở</Button>{dialog}</>;
  }
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(<Panel />));
  const open = host.querySelector("button")!;
  await act(async () => open.click());
  const dialog = document.querySelector('[role="dialog"]')!;
  const cancel = [...dialog.querySelectorAll("button")].find(item => item.textContent === "Huỷ")!;
  expect(document.activeElement).toBe(cancel);
  await act(async () => cancel.click());
  expect(work).not.toHaveBeenCalled();
  await act(async () => open.click());
  await act(async () => document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true})));
  expect(work).not.toHaveBeenCalled();
  await act(async () => open.click());
  const accept = [...document.querySelectorAll('button')].find(item => item.textContent === "Xoá")!;
  await act(async () => { accept.click(); accept.click(); });
  expect(work).toHaveBeenCalledTimes(1);
  await act(async () => root.unmount());
});
