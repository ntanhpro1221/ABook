// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Dialog, Sheet } from "./ui";
import { toggleDetails } from "./motion";

let root: ReturnType<typeof createRoot>;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  const style = document.createElement("style");
  style.textContent = '.motion-dialog[data-state=open], .motion-sheet[data-state=open], .motion-scrim[data-state=open] { animation-name: enter; animation-duration: 1s; } .motion-dialog[data-state=closed], .motion-sheet[data-state=closed], .motion-scrim[data-state=closed] { animation-name: exit; animation-duration: 1s; }';
  document.head.append(style);
});

it("V7 hộp cũ hoàn tất exit không giật focus khỏi hộp vừa mở", async () => {
  const render = (second: boolean) => act(() => root.render(<>
    <Dialog open={!second} onOpenChange={() => {}} title="Cũ" description="Cũ"><button>Cũ</button></Dialog>
    <Dialog open={second} onOpenChange={() => {}} title="Mới" description="Mới"><button>Mới</button></Dialog>
  </>));
  await render(false); await render(true);
  const old = document.querySelector<HTMLElement>('[role="dialog"][data-state="closed"]')!;
  const current = document.querySelector<HTMLElement>('[role="dialog"][data-state="open"]')!;
  const focused = document.activeElement;
  expect(current.contains(focused)).toBe(true);
  const end = new Event("animationend", { bubbles: true }); Object.defineProperty(end, "animationName", { value: "exit" });
  await act(async () => { old.dispatchEvent(end); await new Promise((done) => setTimeout(done, 20)); });
  expect(document.activeElement).toBe(focused);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); document.head.replaceChildren(); vi.restoreAllMocks(); });

it.each(["dialog", "sheet"])("V7 %s: Content vẫn còn để thoát nhưng inert và chặn pointer ngay", async (kind) => {
  const render = (open: boolean) => act(() => root.render(kind === "dialog"
    ? <Dialog open={open} onOpenChange={() => {}} title="Hộp" description="Nội dung"><button>Thực hiện</button></Dialog>
    : <Sheet open={open} onOpenChange={() => {}} title="Tấm" trigger={<button>Mở</button>}><button>Thực hiện</button></Sheet>));
  await render(true);
  await render(false);
  const content = document.querySelector<HTMLElement>('[role="dialog"][data-state="closed"]')!;
  expect(content).not.toBeNull();
  expect(content.inert).toBe(true);
  expect(content.style.pointerEvents).toBe("none");
  const overlay = document.querySelector<HTMLElement>('.motion-scrim[data-state="closed"]')!;
  expect(overlay.inert).toBe(true);
  expect(overlay.style.pointerEvents).toBe("none");
});

it.each(["dialog", "sheet"])("%s đang mở nhận chạm: Content và nền giữ pointer-events auto của Radix khi body bị khoá (máy ảo 0.4.134)", async (kind) => {
  await act(() => root.render(kind === "dialog"
    ? <Dialog open onOpenChange={() => {}} title="Hộp" description="Nội dung"><button>Thực hiện</button></Dialog>
    : <Sheet open onOpenChange={() => {}} title="Tấm" trigger={<button>Mở</button>}><button>Thực hiện</button></Sheet>));
  expect(document.body.style.pointerEvents).toBe("none");
  const content = document.querySelector<HTMLElement>('[role="dialog"][data-state="open"]')!;
  expect(content.style.pointerEvents).toBe("auto");
  const overlay = document.querySelector<HTMLElement>('.motion-scrim[data-state="open"]')!;
  expect(overlay.style.pointerEvents).toBe("auto");
});

it("V7 details: thân inert khi khép, summary còn đảo chiều và mở lại bỏ inert", () => {
  const details = document.createElement("details");
  details.innerHTML = '<summary>Chi tiết</summary><div><button>Thực hiện</button></div>';
  details.open = true; document.body.append(details);
  const animations: Animation[] = [];
  vi.spyOn(details, "animate").mockImplementation(() => { const animation = { cancel: vi.fn(), onfinish: null, oncancel: null } as unknown as Animation; animations.push(animation); return animation; });
  toggleDetails(details as unknown as Parameters<typeof toggleDetails>[0]);
  expect((details.children[1] as HTMLElement).inert).toBe(true);
  expect((details.children[0] as HTMLElement).inert).toBe(false);
  toggleDetails(details as unknown as Parameters<typeof toggleDetails>[0]);
  expect((details.children[1] as HTMLElement).inert).toBe(false);
  expect(details.open).toBe(true);
  expect(animations).toHaveLength(2);
});
