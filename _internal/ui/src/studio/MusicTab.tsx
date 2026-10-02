import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Music2, Pin, Play, RefreshCw, Shuffle, Square, Trash2, Upload, VolumeX, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { MUSIC_CHANGED_EVENT } from "@/listen/musicBed";
import { formatClock } from "@/shared/format";
import { MUSIC_LEVELS as LEVELS } from "@/shared/musicLevels";
import { Button } from "@/shared/ui";
import { api, mediaUrl } from "./api";
import { pickFiles, useAppInfo } from "./data";
import {
  analysisLabel,
  importSummary,
  LOCAL_PREFIX,
  mergeImports,
  previewPath,
  type ImportResult,
  type LocalMusicView,
  type LocalTrack,
} from "./musicLocal";

// Tab "Nhạc nền" của trang dự án (docs/MUSIC_SELECTION_MODEL.md, mục 4 - ba tầng chỉnh): cả cuốn (bật/tắt, thế giới
// của truyện, mức nhạc), từng đoạn (im lặng, bỏ ghim), từng bài (không dùng bài này nữa). Máy tự làm hết; mọi chỉnh ở đây
// là tuỳ chọn và được giữ khi máy chọn lại. Sửa nhạc không bao giờ phải đọc lại giọng.

interface Scene {
  key: string;
  chapterId: number;
  start: number;
  end: number;
  valence: number;
  arousal: number;
  tension?: number;
  /** 13 cường độ cảm xúc độc lập 0..1 (docs/MUSIC_THEORY.md Lớp 2) - không cộng thành 1, đoạn có thể vừa buồn vừa dịu. */
  emotions?: Record<string, number>;
  link: string | null;
  pinned?: boolean;
  silenced?: boolean;
  /** Bài đã ghim không còn dùng được trên máy này (vd. đã xoá khỏi "Nhạc của tôi"): lần dựng này đoạn dùng bài khác. */
  pinUnavailable?: boolean;
}

interface TrackInfo {
  title?: string;
  creator?: string;
  attribution?: string;
  /** "local": bài người dùng tự nhập ("Nhạc của tôi") - không có ghi công / giấy phép, chỉ tên + nghệ sĩ của chính file. */
  source?: string;
}

interface MusicView {
  plan: { enabled: boolean; levelDb: number; genre: string | null; scenes: Scene[]; tracks: Record<string, TrackInfo> } | null;
  overrides: { enabled: boolean; levelDb: number; genre: string | null; pins: Record<string, string>; silenced: string[]; banned: string[] };
  error: string;
  /** Tên các bài đã bỏ (từ danh mục; thiếu thì hiện tên file). */
  bannedTracks?: Record<string, TrackInfo>;
  taxonomy: {
    genres?: Record<string, { vi: string }>;
    /** Tên tiếng Việt của 13 cảm xúc (danh mục gửi, đổi được không cần cập nhật app). */
    emotions?: Record<string, string>;
  };
}

interface Alternative {
  link: string;
  title: string;
  creator: string;
  attribution: string;
  duration?: number;
  score: number;
}

/** Một bài trong nhóm "Nhạc của tôi" của "Đổi bài": mọi bài đã nhập, `fits` = qua ngưỡng hợp không khí của đoạn này. */
interface MineAlternative {
  link: string;
  title: string;
  creator: string;
  duration?: number;
  analysed: boolean;
  fits: boolean;
  score?: number;
}

const PREVIEW_SECONDS = 20;

/** Báo trình phát đang mở (cùng phiên) nạp lại mốc nhạc của cuốn này: bài đổi ngay, không cần tải lại trang. */
function announceChange(bookId: string): void {
  window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: bookId }));
}

