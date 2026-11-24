import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { formatSize } from "../shared/format";
import { MotionPresence, Reveal } from "../shared/MotionPresence";
import { SectionHeading } from "../shared/SectionHeading";
import { S } from "../shared/strings.generated";
import { Button, InlineError } from "../shared/ui";
import { api } from "../studio/api";
import { useDownloads, useLibraryMeta, useSaveTracks, type LibraryTrack } from "./library";
import { PreviewBar, TrackRow } from "./MusicScreen";
import { BundledTrackRow, BundledTrackSheet } from "./BundledTrack";
import { useLibraryPreview } from "./preview";
import { TrackSheet } from "./TrackSheet";
import { Windowed } from "../shared/Windowed";

export interface BookMusicTrack extends LibraryTrack {
  /** Số đoạn của cuốn dùng bài này. */
  scenes: number;
  /** Khoá đoạn đầu tiên dùng bài (mở "Vì sao bài này"). */
  scene: string | null;
  /** Bài kho nhạc không có (`local:` đóng gói kèm sách): tên theo book.json, không nghe thử / lưu, mở BundledTrackSheet. */
  bundled?: boolean;
  /** Bài đi kèm sách: ba cảm xúc mạnh nhất của đoạn đầu tiên dùng bài (rỗng = ẩn "Vì sao bài này"). */
  mood?: { id: string; score: number }[];
}

export function useBookMusicTracks(bookId: string) {
  return useQuery({
    queryKey: ["book-music-library", bookId],
    queryFn: () => api<{ tracks: BookMusicTrack[]; missingBytes: number; unsaved: string[] }>(`/api/books/${bookId}/music/library`),
  });
}

/** Phần "Nhạc trong sách" của trang sách: MỌI bài cuốn này dùng, theo thứ tự nghe (gộp trùng, đếm số đoạn) + "Lưu tất cả (X MB)". Chạm bài
 *  mở chi tiết kèm "Vì sao bài này" (cảm xúc máy đọc được ở đoạn đầu tiên dùng bài); bài đi kèm sách (kho nhạc không có) mở sheet riêng ở mức
 *  có dữ liệu. Mounted only in the dedicated Music tab. */
export function BookMusic({ bookId }: { bookId: string }) {
  const { data, isPending, isError, refetch } = useBookMusicTracks(bookId);
  const { data: downloads } = useDownloads();
  const { data: meta } = useLibraryMeta();
  const { save } = useSaveTracks();
  const preview = useLibraryPreview();
  const [open, setOpen] = useState<BookMusicTrack | null>(null);
  const [bundled, setBundled] = useState<BookMusicTrack | null>(null);
  const tracks = data?.tracks ?? [];
  const unsaved = data?.unsaved ?? [];
  return (
    <MotionPresence open>
      <section aria-labelledby="book-music" className="mt-8 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <SectionHeading id="book-music">{S.s_nhac_trong_sach_9070d53a}</SectionHeading>
          <Reveal when={unsaved.length > 0}><Button size="sm" icon={Download} loading={save.isPending} onClick={() => save.mutate(unsaved)}>
              {S.s_luu_tat_ca_0_e16e7860(formatSize(data?.missingBytes ?? 0))}
            </Button></Reveal>
        </div>
        <Reveal when={isPending}><p role="status">{S.s_dang_tai_465b1987}</p></Reveal>
        <InlineError open={isError} message={S.s_chua_tai_duoc_kho_nhac_9577b7c7} onRetry={() => void refetch()} />
        <Reveal when={!isPending && !isError && tracks.length === 0}><p>{S.s_chua_co_nhac_ed5dc66e}</p></Reveal>
        <div role="list">
          <Windowed items={tracks} estimate={80} memory={`book-music.${bookId}`} row={(track) => (
            <div role="listitem" key={track.link} className="flex items-center gap-2">
              <div className="min-w-0 flex-1">
                {track.bundled ? <BundledTrackRow track={track} onOpen={() => setBundled(track)} />
                  : <TrackRow track={track} preview={preview} downloads={downloads} online styles={meta?.styles} onOpen={() => setOpen(track)} as="div" nested />}
              </div>
              <span className="shrink-0 text-xs text-fg-2">{S.s_0_doan_c2eb5200(track.scenes)}</span>
            </div>
          )} />
        </div>
        <PreviewBar preview={preview} onOpen={(link) => setOpen(tracks.find((track) => track.link === link) ?? null)} />
        <TrackSheet
          link={open?.link ?? null}
          onClose={() => setOpen(null)}
          preview={preview}
          context={open?.scene ? { book: bookId, scene: open.scene } : null}
        />
        <BundledTrackSheet track={bundled} onClose={() => setBundled(null)} />
      </section>
    </MotionPresence>
  );
}
