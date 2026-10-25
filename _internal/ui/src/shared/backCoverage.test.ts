import { readFileSync } from "node:fs";
import { afterEach, expect, it, vi } from "vitest";
import { pushBackLayer } from "./backStack";
import { markBackOpen } from "./backOrder";
import { dismissTopLayer } from "@/android/backLayers";
import { layerHistoryGuard } from "./MotionRouter";

const cleanups: (() => void)[] = [];
afterEach(() => { while (cleanups.length) cleanups.pop()!(); });
it.each([
  ["B1", "../listen/SentenceMenu.tsx", /useBackLayer\(selected !== null, \(\) => select\(null\), barBox\)/],
  ["B2", "../listen/PlayerViews.tsx", /useBackLayer\(asking, \(\) => setAsking\(false\), askBox\)/],
  ["B3", "../listen/OnlineVoicePrompt.tsx", /useBackLayer\(Boolean\(request && choosing\), \(\) => setChoosing\(false\), list, chooseButton\)/],
  ["B4", "../listen/EditBook.tsx", /useBackLayer\(swapping !== null, \(\) => setSwapping\(null\), swapBox, swapButton\)/],
  ["B5", "../listen/EditBook.tsx", /useBackLayer\(open && confirmRevert, \(\) => setConfirmRevert\(false\), revertBox, revertButton\)/],
  ["B6", "../android/DevicesScreen.tsx", /useBackLayer\(btAsk !== null, \(\) => setBtAsk\(null\), btBox, btButton\)/],
  ["B7", "../android/DevicesScreen.tsx", /useBackLayer\(explain && !enabled, \(\) => setExplain\(false\), explainBox, explainButton\)/],
  ["B9", "../listen/WordReadings.tsx", /useBackLayer\(word !== null && joining, \(\) => setJoining\(false\), joinBox, joinButton\)/],
  ["B10", "./ChapterPreview.tsx", /useBackLayer\(editing !== null,[\s\S]*cancelled.current = true/],
  ["B11", "../listen/AddBook.tsx", /useBackLayer\(open && confirmLeave !== null, \(\) => setConfirmLeave\(null\), confirmBox, confirmButton\)/],
  ["B12", "../studio/MusicTab.tsx", /useBackLayer\(swapping !== null, \(\) => setSwapping\(null\), swapBox, swapTrigger\)/],
])("%s đăng ký bước và ref bên trong surface; Back đóng bước trước hộp", (_id, path, pattern) => {
  expect(readFileSync(new URL(path, import.meta.url), "utf8")).toMatch(pattern);
  const step = {};
  const close = vi.fn();
  cleanups.push(pushBackLayer(close, () => step as Element));
  const dispatch = vi.fn();
  const dialog = { getAttribute: (name: string) => name === "data-state" ? "open" : name === "role" ? "dialog" : null, contains: (el: unknown) => el === step };
  const doc = { querySelectorAll: () => [dialog], querySelector: () => null, dispatchEvent: dispatch };
  expect(dismissTopLayer(doc)).toBe(true);
  expect(close).toHaveBeenCalledOnce();
  expect(dispatch).not.toHaveBeenCalled();
});

it.each(["panel", "dialog"])("B13 toast mở sau %s: chỉ đóng toast trên cùng, giữ lớp và toast khác", (kind) => {
  const closeToast = vi.fn();
  const closePanel = vi.fn();
  const dialog = { getAttribute: (name: string) => name === "data-state" ? "open" : name === "role" ? "dialog" : null };
  if (kind === "panel") cleanups.push(pushBackLayer(closePanel));
  else markBackOpen(dialog);
  const toast = { querySelector: () => ({ click: closeToast }) };
  markBackOpen(toast);
  const doc = { querySelectorAll: () => kind === "dialog" ? [dialog] : [], querySelector: () => ({ closest: () => toast }), dispatchEvent: vi.fn() };
  expect(dismissTopLayer(doc as unknown as Document)).toBe(true);
  expect(closeToast).toHaveBeenCalledOnce();
  expect(closePanel).not.toHaveBeenCalled();
  expect(doc.dispatchEvent).not.toHaveBeenCalled();
});

it("browser Back đóng bước → hộp → trang; POP bù không đóng thêm lớp", () => {
  const go = vi.fn();
  const close = vi.fn().mockReturnValueOnce(true).mockReturnValueOnce(true).mockReturnValue(false);
  const guard = layerHistoryGuard(close, go);
  expect(guard("POP", 3, 2)).toBe(true);
  expect(go).toHaveBeenLastCalledWith(1);
  expect(guard("POP", 3, 3)).toBe(true);
  expect(close).toHaveBeenCalledTimes(1);
  expect(guard("POP", 3, 2)).toBe(true);
  expect(guard("POP", 3, 3)).toBe(true);
  expect(guard("POP", 3, 2)).toBe(false);
  expect(go).toHaveBeenCalledTimes(2);
});
