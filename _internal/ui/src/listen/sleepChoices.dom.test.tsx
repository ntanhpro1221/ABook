// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import type { SleepMode } from "./sleep";

// Chủ sách 09-11: bảng hẹn giờ là bộ chọn giá trị chung (DESIGN mục 6) - chip tiêu biểu một chạm + thước kéo / -,+ / gõ số ra mọi số phút 1-240,
// và hàng riêng dưới cùng "Hết chương này" (loa / TV: chỉ chương này; trình phát ở đây: -/+ thành "Hết N chương").
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
const chips = () => [...document.querySelectorAll<HTMLButtonElement>("[data-value-chip]")];
const chapterChoice = () => document.querySelector<HTMLButtonElement>("[data-sleep-chapters] button[aria-pressed]")!;

it("chip tiêu biểu, thước, gõ số và hàng Hết chương này; chạm chip / hàng là đặt", async () => {
  const onSet = await open({ kind: "off" });
  expect(chips().map((button) => button.textContent)).toEqual(["5", "15", "30", "45", "60", "90"]);
  expect(document.querySelector('[role="slider"][data-value-ruler]')).not.toBeNull();
  expect(document.querySelector("[data-value-display]")).not.toBeNull();
  await act(async () => chips()[2].click());
  expect(onSet).toHaveBeenLastCalledWith({ kind: "minutes", minutes: 30 });
  // Loa / TV chỉ biết hết chương này: không có -/+ số chương.
  expect(document.querySelectorAll("[data-sleep-chapters] button").length).toBe(1);
  await act(async () => chapterChoice().click());
  expect(onSet).toHaveBeenLastCalledWith({ kind: "chapter", chapters: 1 });
});

it("số phút tự do: gõ 23 rồi Enter là đặt 23 phút; ngoài biên thì kẹp và báo nhẹ", async () => {
  const onSet = await open({ kind: "off" });
  await act(async () => document.querySelector<HTMLButtonElement>("[data-value-display]")!.click());
  const input = document.querySelector<HTMLInputElement>("[data-value-input]")!;
  input.value = "23";
  await act(async () => input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
  expect(onSet).toHaveBeenLastCalledWith({ kind: "minutes", minutes: 23 });
  await act(async () => document.querySelector<HTMLButtonElement>("[data-value-display]")!.click());
  const again = document.querySelector<HTMLInputElement>("[data-value-input]")!;
  again.value = "999";
  await act(async () => again.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
  expect(onSet).toHaveBeenLastCalledWith({ kind: "minutes", minutes: 240 });
  expect(document.querySelector("[data-value-clamped]")?.textContent).toBe("Trong khoảng 1 phút–240 phút");
});

it("phím trên thước: mũi tên một bước, PageUp mười bước", async () => {
  const onSet = await open({ kind: "minutes", minutes: 23, leftMs: 23 * 60_000, since: null });
  const ruler = document.querySelector<HTMLElement>("[data-value-ruler]")!;
  await act(async () => ruler.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
  expect(onSet).toHaveBeenLastCalledWith({ kind: "minutes", minutes: 24 });
  await act(async () => ruler.dispatchEvent(new KeyboardEvent("keydown", { key: "PageUp", bubbles: true })));
  expect(onSet).toHaveBeenLastCalledWith({ kind: "minutes", minutes: 33 });
});

it("chip trùng giá trị đang hẹn sáng; đang hẹn hết chương thì chỉ hàng ấy sáng", async () => {
  await open({ kind: "minutes", minutes: 30, leftMs: 30 * 60_000, since: null });
  expect(chips().filter((button) => button.getAttribute("aria-pressed") === "true").map((button) => button.textContent)).toEqual(["30"]);
  act(() => root.unmount());
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await open({ kind: "chapter", chapters: 1 });
  expect(chips().some((button) => button.getAttribute("aria-pressed") === "true")).toBe(false);
  expect(chapterChoice().getAttribute("aria-pressed")).toBe("true");
  for (const button of [...chips(), chapterChoice()]) {
    const selected = button.getAttribute("aria-pressed") === "true";
    expect(button.querySelector(".lucide-check")).toBeNull(); // ô hẹp: dấu tích đẩy chữ lệch tâm (soát 141), ô chọn chỉ đổi chữ
    expect(button.classList.contains("text-accent-text")).toBe(selected);
  }
});
