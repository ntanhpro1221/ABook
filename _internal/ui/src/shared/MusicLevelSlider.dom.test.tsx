// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { MusicLevelSlider } from "./MusicLevelSlider";

// Value tests use a controllable animation; real motion has its own browser tests.
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
});
afterEach(() => vi.restoreAllMocks());

it.each(["reset", "keyboard"])("sends the old value again during a save via %s and holds it across an older ACK", async (action) => {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const save = vi.fn();
  const render = (value: number, saving: boolean) => root.render(<MusicLevelSlider value={value} saving={saving} onChange={save} />);
  const key = async (key: string) => act(async () => { host.querySelector('[role="slider"]')!.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true })); });
  try {
    await act(async () => render(-20, false));
    await key("ArrowRight");
    await act(async () => render(-20, true));
    if (action === "reset") await act(async () => host.querySelector("button")!.click());
    else await key("ArrowLeft");
    expect(save.mock.calls).toEqual([[-19], [-20]]);
    await act(async () => render(-19, true));
    expect(host.textContent).toContain("-20 dB (mặc định)");
    await act(async () => render(-20, false));
    expect(host.textContent).toContain("-20 dB (mặc định)");
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});

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
