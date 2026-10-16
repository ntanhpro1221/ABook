import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/shared/ui";
import { PREPARE_STATUS_KEY, clearStorageQuestion, storageLabel, type ReadAloudCacheUsage } from "./prepareAhead";
import { READINGS_CHANGED_EVENT, type ReadingsChanged } from "./readAloud";

// Cài đặt > Giọng đọc: bản đọc đã làm (các đoạn đã đọc xong nằm trong bộ đệm của máy, kể cả phần "Làm trước") chiếm bao nhiêu, và "Dọn bản đọc đã làm".
// Hỏi lại ngay tại chỗ (không hộp thoại của trình duyệt), như "Xoá bản đọc đã làm" ở menu Giọng đọc của trình phát (PlayerViews.ReadAloudCache), nhưng cho cả máy.

export interface ReadAloudStorageApi {
  usage(): Promise<ReadAloudCacheUsage>;
  clear(): Promise<ReadAloudCacheUsage>;
}

export const STORAGE_KEY = ["readaloud", "storage"] as const;

export function ReadAloudStorage({ api }: { api: ReadAloudStorageApi }) {
  const client = useQueryClient();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
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
    } catch (error) {
      toast.error("Chưa dọn được bản đọc", { description: (error as Error).message });
    } finally {
      setBusy(false);
      setAsking(false);
    }
  };
  return (
    <div data-readaloud-storage>
      <h3 className="text-sm font-semibold">Bản đọc đã làm</h3>
      <p className="mt-1 text-[0.8125rem] text-fg-2 text-pretty">
        {storageLabel(usage)} Nghe lại đoạn đã đọc xong thì không phải chờ máy đọc lại; dọn đi thì lấy lại chỗ trống.
      </p>
      {usage.total > 0 &&
        (asking ? (
          <div role="alertdialog" aria-label="Dọn bản đọc đã làm" className="mt-2 max-w-xl">
            <p className="text-[0.8125rem] text-fg text-pretty">{clearStorageQuestion(usage)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button size="sm" variant="danger" loading={busy} onClick={() => void clear()}>
                Dọn
              </Button>
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => setAsking(false)}>
                Giữ lại
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" className="mt-2" onClick={() => setAsking(true)}>
            Dọn bản đọc đã làm
          </Button>
        ))}
    </div>
  );
}
