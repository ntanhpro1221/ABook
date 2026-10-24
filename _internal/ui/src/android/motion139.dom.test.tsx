// @vitest-environment happy-dom
// a139: Cài đặt điện thoại - lời báo trên trang gốc, khối Cập nhật / Bản lưu cũ, dòng Thông báo mở / khép tại chỗ, không bật tắt cứng.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";

const h = vi.hoisted(() => ({ update: null as unknown, oldSaves: undefined as unknown, notification: "granted" as "granted" | "off" }));
vi.mock("./updates", async (load) => ({ ...await load<typeof import("./updates")>(), useAppUpdate: () => ({ current: "1.0", update: h.update }) }));
vi.mock("./oldSaveList", async (load) => ({ ...await load<typeof import("./oldSaveList")>(), useOldSaves: () => ({ data: h.oldSaves }) }));
vi.mock("./notifications", async (load) => ({ ...await load<typeof import("./notifications")>(), notificationState: async () => h.notification }));
vi.mock("@/listen/VoiceSettings", async (load) => ({ ...await load<typeof import("@/listen/VoiceSettings")>(), useDefaultVoiceName: () => "Giọng A" }));
vi.mock("@/listen/MyMusic", () => ({ MyMusicSection: () => null }));
vi.mock("@/listen/ReadAloudStorage", () => ({ ReadAloudStorage: () => null }));

import { SettingsScreen } from "./SettingsScreen";

let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  h.update = null; h.oldSaves = undefined; h.notification = "granted";
  localStorage.clear();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });
const render = (path: string) => act(() => root.render(
  <QueryClientProvider client={client}><TooltipProvider><MemoryRouter initialEntries={[path]}>
    <Routes><Route path="/settings/:group?" element={<SettingsScreen />} /></Routes>
  </MemoryRouter></TooltipProvider></QueryClientProvider>,
));
/** Lớp tự dựng (MotionPresence) đang mở chứa đoạn chữ này. */
const presence = (text: string) => [...host.querySelectorAll<HTMLElement>(".motion-panel")].find((panel) => panel.textContent?.includes(text));

it("V12 trang gốc: lời báo bản mới / bản lưu cũ tới sau một lượt hỏi thì mở ra, gỡ thì khép lại", async () => {
  await render("/settings");
  expect(host.textContent).not.toContain("Có bản mới");
  h.update = { version: "2.0", page: "https://example.invalid" };
  h.oldSaves = [{ name: "a.json" }];
  await render("/settings");
  expect(presence("Có bản mới 2.0")?.getAttribute("data-state")).toBe("open");
  expect(presence("Bản lưu cũ (1)")?.getAttribute("data-state")).toBe("open");
  h.update = null; h.oldSaves = [];
  await render("/settings");
  // Đang khép: vẫn giữ hình cuối, inert, rồi mới gỡ.
  expect(presence("Có bản mới 2.0")?.getAttribute("data-state")).toBe("closed");
  expect(presence("Bản lưu cũ (1)")?.hasAttribute("inert")).toBe(true);
});

it("V14 Nâng cao: khối Cập nhật và Bản lưu cũ mở / khép tại chỗ, giữ lề cũ", async () => {
  await render("/settings/advanced");
  h.update = { version: "2.0", page: "https://example.invalid" };
  h.oldSaves = [{ name: "a.json", size: 10, modified: 0 }];
  await render("/settings/advanced");
  const update = presence("Có bản mới 2.0")!;
  expect(update.getAttribute("data-state")).toBe("open");
  expect(update.querySelector("section")!.className).toContain("first:mt-6");
  expect(presence("Bản lưu cũ (1)")?.getAttribute("data-state")).toBe("open");
  h.update = null;
  await render("/settings/advanced");
  expect(presence("Có bản mới 2.0")?.getAttribute("data-state")).toBe("closed");
});

it("V13 Nghe: dòng xin quyền thông báo mở ra khi hỏi xong, khép lại khi đã cho phép", async () => {
  h.notification = "off";
  await render("/settings/listen");
  await act(async () => { await Promise.resolve(); });
  expect(presence("Thông báo")?.getAttribute("data-state")).toBe("open");
  h.notification = "granted";
  await act(async () => { document.dispatchEvent(new Event("visibilitychange")); await Promise.resolve(); });
  expect(presence("Thông báo")?.getAttribute("data-state")).toBe("closed");
});
