import { S } from "../shared/strings.generated";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "@/shared/toast";
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
      if (!item) throw new Error(S.s_lan_gop_nay_da_duoc_ap_hoac_da_bi_thay_ban_a6f706a3);
      await api(`/api/books/${bookId}/speaker`, {
        method: "POST",
        body: { lines: (item.keys ?? [item.key]).map((stableId) => ({ stableId })), withdraw: true, requestedAt: item.requestedAt },
      });
    },
    onSuccess: (_done, person) => {
      refreshAfterDecision(client, bookId);
      toast.success(S.s_da_bo_gop_0_4a404f0a(person.displayName));
    },
    onError: (error: Error) => toast.error(S.s_chua_bo_gop_duoc_68297e79, { description: error.message }),
  });
}
