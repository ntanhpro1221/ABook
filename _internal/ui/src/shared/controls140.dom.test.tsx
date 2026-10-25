// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Button, DecisionButton, Dialog, DialogActions, Select, SelectionMark, TimeSelect } from "./ui";

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.unstubAllGlobals(); });

it("Select giữ nhãn, ref, lựa chọn dài, disabled và sự kiện đổi của hệ thống", async () => {
  const change = vi.fn(), ref = { current: null as HTMLSelectElement | null };
  await act(() => root.render(<Select ref={ref} aria-label="Thể loại" defaultValue="long" onChange={change}>
    <option value="short">Truyện</option><option value="long">Dị giới / kỳ ảo phương Tây</option>
  </Select>));
  const select = host.querySelector("select")!;
  expect(ref.current).toBe(select); expect(select.value).toBe("long");
  expect(select.getAttribute("aria-label")).toBe("Thể loại"); expect(select.classList.contains("shared-select")).toBe(true);
  await act(() => { select.value = "short"; select.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(change).toHaveBeenCalledOnce();
  await act(() => root.render(<Select disabled aria-label="Thể loại"><option>Truyện</option></Select>));
  expect(select.disabled).toBe(true);
});

it("TimeSelect dùng cùng Select, giữ giờ lẻ và không đổi khi đang chờ xác nhận", async () => {
  const change = vi.fn();
  await act(() => root.render(<TimeSelect label="Từ" value="22:10" onChange={change} ariaDisabled />));
  const select = host.querySelector("select")!;
  expect(select.value).toBe("22:10"); expect(select.classList.contains("shared-select")).toBe(true);
  await act(() => { select.value = "22:15"; select.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(change).not.toHaveBeenCalled();
});

it("dấu chọn chuyển độ mờ tại chỗ, quyết định có icon và cỡ Button", async () => {
  const choose = vi.fn();
  await act(() => root.render(<><SelectionMark selected={false} /><DecisionButton onClick={choose}>Ổn</DecisionButton></>));
  const mark = host.querySelector("svg")!;
  expect(mark.classList.contains("opacity-0")).toBe(true);
  await act(() => root.render(<><SelectionMark selected /><DecisionButton onClick={choose}>Ổn</DecisionButton></>));
  expect(host.querySelector("svg")).toBe(mark); expect(mark.classList.contains("opacity-100")).toBe(true);
  const decision = host.querySelector<HTMLButtonElement>("[data-decision]")!;
  expect(decision.querySelector("svg")).not.toBeNull(); expect(decision.classList.contains("shared-button")).toBe(true);
  await act(() => decision.click()); expect(choose).toHaveBeenCalledOnce();
});

it.each([false, true])("Dialog phone=%s: một cách đóng, chân hộp ngoài vùng cuộn, submit vẫn đúng form", async phone => {
  vi.stubGlobal("matchMedia", () => ({ matches: phone, addEventListener() {}, removeEventListener() {} }));
  const submit = vi.fn();
  function Example() {
    const [open, setOpen] = useState(true);
    return <Dialog open={open} onOpenChange={setOpen} title="Sửa tên" footer={<DialogActions><Button>Thôi</Button><Button type="submit" form="name-form" variant="primary">Lưu</Button></DialogActions>}>
      <form id="name-form" onSubmit={event => { event.preventDefault(); submit(); }}><input aria-label="Tên mới" /></form>
    </Dialog>;
  }
  await act(() => root.render(<Example />));
  const dialog = document.querySelector('[role="dialog"]')!;
  expect(dialog.querySelectorAll('button[aria-label="Đóng"]')).toHaveLength(1);
  expect(dialog.querySelectorAll(".lucide-x")).toHaveLength(phone ? 0 : 1);
  expect(Boolean(dialog.querySelector("[data-sheet-handle]"))).toBe(phone);
  const footer = dialog.querySelector(".surface-footer")!;
  expect(footer.parentElement).toBe(dialog); expect(footer.closest(".sheet-body, .dialog-body")).toBeNull();
  await act(() => footer.querySelector<HTMLButtonElement>('button[type="submit"]')!.click());
  expect(submit).toHaveBeenCalledOnce();
  await act(() => dialog.querySelector<HTMLButtonElement>('button[aria-label="Đóng"]')!.click());
  expect(document.querySelector('[role="dialog"][data-state="open"]')).toBeNull();
});

it("tay nắm kéo rồi trả về không biến thành cú bấm đóng; cú bấm kế tiếp vẫn đóng được", async () => {
  vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener() {}, removeEventListener() {} }));
  const close = vi.fn();
  await act(() => root.render(<Dialog open onOpenChange={close} title="Chọn giờ" />));
  const handle = document.querySelector<HTMLButtonElement>("[data-sheet-handle]")!;
  await act(() => {
    handle.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientY: 10 }));
    handle.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientY: 30 }));
    handle.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientY: 10 }));
    handle.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientY: 10 }));
    handle.click();
  });
  expect(close).not.toHaveBeenCalled();
  await act(() => handle.click());
  expect(close).toHaveBeenCalledWith(false);
});
