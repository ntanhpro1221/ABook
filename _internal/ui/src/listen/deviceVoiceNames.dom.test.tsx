// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { VoiceSettings, type VoiceSettingsApi } from "./VoiceSettings";

it("renders device names and previews the exact selected engine voice", async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.setItem("abook.fold.voice.provider.device", "1");
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), finished: Promise.resolve() }) as unknown as Animation);
  const voices = [
    { id: "device:an", name: "Microsoft An", gender: "male", online: false },
    { id: "device:google", name: "Google ngoại tuyến 1", gender: "", online: false },
    { id: "device:samsung", name: "Samsung cần mạng", gender: "", online: true },
    { id: "device:oem", name: "OPPO ngoại tuyến", gender: "", online: false },
  ].map(voice => ({ ...voice, provider: "device" }));
  const sample = vi.fn(async (_voice: string, _text: string) => { throw new Error("Preview fixture"); });
  const api = { voices: async () => voices, online: async () => [], sample } as unknown as VoiceSettingsApi;
  const client = new QueryClient();
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<QueryClientProvider client={client}><VoiceSettings api={api} deviceHint="" /></QueryClientProvider>));
    const radios = [...host.querySelectorAll<HTMLButtonElement>('[role="radio"]')];
    expect(radios).toHaveLength(voices.length);
    expect(radios.map(row => voices.find(voice => row.textContent?.includes(voice.name))?.id)).toEqual(voices.map(voice => voice.id));
    expect(host.textContent).toContain("Theo bộ đọc hệ thống");
    expect(host.textContent).not.toContain("Mặc định");
    expect(radios.filter(row => row.getAttribute("aria-checked") === "true")).toHaveLength(1);
    for (const row of radios) {
      // Tên giọng qua OneLineFit: thu cỡ cho vừa một dòng hay xuống dòng, không bao giờ cắt "…".
      expect(row.querySelector("[data-one-line-fit]")).not.toBeNull();
      expect(row.querySelector(".truncate")).toBeNull();
      expect(row.parentElement!.className).toContain("gap-3");
    }
    for (const voice of voices) {
      const button = host.querySelector<HTMLButtonElement>(`button[aria-label="Nghe thử ${voice.name}"]`);
      expect(button).not.toBeNull();
      await act(async () => button!.click());
      expect(sample.mock.calls.at(-1)?.[0]).toBe(voice.id);
    }
    expect(host.textContent).not.toMatch(/Tiếng Việt [1-6]|vi-vn-x-/);
  } finally {
    await act(() => root.unmount()); client.clear(); host.remove(); localStorage.clear(); vi.restoreAllMocks();
  }
});
