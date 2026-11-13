import { Ban, Bookmark, BookmarkCheck, Check, Download, ExternalLink, Library, Loader2, Play, Shuffle, Square, Trash2, X } from "lucide-react";
import type { ReactNode } from "react";
import { openExternal } from "../shared/openExternal";
import { SectionHeading } from "../shared/SectionHeading";
import { S } from "../shared/strings.generated";
import { ActionPair, Button, ContentSkeleton, InlineError, Progress, Sheet } from "../shared/ui";
import { DotJoin } from "../shared/DotJoin";
import { formatClock, licenseLabel, musicCreditText } from "../shared/format";
import { labelOf, loadOf, useDownloads, useLibraryMeta, useSaveTracks, useTrackDetail, type TrackDetail } from "./library";
import type { LibraryPreview } from "./preview";

import { Reveal } from "../shared/MotionPresence";
/** Năng lượng (arousal của danh mục, -1..1) thành 0-100 %. Cùng phép đổi: MusicLibrary.kt `energyPercent`, MusicLibrary.js. */
export function energyPercent(arousal: number | undefined): number | null {
  if (typeof arousal !== "number" || !Number.isFinite(arousal)) return null;
  return Math.round(Math.max(0, Math.min(1, (arousal + 1) / 2)) * 100);
}

/** Điểm 0-1 thành phần trăm nguyên để in và vẽ thanh. */
export function percent(score: number): number {
  return Math.round(Math.max(0, Math.min(1, score)) * 100);
}

