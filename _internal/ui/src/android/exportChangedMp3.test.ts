// @vitest-environment happy-dom
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import type { ListenBook } from "@/listen/model";

const h = vi.hoisted(() => ({
  history: vi.fn(), native: vi.fn(), toast: vi.fn(), loading: vi.fn(), error: vi.fn(),
}));
vi.mock("./plugins", () => ({ EbookLibrary: { exportHistory: h.history, exportMp3: h.native, m4bMusicState: vi.fn(async () => ({ available: false, enabled: false })) } }));
vi.mock("sonner", () => ({ toast: Object.assign(h.toast, { loading: h.loading, error: h.error }) }));
vi.mock("@/shared/cover", () => ({ coverArtwork: () => "cover" }));

// Câu hỏi "chỉ chương đổi hay cả cuốn" có HAI lựa chọn nên là hộp nhỏ, không phải thông báo (thông báo: một dòng + tối đa một nút).
it("bạn chọn chỉ chương đổi: native chỉ nhận các mã ấy; chọn cả cuốn thì không có mã nào", async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  h.history.mockResolvedValue({ exports: [{ kind: "mp3", target: "Music/old", changed: [2, 4] }] });
  h.native.mockResolvedValue({ started: false });
  const { exportMp3, Mp3MusicDialogHost } = await import("./ExportMp3");
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(Mp3MusicDialogHost)));
  const book = { id: "book", title: "Sách", chaptersAvailable: 5 } as ListenBook;

  await act(async () => { await exportMp3(book); });
  expect(h.native).not.toHaveBeenCalled();
  expect(h.toast).not.toHaveBeenCalled();
  const button = (label: string) => Array.from(document.querySelectorAll("button")).find((item) => item.textContent === label) as HTMLButtonElement;
  expect(button("Chỉ 2 chương đổi")).toBeTruthy();
  await act(async () => button("Chỉ 2 chương đổi").click());
  await vi.waitFor(() => expect(h.native).toHaveBeenCalledWith({ bookId: "book", cover: "cover", pick: false, chapterIds: [2, 4] }));

  await act(async () => { await exportMp3(book); });
  await act(async () => button("Cả cuốn").click());
  await vi.waitFor(() => expect(h.native).toHaveBeenLastCalledWith({ bookId: "book", cover: "cover", pick: false }));
  await act(async () => root.unmount());
});
