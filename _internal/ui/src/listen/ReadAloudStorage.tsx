import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button, Dialog } from "@/shared/ui";
import { PREPARE_STATUS_KEY, clearStorageQuestion, storageLabel, type ReadAloudCacheUsage } from "./prepareAhead";
import { READINGS_CHANGED_EVENT, type ReadingsChanged } from "./readAloud";

// Cài đặt > Giọng đọc: bản đọc đã làm (các đoạn đã đọc xong nằm trong bộ đệm của máy, kể cả phần "Làm trước") chiếm bao nhiêu, và "Dọn bản đọc đã làm".
// Hỏi lại trong hộp thoại dùng chung (Dialog): con trỏ vào hộp, Esc huỷ, đóng xong con trỏ về nút "Dọn bản đọc đã làm" (soát a100 V4: khối hỏi nội tuyến làm con trỏ
// rơi về BODY và Esc không huỷ). Cùng câu hỏi với "Xoá bản đọc đã làm" ở menu Giọng đọc của trình phát (PlayerViews.ReadAloudCache), nhưng cho cả máy.

export interface ReadAloudStorageApi {
  usage(): Promise<ReadAloudCacheUsage>;
  clear(): Promise<ReadAloudCacheUsage>;
}

export const STORAGE_KEY = ["readaloud", "storage"] as const;

/** Hộp hỏi lại trước khi dọn. Đang dọn thì chưa đóng được (Esc, bấm ra ngoài, "Giữ lại" đều bị bỏ qua) - xong hàm gọi sẽ tự đóng. */
export function ClearDialog({ open, onOpenChange, usage, busy, onClear }: { open: boolean; onOpenChange: (open: boolean) => void; usage: ReadAloudCacheUsage; busy: boolean; onClear: () => void }) {
  return (
    <Dialog open={open} onOpenChange={(next) => (busy ? undefined : onOpenChange(next))} title="Dọn bản đọc đã làm" description={clearStorageQuestion(usage)}>
      <div className="dialog-actions">
        <Button variant="ghost" disabled={busy} onClick={() => onOpenChange(false)}>
          Giữ lại
        </Button>
        <Button variant="danger" loading={busy} onClick={onClear}>
          Dọn
        </Button>
      </div>
    </Dialog>
  );
}

export function ReadAloudStorage({ api }: { api: ReadAloudStorageApi }) {
  const client = useQueryClient();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const region = useRef<HTMLDivElement | null>(null);
  const { data: usage } = useQuery({ queryKey: STORAGE_KEY, queryFn: () => api.usage(), refetchInterval: 15000 });
  if (!usage) return null;
  const clear = async () => {
    setBusy(true);
    try {
      client.setQueryData(STORAGE_KEY, await api.clear());
      // Mọi thứ nhớ về bản đọc cũ đều hỏi lại: trạng thái "Làm trước", số liệu từng cuốn ở menu Giọng đọc, và clip đã nạp sẵn của chương đang mở.
      void client.invalidateQueries({ queryKey: PREPARE_STATUS_KEY });
      void client.invalidateQueries({ queryKey: ["readaloud", "cache"] });
      window.dispatchEvent(new CustomEvent<ReadingsChanged>(READINGS_CHANGED_EVENT, { detail: { bookId: "", surfaces: [], all: true } }));
      toast.success("Đã dọn bản đọc đã làm", { description: "Sách và chỗ đang nghe không đổi; đoạn nào nghe tới thì máy đọc lại." });
      // Dọn xong thì nút "Dọn bản đọc đã làm" biến mất (không còn gì để dọn): con trỏ về lại mục này thay vì rơi về BODY khi hộp đóng.
      window.setTimeout(() => region.current?.focus(), 60);
    } catch (error) {
      toast.error("Chưa dọn được bản đọc", { description: (error as Error).message });
    } finally {
      setBusy(false);
      setAsking(false);
    }
  };
  return (
    <div data-readaloud-storage ref={region} tabIndex={-1} className="outline-none">
      <h3 className="text-sm font-semibold">Bản đọc đã làm</h3>
      <p className="mt-1 text-[0.8125rem] text-fg-2 text-pretty">
        {storageLabel(usage)} Nghe lại đoạn đã đọc xong thì không phải chờ máy đọc lại; dọn đi thì lấy lại chỗ trống.
      </p>
      {usage.total > 0 && (
        <Button size="sm" className="mt-2" onClick={() => setAsking(true)}>
          Dọn bản đọc đã làm
        </Button>
      )}
      <ClearDialog open={asking && usage.total > 0} onOpenChange={setAsking} usage={usage} busy={busy} onClear={() => void clear()} />
    </div>
  );
}
