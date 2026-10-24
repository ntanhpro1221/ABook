// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SleepSchedule } from "./SleepSchedule";

const h = vi.hoisted(() => ({ data: undefined as { sleepSchedule: { from: string; to: string; minutes: number } } | undefined, update: vi.fn() }));
vi.mock("@/studio/data", () => ({ usePreferences: () => ({ data: h.data, update: h.update }) }));
let root: Root, host: HTMLElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host); h.update.mockReset();
  h.data = { sleepSchedule: { from: "22:00", to: "06:00", minutes: 30 } };
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {} }) as Animation);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });

it("V5 đang lưu: controls vẫn focus được, báo aria-disabled và chặn đổi lịch", async () => {
  await act(() => root.render(<SleepSchedule />));
  const minutes = host.querySelector<HTMLSelectElement>('[aria-label="Số phút hẹn"]')!;
  await act(() => { minutes.value = "45"; minutes.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(h.update).toHaveBeenCalledOnce();
  const controls = [...host.querySelectorAll<HTMLElement>('[role="switch"], select')];
  expect(controls).toHaveLength(4);
  for (const control of controls) {
    expect(control.hasAttribute("disabled")).toBe(false);
    expect(control.getAttribute("aria-disabled")).toBe("true");
    control.focus(); expect(document.activeElement).toBe(control);
    if (control.tagName === "SELECT") {
      for (const event of [new Event("pointerdown", { bubbles: true, cancelable: true }), new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true })]) {
        control.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
      }
      const tab = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
      control.dispatchEvent(tab); expect(tab.defaultPrevented).toBe(false);
      await act(() => { control.dispatchEvent(new Event("change", { bubbles: true })); });
    } else await act(() => control.click());
  }
  expect(h.update).toHaveBeenCalledOnce();
  await act(() => h.update.mock.calls[0][1].onSuccess({ sleepSchedule: { from: "22:00", to: "06:00", minutes: 45 } }));
  expect(host.querySelector('[aria-disabled="true"]')).toBeNull();
});

it("V5 chưa tải preferences: switch focus được và không gửi cập nhật", async () => {
  h.data = undefined;
  await act(() => root.render(<SleepSchedule />));
  const toggle = host.querySelector<HTMLElement>('[role="switch"]')!;
  expect(toggle.hasAttribute("disabled")).toBe(false);
  expect(toggle.getAttribute("aria-disabled")).toBe("true");
  toggle.focus(); expect(document.activeElement).toBe(toggle);
  await act(() => toggle.click()); expect(h.update).not.toHaveBeenCalled();
});
