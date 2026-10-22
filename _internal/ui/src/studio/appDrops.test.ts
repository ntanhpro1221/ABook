import { beforeEach, describe, expect, it, vi } from "vitest";

// Soát a98 F8: màn tạo sách của Studio nhận file kéo thả trong cửa sổ app, nghe cùng sự kiện `abook-drag` của vỏ Tauri như Thư viện.

const bridge = vi.hoisted(() => ({ target: new EventTarget() }));
vi.stubGlobal("window", bridge.target);

import { watchAppDropPaths } from "./appDrops";

const drag = (detail: unknown) => bridge.target.dispatchEvent(new CustomEvent("abook-drag", { detail }));

beforeEach(() => vi.stubGlobal("window", bridge.target));

describe("kéo thả trong cửa sổ app", () => {
  it("highlights while files hover, then hands over the real paths and stops listening when removed", () => {
    const calls: unknown[] = [];
    const stop = watchAppDropPaths({ hover: (on) => calls.push(["hover", on]), drop: (paths) => calls.push(["drop", paths]) });
    drag({ state: "enter" });
    drag({ state: "drop", paths: ["D:\\Truyện\\Tập 1.epub", "D:\\Truyện\\001.txt"] });
    expect(calls).toEqual([["hover", true], ["hover", false], ["drop", ["D:\\Truyện\\Tập 1.epub", "D:\\Truyện\\001.txt"]]]);
    stop();
    drag({ state: "enter" });
    expect(calls).toHaveLength(3);
  });

  it("drops the highlight when the drag leaves the window and ignores a drop with no paths", () => {
    const hover = vi.fn();
    const drop = vi.fn();
    const stop = watchAppDropPaths({ hover, drop });
    drag({ state: "enter" });
    drag({ state: "leave" });
    drag({ state: "drop" });
    expect(hover.mock.calls).toEqual([[true], [false], [false]]);
    expect(drop).toHaveBeenCalledWith([]);
    stop();
  });
});
