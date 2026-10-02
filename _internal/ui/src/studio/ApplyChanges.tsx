import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, BookOpenCheck, Mic2, RefreshCw, UserRound, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { formatLength, formatNumber } from "@/shared/format";
import { Button, Dialog, IconButton } from "@/shared/ui";
import { api } from "./api";

// "Áp dụng N thay đổi" mở hộp này thay vì chạy ngay (soát UX a6 01-10: bấm là chạy, không nói sẽ thu lại gì, hết bao lâu; số
// trên nút còn lệch với "chờ áp dụng" ở Việc cần duyệt vì sửa ở Kịch bản / đổi giọng không được liệt kê ở đâu). Máy chủ
// (store.pending_details) liệt kê đủ từng thay đổi bằng lời, số câu ĐÃ THU sẽ thu lại, ở chương nào, và thời gian ước theo
// tốc độ thật của chính cuốn này.

export interface PendingItem {
  kind: "pronunciation" | "speaker" | "line" | "voice" | "retake";
  label: string;
  chapter?: string;
  lines: number;
  /** Đủ để bỏ đúng yêu cầu này (POST …/pending-changes/withdraw). */
  section: string;
  key: string;
  /** "Thu lại cả chương": mọi câu của một lần bấm - bỏ thì bỏ cả nhóm. */
  keys?: string[];
  requestedAt: number;
}

export interface PendingDetails {
  items: PendingItem[];
  lines: number;
  chapters: string[];
  seconds: number;
}

export const KIND_ICON = { pronunciation: BookOpenCheck, speaker: UserRound, line: AudioLines, voice: Mic2, retake: RefreshCw } as const;

/** Danh sách từng thay đổi đang chờ, mỗi dòng có nút "Bỏ thay đổi này" - dùng cho cả hộp "Áp dụng" (dự án) lẫn hộp "Việc đang chờ
 *  Studio" của sách không có xưởng (listen/WishesDialog.tsx). `dropping` = id đang bỏ dở; `showLines`: hiện số câu thu lại. */
export function PendingList({
  items,
  dropping,
  onDrop,
  showLines = true,
}: {
  items: PendingItem[];
  dropping: string | null;
  onDrop: (item: PendingItem) => void;
  showLines?: boolean;
}) {
  return (
    <ul className="max-h-72 divide-y divide-line overflow-y-auto rounded-xl border border-line">
      {items.map((item) => {
        const Icon = KIND_ICON[item.kind] ?? RefreshCw;
        return (
          <li key={`${item.section}:${item.key}`} className="flex items-start gap-3 px-3 py-2 text-sm">
            <Icon className="mt-0.5 size-4 shrink-0 text-fg-3" />
            <span className="min-w-0 flex-1 text-pretty">
              {item.label}
              {item.chapter && <span className="text-fg-3"> · {item.chapter}</span>}
            </span>
            {showLines && (
              <span className="shrink-0 pt-0.5 text-xs tabular text-fg-3">
                {item.lines ? `${formatNumber(item.lines)} câu thu lại` : "chưa thu - không tốn gì"}
              </span>
            )}
            <IconButton
              size="sm"
              icon={X}
              label="Bỏ thay đổi này"
              className="-my-1.5 -mr-1.5"
              disabled={dropping !== null}
              onClick={() => onDrop(item)}
            />
          </li>
        );
      })}
    </ul>
  );
}

export function ApplyChangesDialog({
  bookId,
  count,
  open,
  onOpenChange,
  onApply,
}: {
  bookId: string;
  count: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApply: () => void;
}) {
  const client = useQueryClient();
  const [dropping, setDropping] = useState<string | null>(null);
  // Bỏ một mục ngay tại đây (soát UX a6 01-10: muốn bỏ thì phải đi tìm lại đúng thẻ ở ba tab). Lựa chọn trước đó, nếu có,
  // trở lại; mọi màn đọc lại (số trên nút, Việc cần duyệt, Kịch bản).
  const drop = async (item: PendingItem) => {
    const id = `${item.section}:${item.key}`;
    setDropping(id);
    try {
      await api(`/api/books/${bookId}/pending-changes/withdraw`, {
        method: "POST",
        body: { section: item.section, key: item.key, keys: item.keys, requestedAt: item.requestedAt },
      });
      if (count <= 1) onOpenChange(false);
      await client.invalidateQueries();
    } catch (error) {
      toast.error("Không bỏ được thay đổi này", { description: (error as Error).message });
    } finally {
      setDropping(null);
    }
  };
  const { data } = useQuery({
    queryKey: ["pending-changes", bookId, count],
    queryFn: () => api<PendingDetails>(`/api/books/${bookId}/pending-changes`),
    enabled: open,
  });
  const chapters = data?.chapters ?? [];
  const shownChapters = chapters.slice(0, 4).join(", ") + (chapters.length > 4 ? `, và ${chapters.length - 4} chương khác` : "");
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-xl"
      title={`Áp dụng ${count} thay đổi?`}
      description="Máy chỉ thu lại những câu bị ảnh hưởng, rồi dựng lại các chương có câu ấy - không làm lại cả cuốn."
    >
      {!data ? (
        <p className="text-sm text-fg-2">Đang xem các thay đổi…</p>
      ) : (
        <>
          <PendingList items={data.items} dropping={dropping} onDrop={(item) => void drop(item)} />
          <p className="mt-3 text-sm text-pretty">
            {data.lines ? (
              <>
                Thu lại <span className="font-semibold">{formatNumber(data.lines)} câu</span> ở {chapters.length} chương (
                {shownChapters})
                {data.seconds > 0 && <> - khoảng <span className="font-semibold">{formatLength(data.seconds)}</span> trên máy này</>}.
              </>
            ) : (
              "Không câu đã thu nào phải thu lại - máy chỉ ghi các thay đổi vào sách, vài giây là xong."
            )}
          </p>
        </>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          Để sau
        </Button>
        <Button
          variant="primary"
          icon={RefreshCw}
          onClick={() => {
            onOpenChange(false);
            onApply();
          }}
        >
          Áp dụng
        </Button>
      </div>
    </Dialog>
  );
}
