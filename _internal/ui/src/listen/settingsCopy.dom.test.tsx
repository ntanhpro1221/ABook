// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { VoiceSpeedSetting } from "./VoiceSpeedSetting";
import { VOICE_SPEED_OPTIONS, voiceSpeedDescription } from "./voiceSpeed";
import { VOICE_SPEED_KEY } from "./vieneuModule";
import { ReadAloudStorage, STORAGE_KEY } from "./ReadAloudStorage";

vi.mock("./VieneuModuleCard", () => ({ desktopSupertonic: {}, useModuleStatus: () => ({ working: false }) }));
let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear();
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: 0 } } });
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });
const render = async (view: ReactNode) => { await act(() => root.render(<QueryClientProvider client={client}>{view}</QueryClientProvider>)); };

for (const { value, label } of VOICE_SPEED_OPTIONS) it(`Hiệu năng shows only the current label ${label} in its summary`, async () => {
  client.setQueryData(VOICE_SPEED_KEY, { choice: value, voices: [] });
  await render(<VoiceSpeedSetting />);
  const fold = host.querySelector<HTMLButtonElement>('button[aria-expanded]')!;
  expect(fold.textContent).toBe(`Hiệu năng${label}`);
  const explanation = voiceSpeedDescription(value);
  expect(fold.textContent).not.toContain(explanation);
  expect(host.querySelectorAll("p")).toHaveLength(1);
  expect(host.querySelector("p")!.textContent).toBe(explanation);
  await act(() => fold.click());
  expect(document.getElementById(fold.getAttribute("aria-controls")!)!.hasAttribute("inert")).toBe(false);
});

for (const total of [0, 1024 * 1024]) it(`storage status stays short and the explanation opens with motion, total=${total}`, async () => {
  client.setQueryData(STORAGE_KEY, { book: 0, total });
  await render(<ReadAloudStorage api={{ usage: vi.fn(), clear: vi.fn() }} />);
  const region = host.querySelector('[data-readaloud-storage]')!;
  expect(region.querySelector("p")!.textContent).not.toContain("Nghe lại");
  if (total === 0) expect(region.querySelector("p")!.textContent).toBe("Chưa có bản đọc đã lưu.");
  const more = [...region.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Tìm hiểu thêm")!;
  expect(more).toBeDefined();
  const content = document.getElementById(more.getAttribute("aria-controls")!)!;
  expect(content.hasAttribute("inert")).toBe(true);
  expect(content.textContent).toContain("Nghe lại đoạn đã đọc xong");
  await act(() => more.click()); expect(content.hasAttribute("inert")).toBe(false);
  expect(content.closest(".motion-collapse")).not.toBeNull();
  expect([...region.querySelectorAll("button")].some(button => button.textContent === "Dọn bản đọc")).toBe(total > 0);
});
