// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import type { SleepMode } from "./sleep";

// Soát 0.4.173 B8: sau lần tự dừng, lựa chọn hẹn giờ còn giữ (không về "tắt"). Máy tính và điện thoại vẫn hiện "Hẹn giờ đã tắt tiếng lúc …";
// bản web từng chỉ hiện khi đã tắt hẳn. Nút "Bật lại" thì cả ba nền chỉ hiện khi đã tắt hẳn.
const state: { sleep: SleepMode; stoppedAt: number | null } = { sleep: { kind: "off" }, stoppedAt: null };
vi.mock("./player", async (original) => ({
  ...(await original<typeof import("./player")>()),
  usePlayer: () => ({ options: { extendMinutes: 10, fadeSeconds: 10 }, sleep: state.sleep, sleepStoppedAt: state.stoppedAt, lastSleepMinutes: 20,
    setSleep: () => undefined, extendSleep: () => undefined, track: null, volume: 1, setVolume: () => undefined }),
}));
vi.mock("./source", async (original) => ({
  ...(await original<typeof import("./source")>()),
  useLastNight: () => ({ data: null }),
}));
// Giờ cố định: dòng "đã tắt tiếng" so với mốc dừng, không theo đồng hồ máy chạy test.
const NOW = new Date(2026, 10, 17, 22, 30).getTime();
let root: ReturnType<typeof createRoot>;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(NOW);
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, finished: Promise.resolve() }) as unknown as Animation);
});
afterEach(() => { act(() => root.unmount()); document.body.innerHTML = ""; vi.restoreAllMocks(); vi.useRealTimers(); });

async function open(sleep: SleepMode, stoppedAt: number | null) {
  state.sleep = sleep; state.stoppedAt = stoppedAt;
  const { SleepMenu } = await import("./PlayerViews");
  await act(async () => root.render(<TooltipProvider><SleepMenu /></TooltipProvider>));
  const trigger = document.querySelector<HTMLButtonElement>("button[aria-haspopup], button[aria-expanded]")!;
  await act(async () => trigger.click());
}
const stoppedLine = () => document.querySelector("[data-testid='sleep-stopped']");
const restart = () => [...document.querySelectorAll("button")].find((button) => button.textContent?.startsWith("Bật lại"));

it("the stopped line shows while the choice is kept after a stop, without a restart button", async () => {
  await open({ kind: "minutes", minutes: 15, leftMs: 900_000, since: null }, NOW - 60_000);
  expect(stoppedLine()?.textContent).toContain("Hẹn giờ đã tắt tiếng lúc");
  expect(restart()).toBeUndefined();
});

it("once off, the stopped line and the restart button both show", async () => {
  await open({ kind: "off" }, NOW - 60_000);
  expect(stoppedLine()).not.toBeNull();
  expect(restart()?.textContent).toBe("Bật lại 20 phút");
});

it("neither shows half an hour after the stop", async () => {
  await open({ kind: "off" }, NOW - 31 * 60_000);
  expect(stoppedLine()).toBeNull();
  expect(restart()).toBeUndefined();
});
