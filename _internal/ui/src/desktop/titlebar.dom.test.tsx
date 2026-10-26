// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TitleBar } from "./TitleBar";
import { chromeStateEvent } from "./windowChrome";

let root: Root;
let host: HTMLDivElement;
const action = vi.fn();
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  window.__ABOOK_CHROME__ = { action, state: { maximized: false, focused: true, snapHovered: false, snapPressed: false } };
  action.mockClear();
});
afterEach(async () => { await act(() => root.unmount()); host.remove(); delete window.__ABOOK_CHROME__; });
const mount = async () => { await act(() => root.render(<TitleBar toggle={<button aria-label="Thu gọn">Thu gọn</button>} />)); };
const button = (label: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!;

describe("caption strip", () => {
  it("Vietnamese labels and caption actions stay separate from the sidebar toggle", async () => {
    await mount();
    expect([...host.querySelectorAll(".caption-button")].map(button => button.getAttribute("aria-label"))).toEqual(["Thu nhỏ", "Phóng to", "Đóng"]);
    for (const label of ["Thu nhỏ", "Phóng to", "Đóng"]) await act(() => button(label).click());
    expect(action.mock.calls.map(call => call[0])).toEqual(["minimize", "toggleMaximize", "close"]);
    expect(host.querySelectorAll(".titlebar-toggle button")).toHaveLength(1);
    expect(host.textContent).not.toContain("ABook");
  });

  it("only the empty strip is a native drag region", async () => {
    await mount();
    const regions = host.querySelectorAll("[data-tauri-drag-region]");
    expect(regions).toHaveLength(1);
    expect(regions[0].getAttribute("data-tauri-drag-region")).toBe("");
    expect(regions[0].textContent).toBe("");
    for (const element of host.querySelectorAll("button")) expect(element.closest("[data-tauri-drag-region]")).toBeNull();
  });

  it("OS maximize/restore updates labels while keeping both glyphs mounted for the morph", async () => {
    await mount();
    const maximize = host.querySelector('[data-glyph="maximize"]');
    const restore = host.querySelector('[data-glyph="restore"]');
    await act(() => { window.__ABOOK_CHROME__!.state.maximized = true; window.dispatchEvent(new Event(chromeStateEvent)); });
    expect(button("Khôi phục")).not.toBeNull();
    expect(host.querySelector('[data-glyph="maximize"]')).toBe(maximize);
    expect(host.querySelector('[data-glyph="restore"]')).toBe(restore);
    expect(maximize?.getAttribute("data-shown")).toBe("false");
    expect(restore?.getAttribute("data-shown")).toBe("true");
    await act(() => button("Khôi phục").click());
    expect(action).toHaveBeenCalledWith("toggleMaximize");
    await act(() => { window.__ABOOK_CHROME__!.state.maximized = false; window.dispatchEvent(new Event(chromeStateEvent)); });
    expect(button("Phóng to")).not.toBeNull();
  });

  it("native Snap hover and pressed state survive the flyout taking DOM focus", async () => {
    await mount();
    await act(() => {
      Object.assign(window.__ABOOK_CHROME__!.state, { focused: false, snapHovered: true, snapPressed: true });
      window.dispatchEvent(new Event(chromeStateEvent));
    });
    expect(host.querySelector("header")?.dataset.focused).toBe("false");
    expect(button("Phóng to").dataset.hovered).toBe("true");
    expect(button("Phóng to").dataset.pressed).toBe("true");
  });

  it("does not add window controls to a normal browser or remote Studio", async () => {
    delete window.__ABOOK_CHROME__;
    await mount(); expect(host.children).toHaveLength(0);
  });
});
