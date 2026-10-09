import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setApiTransport } from "@/studio/api";

// Thư viện máy tính nhận file kéo thả (cửa sổ app: vỏ Tauri phát `abook-drag` kèm đường dẫn thật - main.rs) và chọn nhiều file bằng hộp thoại của Windows.

const bridge = vi.hoisted(() => ({ target: new EventTarget() }));
vi.stubGlobal("window", bridge.target);

import { desktopTextImport } from "./httpSource";

const drag = (detail: unknown) => bridge.target.dispatchEvent(new CustomEvent("abook-drag", { detail }));

beforeEach(() => vi.stubGlobal("window", bridge.target));
afterEach(() => setApiTransport(null));

describe("kéo thả trong cửa sổ app", () => {
  it("shows the overlay while files hover and hands over the dropped paths, naming what ABook cannot read", () => {
    const calls: unknown[] = [];
    const stop = desktopTextImport(true).watchDrops!({ hover: (on) => calls.push(["hover", on]), drop: (items) => calls.push(["drop", items]) });
    drag({ state: "enter" });
    drag({ state: "drop", paths: ["D:\\Truyện\\Tập 1.epub", "D:\\Ảnh\\bìa.png"] });
    expect(calls[0]).toEqual(["hover", true]);
    expect(calls[1]).toEqual(["hover", false]);
    const items = (calls[2] as [string, { name: string; choice?: unknown; error?: string }[]])[1];
    expect(items[0]).toEqual({ name: "Tập 1.epub", choice: { ref: "D:\\Truyện\\Tập 1.epub", name: "Tập 1.epub" } });
    expect(items[1].error).toContain(".png");
    stop();
    drag({ state: "enter" });
    expect(calls).toHaveLength(3); // đã gỡ
  });

  it("drops the overlay when the drag leaves the window", () => {
    const hover = vi.fn();
    const stop = desktopTextImport(true).watchDrops!({ hover, drop: () => undefined });
    drag({ state: "enter" });
    drag({ state: "leave" });
    expect(hover.mock.calls).toEqual([[true], [false]]);
    stop();
  });
});

describe("chọn nhiều file bằng hộp thoại", () => {
  it("takes every file the dialog returns, not just one", async () => {
    setApiTransport(async () => ({ paths: ["D:\\a\\Tập 1.epub", "D:\\a\\Tập 2.docx", "D:\\a\\Tập 3.txt"] }));
    const items = await desktopTextImport(true).chooseMany!();
    expect(items.map((item) => item.name)).toEqual(["Tập 1.epub", "Tập 2.docx", "Tập 3.txt"]);
    expect(items.every((item) => "choice" in item)).toBe(true);
  });

  it("is only there in the app window (a browser tab has no file dialog)", () => {
    expect(desktopTextImport(false).chooseMany).toBeUndefined();
    expect(desktopTextImport(false).watchDrops).toBeDefined();
  });
});
