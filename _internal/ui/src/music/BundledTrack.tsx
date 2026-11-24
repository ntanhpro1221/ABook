import { BookAudio, ChevronRight } from "lucide-react";
import { DotJoin } from "../shared/DotJoin";
import { Reveal } from "../shared/MotionPresence";
import { SectionHeading } from "../shared/SectionHeading";
import { S } from "../shared/strings.generated";
import { Progress, Sheet } from "../shared/ui";
import { labelOf, useLibraryMeta } from "./library";
import { MusicArt } from "./MusicArt";
import type { BookMusicTrack } from "./BookMusic";
import { percent } from "./TrackSheet";

/** "Nhạc trong sách": bài kho nhạc không có (`local:` đóng gói kèm sách). Cùng cột với TrackRow để danh sách trộn thẳng hàng: ô nghe thử mang
 *  dấu sách mờ (không có gì để nghe thử hay lưu), dòng phụ "Đi kèm sách", cột tải để trống. Chạm mở BundledTrackSheet. */
export function BundledTrackRow({ track, onOpen }: { track: BookMusicTrack; onOpen: () => void }) {
  return (
    <div className="flex min-h-16 items-center gap-2 border-b border-line py-2 last:border-b-0" data-bundled-track>
      <MusicArt track={track} />
      <span aria-hidden className="music-row-preview grid size-9 shrink-0 place-items-center text-fg-3 pointer-coarse:min-w-[48px]"><BookAudio className="size-5" /></span>
      <button type="button" onClick={onOpen} className="relative min-w-0 flex-1 rounded-control py-2 pr-5 text-left outline-none focus-visible:ring-2 focus-visible:ring-focus">
        <ChevronRight aria-hidden className="ink-end absolute right-0 top-2.5 size-4 text-fg-3" />
        <span className="block text-sm font-medium [overflow-wrap:anywhere]">{track.title || S.s_bai_nay_d9683a01}</span>
        <DotJoin singleLine className="mt-1 text-xs text-fg-2" parts={[track.creator, S.s_bundled_track]} />
      </button>
      <span aria-hidden className="size-9 shrink-0" />
    </div>
  );
}

/** Sheet của bài đi kèm sách: chỉ những gì book.json mang - tên, người sáng tác, câu "đi kèm sách" (không nghe thử, không lưu) và, khi đoạn đầu
 *  tiên dùng bài có cảm xúc cảnh, "Vì sao bài này" ở mức có dữ liệu: ba cảm xúc mạnh nhất của đoạn (bài không có điểm cảm xúc để so). */
export function BundledTrackSheet({ track, onClose }: { track: BookMusicTrack | null; onClose: () => void }) {
  const { data: meta } = useLibraryMeta();
  const mood = track?.mood ?? [];
  return (
    <Sheet open={track !== null} onOpenChange={(open) => { if (!open) onClose(); }} title={track?.title || S.s_bai_nay_d9683a01} description={track?.creator}>
      <div className="space-y-6 pb-2" data-bundled-sheet>
        {track ? <MusicArt track={track} className="mx-auto size-40" /> : null}
        <p className="text-sm text-fg-2">{S.s_bundled_track_note}</p>
        <Reveal when={mood.length > 0}>
          <section aria-labelledby="bundled-why">
            <SectionHeading as="h3" id="bundled-why">{S.s_vi_sao_bai_nay_f681e004}</SectionHeading>
            <p className="text-sm text-fg-2">{mood[0] ? S.s_bundled_scene_mood(labelOf(meta?.emotions, mood[0].id)) : null}</p>
            <ul className="mt-3 space-y-2">
              {mood.map((item) => (
                <li key={item.id} className="grid grid-cols-[minmax(6.5rem,9rem)_1fr_minmax(2.75rem,auto)] items-center gap-3 text-sm">
                  <span className="min-w-0 truncate text-fg-2">{labelOf(meta?.emotions, item.id)}</span>
                  <Progress size="sm" tone="muted" label={`${labelOf(meta?.emotions, item.id)}: ${S.s_doan_nay_82d01522}`} value={item.score} />
                  <span className="whitespace-nowrap text-right text-fg-2">{S.s_percent(percent(item.score))}</span>
                </li>
              ))}
            </ul>
          </section>
        </Reveal>
      </div>
    </Sheet>
  );
}
