import type { SentenceEditing } from "@/listen/SentenceMenu";

/** Màn đọc và tab "Đọc theo" của máy tính sửa được gì: Studio từ xa không sửa từng câu / mở Studio; thiết bị từ xa có quyền sửa dạy được
 *  giọng đọc một từ (PUT readings ở remote_studio.ALLOWED); cuốn có xưởng mở đúng câu ở tab Kịch bản của Studio. */
export function readerEditing(info: { remote?: unknown; listenOnly?: boolean } | undefined): SentenceEditing {
  return {
    // Chưa biết máy là gì (đang hỏi máy chủ): chưa cho sửa.
    editing: Boolean(info) && !info?.remote,
    teachWords: Boolean(info) && !info?.listenOnly,
    onOpenStudioScript: (bookId, chapterId, stableId) =>
      window.location.assign(`#/studio/${bookId}?tab=script&chapter=${chapterId}&line=${encodeURIComponent(stableId)}`),
  };
}
