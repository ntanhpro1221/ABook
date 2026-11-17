// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AudioFxPanel } from "./AudioFxPanel";
import { DEFAULT_FX, selectAudioBook, setAudioFx } from "./audioFx";

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), finished: Promise.resolve() }) as unknown as Animation);
  localStorage.clear(); selectAudioBook(""); setAudioFx({ ...DEFAULT_FX, skipSilence: true });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); localStorage.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });

it("joins the silence threshold and dBFS with a real no-break space, not the six characters backslash-u00a0", async () => {
  await act(() => root.render(<AudioFxPanel setVolume={() => {}} />));
  const text = host.textContent ?? "";
  expect(text).not.toContain(String.raw`\u00a0`);
  expect(text).toMatch(/\d\u00a0dBFS/);
});
