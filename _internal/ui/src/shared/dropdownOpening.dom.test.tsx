// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as Menu from "./DropdownMenu";
import { Sheet, useFocusClearOfToasts } from "./ui";

let root: Root, host: HTMLElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });

it("requires a press inside a menu before release selects; keyboard selection still works", async () => {
  const selected = vi.fn();
  await act(() => root.render(<Menu.Root defaultOpen><Menu.Trigger>Open</Menu.Trigger><Menu.Portal>
    <Menu.Content><Menu.Item onSelect={selected}>Read</Menu.Item></Menu.Content>
  </Menu.Portal></Menu.Root>));
  const item = document.querySelector<HTMLElement>('[role="menuitem"]')!;
  await act(() => { item.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, cancelable: true, pointerId: 1 })); });
  expect(selected).not.toHaveBeenCalled();
  await act(() => {
    item.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 1 }));
    item.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 1 }));
    item.click();
  });
  expect(selected).toHaveBeenCalledTimes(1);
  await act(() => root.render(<Menu.Root open><Menu.Trigger>Open</Menu.Trigger><Menu.Content>
    <Menu.Item onSelect={selected}>Read</Menu.Item>
  </Menu.Content></Menu.Root>));
  await act(() => { document.querySelector<HTMLElement>('[role="menuitem"]')!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true })); });
  expect(selected).toHaveBeenCalledTimes(2);
});

// gateflake 19-11: pointerdown on the trigger opens the menu (a Sheet on phones); the same tap's click is dispatched
// to whatever lies under the finger at release - an item of the menu that just opened - and selected it.
it("the opening tap's click never selects an item; a real tap inside still does", async () => {
  const selected = vi.fn();
  await act(() => root.render(<Menu.Root><Menu.Trigger>Open</Menu.Trigger><Menu.Portal>
    <Menu.Content><Menu.Item onSelect={selected}>Hồ sơ mới</Menu.Item></Menu.Content>
  </Menu.Portal></Menu.Root>));
  const trigger = document.querySelector<HTMLElement>('[aria-haspopup="menu"]')!;
  await act(() => { trigger.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, pointerId: 7, pointerType: "touch", button: 0 })); });
  const item = document.querySelector<HTMLElement>('[role="menuitem"]')!;
  expect(item).not.toBeNull();
  await act(() => {
    trigger.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 7, pointerType: "touch" }));
    item.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, detail: 1 }));
  });
  expect(selected).not.toHaveBeenCalled();
  expect(document.querySelector('[role="menuitem"]')).not.toBeNull();
  await act(() => {
    item.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 8, pointerType: "touch" }));
    item.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 8, pointerType: "touch" }));
    item.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, detail: 1 }));
  });
  expect(selected).toHaveBeenCalledTimes(1);
});

it("a Sheet ignores a pointer click whose press began outside it (opening tap); presses inside and keyboard work", async () => {
  Object.defineProperty(window, "matchMedia", { configurable: true, value: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) });
  const pressed = vi.fn();
  await act(() => root.render(<Sheet open onOpenChange={() => undefined} title="Việc với sách"><button onClick={pressed}>Hồ sơ mới</button></Sheet>));
  const button = [...document.querySelectorAll("button")].find((b) => b.textContent === "Hồ sơ mới")!;
  await act(() => { button.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, detail: 1 })); });
  expect(pressed).not.toHaveBeenCalled();
  await act(() => {
    button.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 3, pointerType: "touch" }));
    button.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, detail: 1 }));
  });
  expect(pressed).toHaveBeenCalledTimes(1);
  await act(() => { button.click(); });
  expect(pressed).toHaveBeenCalledTimes(2);
});

it("does not scroll the page behind a fixed surface to clear a toast", async () => {
  vi.spyOn(window, "requestAnimationFrame").mockImplementation(callback => { callback(0); return 1; });
  const scroll = vi.fn();
  Object.defineProperty(document.documentElement, "scrollBy", { configurable: true, value: scroll });
  function Fixture() { useFocusClearOfToasts(); return <><div data-sonner-toast="" /><div role="dialog" tabIndex={-1} style={{ position: "fixed" }}><button>Inside</button></div></>; }
  await act(() => root.render(<Fixture />));
  const box = { top: 500, bottom: 600, left: 0, right: 400, width: 400, height: 100, x: 0, y: 500, toJSON() {} };
  vi.spyOn(document.querySelector('[data-sonner-toast]')!, "getBoundingClientRect").mockReturnValue(box);
  const surface = document.querySelector<HTMLElement>('[role="dialog"]')!;
  vi.spyOn(surface, "getBoundingClientRect").mockReturnValue(box);
  surface.focus();
  expect(scroll).not.toHaveBeenCalled();
  const button = surface.querySelector('button')!;
  vi.spyOn(button, "getBoundingClientRect").mockReturnValue(box);
  button.focus();
  expect(scroll).not.toHaveBeenCalled();
});
