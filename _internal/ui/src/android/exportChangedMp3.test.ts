import { expect, it, vi } from "vitest";
import type { ListenBook } from "@/listen/model";

const h = vi.hoisted(() => ({
  history: vi.fn(), native: vi.fn(), toast: vi.fn(), loading: vi.fn(), error: vi.fn(),
}));
vi.mock("./plugins", () => ({ EbookLibrary: { exportHistory: h.history, exportMp3: h.native } }));
vi.mock("sonner", () => ({ toast: Object.assign(h.toast, { loading: h.loading, error: h.error }) }));
vi.mock("@/shared/cover", () => ({ coverArtwork: () => "cover" }));

it("bạn chọn chỉ chương đổi: native chỉ nhận các mã ấy", async () => {
  h.history.mockResolvedValue({ exports: [{ kind: "mp3", target: "Music/old", changed: [2, 4] }] });
  h.native.mockResolvedValue({ started: false });
  const { exportMp3 } = await import("./ExportMp3");
  const book = { id: "book", title: "Sách", chaptersAvailable: 5 } as ListenBook;
  await exportMp3(book);
  expect(h.native).not.toHaveBeenCalled();
  const choices = h.toast.mock.calls[0][1];
  expect(choices.action.label).toBe("Chỉ 2 chương đổi");
  choices.action.onClick();
  await vi.waitFor(() => expect(h.native).toHaveBeenCalledWith({ bookId: "book", cover: "cover", pick: false, chapterIds: [2, 4] }));
  choices.cancel.onClick();
  await vi.waitFor(() => expect(h.native).toHaveBeenLastCalledWith({ bookId: "book", cover: "cover", pick: false }));
});