/** Tên một bài: "tên · tác giả" nếu plan còn biết bài ấy, không thì tên file trong liên kết. */
function trackLabel(link: string, info?: TrackInfo): string {
  if (info?.title) return [info.title, info.creator].filter(Boolean).join(" · ");
  const name = link.split(/[?#]/)[0].split("/").filter(Boolean).pop() ?? link;
  try {
    return decodeURIComponent(name);
  } catch {
    return name;
  }
}

/** "Nghe thử": MỘT <audio> dùng chung cho cả tab - bấm bài khác thì bài trước dừng, mỗi lần nghe ~20 giây từ đầu bài,
 *  không bao giờ tự phát. ?mute=1: kiểm thử tự động không phát tiếng ra loa (như musicBed.ts). */
function usePreview() {
  const audio = useRef<HTMLAudioElement | null>(null);
  const current = useRef<string | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const stop = useCallback(() => {
    const element = audio.current;
    if (element) {
      element.pause();
      element.removeAttribute("src");
      element.load();
    }
    current.current = null;
    setPlaying(null);
  }, []);
  const toggle = useCallback(
    (link: string) => {
      if (current.current === link) {
        stop();
        return;
      }
      if (!audio.current) {
        const created = new Audio();
        created.preload = "none";
        created.muted = new URLSearchParams(window.location.search).get("mute") === "1";
        created.addEventListener("timeupdate", () => {
          if (created.currentTime >= PREVIEW_SECONDS) stop();
        });
        created.addEventListener("ended", stop);
        created.addEventListener("error", stop);
        audio.current = created;
      }
      const element = audio.current;
      element.src = mediaUrl(previewPath(link));
      current.current = link;
      setPlaying(link);
      void element.play().catch(() => {
        if (current.current === link) stop();
      });
    },
    [stop],
  );
  useEffect(() => stop, [stop]); // rời tab thì dừng
  return { playing, toggle, stop };
}

// Danh mục cũ chưa gửi tên: dùng bảng có sẵn (cùng bộ với build_catalog.EMOTION_VI).
const EMOTION_VI: Record<string, string> = {
  peacefulness: "bình yên", tenderness: "dịu dàng", nostalgia: "hoài niệm", sadness: "buồn", joy: "vui tươi",
  playful: "tinh nghịch", power: "hào hùng", wonder: "kỳ vĩ", tension: "căng thẳng", fear: "rùng rợn",
  anger: "giận dữ", mystery: "bí ẩn", moved: "xúc động",
};
const MOOD_SHOWN = 0.5; // cường độ từ mức này mới gọi tên
const MOOD_MAX = 2;      // tối đa hai cảm xúc mạnh nhất - pha trộn thì hiện cả hai ("buồn · dịu dàng")

/** Không khí đọc được của đoạn: các cảm xúc mạnh nhất (cường độ độc lập, nên có thể hai cảm xúc cùng cao); không cảm xúc
 * nào đủ mạnh thì "êm" - đoạn kể bình thường, nhạc nền nhẹ. */
function moodOf(scene: Scene, names: Record<string, string> | undefined): string {
  const strong = Object.entries(scene.emotions ?? {})
    .filter(([, value]) => value >= MOOD_SHOWN)
    .sort((a, b) => b[1] - a[1])
    .slice(0, MOOD_MAX)
    .map(([key]) => names?.[key] ?? EMOTION_VI[key] ?? key);
  return strong.length ? strong.join(" · ") : scene.emotions ? "êm" : "";
}

/** Một dòng bài trong "Đổi bài": tên · tác giả · độ dài, "Nghe thử" và "Chọn" (= ghim bài ấy cho đoạn này). */
function TrackRow({
  item,
  note,
  busy,
  choosing,
  previewing,
  canPreview,
  onPreview,
  onChoose,
}: {
  item: { link: string; title: string; creator: string; duration?: number };
  note?: string;
  busy: boolean;
  choosing: string | null;
  previewing: string | null;
  canPreview: boolean;
  onPreview: (link: string) => void;
  onChoose: (link: string) => void;
}) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="min-w-0 flex-1 break-words">
        <Music2 className="mr-1.5 inline size-4 text-fg-2" />
        {item.title || "Bài nhạc"}
        {item.creator && <span className="text-fg-2"> · {item.creator}</span>}
        {item.duration ? <span className="tabular text-fg-2"> · {formatClock(item.duration)}</span> : null}
        {note && <span className="block text-xs text-fg-2">{note}</span>}
      </span>
      <span className="flex shrink-0 gap-1">
        {canPreview && (
          <Button size="sm" variant="ghost" icon={previewing === item.link ? Square : Play} aria-pressed={previewing === item.link}
            onClick={() => onPreview(item.link)}>
            {previewing === item.link ? "Dừng nghe" : "Nghe thử"}
          </Button>
        )}
        <Button size="sm" variant="secondary" icon={Pin} disabled={busy} loading={choosing === item.link}
          onClick={() => onChoose(item.link)}>
          {choosing === item.link ? "Đang đổi…" : "Chọn"}
        </Button>
      </span>
    </li>
  );
}

