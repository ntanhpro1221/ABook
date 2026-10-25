// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import type { SleepMode } from "./sleep";

// Soát 140 V3: bảng hẹn giờ từng có ba cách chọn (ô 5′…90′, bộ −/+ "30 phút" kèm nút "Đặt 30 phút", nút "Hết chương này") và ô đang hẹn không sáng.
// Giờ một cách: bấm một ô là đặt, ô đang hẹn sáng, đơn vị một kiểu "phút".
vi.mock("./player", async (original) => ({
  ...(await original<typeof import("./player")>()),
  usePlayer: () => ({ options: {}, sleep: { kind: "off" }, track: null, volume: 1, setVolume: () => undefined }),
}));
let root: ReturnType<typeof createRoot>;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, finished: Promise.resolve() }) as unknown as Animation);
});
afterEach(() => { act(() => root.unmount()); document.body.innerHTML = ""; vi.restoreAllMocks(); });

async function open(sleep: SleepMode, onSet = vi.fn()) {
  const { RemoteSleepMenu } = await import("./PlayerViews");
  await act(async () => root.render(<TooltipProvider><RemoteSleepMenu sleep={sleep} name="Loa phòng khách" onSet={onSet} /></TooltipProvider>));
  const trigger = document.querySelector<HTMLButtonElement>("button[aria-haspopup], button[aria-expanded]")!;
  await act(async () => trigger.click());
  return onSet;
}
const choices = () => [...document.querySelectorAll<HTMLButtonElement>("button[aria-pressed]")];

it("một lưới ô chọn, không bộ −/+ hay nút Đặt riêng; bấm Hết chương này là đặt", async () => {
  const onSet = await open({ kind: "off" });
  expect(choices().map((button) => button.textContent)).toEqual(["5 phút", "10 phút", "15 phút", "20 phút", "30 phút", "45 phút", "60 phút", "90 phút", "Hết chương này"]);
  expect(document.querySelector('[aria-label="Bớt 5 phút"], [aria-label="Thêm 5 phút"]')).toBeNull();
  expect([...document.querySelectorAll("button")].some((button) => /^Đặt \d+ phút$/.test(button.textContent ?? ""))).toBe(false);
  await act(async () => choices().at(-1)!.click());
  expect(onSet).toHaveBeenCalledWith({ kind: "chapter" });
});

it("ô đang hẹn sáng, kể cả Hết chương này", async () => {
  await open({ kind: "chapter" });
  expect(choices().filter((button) => button.getAttribute("aria-pressed") === "true").map((button) => button.textContent)).toEqual(["Hết chương này"]);
  for (const button of choices()) {
    expect(button.classList.contains("bg-accent-soft")).toBe(false);
    const selected = button.getAttribute("aria-pressed") === "true";
    expect(button.querySelector(".lucide-check")?.classList.contains("opacity-100")).toBe(selected);
    expect(button.classList.contains("text-accent-text")).toBe(selected);
  }
});
