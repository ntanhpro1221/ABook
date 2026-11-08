import { S } from "../shared/strings.generated";
import { MoreInfo } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { DialogActions, Button, Dialog } from "@/shared/ui";
import { api } from "@/studio/api";
import { PendingList, type PendingDetails, type PendingItem } from "@/studio/ApplyChanges";
import { refreshAfterEdit } from "./EditBook";

/** "Việc đang chờ Studio" của cuốn không có xưởng (docs/EDITING.md, P2a): những thay đổi người nghe đã ghi (giọng, giới tính, gộp
 *  người nói, cách đọc, sửa câu, thu lại) nằm trong file sách và chưa áp vào audio nào. Mỗi mục bỏ được; bỏ chỉ có tác dụng trên
 *  máy này. Cùng danh sách và cùng nút "Bỏ" với hộp "Áp dụng thay đổi" của dự án. */
export function WishesDialog({
  bookId,
  count,
  open,
  onOpenChange,
  syncs = false,
}: {
  bookId: string;
  count: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Cuốn tải từ máy tính (điện thoại): các việc này đi về máy tính để chủ máy duyệt, không đi cùng file sách. */
  syncs?: boolean;
}) {
  const client = useQueryClient();
  const [dropping, setDropping] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["pending-changes", bookId, count],
    queryFn: () => api<PendingDetails>(`/api/books/${bookId}/pending-changes`),
    enabled: open,
  });
  const drop = async (item: PendingItem) => {
    setDropping(`${item.section}:${item.key}`);
    try {
      await api(`/api/books/${bookId}/pending-changes/withdraw`, {
        method: "POST",
        body: { section: item.section, key: item.key, keys: item.keys, requestedAt: item.requestedAt },
      });
      if ((data?.items.length ?? 0) <= 1) onOpenChange(false);
      refreshAfterEdit(client, bookId);
      await client.invalidateQueries({ queryKey: ["pending-changes", bookId] });
    } catch (error) {
      toast.error(S.s_chua_bo_duoc_thay_doi_nay_eccfaf9b, { description: (error as Error).message });
    } finally {
      setDropping(null);
    }
  };
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={() => onOpenChange(false)}>{S.s_dong_5d54c2a1}</Button>
      </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-[560px]"
      title={syncs ? S.s_viec_cho_gui_2f10547f : S.s_viec_cho_studio_d4715141}
      description={
        syncs
          ? S.s_cho_may_tinh_nhan_va_studio_thu_lai_bfb954a8
          : S.s_cho_studio_thu_lai_thay_doi_di_cung_file_s_5714487e
      }
    ><MotionRegion>
      <MoreInfo>{syncs ? S.s_tu_gui_khi_ket_noi_lai_may_tinh_chu_may_du_aeab54b7 : S.s_luu_file_sach_se_mang_theo_cac_thay_doi_cu_a23d72b4}</MoreInfo>
      {!data ? (
        <p className="text-sm text-fg-2">{S.s_dang_xem_cac_thay_doi_765915d5}</p>
      ) : data.items.length ? (
        <PendingList items={data.items} dropping={dropping} onDrop={(item) => void drop(item)} showLines={false} />
      ) : (
        <p className="text-sm text-fg-2">{S.s_chua_co_viec_nao_dang_cho_5fa38d2b}</p>
      )}

    </MotionRegion></Dialog>
  );
}
