import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "./api";

// Cách đọc cho BẤT KỲ chữ nào ("TP.HCM", "km/h"): trước khi lưu, nói nó chạm tới bao nhiêu câu (webui/name_readings.reading_reach).

export interface Reach {
  surface: string;
  /** Câu có chữ ấy; `reached` là những câu mà cách đọc thật sự dùng được (ký hiệu bị đổi thành quãng nghỉ thì không), `blocked` là phần còn lại. */
  lines: number;
  reached: number;
  recorded: number;
  blocked: number;
  cost: string;
  chapters: { chapterId: number; title: string; lines: number; recorded: number }[];
  example: { segmentId: number; chapterTitle: string; seq: number; text: string; hasAudio: boolean } | null;
}

/** Gõ xong mới hỏi (mỗi phím một lượt hỏi là phí). */
function useSettled(value: string, ms = 350): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

export function useReach(bookId: string, surface: string, enabled = true) {
  const asked = useSettled(surface.trim());
  return useQuery({
    queryKey: ["pronunciations", bookId, "reach", asked],
    enabled: enabled && Boolean(asked),
    queryFn: () => api<Reach>(`/api/books/${bookId}/pronunciations/reach?surface=${encodeURIComponent(asked)}`),
    staleTime: 15_000,
  });
}

function where(reach: Reach): string {
  const named = reach.chapters.slice(0, 3).map((chapter) => chapter.title || `chương ${chapter.chapterId}`);
  const more = reach.chapters.length - named.length;
  return named.length ? ` · ở ${named.join(", ")}${more > 0 ? ` và ${more} chương nữa` : ""}` : "";
}

/** Dòng dưới ô khi đang thêm cách đọc: có bao nhiêu câu, bao nhiêu câu đã thu sẽ phải thu lại. */
export function reachSummary(reach: Reach): string {
  if (!reach.lines) return "Chưa có câu nào có chữ này - cách đọc sẽ được dùng khi chữ xuất hiện.";
  if (!reach.reached) {
    return `Có ${reach.lines} câu có chữ này, nhưng ký hiệu trong đó bị đổi thành quãng nghỉ trước khi tra cách đọc nên máy chưa dùng được cách đọc cho chữ này.`;
  }
  const cost = reach.recorded ? `${reach.recorded} câu đã thu sẽ được thu lại` : "chưa thu câu nào nên không phải thu lại";
  const blocked = reach.blocked ? ` (${reach.blocked} câu khác không dùng được vì ký hiệu)` : "";
  return `${reach.reached} câu có chữ này · ${cost}${where(reach)}${blocked}`;
}

/** Vế "câu đã thu thì thu lại" của thông báo sau khi lưu, theo số đo thật. */
export function reachSaved(reach: Reach, when: string): string {
  if (!reach.lines) return "Phần này chưa có câu nào có chữ này - cách đọc sẽ được dùng khi chữ xuất hiện.";
  if (!reach.reached) return "Máy chưa dùng được cách đọc này cho chữ có ký hiệu bị đổi thành quãng nghỉ - câu giữ nguyên.";
  return `${reach.recorded ? `${reach.recorded} câu đã thu có chữ này sẽ được thu lại.` : "Các câu có chữ này chưa thu nên không phải thu lại."} ${when}`;
}
