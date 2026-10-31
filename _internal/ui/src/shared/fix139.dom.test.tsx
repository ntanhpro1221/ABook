// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createMemoryRouter, RouterProvider, useLocation, useNavigate } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { Toaster } from "sonner";
import { toast } from "./toast";
import { warnElsewhere } from "@/studio/elsewhere";
import { dismissTopLayer } from "@/shared/backLayers";
import { installBackOrder } from "./backOrder";
import { SettingsList, GroupHeader } from "./SettingsNav";
import { BookCover } from "./BookCover";
import { MotionRegion } from "./MotionRegion";
import { MOTION } from "./motion";

let root: Root, host: HTMLElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
});
afterEach(async () => { toast.dismiss(); await act(() => root.unmount()); vi.useRealTimers(); vi.restoreAllMocks(); document.body.replaceChildren(); document.head.replaceChildren(); });

it("CAO1 toast từ caller không có nút đóng được Back gỡ đúng một lần", async () => {
  const stop = installBackOrder();
  try {
    await act(() => root.render(<Toaster />));
    await act(async () => { warnElsewhere(1, "A", vi.fn()); await new Promise(done => setTimeout(done, 30)); });
    expect(document.querySelector("[data-close-button]")).toBeNull();
    await act(() => { expect(dismissTopLayer()).toBe(true); });
    expect(document.querySelector('[data-sonner-toast][data-removed="true"]')).not.toBeNull();
    expect(dismissTopLayer()).toBe(false);
  } finally { stop(); }
});

it("CAO1 Back không nhận đã đóng khi toast không có ID hoặc nút đóng", () => {
  const item = document.createElement("li"); item.setAttribute("data-sonner-toast", "");
  const button = document.createElement("button"); button.setAttribute("data-button", ""); item.append(button); host.append(item);
  expect(dismissTopLayer()).toBe(false);
  expect(item.hasAttribute("data-removed")).toBe(false);
});

it("CAO2 popper đang đóng giữ animation nhưng không nhận pointer", () => {
  const sheet = new CSSStyleSheet(); sheet.replaceSync(readFileSync(`${cwd()}/src/styles.css`, "utf8"));
  const style = document.createElement("style");
  style.textContent = Array.from(sheet.cssRules).filter(rule => rule.cssText.startsWith("[data-radix-popper-content-wrapper]")).map(rule => rule.cssText).join("\n");
  document.head.append(style);
  const popper = document.createElement("div"); popper.setAttribute("data-radix-popper-content-wrapper", "");
  const menu = document.createElement("div"); menu.dataset.state = "closed"; menu.style.pointerEvents = "auto";
  popper.append(menu); host.append(popper);
  expect(getComputedStyle(popper).pointerEvents).toBe("none");
  expect(getComputedStyle(menu).pointerEvents).toBe("none");
  expect(getComputedStyle(menu).animation).toContain("motion-exit");
  menu.dataset.state = "open"; expect(getComputedStyle(menu).pointerEvents).toBe("auto");
});

function SettingsPage({ wide = false }: { wide?: boolean }) {
  const location = useLocation(), navigate = useNavigate();
  const [columns, setColumns] = useState(wide);
  return <><output>{location.pathname}</output>{columns || location.pathname === "/settings"
    ? <SettingsList rows={[{ id: "voice" }, { id: "look" }]} current={columns ? "voice" : undefined} /> : <GroupHeader id="voice" />}
    <button onClick={() => setColumns(value => !value)}>Resize</button>
    <button onClick={() => navigate(-1)}>History Back</button></>;
}
it("CAO3 mở nhóm rồi đóng và Back không lặp lại Cài đặt", async () => {
  const router = createMemoryRouter([{ path: "*", element: <SettingsPage /> }], { initialEntries: ["/", "/settings"], initialIndex: 1 });
  await act(() => root.render(<RouterProvider router={router} />));
  await act(() => host.querySelector<HTMLAnchorElement>("a")!.click());
  expect(host.querySelector("output")!.textContent).toBe("/settings/voice");
  await act(() => host.querySelector<HTMLButtonElement>('[aria-label="Về Cài đặt"]')!.click());
  expect(host.querySelector("output")!.textContent).toBe("/settings");
  await act(() => [...host.querySelectorAll("button")].find(button => button.textContent === "History Back")!.click());
  expect(host.querySelector("output")!.textContent).toBe("/");
  router.dispose();
});

