// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { dismissTopLayer } from "@/android/backLayers";
import { Sheet } from "./ui";
import { ActionMenu } from "./ActionMenu";

let root: Root;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("max-width"), addEventListener() {}, removeEventListener() {} }));
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.unstubAllGlobals(); });
const wait = () => act(() => new Promise(resolve => setTimeout(resolve, 40)));
function Example() {
  const [open, setOpen] = useState(false);
  return <Sheet open={open} onOpenChange={setOpen} title="Hẹn giờ" trigger={<button>Mở</button>} footer={<button>Đặt giờ</button>}><p>Chọn số phút.</p></Sheet>;
}
const dialog = () => document.querySelector<HTMLElement>('[role="dialog"][data-state="open"]');

it("vuốt tay nắm: dưới ngưỡng giữ bảng, huỷ cử chỉ trả vị trí, đủ 64 px đóng và trả tiêu điểm", async () => {
  await act(() => root.render(<Example />));
  const opener = document.querySelector<HTMLButtonElement>("button")!;
  await act(() => { opener.focus(); opener.click(); }); await wait();
  const grip = document.querySelector<HTMLElement>("[data-sheet-grip]")!;
  await act(() => {
    grip.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientY: 10 }));
    grip.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientY: 60 }));
  });
  expect(dialog()?.style.transform).toBe("translateY(50px)");
  await act(() => grip.dispatchEvent(new PointerEvent("pointercancel", { bubbles: true })));
  expect(dialog()?.style.transform).toBe("");
  expect(document.querySelector(".sheet-footer")?.parentElement).toBe(dialog());
  await act(() => {
    grip.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientY: 10 }));
    grip.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientY: 74 }));
  }); await wait();
  expect(dialog()).toBeNull(); expect(document.activeElement).toBe(opener);
});

it("Back đóng bảng trước trang; menu sách chọn mục chạy đúng một lần và đóng Sheet", async () => {
  await act(() => root.render(<Example />));
  await act(() => document.querySelector<HTMLButtonElement>("button")!.click()); await wait();
  await act(() => { expect(dismissTopLayer()).toBe(true); }); await wait();
  expect(dialog()).toBeNull();
  const selected = vi.fn();
  await act(() => root.render(<ActionMenu title="Việc với sách" trigger={<button>Thêm</button>}>
    <DropdownMenu.Item onSelect={selected}>Xuất MP3</DropdownMenu.Item>
  </ActionMenu>));
  await act(() => {
    const trigger = document.querySelector<HTMLButtonElement>("button")!;
    trigger.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 }));
  }); await wait();
  expect(dialog()).not.toBeNull();
  await act(() => document.querySelector<HTMLElement>('[role="menuitem"]')!.click()); await wait();
  expect(selected).toHaveBeenCalledOnce(); expect(dialog()).toBeNull();
});

it("vuốt nội dung chỉ đóng khi vùng cuộn đã ở đầu", async () => {
  await act(() => root.render(<Example />));
  await act(() => document.querySelector<HTMLButtonElement>("button")!.click()); await wait();
  const body = document.querySelector<HTMLElement>(".sheet-body")!;
  const touch = (name: string, y: number) => {
    const event = new Event(name, { bubbles: true, cancelable: true });
    Object.defineProperty(event, "touches", { value: [{ clientX: 20, clientY: y }] });
    body.dispatchEvent(event);
  };
  body.scrollTop = 20;
  await act(() => { touch("touchstart", 0); touch("touchmove", 90); touch("touchend", 90); });
  expect(dialog()).not.toBeNull();
  body.scrollTop = 0;
  await act(() => { touch("touchstart", 0); touch("touchmove", 90); touch("touchend", 90); }); await wait();
  expect(dialog()).toBeNull();
});

