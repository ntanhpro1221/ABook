// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Dialog, Tooltip, TooltipProvider } from "./ui";
import { backLayerCount } from "./backStack";
import { installBackOrder } from "./backOrder";
import { dismissTopLayer } from "@/android/backLayers";
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
