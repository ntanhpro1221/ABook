// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VoicePicker } from "@/studio/VoicePicker";
import { MyMusicSection } from "@/listen/MyMusic";
import { MyMusic } from "@/studio/MusicTab";
import { dismissTopLayer } from "@/android/backLayers";
import { installBackOrder } from "./backOrder";
import { MotionHashRouter } from "./MotionRouter";

vi.mock("@/listen/clip", () => ({ useClip: () => ({ stop() {}, current: null }) }));
vi.mock("@/studio/VoiceTry", () => ({ useVoiceTry: () => ({ note: null }) }));
const clients: QueryClient[] = [];
const roots: ReturnType<typeof createRoot>[] = [];
const cleanup: (() => void)[] = [];
beforeEach(() => { vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null }) as Animation); });
afterEach(async () => { for (const root of roots.splice(0)) await act(() => root.unmount()); for (const stop of cleanup.splice(0)) stop(); clients.splice(0).forEach((client) => client.clear()); document.body.replaceChildren(); localStorage.clear(); vi.restoreAllMocks(); });
async function mount(child: React.ReactNode, data: [unknown[], unknown][]) {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } }); clients.push(client);
  for (const [key, value] of data) client.setQueryData(key, value);
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host); roots.push(root);
  cleanup.push(installBackOrder());
  await act(() => root.render(<QueryClientProvider client={client}><MotionHashRouter>{child}</MotionHashRouter></QueryClientProvider>));
}
const button = (name: string) => Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((el) => el.textContent?.trim() === name)!;
async function click(name: string) { const el = button(name); await act(() => { el.focus(); el.click(); }); return el; }

it("V3 đổi giới: Esc chỉ huỷ xác nhận, giữ Dialog và trả focus về giọng đã chọn", async () => {
  const close = vi.fn();
  await mount(<VoicePicker bookId="b" person={{ name: "A", displayName: "An" }} onClose={close} />, [
    [["voice-choices", "b", "A"], { character: { value: "A", label: "An", gender: "male", lines: 1, chapters: 1 }, current: "Nam", pending: null,
      voices: [{ key: "f", name: "Nữ", gender: "female", genderLabel: "Nữ", engine: "vieneu", installed: true, current: false, sharedWith: [], description: "", preview: false }] }],
  ]);
  await click("Nữ");
  const choose = await click("Chọn");
  expect(button("Đổi giọng và giới")).toBeDefined();
  await act(() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })));
  expect(button("Đổi giọng và giới")).toBeUndefined();
  expect(close).not.toHaveBeenCalled();
  expect(document.activeElement).toBe(choose);
});

it.each(["listen", "studio"])("V3 xoá nhạc %s: Back huỷ riêng câu hỏi và focus nút Xoá được dựng lại", async (where) => {
  await mount(where === "listen" ? <MyMusicSection /> : <MyMusic bookId="b" previewing={null} onPreview={() => {}} />, [
    [["app"], { dialogs: true }],
    [["music-local"], { tracks: [{ link: "local:test", title: "Bài A", creator: "", analysed: true }], module: { installed: true } }],
  ]);
  if (where === "listen") await click("Nhạc của tôi1 bài");
  await click("Xoá");
  expect(button("Xoá khỏi kho")).toBeDefined();
  await act(() => { expect(dismissTopLayer()).toBe(true); });
  expect(button("Xoá khỏi kho")).toBeUndefined();
  expect(document.activeElement).toBe(button("Xoá"));
});
