import { useMutation } from "@tanstack/react-query";
import { Pause, Volume2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useClip } from "@/listen/clip";
import type { ReadAloudTry } from "@/listen/readings";
import { cn } from "@/shared/cn";
import { Button } from "@/shared/ui";
import { api, ApiError, suggestionOf, urls } from "./api";
import { useCachedBook } from "./data";
import { previewCaption, refusalText, tryNote } from "./previewText";

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
 *  `unavailable`: lý do không nghe thử được ở cuốn này (không có xưởng để thu thử) - nút vẫn hiện, mờ đi, kèm câu ấy; có `aloud` (trang nghe,
 *  máy có giọng đọc) thì nút nghe thử bằng giọng đọc của "Nghe ngay" thay vì mờ đi (listen/readings.ts). */
export function useTryReading({
  bookId,
  surface,
  spoken,
  disabled,
  onRejected,
  unavailable,
  aloud,
}: {
  bookId: string;
  surface: string;
  spoken: string;
  disabled: boolean;
  onRejected: (message: string, suggestion: string) => void;
  unavailable?: string;
  aloud?: ReadAloudTry;
}): { button: ReactNode; note: ReactNode } {
  const clip = useClip();
  // Sách đang thu (không phải tạm dừng) thì máy chủ từ chối nghe thử - nói trước, đừng đợi bấm mới biết.
  const book = useCachedBook(bookId).data?.book;
  const bookBusy = Boolean(book && (book.running || book.starting) && !book.paused);
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
      const reason = error instanceof ApiError ? error.detail.reason : undefined;
      const why = refusalText(reason, error.message);
      setRefusal(why === error.message ? `Chưa nghe thử được - ${why}` : why);
    },
  });
  useEffect(() => setRefusal(""), [spoken]);
  // Đã nghe đúng cách đọc này rồi thì bấm lại là phát lại, không hỏi máy chủ.
  const same = heard !== null && heard.surface === surface && heard.spoken === spoken;
  const playing = same && clip.current === `try-${heard.preview.url}`;
  if (unavailable && aloud?.available) {
    const speaking = aloud.playing(surface, spoken);
    return {
      button: (
        <Button
          size="sm"
          variant="secondary"
          type="button"
          disabled={disabled || !spoken}
          loading={aloud.loading(surface, spoken)}
          onClick={() => void aloud.play(surface, spoken)}
          aria-label={speaking ? "Dừng nghe thử" : `Nghe thử ${surface} đọc là ${spoken}`}
        >
          {speaking ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Volume2 className="size-4" strokeWidth={2} />}
          {speaking ? "Dừng" : "Nghe thử"}
        </Button>
      ),
      note: aloud.failed ? (
        <p role="status" className="text-xs text-fg-2">{aloud.failed}</p>
      ) : (
        <p className="text-xs text-fg-3">Nghe thử bằng giọng đọc của máy - giọng trong sách nói có thể đọc hơi khác.</p>
      ),
    };
  }
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
  const status = tryNote({
    pending: ask.isPending,
    refusal,
    playing,
    caption: same ? previewCaption(heard.preview.text, heard.preview.speaker) : null,
    bookBusy,
  });
  const note = unavailable ? (
    <p className="text-xs text-fg-3">Chưa nghe thử được: {unavailable}</p>
  ) : status ? (
    <p role="status" className={cn("text-xs", refusal && !ask.isPending ? "text-warning" : "text-fg-3")}>
      {status}
    </p>
  ) : null;
  return { button, note };
}
