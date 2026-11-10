import { S } from "../shared/strings.generated";
import { TickingValue } from "@/shared/TickingValue";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import { useListPresence } from "@/shared/motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EighthNote, Pin, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useBackLayer } from "@/shared/backStack";
import { MoreInfo } from "@/shared/SettingsNav";
import { MY_MUSIC_HELP } from "@/studio/musicLocal";
import { toast } from "@/shared/toast";
import { formatClock } from "@/shared/format";
import { Button, WRAP_LABEL, ContentSkeleton, InlineError, EmptyState } from "@/shared/ui";
import { api, type AppInfo } from "@/studio/api";
import { hasNativeMusicImport, importMusic } from "@/studio/musicImport";
import { importSummary, LOCAL_PREFIX, MY_MUSIC_INTRO, mineNote, type LocalMusicView } from "@/studio/musicLocal";
import { AutoPickNote } from "@/studio/AutoPickNote";
import { MusicModuleNotice } from "@/studio/MusicModuleNotice";
import { MUSIC_CHANGED_ALL, MUSIC_CHANGED_EVENT } from "./musicBed";

// "Nhạc của tôi" trên trang sửa sách (docs/MUSIC_IMPORT.md): nhạc bạn tự có làm nhạc nền. Nhập, xem, xoá ở đây; "Đổi bài" ở từng đoạn
// nhạc của sách. Cùng JSON ở máy tính (server.py) và điện thoại (LocalStudio.kt, MusicStore.kt).

export const MY_MUSIC_KEY = ["music-local"] as const;

/** Một bài trong nhóm "Nhạc của tôi" của "Đổi bài" (`GET /api/books/<mã>/music/scenes/<khoá>/alternatives` -> `mine`). */
export interface MineItem {
  link: string;
  title: string;
  creator: string;
  duration?: number;
  analysed: boolean;
  fits: boolean;
  /** Như `LocalTrack`: nhãn "Có vẻ có lời" / "Máy không tự chọn bài này" - cùng nhãn với Cài đặt. */
  vocalsLikely?: boolean;
  auto?: "on" | "off";
}

/** Hộp chọn file nhập nhạc có dùng được ở đây không: điện thoại luôn có; máy tính cần hộp chọn file của máy chủ (Studio từ xa thì không). */
export function useCanImportMusic(): boolean {
  const native = hasNativeMusicImport(); // điện thoại không có máy chủ để hỏi `/api/app`
  const { data: info } = useQuery({ queryKey: ["app"], queryFn: () => api<AppInfo>("/api/app"), staleTime: Infinity, enabled: !native });
  return native || Boolean(info?.dialogs);
}

/** Các bài đã nhập (kho của máy này). */
export function useMyMusic(enabled = true) {
  return useQuery({ queryKey: MY_MUSIC_KEY, queryFn: () => api<LocalMusicView>("/api/music/local"), enabled });
}

/** "Đổi bài" của một đoạn nhạc: chọn một bài trong "Nhạc của tôi" thay bài người làm sách gắn; "Về bài gốc" trả lại. */
export function SwapTrack({
  bookId,
  cueKey,
  busy,
  choosing,
  onChoose,
}: {
  bookId: string;
  cueKey: string;
  busy: boolean;
  choosing: string | null;
  onChoose: (link: string) => void;
}) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["music-alternatives", bookId, cueKey],
    queryFn: () => api<{ mine?: MineItem[] }>(`/api/books/${bookId}/music/scenes/${encodeURIComponent(cueKey)}/alternatives`),
    staleTime: 0,
    gcTime: 0,
  });
  if (isLoading) return <MotionRegion fadeThrough><ContentSkeleton className="px-3 py-2" label={S.s_dang_tai_bai_nhac_0c9498d1} /></MotionRegion>;
  if (error && !data) return <MotionRegion fadeThrough><InlineError message={S.s_ban_hay_kiem_tra_ket_noi_roi_tim_lai_bai_n_acc346b4} onRetry={() => void refetch()} /></MotionRegion>;
  const mine = data?.mine ?? [];
  if (!mine.length) {
    return <MotionRegion as="p" className="px-3 py-2 text-xs text-fg-2">{S.s_chua_co_bai_nao_khac_trong_nhac_cua_toi_811d988a}</MotionRegion>;
  }
  return (
    <MotionRegion as="ul" className="divide-y divide-line border-t border-line bg-bg/40">
      {mine.map((item) => (
        <li key={item.link} className="flex items-center gap-3 px-3 py-2">
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm">{item.title}</div>
            <div className="truncate text-xs text-fg-2">
              {[item.creator, item.duration ? formatClock(item.duration) : ""].filter(Boolean).join(" · ")}
            </div>
            {mineNote(item) && <div className="text-xs text-fg-2">{mineNote(item)}</div>}
          </div>
          <Button size="sm" variant="ghost" icon={Pin} disabled={busy} loading={choosing === item.link} onClick={() => onChoose(item.link)}>{S.s_chon_1171ca97}</Button>
        </li>
      ))}
    </MotionRegion>
  );
}

