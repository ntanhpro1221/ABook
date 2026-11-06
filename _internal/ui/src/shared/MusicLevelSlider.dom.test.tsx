// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { MusicLevelSlider } from "./MusicLevelSlider";

// Value tests use a controllable animation; real motion has its own browser tests.
beforeEach(() => { vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null, finished: Promise.resolve() }) as unknown as Animation); });
afterEach(() => vi.restoreAllMocks());

it("reset saves the default once, including a book's fractional level", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const save = vi.fn();
  try {
    await act(async () => root.render(<MusicLevelSlider value={-18.5} onChange={save} />));
    const reset = host.querySelector("button")!;
    expect(reset.textContent).toBe("Về mặc định");
    await act(async () => reset.click());
    expect(save.mock.calls).toEqual([[-20]]);
    expect(host.textContent).toContain("-20 dB (mặc định)");
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});

it("disabled slider cannot reset or change via keyboard", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const save = vi.fn();
  try {
    await act(async () => root.render(<MusicLevelSlider value={-18} disabled onChange={save} />));
    expect(host.querySelector("button")).toBeNull();
    const thumb = host.querySelector('[role="slider"]')!;
    await act(async () => thumb.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
    expect(save).not.toHaveBeenCalled();
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});
