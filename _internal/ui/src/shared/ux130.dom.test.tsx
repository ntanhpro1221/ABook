// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { Switch } from "@/desktop/PhoneSync";
import { Toaster } from "sonner";
import { toast } from "@/shared/toast";
import { installBackOrder } from "./backOrder";
import { pushBackLayer } from "./backStack";
import { dismissTopLayer } from "@/android/backLayers";

let root: Root;
let host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});

it("V2 Toaster Android không nút đóng: Back chỉ gỡ toast mới nhất trước panel", async () => {
  const stop = installBackOrder();
  const close = vi.fn();
  const pop = pushBackLayer(close);
  try {
    await render(<Toaster toastOptions={{ duration: Infinity }} />);
    await act(async () => { toast("Cũ", { id: "old", action: { label: "Hoàn tác", onClick() {} } }); await new Promise((done) => setTimeout(done, 20)); });
    await act(async () => { toast("Mới", { id: 42, action: { label: "Ghi chú", onClick() {} } }); await new Promise((done) => setTimeout(done, 20)); });
    expect(document.querySelector("[data-close-button]")).toBeNull();
    const dismiss = vi.spyOn(toast, "dismiss");
    await act(async () => { expect(dismissTopLayer()).toBe(true); await new Promise((done) => setTimeout(done, 20)); });
    expect(close).not.toHaveBeenCalled();
    expect(dismiss).toHaveBeenCalledExactlyOnceWith(42);
    expect(toast.getToasts().some((item) => item.id === "old")).toBe(true);
    await act(async () => { expect(dismissTopLayer()).toBe(true); await new Promise((done) => setTimeout(done, 20)); });
    expect(dismiss).toHaveBeenNthCalledWith(2, "old");
    expect(close).not.toHaveBeenCalled();
    await act(() => { expect(dismissTopLayer()).toBe(true); });
    expect(close).toHaveBeenCalledOnce();
  } finally { stop(); pop(); toast.dismiss(); }
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); document.head.replaceChildren(); vi.restoreAllMocks(); });
const render = async (node: ReactNode) => { await act(() => root.render(node)); };

it("V1 reduced Switch: không cộng translate; bật và tắt đều fade", async () => {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(readFileSync(`${cwd()}/src/styles.css`, "utf8"));
  const reduced = Array.from(sheet.cssRules).filter((rule) => rule.type === 4 && (rule as CSSMediaRule).conditionText.includes("prefers-reduced-motion"));
  expect(reduced.length).toBeGreaterThan(0);
  const style = document.createElement("style");
  style.textContent = Array.from(sheet.cssRules).filter((rule) => (rule as CSSStyleRule).selectorText?.startsWith(".ui-switch")).map(rule => rule.cssText).join("\n") + "\n" + reduced.map((rule) => Array.from((rule as CSSMediaRule).cssRules).map((child) => child.cssText).join("\n")).join("\n");
  document.head.append(style);
  const names: string[] = [];
  for (const checked of [false, true, false]) {
    await render(<Switch checked={checked} onCheckedChange={() => {}} label="Lịch đêm" />);
    const thumb = host.querySelector<HTMLElement>(".motion-switch-thumb")!;
    const computed = getComputedStyle(thumb);
    expect(computed.position).toBe("absolute"); // Hình học và inset đo bằng Edge: happy-dom không có layout.
    expect(computed.translate).toBe("none");
    expect(computed.transform).toBe("none");
    const name = computed.animationName || computed.animation.split(" ")[0];
    expect(name).toMatch(/^fade-in/);
    names.push(name);
  }
  expect(names[0]).not.toBe(names[1]); // đổi animation-name để mỗi chiều đều bắt đầu fade mới.
  expect(names[2]).toBe(names[0]);
});
