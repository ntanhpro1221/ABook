import type { QueryClient } from "@tanstack/react-query";
import { toast } from "@/shared/toast";
import { musicEditView, musicQuery } from "./EditBook";

/**
 * Loa / TV chỉ nhận file giọng đọc của chương (máy phục vụ chương đã trộn nhạc cần ffmpeg + numpy, là phần tải thêm), nên cuốn có
 * lớp nhạc riêng đang bật mà phát ra ngoài sẽ mất nhạc. Báo trước một dòng, không chặn việc chuyển (soát a104 F3).
 */
export async function noteCastHasNoMusic(client: QueryClient, bookId: string): Promise<void> {
  try {
    const view = musicEditView(await client.fetchQuery(musicQuery(bookId))); // dự án Studio trả {plan, overrides}: đưa về cùng dạng
    if (view.hasMusic && view.enabled) {
      toast.info("Loa, TV chỉ phát giọng đọc", { id: "cast-no-music", description: "Nhạc nền của cuốn này chưa phát được trên loa, TV." });
    }
  } catch {
    // Không đọc được nhạc của cuốn thì không có gì để báo.
  }
}
