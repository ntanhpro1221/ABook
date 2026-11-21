// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi, type MockInstance } from "vitest";
import { eventually } from "@/testing/eventually";
import * as Menu from "./DropdownMenu";
import * as Popover from "./Popover";
import { Dialog, Sheet } from "./ui";

// Soát 18-11 lần 4: menu "Xếp theo" (modal={false}), ChipMenu, mọi Popover của web - bấm ra ngoài vừa đóng vừa mở cuốn sách / dòng nằm dưới.
// Qt (Backdrop) và Android (SortMenu, nền tấm) chỉ đóng. Ở web: lớp chặn trong suốt nằm ngay dưới bảng, phủ cả cửa sổ; Radix vẫn thấy cú nhấn "ra
// ngoài" (lớp ở ngoài cây của bảng) và tự đóng, còn cú bấm / hover / chuột phải / lăn dừng ở lớp chặn.

let root: Root, host: HTMLElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  documentListeners = vi.spyOn(document, "addEventListener");
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });

// Radix gắn bộ nghe "nhấn ra ngoài" (pointerdown trên document) sau một nhịp hẹn giờ: chờ tới khi đủ `layers` lớp đã gắn, không chờ một nhịp cố định.
let documentListeners: MockInstance<typeof document.addEventListener>;
const listening = (layers = 1) => until(() =>
  expect(documentListeners.mock.calls.filter(([type]) => type === "pointerdown").length).toBeGreaterThanOrEqual(layers));
const until = (check: () => void) => act(() => eventually(check));
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
  await listening();
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
  await listening();
  await act(() => { document.querySelector('[role="menu"]')!.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 1, pointerType: "mouse" })); });
  expect(document.querySelector('[role="menu"]')).not.toBeNull();
  expect(shield()).not.toBeNull();
});

it("the shield stops catching as soon as the menu starts closing", async () => {
  await act(() => root.render(<SortMenu under={() => undefined} />));
  await listening();
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
  await listening();
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
  await listening();
  expect(document.querySelector('[role="menu"]')).not.toBeNull();
  expect(shield()).toBeNull();
});

// Soát Chromium thật 18-11 (T1): menu đóng ngay ở pointerdown. Lớp chặn phải giữ tới hết CHÍNH cú nhấn ấy - click giả lập sau cú chạm, contextmenu
// sau chuột phải - không thì trình duyệt dò lại vị trí và phần còn lại của cú nhấn rơi xuống thẻ sách bên dưới.
it("the shield keeps catching until the press that closed the menu has finished", async () => {
  await act(() => root.render(<SortMenu under={() => undefined} />));
  await listening();
  const cover = shield()!;
  await act(() => { cover.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, button: 0, pointerId: 1, pointerType: "touch" })); });
  expect(document.querySelector('[role="menu"]')).toBeNull();          // menu đã đóng ngay ở pointerdown
  expect(cover.isConnected).toBe(true);                                // bảng đã rời cây, lớp vẫn còn
  expect(cover.style.pointerEvents).toBe("auto");                      // và vẫn bắt
  cover.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, cancelable: true, pointerId: 1, pointerType: "touch" }));
  expect(cover.style.pointerEvents).toBe("auto");
  cover.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  await until(() => expect(cover.isConnected).toBe(false));
  expect(cover.isConnected).toBe(false);                               // cú nhấn xong: gỡ lớp
});

it("a right press outside: the shield catches the contextmenu that follows on release, then goes", async () => {
  await act(() => root.render(<SortMenu under={() => undefined} />));
  await listening();
  const cover = shield()!;
  await act(() => { cover.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, button: 2, pointerId: 1, pointerType: "mouse" })); });
  expect(cover.isConnected).toBe(true);
  const context = new MouseEvent("contextmenu", { bubbles: true, cancelable: true, button: 2 });
  cover.dispatchEvent(context);
  expect(context.defaultPrevented).toBe(true);                         // không bật menu chuột phải của trình duyệt
  await until(() => expect(cover.isConnected).toBe(false));
  expect(cover.isConnected).toBe(false);
});

