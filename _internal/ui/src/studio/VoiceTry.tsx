import { BookOpenText, Loader2, Pause } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { Button, Vu } from "@/shared/ui";
import { api, ApiError, urls } from "./api";
import { previewCaption, refusalText } from "./previewText";
import { tryKey, type VoiceRequest } from "./voiceTryText";

// "Nghe thử bằng câu của sách" (webui/reading_preview.py `voice_preview`): máy thu thử một câu của chính nhân vật bằng giọng
// đang cân nhắc - đúng giọng sẽ áp, đúng đường của lần thu thật, không ghi gì vào sách. Dùng ở hộp "Đổi giọng" (một nút mỗi
// giọng) và hộp "Áp dụng" (giọng đang chờ áp). Máy đang làm sách hay card bận thì báo, không chen vào; người chưa có câu nào
// thì phát câu mẫu chung của giọng.

interface VoicePreview {
  url: string;
  segmentId: number;
  text: string;
  speaker: string;
  cached: boolean;
}

// Bản đã nghe trong phiên (theo sách, người, giọng): bấm lại là phát lại, không hỏi máy chủ.
const heard = new Map<string, VoicePreview>();

/** `button(request, voiceName, options)`: nút nghe thử cho một giọng; `note`: một dòng máy đang làm gì / đã đọc câu nào / vì sao
 *  chưa nghe được - đặt một chỗ cho cả danh sách. `fallbackUrl`: câu mẫu chung của giọng, phát khi người ấy không có câu nào. */
export function useVoiceTry(bookId: string): {
  button: (request: VoiceRequest, voiceName: string, options?: { fallbackUrl?: string; compact?: boolean; disabled?: boolean }) => ReactNode;
  note: ReactNode;
} {
  const clip = useClip();
  const [asking, setAsking] = useState<string | null>(null);
  const [said, setSaid] = useState<{ text: string; status: boolean } | null>(null);
  const clipId = (preview: VoicePreview) => `voice-try-${preview.url}`;
  const play = (preview: VoicePreview, voiceName: string) => {
    clip.toggle(clipId(preview), urls.readingPreview(preview.url));
    setSaid({ text: previewCaption(preview.text, voiceName), status: false });
  };
  const ask = async (request: VoiceRequest, voiceName: string, fallbackUrl?: string) => {
    const key = tryKey(bookId, request);
    const known = heard.get(key);
    if (known) {
      play(known, voiceName);
      return;
    }
    clip.stop();
    setAsking(key);
    setSaid({ text: `Máy đang đọc thử giọng ${voiceName} - lần đầu có thể mất vài chục giây`, status: true });
    try {
      const preview = await api<VoicePreview>(`/api/books/${bookId}/voice/preview`, { method: "POST", body: request });
      heard.set(key, preview);
      play(preview, voiceName);
    } catch (error) {
      const reason = error instanceof ApiError ? error.detail.reason : undefined;
      if (reason === "no-line" && fallbackUrl) {
        clip.toggle(`voice-${voiceName}`, fallbackUrl);
        setSaid({ text: "Người này chưa có câu nào để đọc thử - đang phát câu mẫu chung của giọng", status: true });
      } else {
        const why = refusalText(reason, (error as Error).message);
        setSaid({ text: fallbackUrl ? `${why} - nút ▶ vẫn nghe được câu mẫu chung của giọng` : why, status: true });
      }
    } finally {
      setAsking(null);
    }
  };
  const button = (
    request: VoiceRequest,
    voiceName: string,
    { fallbackUrl, compact = false, disabled = false }: { fallbackUrl?: string; compact?: boolean; disabled?: boolean } = {},
  ) => {
    const key = tryKey(bookId, request);
    const known = heard.get(key);
    const playing = known !== undefined && clip.current === clipId(known);
    const loading = asking === key || (playing && clip.loading);
    const label = playing ? "Dừng nghe thử" : `Nghe giọng ${voiceName} đọc một câu của sách`;
    if (compact)
      return (
        <button
          type="button"
          onClick={() => void ask(request, voiceName, fallbackUrl)}
          disabled={disabled || (asking !== null && asking !== key)}
          aria-label={label}
          title={label}
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-full border transition-colors disabled:opacity-40",
            playing ? "border-accent bg-accent text-accent-ink" : "border-line text-fg-2 hover:border-line-strong hover:text-fg",
          )}
        >
          {loading ? <Loader2 className="size-4 animate-spin" /> : playing ? <Vu className="h-3" /> : <BookOpenText className="size-4" />}
        </button>
      );
    return (
      <Button
        size="sm"
        variant="secondary"
        type="button"
        loading={asking === key}
        disabled={disabled || (asking !== null && asking !== key)}
        onClick={() => void ask(request, voiceName, fallbackUrl)}
        aria-label={label}
      >
        {playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <BookOpenText className="size-4" />}
        {playing ? "Dừng" : "Nghe thử"}
      </Button>
    );
  };
  const note = said ? (
    <p role={said.status ? "status" : undefined} className={cn("text-xs", said.status ? "text-fg-2" : "text-fg-3")}>
      {said.text}
    </p>
  ) : null;
  return { button, note };
}