it.each([false, true])("CAO3 đổi nhóm bằng replace rồi thu hẹp giữ đúng nguồn lịch sử, pushed=%s", async pushed => {
  const router = createMemoryRouter([{ path: "*", element: <SettingsPage wide={!pushed} /> }], { initialEntries: ["/", "/settings"], initialIndex: 1 });
  const click = (label: string) => act(() => [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === label)!.click());
  await act(() => root.render(<RouterProvider router={router} />));
  if (pushed) {
    await act(() => host.querySelector<HTMLAnchorElement>("a")!.click());
    await click("Resize");
  }
  await act(() => host.querySelector<HTMLAnchorElement>('a[href="/settings/look"]')!.click());
  await click("Resize");
  await act(() => host.querySelector<HTMLButtonElement>('[aria-label="Về Cài đặt"]')!.click());
  expect(host.querySelector("output")!.textContent).toBe("/settings");
  await click("History Back"); expect(host.querySelector("output")!.textContent).toBe("/");
  router.dispose();
});

it("V7 MotionRegion trống fade về 0 và giữ chiều cao cho đến khi kết thúc", async () => {
  vi.useFakeTimers();
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const height = this.textContent ? 20 : 0;
    return { top: 0, left: 0, width: 30, height, right: 30, bottom: height } as DOMRect;
  });
  await act(() => root.render(<MotionRegion>Đang nghe</MotionRegion>));
  await act(() => root.render(<MotionRegion />));
  const region = host.firstElementChild as HTMLElement;
  expect(region.style.height).toBe("20px");
  expect(document.querySelector(".motion-snapshot")?.textContent).toBe("Đang nghe");
  const frames = vi.mocked(region.animate).mock.calls.at(-1)![0] as Keyframe[];
  expect(frames[0]).toMatchObject({ opacity: 1, height: "20px" });
  expect(frames.at(-1)).toMatchObject({ opacity: 0, height: "0px" });
  const animation = vi.mocked(region.animate).mock.results.at(-1)!.value as Animation;
  await act(() => animation.onfinish?.(new Event("finish") as AnimationPlaybackEvent));
  expect(region.hasAttribute("data-motion-exit")).toBe(false); expect(region.style.height).toBe("");
});

it.each([false, true])("V7 nền badge nằm trên con được fade, ảnh=%s", async photo => {
  vi.useFakeTimers();
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ top: 0, left: 0, width: 30, height: 20, right: 30, bottom: 20 } as DOMRect);
  const draw = (playing: boolean) => act(() => root.render(<BookCover title="Sách" playing={playing} image={photo ? { url: "cover.jpg" } : undefined} />));
  await draw(true);
  // Vùng huy hiệu là vùng chuyển động cuối của bìa (trước nó là vùng mờ chéo ảnh bìa).
  const region = [...host.querySelectorAll<HTMLElement>("[data-motion-region]")].at(-1)!;
  expect(region.className).not.toContain("bg-cover-overlay");
  expect(region.firstElementChild?.className).toContain("bg-cover-overlay");
  await draw(false);
  expect(document.querySelector(".motion-snapshot .bg-cover-overlay")).not.toBeNull();
  const frames = vi.mocked(region.animate).mock.calls.at(-1)![0] as Keyframe[];
  expect(frames[0].opacity).toBe(1); expect(frames.at(-1)?.opacity).toBe(0);
  await act(() => vi.advanceTimersByTime(MOTION.medium + 81));
  expect(region.hasAttribute("data-motion-exit")).toBe(false);
  expect(region.children).toHaveLength(0);
});

it.each(["same-key", "same-dom"])("L9 dọn exit khi update bỏ qua animation: %s", async branch => {
  vi.useFakeTimers();
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ top: 0, left: 0, width: 30, height: 20, right: 30, bottom: 20 } as DOMRect);
  const draw = (step: number) => act(() => root.render(<MotionRegion motionKey={branch === "same-key" ? step === 0 ? "old" : "new" : undefined}>{step === 0 ? "Sách" : step === 1 ? null : branch === "same-key" ? "Trở lại" : [null, null]}</MotionRegion>));
  await draw(0); await draw(1);
  const box = host.firstElementChild as HTMLElement;
  expect(box.hasAttribute("data-motion-exit")).toBe(true);
  const exit = vi.mocked(box.animate).mock.results.at(-1)!.value as Animation;
  await draw(2);
  expect(exit.cancel).toHaveBeenCalledOnce();
  expect(box.hasAttribute("data-motion-exit")).toBe(false);
  expect(box.style.height).toBe(""); expect(box.style.overflow).toBe("");
  await act(() => vi.advanceTimersByTime(MOTION.medium + 81));
  expect(box.style.height).toBe("");
});
