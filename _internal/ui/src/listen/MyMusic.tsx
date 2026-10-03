import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Music2, Pin, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { formatClock } from "@/shared/format";
import { Button } from "@/shared/ui";
import { api, type AppInfo } from "@/studio/api";
import { hasNativeMusicImport, importMusic } from "@/studio/musicImport";
import { importSummary, LOCAL_PREFIX, type LocalMusicView, type LocalTrack } from "@/studio/musicLocal";
import { MusicModuleNotice } from "@/studio/MusicModuleNotice";

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
  const { data, isLoading, error } = useQuery({
    queryKey: ["music-alternatives", bookId, cueKey],
    queryFn: () => api<{ mine?: MineItem[] }>(`/api/books/${bookId}/music/scenes/${encodeURIComponent(cueKey)}/alternatives`),
    staleTime: 0,
    gcTime: 0,
  });
  if (isLoading) return <p className="px-3 py-2 text-xs text-fg-2">Đang tìm bài của bạn…</p>;
  if (error) return <p className="px-3 py-2 text-xs text-warning">{(error as Error).message}</p>;
  const mine = data?.mine ?? [];
  if (!mine.length) {
    return <p className="px-3 py-2 text-xs text-fg-2">Chưa có bài nào khác trong Nhạc của tôi - nhập nhạc của bạn ở mục “Nhạc của tôi” bên dưới.</p>;
  }
  return (
    <ul className="divide-y divide-line border-t border-line bg-bg/40">
      {mine.map((item) => (
        <li key={item.link} className="flex items-center gap-3 px-3 py-2">
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm">{item.title}</div>
            <div className="tabular truncate text-xs text-fg-2">
              {[item.creator, item.duration ? formatClock(item.duration) : ""].filter(Boolean).join(" · ")}
            </div>
          </div>
          <Button size="sm" variant="secondary" icon={Pin} disabled={busy} loading={choosing === item.link} onClick={() => onChoose(item.link)}>
            Chọn
          </Button>
        </li>
      ))}
    </ul>
  );
}

/** Danh sách bài đã nhập + nút nhập + xoá (hai bước). */
export function MyMusicSection() {
  const client = useQueryClient();
  const canImport = useCanImportMusic();
  const { data } = useMyMusic();
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const refresh = (view: LocalMusicView) => {
    client.setQueryData(MY_MUSIC_KEY, view);
    void client.invalidateQueries({ queryKey: ["music-alternatives"] });
  };
  const importFiles = async () => {
    try {
      const { result, error } = await importMusic((done, total, latest) => {
        setProgress({ done, total });
        if (latest) refresh(latest);
      });
      if (error) toast.error("Đang nhập nhạc thì dừng", { description: error.message });
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
      toast("Đã xoá khỏi Nhạc của tôi", { description: "Sách đã chọn bài này vẫn giữ bản của nó." });
    },
    onError: (error: Error) => toast.error("Không xoá được bài này", { description: error.message }),
  });
  const tracks = data?.tracks ?? [];
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <h4 className="text-sm font-medium">Nhạc của tôi{tracks.length ? ` (${tracks.length})` : ""}</h4>
        {canImport && (
          <Button size="sm" variant="secondary" icon={Upload} loading={Boolean(progress)} onClick={() => void importFiles()}>
            {progress ? `Đang nhập ${progress.done}/${progress.total}…` : "Nhập nhạc của tôi…"}
          </Button>
        )}
      </div>
      {!!tracks.length && <MusicModuleNotice view={data} queryKey={MY_MUSIC_KEY} />}
      <p className="text-xs text-fg-2 text-pretty">
        Thêm nhạc của riêng bạn (mp3, m4a, ogg, opus, flac, wav) làm nhạc nền. File được chép vào kho nhạc của máy này. Bài nào bạn chọn
        cho một đoạn sẽ đi cùng file sách khi bạn lưu, nên máy khác cũng nghe được. ABook chỉ ghi tên bài và nghệ sĩ có sẵn trong file,
        không nói gì về giấy phép.
      </p>
      {!canImport && <p className="text-xs text-fg-2">Nhập và xoá nhạc làm trên máy tính chủ sách.</p>}
      {canImport && !tracks.length && <p className="text-xs text-fg-2">Chưa có bài nào.</p>}
      {!!tracks.length && (
        <ul className="divide-y divide-line rounded-lg border border-line">
          {tracks.map((track: LocalTrack) => (
            <li key={track.link} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
              <span className="min-w-0 flex-1 break-words">
                <Music2 className="mr-1.5 inline size-4 text-accent-text" />
                {track.title}
                {track.creator && <span className="text-fg-2"> · {track.creator}</span>}
                {track.duration ? <span className="tabular text-fg-2"> · {formatClock(track.duration)}</span> : null}
              </span>
              {canImport &&
                (removing === track.link ? (
                  <span className="flex shrink-0 gap-1">
                    <Button size="sm" variant="secondary" icon={Trash2} loading={remove.isPending} onClick={() => remove.mutate(track.link)}>
                      Xoá khỏi kho
                    </Button>
                    <Button size="sm" variant="ghost" disabled={remove.isPending} onClick={() => setRemoving(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setRemoving(track.link)}>
                    Xoá
                  </Button>
                ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
