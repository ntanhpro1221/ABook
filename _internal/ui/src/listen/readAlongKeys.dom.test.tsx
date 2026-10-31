// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { textScript } from "./textScript";

vi.mock("@/listen/LibraryScreen", () => ({ usePlayListenBook: () => vi.fn() }));
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: null, jumpTo: vi.fn() }) }));
import { ReadAlongText } from "./ReadAlongText";

// Đọc theo không chỉ dùng được bằng chuột: "sửa cách đọc" (chuột phải / giữ ngón) có lối phím - phím menu hay Shift+F10 trên câu đang chọn
// mở bảng cho chữ đầu câu; Enter nghe từ câu ấy như cũ.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

it("Shift+F10 / phím menu trên một câu mở bảng sửa cách đọc, Enter nghe từ câu ấy", async () => {
  const onTap = vi.fn();
  const onWordMenu = vi.fn();
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(
    <ReadAlongText script={textScript(1, "Một", "Câu thứ nhất.\n\nCâu thứ hai.")} playingIndex={-1} focusIndex={0} onTap={onTap} onWordMenu={onWordMenu} headingClassName="" />,
  ));
  const sentence = host.querySelector<HTMLElement>('[data-sentence][data-index="1"]')!;
  await act(async () => sentence.focus());
  const press = (init: KeyboardEventInit) => {
    const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init });
    sentence.dispatchEvent(event);
    return event.defaultPrevented;
  };
  expect(press({ key: "F10", shiftKey: true })).toBe(true);
  expect(onWordMenu).toHaveBeenLastCalledWith(1, 0);
  expect(press({ key: "ContextMenu" })).toBe(true);
  expect(onWordMenu).toHaveBeenCalledTimes(2);
  expect(press({ key: "Enter" })).toBe(true);
  expect(onTap).toHaveBeenLastCalledWith(1, -1);
  expect(document.getElementById(sentence.getAttribute("aria-describedby") ?? "")?.textContent).toContain("Shift F10");
  // F10 trơn (không Shift) không phải phím menu.
  expect(press({ key: "F10" })).toBe(false);
  await act(async () => root.unmount());
  host.remove();
});
