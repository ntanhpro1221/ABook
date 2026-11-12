// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as Menu from "./DropdownMenu";
import { useFocusClearOfToasts } from "./ui";

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
