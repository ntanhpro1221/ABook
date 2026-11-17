// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";

vi.mock("../studio/api", () => ({ api: vi.fn(), mediaUrl: (path: string) => path }));
vi.mock("../listen/EditBook", () => ({ useBookMusic: () => ({ change: { mutate: vi.fn(), isPending: false } }) }));
vi.mock("../listen/MyMusic", () => ({ MyMusicSection: () => null }));
import { PreviewBar } from "./MusicScreen";
import type { LibraryPreview } from "./preview";
import { S } from "../shared/strings.generated";
import { TooltipProvider } from "../shared/ui";

/** Ảnh của chủ sách 17-11 (Kho nhạc trên điện thoại): bấm thanh "Đang nghe thử" mở chi tiết của CHÍNH bài đang nghe thử, cùng `onOpen` mà dòng bài gọi;
 *  nút ■ chỉ dừng nghe thử; bấm vào chỗ trống / phần đệm của thanh không tới dòng bài nằm dưới (thanh không có lớp `pointer-events-none`). */
function previewOf(patch: Partial<LibraryPreview> = {}): LibraryPreview {
  return {
    playing: { link: "https://music/03.mp3", title: "03 Jungle of Mysteries" }, loading: false, error: "", paused: false,
    toggle: vi.fn(), stop: vi.fn(), position: 0, duration: 0, seek: vi.fn(), retry: vi.fn(), ...patch,
  } as LibraryPreview;
}

const roots: { unmount: () => void; host: HTMLElement }[] = [];
afterEach(async () => {
  for (const { unmount, host } of roots.splice(0)) { await act(async () => unmount()); host.remove(); }
});

async function render(preview: LibraryPreview, onOpen: (link: string) => void) {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div");
  document.body.append(host);
  // Dòng bài "nằm dưới" thanh: một nút bấm được là anh em của thanh, như danh sách và thanh trong MusicScreen.
  const row = vi.fn();
  const root = createRoot(host);
  await act(async () => root.render(<TooltipProvider><div><button type="button" data-row onClick={row}>row</button><PreviewBar preview={preview} onOpen={onOpen} /></div></TooltipProvider>));
  roots.push({ unmount: () => root.unmount(), host });
  return { host, row };
}

it("opens the previewing track from the bar body, like tapping its row", async () => {
  const onOpen = vi.fn();
  const preview = previewOf();
  const { host, row } = await render(preview, onOpen);
  const body = host.querySelector<HTMLButtonElement>("[data-preview-open]")!;
  // Tên đọc = chính dòng chữ (trạng thái · tên bài), gợi ý "Mở" ở mô tả - như Qt và Android.
  expect(body.getAttribute("aria-label")).toBeNull();
  expect(body.textContent).toBe(`${S.s_dang_nghe_thu_f1fb4cba} · 03 Jungle of Mysteries`);
  expect(body.getAttribute("aria-description")).toBe(S.s_mo_741bd2c2);
  expect(body.className).toContain("press");
  await act(async () => body.click());
  expect(onOpen).toHaveBeenCalledExactlyOnceWith("https://music/03.mp3");
  expect(preview.stop).not.toHaveBeenCalled();
  expect(row).not.toHaveBeenCalled();
});

it("stop only stops the preview and never opens the track", async () => {
  const onOpen = vi.fn();
  const preview = previewOf();
  const { host, row } = await render(preview, onOpen);
  const stop = host.querySelector<HTMLButtonElement>(`[aria-label="${S.s_dung_nghe_thu_41a2925b}"]`)!;
  await act(async () => stop.click());
  expect(preview.stop).toHaveBeenCalledOnce();
  expect(onOpen).not.toHaveBeenCalled();
  expect(row).not.toHaveBeenCalled();
});

it("the screen-reader name keeps the buffering / paused state", async () => {
  for (const [patch, status] of [[{ loading: true }, S.s_buffering], [{ paused: true }, S.s_music_paused]] as const) {
    const { host } = await render(previewOf(patch), vi.fn());
    const body = host.querySelector<HTMLButtonElement>("[data-preview-open]")!;
    expect(body.getAttribute("aria-label")).toBeNull();
    expect(body.textContent).toBe(`${status} · 03 Jungle of Mysteries`);
  }
});

it("a long title wraps instead of being cut", async () => {
  const { host } = await render(previewOf(), vi.fn());
  const line = host.querySelector("[data-preview-open] span.text-sm")!;
  expect(line.className).not.toMatch(/truncate|line-clamp|text-ellipsis|whitespace-nowrap/);
  expect(line.className).toContain("break-words");
});

// Phạm vi: happy-dom không dàn trang, nên ca này chỉ giữ hai điều - cú bấm vào chính thanh không gọi gì, và không lớp nào cho cú bấm đi
// xuyên (pointer-events-none). Phép bấm thật vào phần đệm / khe của thanh nằm ở scripts/check_preview_bar.mjs (Chromium, elementFromPoint).
it("a click on the bar's padding reaches neither the row below nor the open action", async () => {
  const onOpen = vi.fn();
  const { host, row } = await render(previewOf(), onOpen);
  const bar = host.querySelector<HTMLElement>("[data-preview-bar]")!;
  await act(async () => bar.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  expect(onOpen).not.toHaveBeenCalled();
  expect(row).not.toHaveBeenCalled();
  // Không lớp nào từ thanh lên tới gốc của nó cho cú bấm đi xuyên.
  for (let node: HTMLElement | null = bar; node && node !== host; node = node.parentElement) {
    expect(node.className).not.toMatch(/pointer-events-none/);
  }
});