/** "Đổi bài": các bài khác hợp đoạn này, hợp nhất trước (cùng cách chấm điểm với lúc máy chọn). Chọn = ghim bài ấy. Dưới là
 *  nhóm "Nhạc của tôi": mọi bài bạn đã nhập, kể cả bài chưa phân tích (máy không tự chọn chúng, nhưng bạn ghim được). */
function Alternatives({
  bookId,
  sceneKey,
  busy,
  choosing,
  previewing,
  onPreview,
  onStopPreview,
  onChoose,
}: {
  bookId: string;
  sceneKey: string;
  busy: boolean;
  choosing: string | null;
  previewing: string | null;
  onPreview: (link: string) => void;
  onStopPreview: () => void;
  onChoose: (link: string) => void;
}) {
  useEffect(() => onStopPreview, [onStopPreview]); // đóng danh sách (hay mở đoạn khác) thì bài nghe thử dừng
  const { data: info } = useAppInfo();
  const { data, isLoading, error } = useQuery({
    queryKey: ["music-alternatives", bookId, sceneKey],
    queryFn: () =>
      api<{ alternatives: Alternative[]; mine?: MineAlternative[] }>(
        `/api/books/${bookId}/music/scenes/${encodeURIComponent(sceneKey)}/alternatives`,
      ),
    staleTime: 0,
    gcTime: 0,
  });
  if (isLoading) return <p className="text-fg-2">Đang tìm bài khác…</p>;
  if (error) return <p className="text-warning">{(error as Error).message}</p>;
  const mine = data?.mine ?? [];
  // Nhạc của tôi nằm trên máy tính chủ sách: nghe thử từ máy khác (Studio từ xa) không đi qua đường theo sách.
  const canPreviewMine = !info?.remote;
  const row = { busy, choosing, previewing, onPreview, onChoose };
  return (
    <div className="space-y-3">
      {data?.alternatives.length ? (
        <ul className="space-y-1">
          {data.alternatives.map((item) => (
            <TrackRow key={item.link} item={item} canPreview {...row} />
          ))}
        </ul>
      ) : (
        <p className="text-fg-2">Không còn bài nào khác trong danh mục đủ hợp đoạn này.</p>
      )}
      <div>
        <h4 className="font-medium">Nhạc của tôi</h4>
        {mine.length ? (
          <ul className="mt-1 space-y-1">
            {mine.map((item) => (
              <TrackRow
                key={item.link}
                item={item}
                note={item.analysed ? (item.fits ? "Hợp không khí đoạn này" : undefined) : "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được"}
                canPreview={canPreviewMine}
                {...row}
              />
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-fg-2">
            {info?.remote
              ? "Chưa có bài nào. Nhập nhạc của bạn trên máy tính chủ sách."
              : "Chưa có bài nào - bấm “Nhập nhạc của tôi…” ở đầu trang để thêm nhạc của riêng bạn."}
          </p>
        )}
      </div>
    </div>
  );
}

/** "Nhạc của tôi": nhạc bạn tự có, làm nhạc nền ngoài danh mục. Nhập, xem, xoá, nghe thử ở đây; ghim cho từng đoạn ở "Đổi bài". */
function MyMusic({ bookId, previewing, onPreview }: { bookId: string; previewing: string | null; onPreview: (link: string) => void }) {
  const client = useQueryClient();
  const { data: info } = useAppInfo();
  const canImport = Boolean(info?.dialogs); // hộp chọn file là của máy tính chủ sách, không có ở Studio từ xa
  const key = ["music-local"];
  const { data } = useQuery({ queryKey: key, queryFn: () => api<LocalMusicView>("/api/music/local"), enabled: canImport });
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const refresh = (view: LocalMusicView) => {
    client.setQueryData(key, view);
    void client.invalidateQueries({ queryKey: ["music-alternatives", bookId] });
  };
  const importFiles = async () => {
    const paths = await pickFiles("Chọn nhạc của bạn", "", "music").catch((error: Error) => {
      toast.error(error.message);
      return [] as string[];
    });
    if (!paths.length) return;
    const results: ImportResult[] = [];
    setProgress({ done: 0, total: paths.length });
    try {
      // Từng file một: thấy tiến độ, và một file hỏng không làm mất những file đã vào.
      for (const [index, path] of paths.entries()) {
        const result = await api<ImportResult>("/api/music/local/import", { method: "POST", body: { paths: [path] } });
        results.push(result);
        refresh(result);
        setProgress({ done: index + 1, total: paths.length });
      }
    } catch (error) {
      toast.error("Đang nhập nhạc thì dừng", { description: (error as Error).message });
    } finally {
      setProgress(null);
    }
    if (!results.length) return;
    const summary = importSummary(mergeImports(results));
    toast[summary.kind](summary.title, { description: summary.description });
  };
  const remove = useMutation({
    mutationFn: (link: string) => api<LocalMusicView>(`/api/music/local/${link.slice(LOCAL_PREFIX.length)}`, { method: "DELETE" }),
    onSuccess: (view) => {
      refresh(view);
      setRemoving(null);
      toast("Đã xoá khỏi Nhạc của tôi", {
        description: "Sách đã xuất vẫn giữ bản của bài này. Đoạn đang ghim bài ấy trên máy này sẽ dùng bài khác ở lần dựng sau.",
      });
    },
    onError: (error: Error) => toast.error("Không xoá được bài này", { description: error.message }),
  });
  const tracks = data?.tracks ?? [];
  return (
    <section className="space-y-3 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-semibold">Nhạc của tôi{canImport && tracks.length ? ` (${tracks.length})` : ""}</h3>
        {canImport && (
          <Button size="sm" variant="secondary" icon={Upload} loading={Boolean(progress)} onClick={() => void importFiles()}>
            {progress ? `Đang nhập ${progress.done}/${progress.total}…` : "Nhập nhạc của tôi…"}
          </Button>
        )}
      </div>
      <p className="text-sm text-fg-2 text-pretty">
        Thêm nhạc của riêng bạn (mp3, m4a, ogg, opus, flac, wav) làm nhạc nền. File được chép vào kho nhạc của máy này. Bài nào bạn
        ghim cho một đoạn (ở “Đổi bài”) sẽ đi cùng file sách .abook / .abookproj và sang điện thoại, vì không ai khác tải được nó.
        ABook chỉ ghi tên bài và nghệ sĩ có sẵn trong file, không nói gì về giấy phép.
      </p>
      {!canImport && (
        <p className="text-sm text-fg-2">Nhập và xoá nhạc làm trên máy tính chủ sách. Ở đây bạn vẫn ghim được bài đã nhập qua “Đổi bài”.</p>
      )}
      {canImport && !!tracks.length && data && !data.analyzer && tracks.some((track) => !track.analysed) && (
        <p className="text-sm text-fg-2">
          Máy chưa có bộ phân tích âm thanh nên chưa tự chọn nhạc của bạn cho đoạn nào. Bạn vẫn ghim được từng bài cho từng đoạn ở “Đổi bài”.
        </p>
      )}
      {canImport && !tracks.length && <p className="text-sm text-fg-2">Chưa có bài nào.</p>}
      {!!tracks.length && (
        <ul className="divide-y divide-line rounded-lg border border-line">
          {tracks.map((track: LocalTrack) => (
            <li key={track.link} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
              <span className="min-w-0 flex-1 break-words">
                <Music2 className="mr-1.5 inline size-4 text-accent-text" />
                {track.title}
                {track.creator && <span className="text-fg-2"> · {track.creator}</span>}
                {track.duration ? <span className="tabular text-fg-2"> · {formatClock(track.duration)}</span> : null}
                <span className="block text-xs text-fg-2">{analysisLabel(track)}</span>
              </span>
              <span className="flex shrink-0 gap-1">
                <Button size="sm" variant="ghost" icon={previewing === track.link ? Square : Play} aria-pressed={previewing === track.link}
                  onClick={() => onPreview(track.link)}>
                  {previewing === track.link ? "Dừng nghe" : "Nghe thử"}
                </Button>
                {removing === track.link ? (
                  <>
                    <Button size="sm" variant="secondary" icon={Trash2} loading={remove.isPending} onClick={() => remove.mutate(track.link)}>
                      Xoá khỏi kho
                    </Button>
                    <Button size="sm" variant="ghost" disabled={remove.isPending} onClick={() => setRemoving(null)}>
                      Giữ lại
                    </Button>
                  </>
                ) : (
                  <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setRemoving(track.link)}>
                    Xoá
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function MusicTab({ bookId, chapterTitle }: { bookId: string; chapterTitle: (id: number) => string }) {
  const client = useQueryClient();
  const [swapping, setSwapping] = useState<string | null>(null); // khoá đoạn đang mở "Đổi bài"
  const preview = usePreview();
  const key = ["music", bookId];
  const { data, isLoading } = useQuery({ queryKey: key, queryFn: () => api<MusicView>(`/api/books/${bookId}/music`) });
  const change = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<MusicView>(`/api/books/${bookId}/music`, { method: "PUT", body }),
    onSuccess: (result) => {
      client.setQueryData(key, result);
      setSwapping(null);
      announceChange(bookId);
      if (result.error) toast.warning("Đã lưu lựa chọn", { description: result.error });
    },
    onError: (error: Error) => toast.error("Không đổi được nhạc nền", { description: error.message }),
  });
  const rebuild = useMutation({
    mutationFn: () => api<MusicView>(`/api/books/${bookId}/music/rebuild`, { method: "POST" }),
    onSuccess: (result) => {
      client.setQueryData(key, result);
      setSwapping(null);
      announceChange(bookId);
    },
    onError: (error: Error) => toast.error("Không chọn lại được nhạc", { description: error.message }),
  });

  /** Bỏ một bài cho cả cuốn: lặng lẽ thì khó hiểu vì sao các đoạn khác cũng đổi bài, nên báo (kèm số đoạn đang dùng bài
   *  ấy, đếm trước khi đổi) và cho "Hoàn tác". */
  const ban = (link: string, label: string) => {
    const used = (data?.plan?.scenes ?? []).filter((scene) => scene.link === link).length;
    change.mutate(
      { ban: [link] },
      {
        onSuccess: () =>
          toast(`Đã bỏ bài này cho cả cuốn (đang dùng ở ${used} đoạn)`, {
            description: label,
            action: { label: "Hoàn tác", onClick: () => change.mutate({ unban: [link] }) },
          }),
      },
    );
  };

  if (isLoading || !data) return <p className="mt-6 text-sm text-fg-2">Đang dựng nhạc nền…</p>;
  const { plan, overrides, taxonomy } = data;
  const genres = Object.entries(taxonomy.genres ?? {});
  const byChapter = new Map<number, Scene[]>();
  for (const scene of plan?.scenes ?? []) byChapter.set(scene.chapterId, [...(byChapter.get(scene.chapterId) ?? []), scene]);
  // Bài đang được đổi sang (nút "Chọn" của nó hiện "Đang đổi…").
  const pending = change.isPending ? (change.variables?.pins as Record<string, string | null> | undefined) : undefined;
  const choosing = Object.values(pending ?? {}).find((link): link is string => !!link) ?? null;

  return (
    <div className="mt-6 space-y-6">
      <section className="flex flex-wrap items-end gap-4 rounded-xl border border-line bg-panel p-4">
        <Button
          variant={overrides.enabled ? "primary" : "secondary"}
          icon={overrides.enabled ? Volume2 : VolumeX}
          loading={change.isPending}
          aria-pressed={overrides.enabled}
          onClick={() => change.mutate({ enabled: !overrides.enabled })}
        >
          {overrides.enabled ? "Nhạc nền đang bật" : "Nhạc nền đang tắt"}
        </Button>
        <label className="min-w-0 basis-full text-sm sm:basis-auto">
          <span className="block text-fg-2">Thế giới của truyện</span>
          <select
            id="music-genre"
            value={overrides.genre ?? ""}
            title={genres.find(([value]) => value === overrides.genre)?.[1].vi ?? "Chưa chọn (mọi phong cách)"}
            onChange={(event) => change.mutate({ genre: event.target.value || null })}
            className="mt-1 h-9 w-full overflow-hidden text-ellipsis whitespace-nowrap rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent sm:w-64"
          >
            <option value="">Chưa chọn (mọi phong cách)</option>
            {genres.map(([value, genre]) => (
              <option key={value} value={value}>
                {genre.vi}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-0 basis-full text-sm sm:basis-auto">
          <span className="block text-fg-2">Mức nhạc dưới giọng đọc</span>
          <span className="block text-xs text-fg-2">Nhỏ hơn giọng đọc bấy nhiêu; máy tự bù bài to hay nhỏ</span>
          <select
            id="music-level"
            value={String(overrides.levelDb)}
            onChange={(event) => change.mutate({ levelDb: Number(event.target.value) })}
            className="mt-1 h-9 w-full rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent sm:w-48"
          >
            {LEVELS.map(([value, label]) => (
              <option key={value} value={String(value)}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <Button variant="ghost" icon={RefreshCw} loading={rebuild.isPending} onClick={() => rebuild.mutate()}>
          {rebuild.isPending ? "Đang chọn lại…" : "Chọn lại nhạc"}
        </Button>
        {overrides.banned.length > 0 && (
          <details className="basis-full text-sm">
            <summary className="cursor-pointer text-fg-2">Bài đã bỏ ({overrides.banned.length})</summary>
            <ul className="mt-2 space-y-1">
              {overrides.banned.map((link) => (
                <li key={link} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="min-w-0 flex-1 break-words">{trackLabel(link, data.bannedTracks?.[link] ?? plan?.tracks[link])}</span>
                  <Button size="sm" variant="ghost" disabled={change.isPending} onClick={() => change.mutate({ unban: [link] })}>
                    Dùng lại
                  </Button>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <MyMusic bookId={bookId} previewing={preview.playing} onPreview={preview.toggle} />

      {data.error && <p className="text-sm text-warning">{data.error}</p>}
      {!overrides.enabled && !!plan?.scenes.length && (
        <p className="text-sm text-fg-2">Nhạc nền đang tắt - các đoạn dưới đây sẽ không phát.</p>
      )}
      {!plan?.scenes.length ? (
        <p className="text-sm text-fg-2">Chưa có đoạn nào - nhạc nền dựng sau khi sách đã phân tích.</p>
      ) : (
        [...byChapter.entries()].map(([chapterId, scenes]) => (
          <section key={chapterId} className={overrides.enabled ? undefined : "opacity-50"}>
            <h3 className="mb-2 text-sm font-semibold">{chapterTitle(chapterId)}</h3>
            <ul className="divide-y divide-line rounded-xl border border-line">
              {scenes.map((scene, index) => {
                const track = scene.link ? plan.tracks[scene.link] : undefined;
                return (
                  <li key={scene.key} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-3 py-2.5 text-sm">
                    <span className="tabular w-28 shrink-0 text-fg-2">
                      {/* Các đoạn nối liền: đoạn này hết ở đúng chỗ đoạn sau bắt đầu (cùng cách làm tròn). */}
                      {formatClock(scene.start)}–{formatClock(scenes[index + 1]?.start ?? scene.end)}
                    </span>
                    <span className="w-32 shrink-0">{moodOf(scene, taxonomy.emotions)}</span>
                    <span className="min-w-0 basis-full break-words sm:flex-1 sm:basis-0">
                      {scene.link ? (
                        <>
                          <Music2 className="mr-1.5 inline size-4 text-accent-text" />
                          {track?.title ?? "Bài nhạc"}
                          {track?.creator && <span className="text-fg-2"> · {track.creator}</span>}
                          {track?.source === "local" && (
                            <span className="ml-1.5 rounded bg-sunken px-1.5 py-0.5 text-xs text-fg-2">Nhạc của tôi</span>
                          )}
                          {scene.pinned && <Pin className="ml-1.5 inline size-3.5 text-fg-2" aria-label="Đã ghim" />}
                          {scene.pinUnavailable && (
                            <span className="block text-xs text-warning">Bài bạn ghim không còn trên máy này - đoạn dùng bài khác.</span>
                          )}
                        </>
                      ) : (
                        <span className="text-fg-2">{scene.silenced ? "Im lặng (bạn chọn)" : "Im lặng - không bài nào đủ hợp"}</span>
                      )}
                    </span>
                    <span className="flex basis-full flex-wrap gap-1 sm:basis-auto sm:shrink-0">
                      <Button size="sm" variant="ghost" icon={Shuffle} aria-expanded={swapping === scene.key}
                        onClick={() => setSwapping(swapping === scene.key ? null : scene.key)}>
                        Đổi bài
                      </Button>
                      <Button size="sm" variant="ghost" icon={VolumeX}
                        onClick={() => change.mutate({ silence: { [scene.key]: !scene.silenced } })}>
                        {scene.silenced ? "Có nhạc" : "Im lặng"}
                      </Button>
                      {scene.pinned && (
                        <Button size="sm" variant="ghost" onClick={() => change.mutate({ pins: { [scene.key]: null } })}>
                          Bỏ ghim
                        </Button>
                      )}
                      {scene.link && (
                        <Button size="sm" variant="ghost" icon={Ban} onClick={() => ban(scene.link!, trackLabel(scene.link!, track))}>
                          Không dùng bài này cho cả cuốn
                        </Button>
                      )}
                    </span>
                    {swapping === scene.key && (
                      <div className="basis-full rounded-lg bg-sunken p-2.5 text-sm">
                        <Alternatives
                          bookId={bookId}
                          sceneKey={scene.key}
                          busy={change.isPending}
                          choosing={choosing}
                          previewing={preview.playing}
                          onPreview={preview.toggle}
                          onStopPreview={preview.stop}
                          onChoose={(link) =>
                            // Đoạn đang im lặng (bạn chọn) mà chọn bài thì có nhạc lại.
                            change.mutate({ pins: { [scene.key]: link }, ...(scene.silenced ? { silence: { [scene.key]: false } } : {}) })
                          }
                        />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      )}
      {plan && Object.keys(plan.tracks).length > 0 && (
        <details className="text-xs text-fg-2">
          <summary className="cursor-pointer">Ghi công các bài nhạc ({Object.keys(plan.tracks).length})</summary>
          <ul className="mt-2 space-y-1">
            {Object.entries(plan.tracks).map(([link, track]) => (
              <li key={link} className="break-words">
                {track.source === "local"
                  ? `${[track.title, track.creator].filter(Boolean).join(" · ")} - nhạc của bạn, không có thông tin giấy phép`
                  : (track.attribution ?? link)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