function Bar({ label, value, tone = "accent" }: { label: ReactNode; value: number; tone?: "accent" | "muted" }) {
  return (
    <div className="grid grid-cols-[minmax(6.5rem,9rem)_1fr_2.75rem] items-center gap-3 text-sm">
      <span className="min-w-0 truncate text-fg-2">{label}</span>
      <Progress value={value / 100} size="sm" tone={tone} label={typeof label === "string" ? label : S.s_cam_xuc_05c1aee0} />
      <span className="text-right text-fg-2">{value} %</span>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 text-sm">
      <dt className="shrink-0 text-fg-2">{label}</dt>
      <dd className="min-w-0 text-right [overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

/** Sheet chi tiết bài (docs/DESIGN.md mục Nhạc): đủ 13 cảm xúc xếp giảm dần, năng lượng, nhịp, phong cách, độ dài, giấy phép / ghi công /
 *  nguồn, danh sách phát chứa bài; nút Nghe thử, Tải về | Xoá bản tải, và ở chế độ chọn: Dùng, Không tự chọn bài này. Mở từ bài đang phát
 *  hay "Nhạc trong sách" (`context`): thêm "Vì sao bài này" khi đoạn có cảm xúc máy đọc được. */
export function TrackSheet({
  link,
  onClose,
  preview,
  context,
  onUse,
  onBan,
  busy,
  playing,
}: {
  link: string | null;
  onClose: () => void;
  preview: LibraryPreview;
  context?: { book: string; scene: string } | null;
  onUse?: (link: string) => void;
  onBan?: (link: string) => void;
  busy?: boolean;
  /** Mở từ dòng Nhạc nền của trình phát ("Bài đang phát"): nút Lưu / Bỏ lưu, Xem trong kho, Đổi bài thay cho Nghe thử / Tải về. */
  playing?: { onOpenLibrary: (title: string) => void; onSwap?: () => void };
}) {
  const { data, isLoading, error, refetch } = useTrackDetail(link, context);
  const { data: meta } = useLibraryMeta();
  const name = data?.title || S.s_bai_nay_d9683a01;
  const title = playing ? S.s_bai_dang_phat_3c20c832 : name;
  const description = playing ? [data?.title, data?.creator].filter(Boolean).join(" · ") : data?.creator;
  return (
    <Sheet open={link !== null} onOpenChange={(open) => { if (!open) onClose(); }} title={title} description={description}>
      {isLoading ? (
        <ContentSkeleton />
      ) : error || !data ? (
        <InlineError message={S.s_chua_tai_duoc_bai_nay_d66f95b6} onRetry={() => void refetch()} />
      ) : (
        <TrackBody track={data} preview={preview} styles={meta?.styles} emotions={meta?.emotions} onUse={onUse} onBan={onBan} busy={busy} playing={playing} />
      )}
    </Sheet>
  );
}

function TrackBody({
  track,
  preview,
  styles,
  emotions,
  onUse,
  onBan,
  busy,
  playing,
}: {
  track: TrackDetail;
  preview: LibraryPreview;
  styles?: { id: string; label: string }[];
  emotions?: { id: string; label: string }[];
  onUse?: (link: string) => void;
  onBan?: (link: string) => void;
  busy?: boolean;
  playing?: { onOpenLibrary: (title: string) => void; onSwap?: () => void };
}) {
  const { data: downloads } = useDownloads();
  const { save, unsave } = useSaveTracks();
  const load = loadOf(track, downloads);
  const previewing = preview.playing?.link === track.link;
  const energy = energyPercent(track.arousal);
  const credit = musicCreditText(track);
  const license = licenseLabel(track.license, track.licenseUrl);
  return (
    <div className="space-y-6 pb-2">
      {playing ? (
        <div className="flex flex-wrap gap-2">
          {/* "Lưu" = tải về + ghim vào Đã lưu; chạm lại = bỏ lưu. Đang tải thì vòng phần trăm trên chính nút. */}
          <Button variant="primary" icon={track.saved ? BookmarkCheck : Bookmark} aria-pressed={track.saved} loading={save.isPending || unsave.isPending}
            onClick={() => (track.saved ? unsave.mutate([track.link]) : save.mutate([track.link]))}>
            {track.saved ? S.s_bo_luu_2fd51455 : S.s_luu_e91f26c0}
            {load.kind === "loading" && load.percent !== null && <span data-motion-live>{load.percent} %</span>}
          </Button>
          <Button variant="ghost" icon={Library} onClick={() => playing.onOpenLibrary(track.title ?? "")}>{S.s_xem_trong_kho_2a139d05}</Button>
          <Reveal when={playing.onSwap}><Button variant="ghost" icon={Shuffle} onClick={playing.onSwap}>{S.s_doi_bai_7b81488f}</Button></Reveal>
        </div>
      ) : (
      <div className="space-y-2">
      <ActionPair primary={
        <Button icon={previewing ? Square : Play} aria-pressed={previewing} onClick={() => preview.toggle(track)}>
          {previewing ? S.s_dung_nghe_f20939be : S.s_nghe_thu_fa024065}
        </Button>
        } secondary={load.kind === "loading" ? (
          <Button icon={X} onClick={() => unsave.mutate([track.link])}>
            {S.s_huy_tai_1a9ff73d}
            <span data-motion-live className="text-fg-2">{load.percent === null ? <Loader2 className="size-4 animate-spin" /> : `${load.percent} %`}</span>
          </Button>
        ) : track.saved || load.kind === "done" ? (
          <Button icon={Trash2} loading={unsave.isPending} onClick={() => unsave.mutate([track.link])}>{S.s_xoa_ban_tai_4b461f4a}</Button>
        ) : (
          <Button icon={Download} loading={save.isPending} onClick={() => save.mutate([track.link])}>
            {load.kind === "failed" ? S.s_tai_tiep_1efbd854 : S.s_tai_ve_9b5bdb44}
          </Button>
        )} />
        {onUse && <Button icon={Check} loading={busy} onClick={() => onUse(track.link)}>{S.s_dung_7927ca4e}</Button>}
        {onBan && <Button icon={Ban} onClick={() => onBan(track.link)}>{S.s_khong_tu_chon_02ae1742}</Button>}
      </div>
      )}
      {track.why && track.why.matches.length > 0 && (
        <section aria-labelledby="track-why">
          <SectionHeading as="h3" id="track-why">{S.s_vi_sao_bai_nay_f681e004}</SectionHeading>
          <p className="text-sm text-fg-2">{S.s_doan_va_bai_cung_0_music(labelOf(emotions, track.why.matches[0].id))}</p>
          <div className="mt-3 flex gap-4 text-xs text-fg-2" aria-hidden>
            <span className="flex items-center gap-2"><span className="h-1 w-4 rounded-full bg-fg-3" />{S.s_doan_nay_82d01522}</span>
            <span className="flex items-center gap-2"><span className="h-1 w-4 rounded-full bg-accent" />{S.s_bai_nay_d9683a01}</span>
          </div>
          <ul className="mt-2 space-y-2">
            {track.why.matches.map((match) => (
              <li key={match.id} className="grid grid-cols-[minmax(6.5rem,9rem)_1fr] items-center gap-3 text-sm">
                <span className="text-fg-2">{labelOf(emotions, match.id)}</span>
                <div className="space-y-1">
                  <Progress size="xs" tone="muted" label={`${labelOf(emotions, match.id)}: ${S.s_doan_nay_82d01522}`} value={match.scene} />
                  <Progress size="xs" label={`${labelOf(emotions, match.id)}: ${S.s_bai_nay_d9683a01}`} value={match.track} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section aria-labelledby="track-emotions">
        <SectionHeading as="h3" id="track-emotions">{S.s_cam_xuc_05c1aee0}</SectionHeading>
        <div className="mt-3 space-y-2">
          {track.emotions.map((item) => <Bar key={item.id} label={labelOf(emotions, item.id)} value={percent(item.score)} />)}
        </div>
      </section>
      <section aria-labelledby="track-info">
      <SectionHeading as="h3" id="track-info">{S.s_thong_tin_4aa16c92}</SectionHeading>
      <dl>
        {energy !== null && <Fact label={S.s_nang_luong_1b9cc9af}>{energy} %</Fact>}
        {typeof track.bpm === "number" && track.bpm > 0 && <Fact label={S.s_nhip_8a75919d}>{S.s_0_nhip_phut_3c154e09(Math.round(track.bpm))}</Fact>}
        {track.style && <Fact label={S.s_phong_cach_d80ae8d9}>{labelOf(styles, track.style)}</Fact>}
        {typeof track.duration === "number" && <Fact label={S.s_do_dai_5e055f59}>{formatClock(track.duration)}</Fact>}
        {(track.vocals ?? 0) >= 0.5 && <Fact label={S.s_co_loi_4b381f10}><Check aria-hidden className="ml-auto size-4" /></Fact>}
        {license && <Fact label={S.s_giay_phep_b609ade1}>{license}</Fact>}
        {track.playlists.length > 0 && <Fact label={S.s_co_trong_1312af9f}><DotJoin parts={track.playlists.map((item) => item.name)} /></Fact>}
        {credit && <Fact label={S.s_ghi_cong_9c291f64}>{credit}</Fact>}
        {track.landing && <Fact label={S.s_nguon_c76d57b3}>
            <a href={track.landing} target="_blank" rel="noreferrer" onClick={(event) => openExternal(track.landing!, event)} className="inline-flex items-center gap-2 text-sm font-medium text-accent-text">
              <ExternalLink aria-hidden className="size-4" />{S.s_mo_trang_nguon_af980960}
            </a>
        </Fact>}
      </dl>
      </section>
    </div>
  );
}
