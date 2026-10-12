import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { CastMember } from "@/listen/model";
import type { PendingDetails } from "./ApplyChanges";
import { api } from "./api";
import { refreshAfterDecision } from "./decisions";

/** "Bỏ gộp" cho người đang ghi "Chờ áp dụng: gộp vào X" (Duyệt trước khi thu, tab Nhân vật). Không có đường riêng: tìm đúng lần
 *  "Gộp vào…" ấy trong danh sách thay đổi đang chờ (cùng mốc `mergedAt` với các câu) rồi rút bằng đường hoàn tác có sẵn của
 *  "Ai nói câu này" - máy chủ rút luôn bí danh ghi cùng mốc, và đường ấy dùng được cả lúc sách đang giữ chờ duyệt. */
export function useUnmerge(bookId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (person: CastMember) => {
      const stamp = person.mergedAt;
      const details = await api<PendingDetails>(`/api/books/${bookId}/pending-changes`);
      const item = typeof stamp === "number" ? details.items.find((entry) => entry.section === "speakers" && Math.abs(entry.requestedAt - stamp) < 1e-6) : undefined;
      if (!item) throw new Error("Lần gộp này đã được áp hoặc đã bị thay bằng lựa chọn khác - mở lại màn này để xem.");
      await api(`/api/books/${bookId}/speaker`, {
        method: "POST",
        body: { lines: (item.keys ?? [item.key]).map((stableId) => ({ stableId })), withdraw: true, requestedAt: item.requestedAt },
      });
    },
    onSuccess: (_done, person) => {
      refreshAfterDecision(client, bookId);
      toast.success(`Đã bỏ gộp ${person.displayName}`, { description: "Các câu của người này trở lại như trước, không còn chờ gộp." });
    },
    onError: (error: Error) => toast.error("Chưa bỏ gộp được", { description: error.message }),
  });
}
