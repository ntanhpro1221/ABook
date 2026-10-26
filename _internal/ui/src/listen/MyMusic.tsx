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
import { analysisLabel, importSummary, LOCAL_PREFIX, MY_MUSIC_INTRO, mineNote, type LocalMusicView } from "@/studio/musicLocal";
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
  if (isLoading) return <MotionRegion fadeThrough><ContentSkeleton className="px-3 py-2" label="Đang tải bài nhạc" /></MotionRegion>;
  if (error && !data) return <MotionRegion fadeThrough><InlineError message="Bạn hãy kiểm tra kết nối rồi tìm lại bài nhạc." onRetry={() => void refetch()} /></MotionRegion>;
  const mine = data?.mine ?? [];
  if (!mine.length) {
    return <MotionRegion as="p" className="px-3 py-2 text-xs text-fg-2">Chưa có bài nào khác trong Nhạc của tôi.</MotionRegion>;
  }
  return (
    <MotionRegion as="ul" className="divide-y divide-line border-t border-line bg-bg/40">
      {mine.map((item) => (
        <li key={item.link} className="flex items-center gap-3 px-3 py-2">
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm">{item.title}</div>
            <div className="tabular truncate text-xs text-fg-2">
              {[item.creator, item.duration ? formatClock(item.duration) : ""].filter(Boolean).join(" · ")}
            </div>
            {mineNote(item) && <div className="text-xs text-fg-2">{mineNote(item)}</div>}
          </div>
          <Button size="sm" variant="ghost" icon={Pin} disabled={busy} loading={choosing === item.link} onClick={() => onChoose(item.link)}>
            Chọn
          </Button>
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
      if (error) toast.error("Đang thêm nhạc thì dừng", { description: error.message });
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
      toast("Đã xoá khỏi Nhạc của tôi");
    },
    onError: (error: Error) => toast.error("Chưa xoá được bài này", { description: error.message }),
  });
  const tracks = data?.tracks ?? [];
  const rows = useListPresence(tracks, (track) => track.link);
  return (
    <MotionRegion><Fold storageKey="my-music.library" title="Nhạc của tôi" summary={tracks.length ? `${tracks.length} bài` : "Chưa có bài nào"} bodyClassName="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {canImport && (
          <Button size="sm" variant="ghost" icon={Upload} className={WRAP_LABEL} loading={Boolean(progress)} onClick={() => void importFiles()}>
            {progress ? `Đang thêm ${progress.done}/${progress.total}` : "Thêm nhạc của bạn"}
          </Button>
        )}
      </div>
      {!!tracks.length && <MusicModuleNotice view={data} queryKey={MY_MUSIC_KEY} />}
      <p className="text-xs text-fg-2 text-pretty">{MY_MUSIC_INTRO}</p>
      <MoreInfo label="Nhạc riêng">{MY_MUSIC_HELP}</MoreInfo>
      {!canImport && <p className="text-xs text-fg-2">Thêm và xoá nhạc làm trên máy tính chủ sách.</p>}
      <MotionRegion motionKey={isLoading ? "loading" : error && !data ? "error" : tracks.length ? "ready" : "empty"}>{isLoading ? <ContentSkeleton count={2} label="Đang tải nhạc riêng" /> : error && !data ? <InlineError message="Bạn hãy thử tải lại nhạc của bạn." onRetry={() => void refetch()} /> : canImport && !tracks.length ? <EmptyState icon={EighthNote} title="Chưa có bài nào" className="py-6" action={<Button icon={Upload} onClick={() => void importFiles()} loading={Boolean(progress)}>Thêm nhạc của bạn</Button>} /> : null}</MotionRegion>
      {!!rows.length && (
        <ul className="divide-y divide-line">
          {rows.map(({ item: track, key, state, ref }) => (
            <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}><div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
              <span className="min-w-0 flex-1 break-words">
                <EighthNote className="mr-1.5 inline size-4 text-accent-text" />
                {track.title}
                {track.creator && <span className="text-fg-2"> · {track.creator}</span>}
                {track.duration ? <span className="tabular text-fg-2"> · {formatClock(track.duration)}</span> : null}
                {/* Chưa phân tích: nói như tab Nhạc của dự án. Máy tính còn nói bài đã phân tích thì máy tự chọn được; điện thoại không tự chọn nên không nói. */}
                <AutoPickNote
                  track={track}
                  canOverride={canImport && !hasNativeMusicImport()}
                  onView={refresh}
                  idleLabel={hasNativeMusicImport() && track.analysed ? undefined : analysisLabel(track)}
                />
              </span>
              {canImport &&
                (removing === track.link ? (
                  <span ref={removeBox} className="flex shrink-0 gap-1">
                    <Button size="sm" variant="ghost" icon={Trash2} aria-label={`Xoá bài: ${track.title}`} loading={remove.isPending} onClick={() => remove.mutate(track.link)}>
                      Xoá bài
                    </Button>
                    <Button size="sm" variant="ghost" aria-label={`Giữ lại: ${track.title}`} disabled={remove.isPending} onClick={() => setRemoving(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <Button ref={(el) => { if (removeLink.current === track.link) removeButton.current = el; }} size="sm" variant="ghost" icon={Trash2} aria-label={`Xoá: ${track.title}`} onClick={() => { removeLink.current = track.link; setRemoving(track.link); }}>
                    Xoá
                  </Button>
                ))}
            </div></li>
          ))}
        </ul>
      )}
    </Fold></MotionRegion>
  );
}
