import { useQuery } from "@tanstack/react-query";
import { Clock } from "lucide-react";
import { cn } from "@/shared/cn";
import { api } from "@/studio/api";

// Phần nhỏ của "sửa một câu" (LineWishes.tsx) mà trang đọc cần ngay: ý muốn đang chờ Studio và dấu cạnh câu. Hộp sửa câu (cùng các bảng chọn
// của tab Kịch bản) tải lười khi trang đọc mở - không nằm trong gói đầu của app (docs/PERF_WEB.md).

/** Ý muốn của một câu đang chờ Studio (GET /wishes): người nói, cách đọc, thu lại. */
export interface LineWish {
  /** `newGender`: người nghe TẠO người này (chưa có trong sách) - chọn lại ở câu khác cần cùng giới. */
  speaker?: { name: string; shown: string; requestedAt: number; newGender?: "male" | "female" | "unknown"; held?: boolean };
  delivery?: { kind: string; emotion: string; intensity: number | null; spoken?: string; requestedAt: number };
  retake?: { requestedAt: number };
}

export interface NameWish {
  key: string;
  surface: string;
  spokenForm: string;
  requestedAt: number;
}

export interface WishesView {
  pronunciations: NameWish[];
  lines: Record<string, LineWish>;
}

/** Ý muốn theo từng câu của cuốn không có xưởng - trang đọc đánh dấu "đang chờ Studio" ngay trên câu. */
export function useWishes(bookId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["wishes", bookId],
    enabled,
    queryFn: () => api<WishesView>(`/api/books/${bookId}/wishes`),
  });
}

/** Dấu "đang chờ Studio" cạnh một câu trong trang đọc. */
export function WaitingMark({ className }: { className?: string }) {
  return <Clock aria-label="Đang chờ máy làm sách" role="img" className={cn("ml-1 inline size-[0.7em] align-[-0.05em] text-fg-3", className)} />;
}
