import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
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
      width="max-w-xl"
      title={syncs ? "Việc chờ gửi về máy tính" : "Việc đang chờ máy làm sách"}
      description={
        syncs
          ? "Bạn đã ghi những thay đổi này; giọng đọc chỉ đổi khi máy tính làm lại sách. Chúng được gửi về máy tính (tự động khi tới được máy tính); ở đó bạn xem và chọn Áp dụng hay Bỏ qua từng việc - không việc nào tự áp."
          : "Bạn đã ghi những thay đổi này; giọng đọc chỉ đổi khi một máy làm sách (ABook Studio trên máy tính) làm lại. Chúng đi cùng file sách khi bạn lưu; mở file ở máy ấy, ABook sẽ hỏi có áp vào dự án không."
      }
    >
      {!data ? (
        <p className="text-sm text-fg-2">Đang xem các thay đổi…</p>
      ) : data.items.length ? (
        <PendingList items={data.items} dropping={dropping} onDrop={(item) => void drop(item)} showLines={false} />
      ) : (
        <p className="text-sm text-fg-2">Chưa có việc nào đang chờ.</p>
      )}
      <div className="mt-5 flex justify-end">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          Đóng
        </Button>
      </div>
    </Dialog>
  );
}