/** Danh sách bài đã nhập + nút nhập + xoá (hai bước). */
export function MyMusicSection() {
  const client = useQueryClient();
  const canImport = useCanImportMusic();
  const { data, isLoading, error, refetch } = useMyMusic();
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const removeBox = useRef<HTMLElement>(null);
  const removeButton = useRef<HTMLButtonElement>(null);
  const removeLink = useRef<string | null>(null);
  useBackLayer(removing !== null, () => setRemoving(null), removeBox, removeButton);
  const refresh = (view: LocalMusicView) => {
    client.setQueryData(MY_MUSIC_KEY, view);
    void client.invalidateQueries({ queryKey: ["music-alternatives"] });
    void client.invalidateQueries({ queryKey: ["music", "playlists"] });
    window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: MUSIC_CHANGED_ALL }));
  };
  const importFiles = async () => {
    try {
      const { result, error } = await importMusic((done, total, latest) => {
        setProgress({ done, total });
        if (latest) refresh(latest);
      });
      if (error) toast.error(S.s_dang_them_nhac_thi_dung_8712c030, { description: error.message });
      if (!result) return;
      refresh(result);
      const summary = importSummary(result);
      toast[summary.kind](summary.title, { description: summary.description });
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setProgress(null);
    }
  };
  const remove = useMutation({
    mutationFn: (link: string) => api<LocalMusicView>(`/api/music/local/${link.slice(LOCAL_PREFIX.length)}`, { method: "DELETE" }),
    onSuccess: (view) => {
      refresh(view);
      setRemoving(null);
      toast(S.s_da_xoa_khoi_nhac_cua_toi_ccb5da2a);
    },
    onError: (error: Error) => toast.error(S.s_chua_xoa_duoc_bai_nay_6ba1ed47, { description: error.message }),
  });
  const tracks = data?.tracks ?? [];
  const rows = useListPresence(tracks, (track) => track.link);
  return (
    <MotionRegion><Fold storageKey="my-music.library" title={S.s_nhac_cua_toi_f65b7ac6} summary={tracks.length ? S.s_0_bai_1e392237(tracks.length) : S.s_chua_co_bai_nao_c1c708be} bodyClassName="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {canImport && (
          <Button size="sm" variant="ghost" icon={Upload} className={`edge-start-action ${WRAP_LABEL}`} loading={Boolean(progress)} onClick={() => void importFiles()}>
            <TickingValue>{progress ? S.s_dang_them_0_1_84372256(progress.done, progress.total) : S.s_them_nhac_cua_ban_dbd7d8c4}</TickingValue>
          </Button>
        )}
      </div>
      {/* Câu giới thiệu tả nút Thêm ngay trên nó, rồi mới tới khối tải Phân tích nhạc */}
      <p className="text-xs text-fg-2 text-pretty">{MY_MUSIC_INTRO}</p>
      <MoreInfo label={S.s_nhac_rieng_732d7761}>{MY_MUSIC_HELP}</MoreInfo>
      {!!tracks.length && <MusicModuleNotice view={data} queryKey={MY_MUSIC_KEY} />}
      {!canImport && <p className="text-xs text-fg-2">{S.s_them_va_xoa_nhac_lam_tren_may_tinh_chu_sac_bdde38b6}</p>}
      <MotionRegion motionKey={isLoading ? "loading" : error && !data ? "error" : tracks.length ? "ready" : "empty"}>{isLoading ? <ContentSkeleton count={2} label={S.s_dang_tai_nhac_rieng_144f69a2} /> : error && !data ? <InlineError message={S.s_ban_hay_thu_tai_lai_nhac_cua_ban_f18be139} onRetry={() => void refetch()} /> : canImport && !tracks.length ? <EmptyState icon={EighthNote} title={S.s_chua_co_bai_nao_c1c708be} className="py-6" action={<Button icon={Upload} onClick={() => void importFiles()} loading={Boolean(progress)}>{S.s_them_nhac_cua_ban_dbd7d8c4}</Button>} /> : null}</MotionRegion>
      {!!rows.length && (
        <ul className="divide-y divide-line">
          {rows.map(({ item: track, key, state, ref }) => (
            <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}><div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
              <span className="min-w-0 flex-1 break-words">
                <EighthNote className="mr-1.5 inline size-4 text-accent-text" />
                {track.title}
                {track.creator && <span className="text-fg-2"> · {track.creator}</span>}
                {track.duration ? <span className="text-fg-2"> · {formatClock(track.duration)}</span> : null}
                {/* Nhãn ngắn như tab Nhạc của dự án; công tắc Tự chọn chỉ ở máy tính (điện thoại không tự chọn). */}
                <AutoPickNote track={track} canOverride={canImport && !hasNativeMusicImport()} onView={refresh} />
              </span>
              {canImport &&
                (removing === track.link ? (
                  <span ref={removeBox} className="flex shrink-0 gap-1">
                    <Button size="sm" variant="ghost" icon={Trash2} aria-label={S.s_xoa_bai_0_d2cc8ffb(track.title)} loading={remove.isPending} onClick={() => remove.mutate(track.link)}>{S.s_xoa_bai_d554a496}</Button>
                    <Button size="sm" variant="ghost" aria-label={S.s_giu_lai_0_9b038c0f(track.title)} disabled={remove.isPending} onClick={() => setRemoving(null)}>{S.s_giu_lai_3c3ba2db}</Button>
                  </span>
                ) : (
                  <Button ref={(el) => { if (removeLink.current === track.link) removeButton.current = el; }} size="sm" variant="ghost" icon={Trash2} aria-label={S.s_xoa_0_179508ae(track.title)} onClick={() => { removeLink.current = track.link; setRemoving(track.link); }}>{S.s_xoa_777195ab}</Button>
                ))}
            </div></li>
          ))}
        </ul>
      )}
    </Fold></MotionRegion>
  );
}
