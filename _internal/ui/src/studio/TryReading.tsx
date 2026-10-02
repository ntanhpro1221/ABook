import { useMutation } from "@tanstack/react-query";
import { Pause, Volume2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useClip } from "@/listen/clip";
import { Button } from "@/shared/ui";
import { api, ApiError, suggestionOf, urls } from "./api";
import { previewCaption, refusalText } from "./previewText";

// "Nghe thử" trước khi lưu (webui/reading_preview.py): máy thu thử một câu có tên ấy bằng đúng cách đọc đang gõ, đúng giọng và
// đúng đường của lần thu thật - không ghi gì vào sách. Dùng chung cho dòng "Cách đọc tên" và thẻ hộp việc.

interface ReadingPreview {
  url: string;
  segmentId: number;
  text: string;
  speaker: string;
  cached: boolean;
}

/** Nút "Nghe thử" (`button`, đặt trước nút "Lưu") và dòng nói máy đang làm gì / đã đọc câu nào / vì sao không nghe được (`note`,
 *  đặt dưới hàng nút - nó rộng hơn nút nên không để chung hàng). `spoken`: cách đọc đang gõ. `disabled`: ô đang báo lỗi.
 *  `onRejected`: máy chủ chê cách đọc (sai chính tả, nhiều từ) - cùng lời báo và cách sửa như khi bấm "Lưu".
 *  `unavailable`: lý do không nghe thử được ở cuốn này (không có xưởng để thu thử) - nút vẫn hiện, mờ đi, kèm câu ấy. */
export function useTryReading({
  bookId,
  surface,
  spoken,
  disabled,
  onRejected,
  unavailable,
}: {
  bookId: string;
  surface: string;
  spoken: string;
  disabled: boolean;
  onRejected: (message: string, suggestion: string) => void;
  unavailable?: string;
}): { button: ReactNode; note: ReactNode } {
  const clip = useClip();
  const [heard, setHeard] = useState<{ surface: string; spoken: string; preview: ReadingPreview } | null>(null);
  const [refusal, setRefusal] = useState("");
  const play = (preview: ReadingPreview) => clip.toggle(`try-${preview.url}`, urls.readingPreview(preview.url));
  const ask = useMutation({
    mutationFn: () =>
      api<ReadingPreview>(`/api/books/${bookId}/pronunciation/preview`, { method: "POST", body: { surface, spokenForm: spoken } }),
    onSuccess: (preview) => {
      setHeard({ surface, spoken, preview });
      play(preview);
    },
    onError: (error: Error) => {
      if (error instanceof ApiError && error.status === 400) {
        onRejected(error.message, suggestionOf(error));
        return;
      }
      setRefusal(refusalText(error instanceof ApiError ? error.detail.reason : undefined, error.message));
    },
  });
  useEffect(() => setRefusal(""), [spoken]);
  // Đã nghe đúng cách đọc này rồi thì bấm lại là phát lại, không hỏi máy chủ.
  const same = heard !== null && heard.surface === surface && heard.spoken === spoken;
  const playing = same && clip.current === `try-${heard.preview.url}`;
  const button = (
    <Button
      size="sm"
      variant="secondary"
      type="button"
      disabled={disabled || !spoken || Boolean(unavailable)}
      loading={ask.isPending}
      onClick={() => {
        setRefusal("");
        if (same) play(heard.preview);
        else ask.mutate();
      }}
      aria-label={playing ? "Dừng nghe thử" : `Nghe thử ${surface} đọc là ${spoken}`}
    >
      {playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Volume2 className="size-4" strokeWidth={2} />}
      {playing ? "Dừng" : "Nghe thử"}
    </Button>
  );
  const note = unavailable ? (
    <p className="text-xs text-fg-3">Chưa nghe thử được: {unavailable}</p>
  ) : ask.isPending ? (
    <p role="status" className="text-xs text-fg-2">
      Máy đang đọc thử - lần đầu có thể mất vài chục giây
    </p>
  ) : refusal ? (
    <p role="status" className="text-xs text-fg-2">
      {refusal}
    </p>
  ) : same ? (
    <p className="text-xs text-fg-3">{previewCaption(heard.preview.text, heard.preview.speaker)}</p>
  ) : null;
  return { button, note };
}
