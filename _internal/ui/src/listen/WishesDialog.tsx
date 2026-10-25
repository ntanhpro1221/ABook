import { MoreInfo } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { Button, Dialog } from "@/shared/ui";
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
      toast.error("Không bỏ được thay đổi này", { description: (error as Error).message });
    } finally {
      setDropping(null);
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-[560px]"
      title={syncs ? "Việc chờ gửi" : "Việc chờ Studio"}
      description={
        syncs
          ? "Chờ máy tính nhận và Studio thu lại."
          : "Chờ Studio thu lại; thay đổi đi cùng file sách."
      }
    ><MotionRegion>
      <MoreInfo>{syncs ? "Tự gửi khi kết nối lại máy tính. Chủ máy duyệt Áp dụng hoặc Bỏ qua trước khi Studio thu lại." : "Lưu file sách sẽ mang theo các thay đổi của bạn và thiết bị đã ghép. Mở bằng Studio trên máy tính để áp vào dự án và thu lại."}</MoreInfo>
      {!data ? (
        <p className="text-sm text-fg-2">Đang xem các thay đổi…</p>
      ) : data.items.length ? (
        <PendingList items={data.items} dropping={dropping} onDrop={(item) => void drop(item)} showLines={false} />
      ) : (
        <p className="text-sm text-fg-2">Chưa có việc nào đang chờ.</p>
      )}
      <div className="mt-5 dialog-actions">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          Đóng
        </Button>
      </div>
    </MotionRegion></Dialog>
  );
}
