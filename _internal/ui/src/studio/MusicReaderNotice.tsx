import { Button, Progress } from "@/shared/ui";
import { cancelMusicReader, readerLabel, readerPercent, retryMusicReader } from "./musicImport";
import type { MusicReader } from "./musicLocal";

/** Lúc nhập nhạc mà máy chưa có bộ đọc nhạc: thanh tiến độ tải (một lần), hay lý do tải hỏng + "Thử lại". */
export function MusicReaderNotice({ reader }: { reader: MusicReader | null }) {
  if (!reader) return null;
  const failed = reader.state === "error";
  return (
    <div role="status" className="space-y-1.5 text-xs text-fg-2">
      <p className={failed ? "text-danger" : undefined}>{readerLabel(reader)}</p>
      {failed ? (
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={retryMusicReader}>
            Thử lại
          </Button>
          <Button size="sm" variant="ghost" onClick={cancelMusicReader}>
            Bỏ qua
          </Button>
        </div>
      ) : (
        <Progress value={readerPercent(reader) / 100} size="sm" running label="Đang tải bộ đọc nhạc" />
      )}
    </div>
  );
}
