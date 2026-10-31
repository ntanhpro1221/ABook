// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Dialog, Tooltip, TooltipProvider } from "./ui";
import { backLayerCount } from "./backStack";
import { installBackOrder } from "./backOrder";
import { dismissTopLayer } from "@/shared/backLayers";
import { layerHistoryGuard } from "./MotionRouter";

let root: Root, cleanup: () => void;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  cleanup = installBackOrder();
  // happy-dom không tính :focus-visible như trình duyệt; mô phỏng focus bàn phím.
  const matches = HTMLElement.prototype.matches;
  vi.spyOn(HTMLElement.prototype, "matches").mockImplementation(function (this: HTMLElement, selector) {
    return selector === ":focus-visible" || matches.call(this, selector);
  });
  const style = document.createElement("style");
  style.textContent = '.motion-tooltip:is([data-state=instant-open], [data-state=delayed-open]) { animation-name: enter; animation-duration: 1s; } .motion-tooltip[data-state=closed] { animation-name: exit; animation-duration: 1s; }';
  document.head.append(style);
});
afterEach(async () => {
  await act(() => root.unmount()); cleanup(); document.body.replaceChildren(); document.head.replaceChildren(); vi.restoreAllMocks();
  expect(backLayerCount()).toBe(0);
});

function Page({ dialog }: { dialog: boolean }) {
  const [open, setOpen] = useState(true);
  const trigger = <Tooltip label="Giải thích"><button id="help">Trợ giúp</button></Tooltip>;
  return <TooltipProvider delayDuration={0}>{dialog
    ? <Dialog open={open} onOpenChange={setOpen} title="Hộp" description="Lời dẫn"><button>Đầu tiên</button>{trigger}</Dialog>
    : trigger}</TooltipProvider>;
}

it.each([false, true])("Back hệ thống đóng tooltip trước, dialog=%s", async dialog => {
  await act(() => root.render(<Page dialog={dialog} />));
  await act(() => document.getElementById("help")!.focus());
  expect(document.querySelector('[role="tooltip"]')).not.toBeNull();
  const escape = vi.fn(); document.addEventListener("keydown", escape);
  const navigateOrMinimize = vi.fn();
  await act(() => { if (!dismissTopLayer()) navigateOrMinimize(); });
  expect(navigateOrMinimize).not.toHaveBeenCalled();
  expect(escape).not.toHaveBeenCalled();
  expect(document.querySelector('.motion-tooltip[data-state="closed"]')).not.toBeNull();
  expect(backLayerCount()).toBe(0);
  if (dialog) expect(document.querySelector('[role="dialog"][data-state="open"]')).not.toBeNull();
  document.removeEventListener("keydown", escape);
});

it("Browser Back có tooltip khôi phục history slot, không đổi trang hay đóng dialog", async () => {
  await act(() => root.render(<Page dialog />));
  await act(() => document.getElementById("help")!.focus());
  const go = vi.fn(); const route = vi.fn();
  const guard = layerHistoryGuard(() => dismissTopLayer(), go);
  await act(() => { if (!guard("POP", 2, 1)) route(); });
  expect(go).toHaveBeenCalledExactlyOnceWith(1);
  expect(route).not.toHaveBeenCalled();
  expect(document.querySelector('.motion-tooltip[data-state="closed"]')).not.toBeNull();
  expect(document.querySelector('[role="dialog"][data-state="open"]')).not.toBeNull();
  expect(guard("POP", 2, 2)).toBe(true); // POP bù không đóng tiếp dialog.
  expect(document.querySelector('[role="dialog"][data-state="open"]')).not.toBeNull();
});

// Từ r136b/review-evidence.test.tsx F1: giữ Presence/Radix thật, đổi sang hành vi đúng.
function TipLayer({ kind }: { kind: "dialog" | "menu" }) {
  const [open, setOpen] = useState(true);
  const tip = <Tooltip label="Giải thích"><button id="help">Trợ giúp</button></Tooltip>;
  return <TooltipProvider delayDuration={0}>{kind === "dialog"
    ? <Dialog open={open} onOpenChange={setOpen} title="Hộp"><button>Đầu</button>{tip}</Dialog>
    : <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <DropdownMenu.Trigger>Menu</DropdownMenu.Trigger>
      <DropdownMenu.Portal><DropdownMenu.Content>{tip}<DropdownMenu.Item>Mục</DropdownMenu.Item></DropdownMenu.Content></DropdownMenu.Portal>
    </DropdownMenu.Root>}</TooltipProvider>;
}

it.each(["dialog", "menu"] as const)("Back lần hai khi tooltip đang fade đóng lớp %s bên dưới", async kind => {
  await act(() => root.render(<TipLayer kind={kind} />));
  await act(() => document.getElementById("help")!.focus());
  expect(backLayerCount()).toBe(1);
  await act(() => { expect(dismissTopLayer()).toBe(true); });
  expect(backLayerCount()).toBe(0);
  const tooltip = document.querySelector<HTMLElement>('.motion-tooltip[data-state="closed"]')!;
  expect(tooltip).not.toBeNull(); // Back đầu vẫn giữ fade, chưa animationend.
  expect(document.querySelector(`[role="${kind}"][data-state="open"]`)).not.toBeNull();
  const finish = vi.fn(() => tooltip.dispatchEvent(new AnimationEvent("animationend", { animationName: "exit", bubbles: true })));
  vi.spyOn(tooltip, "getAnimations").mockReturnValue([{ finish }] as unknown as Animation[]);
  const waits: (() => void)[] = [];
  await act(() => { expect(dismissTopLayer(document, undefined, undefined, step => waits.push(step))).toBe(true); });
  // WAAPI finish nhả Presence; nhịp sau mới gửi Esc cho lớp dưới.
  await act(() => { waits.shift()?.(); });
  expect(document.querySelector(`[role="${kind}"][data-state="open"]`)).toBeNull();
  expect(finish).toHaveBeenCalledOnce();
});

it("tooltip đang fade đóng có inert và không chặn chạm", async () => {
  await act(() => root.render(<Page dialog />));
  await act(() => document.getElementById("help")!.focus());
  await act(() => { dismissTopLayer(); });
  const tooltip = document.querySelector<HTMLElement>('.motion-tooltip[data-state="closed"]')!;
  expect(tooltip).not.toBeNull();
  expect(tooltip.hasAttribute("inert")).toBe(true);
  expect(tooltip.style.pointerEvents).toBe("none");
});
