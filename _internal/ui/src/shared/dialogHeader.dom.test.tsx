// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Dialog, Sheet } from "./ui";

let root: Root;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });

it.each(["dialog", "sheet"])("%s: header đổi số thứ tự có fade và giữ liên kết ARIA", async kind => {
  const render = (index: number) => act(() => root.render(kind === "dialog"
    ? <Dialog open onOpenChange={() => {}} title={`${index} - Thêm sách từ file`} description={`Đang xem sách ${index}`}><button>Tiếp</button></Dialog>
    : <Sheet open onOpenChange={() => {}} title={`${index} - Thêm sách từ file`} trigger={<button>Mở</button>}><button>Tiếp</button></Sheet>));
  await render(1);
  const dialog = document.querySelector('[role="dialog"]')!;
  const title = document.getElementById(dialog.getAttribute("aria-labelledby")!)!;
  const description = document.getElementById(dialog.getAttribute("aria-describedby") ?? "");
  const titleRegion = title.querySelector<HTMLElement>("[data-motion-region]");
  expect(titleRegion).not.toBeNull();
  if (kind === "dialog") expect(description?.querySelector("[data-motion-region]")).not.toBeNull();
  await render(2);
  expect(document.getElementById(dialog.getAttribute("aria-labelledby")!)).toBe(title);
  expect(title.textContent).toBe("2 - Thêm sách từ file");
  const animated = vi.mocked(HTMLElement.prototype.animate).mock.contexts;
  expect(animated).toContain(titleRegion);
  if (kind === "dialog") {
    expect(document.getElementById(dialog.getAttribute("aria-describedby")!)).toBe(description);
    expect(description?.textContent).toBe("Đang xem sách 2");
    expect(animated).toContain(description?.querySelector("[data-motion-region]"));
  }
});