it("a press that never ends in a click lets the shield go after a second", async () => {
  vi.useFakeTimers();   // chỉ đồng hồ giả: máy bận không được đẩy mốc 1 giây
  try {
    await act(() => root.render(<SortMenu under={() => undefined} />));
    await act(() => vi.advanceTimersByTimeAsync(1));
    const cover = shield()!;
    await act(() => { cover.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, button: 0, pointerId: 1, pointerType: "touch" })); });
    expect(cover.isConnected).toBe(true);
    await act(() => vi.advanceTimersByTimeAsync(999));
    expect(cover.isConnected).toBe(true);
    await act(() => vi.advanceTimersByTimeAsync(2));
    expect(cover.isConnected).toBe(false);
  } finally { vi.useRealTimers(); }
});

// Soát 18-11 T2: Popover trong hộp thoại ("Phát trên" -> "Hẹn giờ"): bấm ngoài bảng nhưng trong hộp chỉ đóng bảng, hộp đứng yên - như Qt / Android.
it.each(["dialog", "sheet"] as const)("a popover inside a %s: a press on its shield closes only the popover", async kind => {
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  const closed = vi.fn();
  function Remote() {
    const [sleep, setSleep] = useState(false);
    const body = <>
      <button type="button">Tạm dừng</button>
      <Popover.Root open={sleep} onOpenChange={setSleep}>
        <Popover.Trigger>Hẹn giờ</Popover.Trigger>
        <Popover.Portal><Popover.Content aria-label="Hẹn giờ ngủ" style={{ zIndex: 60 }}>15 phút</Popover.Content></Popover.Portal>
      </Popover.Root>
    </>;
    return kind === "dialog"
      ? <Dialog open onOpenChange={closed} title="Phát trên">{body}</Dialog>
      : <Sheet open onOpenChange={closed} title="Phát trên" trigger={<button>Mở</button>}>{body}</Sheet>;
  }
  await act(() => root.render(<Remote />));
  await listening();
  await until(() => expect(document.querySelector('[role="dialog"]')!.contains(document.activeElement)).toBe(true));
  // Mở bảng sau khi hộp đã nhận tiêu điểm (hộp chuyển tiêu điểm vào trong lúc mở - bảng mở sẵn sẽ tự đóng vì mất tiêu điểm).
  await act(() => { [...document.querySelectorAll("button")].find(button => button.textContent === "Hẹn giờ")!.click(); });
  await listening(2);
  expect(document.querySelector('[aria-label="Hẹn giờ ngủ"]')).not.toBeNull();
  const cover = shield()!;
  expect(cover).not.toBeNull();
  await act(() => { press(cover); });
  await until(() => expect(document.querySelector('[aria-label="Hẹn giờ ngủ"]')).toBeNull());
  expect(document.querySelector('[aria-label="Hẹn giờ ngủ"]')).toBeNull();      // bảng đóng
  expect(closed).not.toHaveBeenCalled();                                         // hộp không đóng
  expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  expect(shield()).toBeNull();
});

it("a popover inside a popover: a press on the inner shield closes only the inner one", async () => {
  function Nested() {
    const [outer, setOuter] = useState(true);
    const [inner, setInner] = useState(true);
    return <Popover.Root open={outer} onOpenChange={setOuter}>
      <Popover.Trigger>Ngoài</Popover.Trigger>
      <Popover.Portal><Popover.Content aria-label="Ngoài" style={{ zIndex: 50 }}>
        <Popover.Root open={inner} onOpenChange={setInner}>
          <Popover.Trigger>Trong</Popover.Trigger>
          <Popover.Portal><Popover.Content aria-label="Trong" style={{ zIndex: 60 }}>x</Popover.Content></Popover.Portal>
        </Popover.Root>
      </Popover.Content></Popover.Portal>
    </Popover.Root>;
  }
  await act(() => root.render(<Nested />));
  await listening(2);
  const covers = document.querySelectorAll<HTMLElement>("[data-outside-shield]");
  expect(covers).toHaveLength(2);
  const innerCover = [...covers].find(cover => cover.style.zIndex === "60")!;
  await act(() => { press(innerCover); });
  await until(() => expect(document.querySelector('[aria-label="Trong"]')).toBeNull());
  expect(document.querySelector('[aria-label="Trong"]')).toBeNull();
  expect(document.querySelector('[aria-label="Ngoài"]')).not.toBeNull();
});
