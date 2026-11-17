// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as Menu from "./DropdownMenu";
import * as Popover from "./Popover";

// Soát 18-11 lần 4: menu "Xếp theo" (modal={false}), ChipMenu, mọi Popover của web - bấm ra ngoài vừa đóng vừa mở cuốn sách / dòng nằm dưới.
// Qt (Backdrop) và Android (SortMenu, nền tấm) chỉ đóng. Ở web: lớp chặn trong suốt nằm ngay dưới bảng, phủ cả cửa sổ; Radix vẫn thấy cú nhấn "ra
// ngoài" (lớp ở ngoài cây của bảng) và tự đóng, còn cú bấm / hover / chuột phải / lăn dừng ở lớp chặn.

let root: Root, host: HTMLElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });

// Radix gắn bộ nghe "nhấn ra ngoài" sau một nhịp setTimeout(0).
const tick = () => act(() => new Promise<void>(resolve => setTimeout(resolve, 0)));
const shield = () => document.querySelector<HTMLElement>("[data-outside-shield]");

function press(target: Element, init: PointerEventInit = {}) {
  target.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, button: 0, pointerId: 1, pointerType: "mouse", ...init }));
  target.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, cancelable: true, button: 0, pointerId: 1, pointerType: "mouse", ...init }));
  target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

function SortMenu({ under }: { under: () => void }) {
  const [open, setOpen] = useState(true);
  return <>
    <button type="button" data-under onClick={under}>Cuốn sách</button>
    <Menu.Root modal={false} open={open} onOpenChange={setOpen}>
      <Menu.Trigger>Xếp theo</Menu.Trigger>
      <Menu.Portal><Menu.Content style={{ zIndex: 60 }}><Menu.Item>Mới nghe</Menu.Item></Menu.Content></Menu.Portal>
    </Menu.Root>
  </>;
}

it("a non-modal menu lays a full-window shield right under itself; a press on it only closes the menu", async () => {
  const under = vi.fn();
  await act(() => root.render(<SortMenu under={under} />));
  await tick();
  const cover = shield()!;
  expect(cover).not.toBeNull();
  const wrapper = document.querySelector("[data-radix-popper-content-wrapper]")!;
  expect(cover.nextElementSibling).toBe(wrapper);                    // ngay dưới bảng trong thứ tự vẽ
  expect(cover.parentElement).toBe(document.body);
  expect(cover.style.position).toBe("fixed");
  for (const side of [cover.style.top, cover.style.right, cover.style.bottom, cover.style.left]) expect(parseFloat(side)).toBe(0);
  expect(cover.style.zIndex).toBe("60");
  expect(cover.style.pointerEvents).toBe("auto");
  expect(cover.getAttribute("aria-hidden")).toBe("true");
  // Chuột phải và lăn ra ngoài không mở menu chuột phải / không cuộn trang dưới
  const context = new MouseEvent("contextmenu", { bubbles: true, cancelable: true });
  cover.dispatchEvent(context);
  expect(context.defaultPrevented).toBe(true);
  const wheel = new WheelEvent("wheel", { bubbles: true, cancelable: true, deltaY: 120 });
  cover.dispatchEvent(wheel);
  expect(wheel.defaultPrevented).toBe(true);
  await act(() => { press(cover); });
  expect(document.querySelector('[role="menu"]')).toBeNull();          // Radix đóng menu: cú nhấn nằm ngoài bảng
  expect(under).not.toHaveBeenCalled();
  expect(shield()).toBeNull();                                         // đóng xong thì gỡ lớp chặn
  // Đối chứng: không còn menu thì cú bấm tới nút như thường
  await act(() => { press(document.querySelector("[data-under]")!); });
  expect(under).toHaveBeenCalledTimes(1);
});

it("a press inside the menu does not reach the shield and keeps the menu open", async () => {
  await act(() => root.render(<SortMenu under={() => undefined} />));
  await tick();
  await act(() => { document.querySelector('[role="menu"]')!.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 1, pointerType: "mouse" })); });
  expect(document.querySelector('[role="menu"]')).not.toBeNull();
  expect(shield()).not.toBeNull();
});

it("the shield stops catching as soon as the menu starts closing", async () => {
  await act(() => root.render(<SortMenu under={() => undefined} />));
  await tick();
  const content = document.querySelector<HTMLElement>('[role="menu"]')!;
  content.setAttribute("data-state", "closed");
  await act(() => Promise.resolve());
  expect(shield()!.style.pointerEvents).toBe("none");
});

it("a popover only closes on a press outside, like the menus", async () => {
  const under = vi.fn();
  function Volume() {
    const [open, setOpen] = useState(true);
    return <>
      <button type="button" data-under onClick={under}>Phát</button>
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger>Âm lượng</Popover.Trigger>
        <Popover.Portal><Popover.Content aria-label="Âm lượng">70 %</Popover.Content></Popover.Portal>
      </Popover.Root>
    </>;
  }
  await act(() => root.render(<Volume />));
  await tick();
  const cover = shield()!;
  expect(cover.nextElementSibling).toBe(document.querySelector("[data-radix-popper-content-wrapper]"));
  expect(cover.style.zIndex).toBe("50");                               // bảng không đặt z-index: như lớp z-50 của app
  await act(() => { press(cover); });
  expect(document.querySelector('[aria-label="Âm lượng"][role="dialog"]')).toBeNull();
  expect(under).not.toHaveBeenCalled();
  expect(shield()).toBeNull();
});

it("a menu that is not portalled to the body (inside a phone sheet) gets no shield: the sheet's scrim already stops the outside", async () => {
  await act(() => root.render(<Menu.Root open modal={false}><Menu.Trigger>Open</Menu.Trigger>
    <Menu.Content><Menu.Item>Read</Menu.Item></Menu.Content></Menu.Root>));
  await tick();
  expect(document.querySelector('[role="menu"]')).not.toBeNull();
  expect(shield()).toBeNull();
});
