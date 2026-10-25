// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { dismissTopLayer } from "@/android/backLayers";
import { PlaylistSubmenu } from "@/listen/PlaylistChoice";
import { ActionMenu, ActionSubmenu } from "./ActionMenu";

vi.mock("@/studio/api", async (original) => ({
  ...(await original<typeof import("@/studio/api")>()),
  api: vi.fn(async (path: string) => (path.includes("playlists") ? { playlists: [], mine: 0, error: "" } : {})),
}));

// Menu sách trên điện thoại: menu con (Nhạc nền) là một bước ngay trong Sheet, không phải SubContent nổi rơi ra ngoài mép (emulator 412 dp: x = -230);
// Back / Esc đầu về danh sách chính, lần hai mới đóng Sheet.
let root: Root;
let phone = true;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  phone = true;
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: phone && query.includes("max-width"), addEventListener() {}, removeEventListener() {} }));
  // happy-dom: MotionRegion chụp ảnh nội dung cũ để trượt; cần lặp được CSSStyleDeclaration và animate() giả.
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const wait = () => act(() => new Promise(resolve => setTimeout(resolve, 40)));
const dialog = () => document.querySelector<HTMLElement>('[role="dialog"][data-state="open"]');
const list = () => document.querySelector<HTMLElement>("[data-action-list]");
const stepHost = () => document.querySelector<HTMLElement>("[data-action-step]");
const item = (text: string) => Array.from(document.querySelectorAll<HTMLElement>('[role="menuitem"]')).find(element => element.textContent?.includes(text));
const escape = () => act(() => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })); });

async function openBookMenu() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await act(() => root.render(<QueryClientProvider client={client}>
    <ActionMenu title="Việc với sách" trigger={<button>Thêm</button>}>
      <DropdownMenu.Item>Xuất MP3</DropdownMenu.Item>
      <PlaylistSubmenu bookId="b1" />
    </ActionMenu>
  </QueryClientProvider>));
  await act(() => { document.querySelector<HTMLButtonElement>("button")!.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 })); });
  await wait();
}
async function enterMusicStep() {
  await act(() => item("Nhạc nền")!.click()); await wait();
}

it("điện thoại: Nhạc nền mở thành một bước trong Sheet, không phải menu con nổi", async () => {
  await openBookMenu();
  expect(dialog()).not.toBeNull();
  expect(stepHost()?.hidden).toBe(true);
  await enterMusicStep();
  const sheet = dialog()!;
  expect(sheet).not.toBeNull(); // Sheet vẫn mở
  const step = stepHost()!;
  expect(step.hidden).toBe(false);
  expect(sheet.contains(step)).toBe(true);
  expect(step.dataset.actionStep).toBe("music");
  // Các lựa chọn nằm trong Sheet; chỉ có đúng một menu (không có SubContent thứ hai ở cuối body).
  expect(sheet.contains(item("Để máy chọn")!)).toBe(true);
  expect(document.querySelectorAll('[role="menu"]').length).toBe(1);
  // Nút Quay lại ở đầu bước; danh sách chính ẩn (không gỡ) và không bấm được.
  expect(step.querySelector('[role="menuitem"]')?.textContent).toContain("Quay lại");
  expect(list()?.hidden).toBe(true);
  expect(list()?.inert).toBe(true);
  expect(item("Xuất MP3") && list()!.contains(item("Xuất MP3")!)).toBe(true);
});

it("Back đầu về danh sách chính khi Sheet còn mở; Back thứ hai đóng Sheet", async () => {
  await openBookMenu();
  await enterMusicStep();
  await act(() => { expect(dismissTopLayer()).toBe(true); }); await wait();
  expect(dialog()).not.toBeNull();
  expect(list()?.hidden).toBe(false);
  expect(list()?.getAttribute("data-direction")).toBe("back");
  expect(list()?.classList.contains("motion-step")).toBe(true); // về từ trái
  expect(stepHost()?.hidden).toBe(true);
  expect(stepHost()?.childElementCount).toBe(0);
  expect(document.activeElement).toBe(list()); // mở bằng chạm: tiêu điểm về khung danh sách, không tô mục nào
  await act(() => { expect(dismissTopLayer()).toBe(true); }); await wait();
  expect(dialog()).toBeNull();
});

it("Esc bàn phím: lần đầu về danh sách chính, lần hai đóng Sheet", async () => {
  await openBookMenu();
  await enterMusicStep();
  await escape(); await wait();
  expect(dialog()).not.toBeNull();
  expect(list()?.hidden).toBe(false);
  expect(stepHost()?.hidden).toBe(true);
  await escape(); await wait();
  expect(dialog()).toBeNull();
});

it("nút Quay lại về danh sách chính; mở Sheet lần sau luôn bắt đầu ở danh sách chính", async () => {
  await openBookMenu();
  await enterMusicStep();
  await act(() => item("Quay lại")!.click()); await wait();
  expect(dialog()).not.toBeNull();
  expect(list()?.hidden).toBe(false);
  await enterMusicStep();
  await escape(); await escape(); await wait();
  expect(dialog()).toBeNull();
  await act(() => { document.querySelector<HTMLButtonElement>("button")!.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 })); }); await wait();
  expect(list()?.hidden).toBe(false);
  expect(stepHost()?.hidden).toBe(true);
});

it("chọn một lựa chọn trong bước thì đóng Sheet như mục thường", async () => {
  const picked = vi.fn();
  await act(() => root.render(<ActionMenu title="Việc với sách" trigger={<button>Thêm</button>}>
    <ActionSubmenu id="hai" label="Mục hai" trigger={<span>Mục hai</span>}>
      <DropdownMenu.Item onSelect={picked}>Chọn A</DropdownMenu.Item>
    </ActionSubmenu>
  </ActionMenu>));
  await act(() => { document.querySelector<HTMLButtonElement>("button")!.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 })); }); await wait();
  await act(() => item("Mục hai")!.click()); await wait();
  expect(dialog()!.contains(item("Chọn A")!)).toBe(true);
  await act(() => item("Chọn A")!.click()); await wait();
  expect(picked).toHaveBeenCalledOnce();
  expect(dialog()).toBeNull();
});

it("máy tính giữ menu con nổi của Radix, không dựng bước trong Sheet", async () => {
  phone = false;
  await openBookMenu();
  expect(dialog()).toBeNull();
  expect(stepHost()).toBeNull();
  await act(() => { item("Nhạc nền")!.click(); }); await wait();
  expect(document.querySelectorAll('[role="menu"]').length).toBe(2);
  expect(item("Quay lại")).toBeUndefined();
});

it("điện thoại: chạm mở bước thì không mục nào bị tô; mở bằng phím thì tiêu điểm vào Quay lại và trả về Nhạc nền", async () => {
  await openBookMenu();
  await act(() => { item("Nhạc nền")!.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 })); item("Nhạc nền")!.click(); }); await wait();
  expect(document.activeElement).toBe(stepHost());
  expect(document.querySelector("[data-highlighted]")).toBeNull();
  await act(() => item("Quay lại")!.click()); await wait();
  expect(document.activeElement).toBe(list());

  await act(() => { item("Nhạc nền")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true })); }); await wait();
  expect(stepHost()?.hidden).toBe(false);
  expect(document.activeElement?.textContent).toContain("Quay lại");
  await escape(); await wait();
  expect(document.activeElement?.textContent).toContain("Nhạc nền");
});
