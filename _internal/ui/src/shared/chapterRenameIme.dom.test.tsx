// @vitest-environment happy-dom
// Đổi tên chương lúc thêm sách, gõ bằng bộ gõ có khung soạn (IME): Esc / Enter của bộ gõ (huỷ / chốt chữ đang soạn) không đóng ô và không bỏ tên đang gõ.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ChapterPreview } from "./ChapterPreview";

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });

it("Esc / Enter khi đang soạn chữ giữ ô sửa; Enter thường lưu tên đã gõ", async () => {
  const onRename = vi.fn();
  await act(() => root.render(
    <ChapterPreview chapters={[{ title: "Chương 1", words: 10, chars: 50 }]} choice={{ picked: new Set([1]), names: {}, onPick: vi.fn(), onRename }} />,
  ));
  await act(() => host.querySelector<HTMLButtonElement>('[data-rename="1"]')!.click());
  const input = host.querySelector<HTMLInputElement>("input[data-escape-local]")!;
  input.value = "Mở đầu";
  for (const key of ["Escape", "Enter"]) {
    await act(() => { input.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, isComposing: true })); });
    expect(host.querySelector("input[data-escape-local]")).toBe(input);
    expect(onRename).not.toHaveBeenCalled();
  }
  await act(() => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true })); });
  expect(onRename).toHaveBeenCalledWith({ index: 1, title: "Chương 1" }, "Mở đầu");
});

it("Esc của bộ gõ đang soạn chữ không đóng lớp đang mở (bộ bắt Esc chung của app); Esc thường thì đóng", async () => {
  const { MotionHashRouter } = await import("./MotionRouter");
  const { installBackOrder } = await import("./backOrder");
  const { useBackLayer } = await import("./backStack");
  const stop = installBackOrder();
  const onBack = vi.fn();
  function Layer() {
    useBackLayer(true, onBack);
    return <input aria-label="Tên" />;
  }
  try {
    await act(() => root.render(<MotionHashRouter><Layer /></MotionHashRouter>));
    const input = host.querySelector("input")!;
    input.focus();
    await act(() => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true, isComposing: true })); });
    expect(onBack).not.toHaveBeenCalled();
    await act(() => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })); });
    expect(onBack).toHaveBeenCalledTimes(1);
  } finally {
    stop();
  }
});

it("hộp thoại có ô nhập: Esc của bộ gõ đang soạn chữ không đóng hộp; Esc thường thì đóng", async () => {
  const { MotionHashRouter } = await import("./MotionRouter");
  const { installBackOrder } = await import("./backOrder");
  const { Dialog, TooltipProvider } = await import("./ui");
  const stop = installBackOrder();
  const onOpenChange = vi.fn();
  try {
    await act(() => root.render(<MotionHashRouter><TooltipProvider><Dialog open onOpenChange={onOpenChange} title="Đổi tên"><input aria-label="Tên" /></Dialog></TooltipProvider></MotionHashRouter>));
    const input = document.querySelector<HTMLInputElement>('[role="dialog"] input')!;
    input.focus();
    await act(() => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true, isComposing: true })); });
    expect(onOpenChange).not.toHaveBeenCalled();
    await act(() => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })); });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  } finally {
    stop();
  }
});
