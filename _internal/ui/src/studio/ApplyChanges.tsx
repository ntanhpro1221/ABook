import { MotionRegion } from "@/shared/MotionRegion";
import { useListPresence } from "@/shared/motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, BookOpenCheck, Mic2, RefreshCw, UserRound, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "@/shared/toast";
import { formatNumber } from "@/shared/format";
import { Button, Dialog, IconButton } from "@/shared/ui";
import { api } from "./api";
import { useVoiceTry } from "./VoiceTry";
import { estimateText, type VoiceRequest } from "./voiceTryText";

// "Áp dụng N thay đổi" mở hộp này thay vì chạy ngay (soát UX a6 01-10: bấm là chạy, không nói sẽ thu lại gì, hết bao lâu; số
// trên nút còn lệch với "chờ áp dụng" ở Việc cần duyệt vì sửa ở Kịch bản / đổi giọng không được liệt kê ở đâu). Máy chủ
// (store.pending_details) liệt kê đủ từng thay đổi bằng lời, số câu ĐÃ THU sẽ thu lại, ở chương nào, và thời gian ước theo
// tốc độ thật của chính cuốn này (chưa đo được thì số ước, nói rõ là ước). Đổi giọng nghe thử được ngay trong hộp, trên một câu
// của chính người ấy (VoiceTry.tsx) - soát UX Studio mục 15: áp là thu lại mà chưa nghe giọng mới lần nào.

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
  /** Đổi giọng: đủ để nghe thử đúng giọng sẽ áp (POST …/voice/preview). */
  voice?: VoiceRequest;
  /** Tên giọng đang chờ để hiện ("Bảo Trang"); `voice.preset` là khoá gửi máy chủ. */
  voiceLabel?: string;
  /** Tên máy đã ghép gửi việc này tới (cuốn nhập từ file - book_wishes.note_sources); không có: ghi ở chính máy này. */
  from?: string;
}

export interface PendingDetails {
  items: PendingItem[];
  lines: number;
  chapters: string[];
  seconds: number;
  /** False: cuốn chưa xong chương nào để đo - `seconds` là số ước dư tay. */
  measured?: boolean;
}

export const KIND_ICON = { pronunciation: BookOpenCheck, speaker: UserRound, line: AudioLines, voice: Mic2, retake: RefreshCw } as const;

/** Nút bỏ một dòng nói rõ nó bỏ gì ("Bỏ cách đọc “Lucien”") - mọi nút cùng nhãn "Bỏ thay đổi này" thì trình đọc màn hình (và chú thích khi rê
 *  chuột) không phân biệt được dòng nào (soát a70). */
export function dropLabel(item: Pick<PendingItem, "kind" | "label">): string {
  if (item.kind === "pronunciation") {
    const surface = /^“([^”]+)”/.exec(item.label)?.[1];
    if (surface) return `Bỏ cách đọc “${surface}”`;
  }
  const verb = { pronunciation: "Bỏ cách đọc", speaker: "Bỏ đổi người nói", line: "Bỏ sửa cách đọc câu", voice: "Bỏ đổi giọng", retake: "Bỏ thu lại" }[item.kind] ?? "Bỏ";
  return `${verb}: ${item.label}`;
}

/** Danh sách từng thay đổi đang chờ, mỗi dòng có nút bỏ (`dropLabel`) - dùng cho cả hộp "Áp dụng" (dự án) lẫn hộp "Việc đang chờ
 *  Studio" của sách không có xưởng (listen/WishesDialog.tsx). `dropping` = id đang bỏ dở; `showLines`: hiện số câu thu lại;
 *  `extra`: nút thêm của một dòng (nghe thử giọng chờ áp). */
export function PendingList({
  items,
  dropping,
  onDrop,
  showLines = true,
  extra,
}: {
  items: PendingItem[];
  dropping: string | null;
  onDrop: (item: PendingItem) => void;
  showLines?: boolean;
  extra?: (item: PendingItem) => ReactNode;
}) {
  const rows = useListPresence(items, (item) => `${item.section}:${item.key}`);
  return (
    <ul className="max-h-72 divide-y divide-line overflow-y-auto rounded-xl border border-line">
      {rows.map(({ item, key, state, ref }) => {
        const Icon = KIND_ICON[item.kind] ?? RefreshCw;
        return (
          <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}><div className="flex items-start gap-3 px-3 py-2 text-sm">
            <Icon className="mt-0.5 size-4 shrink-0 text-fg-3" />
            <span className="min-w-0 flex-1 text-pretty">
              {item.label}
              {item.chapter && <span className="text-fg-3"> · {item.chapter}</span>}
              {item.from && <span className="text-fg-3"> · từ {item.from}</span>}
            </span>
            {showLines && (
              <span className="shrink-0 pt-0.5 text-xs tabular text-fg-3">
                {item.lines ? `${formatNumber(item.lines)} câu thu lại` : "chưa thu - không tốn gì"}
              </span>
            )}
            {extra && <span className="-my-1 shrink-0">{extra(item)}</span>}
            <IconButton
              size="sm"
              icon={X}
              label={dropLabel(item)}
              className="-my-1.5 -mr-1.5"
              disabled={dropping !== null}
              onClick={() => onDrop(item)}
            />
          </div></li>
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
  running,
}: {
  bookId: string;
  count: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApply: () => void;
  /** Sách đang chạy: máy tự áp ở ranh giới chương kế nên không có nút "Áp dụng". Bỏ một việc thì bất cứ lúc nào (máy chủ từ chối việc đã áp). */
  running?: "busy" | "checkpoint";
}) {
  const client = useQueryClient();
  const [dropping, setDropping] = useState<string | null>(null);
  const tryVoice = useVoiceTry(bookId);
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
      title={running ? `${count} thay đổi đang chờ áp` : `Áp dụng ${count} thay đổi?`}
      description={
        running
          ? "Máy tự áp chúng ở chương kế tiếp. Bạn bỏ được một việc ở đây bất cứ lúc nào, miễn là máy chưa áp nó - việc đã áp rồi thì máy báo và giữ nguyên."
          : "Máy chỉ thu lại những câu bị ảnh hưởng, rồi dựng lại các chương có câu ấy - không làm lại cả cuốn."
      }
    ><MotionRegion>
      {!data ? (
        <p className="text-sm text-fg-2">Đang xem các thay đổi…</p>
      ) : (
        <>
          <PendingList
            items={data.items}
            dropping={dropping}
            onDrop={(item) => void drop(item)}
            extra={(item) => (item.voice ? tryVoice.button(item.voice, item.voiceLabel || "mới") : null)}
          />
          {tryVoice.note}
          <p className="mt-3 text-sm text-pretty">
            {data.lines ? (
              <>
                Thu lại <span className="font-semibold">{formatNumber(data.lines)} câu</span> ở {chapters.length} chương (
                {shownChapters})
                {data.seconds > 0 && <> - {estimateText(data.seconds, data.measured)}</>}.
              </>
            ) : (
              "Không câu đã thu nào phải thu lại - máy chỉ ghi các thay đổi vào sách, vài giây là xong."
            )}
          </p>
        </>
      )}
      <div className="mt-5 dialog-actions">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          {running ? "Đóng" : "Để sau"}
        </Button>
        {!running && (
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
        )}
      </div>
    </MotionRegion></Dialog>
  );
}
