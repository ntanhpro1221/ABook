import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Ban, Download, Music2, MoreHorizontal, Pin, PinOff, Play, RefreshCw, Shuffle, Square, Trash2, Upload, VolumeX, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { MUSIC_CHANGED_EVENT } from "@/listen/musicBed";
import { cn } from "@/shared/cn";
import { formatClock } from "@/shared/format";
import { MUSIC_LEVELS as LEVELS } from "@/shared/musicLevels";
import { Button, IconButton, Progress } from "@/shared/ui";
import { api, mediaUrl } from "./api";
import { useAppInfo } from "./data";
import { importMusic } from "./musicImport";
import { CONTINUED_NOTE, downloadShare, downloadText, isContinuation, swapButton, type MusicDownload } from "./musicScenes";
import {
  analysisLabel,
  importSummary,
  LOCAL_PREFIX,
  MY_MUSIC_INTRO,
  mineNote,
  previewPath,
  type LocalMusicView,
  type LocalTrack,
} from "./musicLocal";
import { AutoPickNote } from "./AutoPickNote";
import { MusicModuleNotice } from "./MusicModuleNotice";

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
  /** Mảnh nối tiếp của một đoạn dài: chơi tiếp bài của đoạn trên (docs/MUSIC_RESEARCH.md), không phải một lựa chọn riêng. */
  continued?: boolean;
  /** Bài đã ghim không còn dùng được trên máy này (vd. đã xoá khỏi "Nhạc của tôi"): lần dựng này đoạn dùng bài khác. */
  pinUnavailable?: boolean;
  /** "llm": vui/buồn và căng thẳng của đoạn do AI đọc cả đoạn; "student": AI còn đoán hình không khí trong chương; "labels": cộng từ cảm xúc từng câu. */
  moodSource?: "llm" | "chapter" | "student" | "labels";
}

/** Model AI đọc không khí cả đoạn (tuỳ chọn, tải khi bấm): `downloadable` false = Ollama của máy, người dùng tự kéo model. */
interface MoodsModel {
  installed: boolean;
  downloading: boolean;
  progress: { done: number; total: number } | null;
  error: string | null;
  downloadable: boolean;
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
  /** Việc nền "Đọc lại không khí các đoạn" của cuốn này. */
  moods?: { running: boolean; error: string };
  /** Máy đang tải sẵn các bài của rãnh nhạc (để nghe / điện thoại / file sách có nhạc ngay) - huỷ được. */
  download?: MusicDownload;
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
  /** Như `LocalTrack`: nhãn "Có vẻ có lời" / "Máy không tự chọn bài này" ở danh sách "Đổi bài" giống ở Cài đặt. */
  vocalsLikely?: boolean;
  auto?: "on" | "off";
}

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

/** "Chọn lại nhạc" (và đổi thể loại) dựng lại nhạc cả cuốn - sách 43 chương mất cỡ nửa phút: nói ra để các nút mờ không có vẻ như bị treo. */
const REBUILDING = "Đang chọn lại nhạc cho cả cuốn - cỡ nửa phút với sách dài. Bạn cứ chờ ở đây, xong là tự cập nhật.";
/** Sửa một đoạn (chọn bài, ghim, im lặng, bỏ bài) chỉ mất chốc lát: chỉ báo bận nhẹ, không hứa nửa phút. */
const SAVING = "Đang lưu lựa chọn…";

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
      {busy && (
        <p role="status" className="text-fg-2">
          {SAVING}
        </p>
      )}
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
                note={mineNote(item)}
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
    try {
      const { result, error } = await importMusic((done, total, latest) => {
        setProgress({ done, total });
        if (latest) refresh(latest);
      });
      if (error) toast.error("Đang nhập nhạc thì dừng", { description: error.message });
      if (!result) return;
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
      <p className="text-sm text-fg-2 text-pretty">{MY_MUSIC_INTRO}</p>
      {!canImport && (
        <p className="text-sm text-fg-2">Nhập và xoá nhạc làm trên máy tính chủ sách. Ở đây bạn vẫn ghim được bài đã nhập qua “Đổi bài”.</p>
      )}
      {canImport && !!tracks.length && <MusicModuleNotice view={data} queryKey={key} />}
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
                <AutoPickNote track={track} canOverride={canImport} onView={refresh} idleLabel={analysisLabel(track)} />
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

/** "Chọn nhạc sát không khí hơn": model nhỏ (tuỳ chọn, tải khi bấm) đọc nguyên đoạn để chọn nhạc sát không khí hơn. Chưa tải:
 *  nút "Tải thêm"; đang tải: tiến độ; đã tải: "Đọc lại không khí các đoạn" cho cuốn này. */
function MoodsPanel({ bookId, moods, onCompute }: { bookId: string; moods?: { running: boolean; error: string }; onCompute: (view: MusicView) => void }) {
  const client = useQueryClient();
  const { data: info } = useAppInfo();
  const key = ["music-moods-model"];
  const { data } = useQuery({
    queryKey: key,
    queryFn: () => api<MoodsModel>("/api/music/moods-model"),
    refetchInterval: (query) => (query.state.data?.downloading ? 2000 : false),
  });
  const download = useMutation({
    mutationFn: () => api<MoodsModel>("/api/music/moods-model", { method: "POST" }),
    onSuccess: (result) => client.setQueryData(key, result),
    onError: (error: Error) => toast.error("Không tải được phần đọc không khí", { description: error.message }),
  });
  const compute = useMutation({
    mutationFn: () => api<MusicView>(`/api/books/${bookId}/music/moods`, { method: "POST" }),
    onSuccess: onCompute,
    onError: (error: Error) => toast.error("Không đọc lại được không khí các đoạn", { description: error.message }),
  });
  if (!data) return null;
  const running = Boolean(moods?.running) || compute.isPending;
  const percent = data.progress && data.progress.total > 0 ? Math.round((data.progress.done * 100) / data.progress.total) : null;
  return (
    <section className="space-y-2 rounded-xl border border-line bg-panel p-4">
      <h3 className="text-sm font-semibold">Chọn nhạc sát không khí hơn</h3>
      <p className="text-sm text-fg-2 text-pretty">
        Máy đọc kỹ cả đoạn truyện để hiểu không khí (buồn, căng thẳng, êm…) thay vì cộng cảm xúc từng câu, nên nhạc hợp đoạn hơn. Chạy
        sau khi phân tích xong - cỡ 1 phút cho mỗi giờ sách nếu máy có card đồ hoạ.
      </p>
      {data.installed ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" variant="secondary" icon={RefreshCw} loading={running} onClick={() => compute.mutate()}>
            {running ? "Đang đọc không khí…" : "Đọc lại không khí các đoạn"}
          </Button>
          {moods?.error && <span className="text-sm text-warning">{moods.error}</span>}
        </div>
      ) : data.downloading ? (
        <p className="text-sm">Đang tải phần đọc không khí{percent !== null ? ` - ${percent}%` : "…"}</p>
      ) : data.downloadable && !info?.remote ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" variant="secondary" icon={Download} loading={download.isPending} onClick={() => download.mutate()}>
            Tải thêm (3,2 GB)
          </Button>
          {data.error && <span className="text-sm text-warning">{data.error}</span>}
        </div>
      ) : (
        <p className="text-sm text-fg-2">
          {data.downloadable ? "Tải phần đọc không khí trên máy tính chủ sách." : "Máy này chưa có phần đọc không khí (cài qua Ollama)."}
        </p>
      )}
    </section>
  );
}

/** "…" của một đoạn nhạc: im lặng / có nhạc, bỏ ghim (khi đã ghim), không dùng bài này cho cả cuốn. Gom vào đây thay vì bốn nút lặp ở mỗi dòng. */
function SceneMenu({
  scene,
  disabled,
  onSilence,
  onUnpin,
  onBan,
}: {
  scene: Scene;
  disabled: boolean;
  onSilence: () => void;
  onUnpin: () => void;
  onBan?: () => void;
}) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <IconButton label="Thêm tuỳ chọn cho đoạn này" icon={MoreHorizontal} size="sm" disabled={disabled} className="data-[state=open]:bg-hover" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={4} collisionPadding={12} className="z-50 min-w-56 rounded-xl border border-line bg-panel p-1.5 shadow-float">
          <DropdownMenu.Item onSelect={onSilence} className={MENU_ITEM}>
            <VolumeX className="size-4" /> {scene.silenced ? "Cho đoạn này có nhạc" : "Để đoạn này im lặng"}
          </DropdownMenu.Item>
          {scene.pinned && (
            <DropdownMenu.Item onSelect={onUnpin} className={MENU_ITEM}>
              <PinOff className="size-4" /> Bỏ ghim - để máy chọn lại bài
            </DropdownMenu.Item>
          )}
          {onBan && (
            <>
              <DropdownMenu.Separator className="my-1 h-px bg-line" />
              <DropdownMenu.Item onSelect={onBan} className={cn(MENU_ITEM, "text-danger")}>
                <Ban className="size-4" /> Không dùng bài này cho cả cuốn
              </DropdownMenu.Item>
            </>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function MusicTab({ bookId, chapterTitle }: { bookId: string; chapterTitle: (id: number) => string }) {
  const client = useQueryClient();
  const [swapping, setSwapping] = useState<string | null>(null); // khoá đoạn đang mở "Đổi bài"
  const preview = usePreview();
  const key = ["music", bookId];
  const { data, isLoading } = useQuery({
    queryKey: key,
    queryFn: () => api<MusicView>(`/api/books/${bookId}/music`),
    // Đang đọc không khí / đang tải sẵn nhạc: hỏi lại tới khi xong.
    refetchInterval: (query) => (query.state.data?.moods?.running ? 3000 : query.state.data?.download?.active ? 2000 : false),
  });
  // Việc "Đọc lại không khí các đoạn" vừa xong: nhạc đã dựng lại, báo trình phát nạp lại mốc nhạc.
  const moodsRunning = useRef(false);
  useEffect(() => {
    const running = Boolean(data?.moods?.running);
    if (moodsRunning.current && !running) {
      announceChange(bookId);
      if (data?.moods?.error) toast.error("Không đọc xong không khí các đoạn", { description: data.moods.error });
      else toast("Đã đọc xong không khí các đoạn - nhạc đã chọn lại");
    }
    moodsRunning.current = running;
  }, [bookId, data?.moods?.running, data?.moods?.error]);
  const change = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<MusicView>(`/api/books/${bookId}/music`, { method: "PUT", body }),
    onSuccess: (result) => {
      client.setQueryData(key, result);
      setSwapping(null);
      announceChange(bookId);
      refreshSoon();
      if (result.error) toast.warning("Đã lưu lựa chọn", { description: result.error });
    },
    onError: (error: Error) => toast.error("Không đổi được nhạc nền", { description: error.message }),
  });
  const cancelDownload = useMutation({
    mutationFn: () => api<MusicView>(`/api/books/${bookId}/music/download/cancel`, { method: "POST" }),
    onSuccess: (result) => {
      // Máy chủ dừng ở khúc kế (một phần giây): ẩn dòng tiến độ ngay thay vì đợi lần hỏi sau.
      client.setQueryData(key, { ...result, download: undefined });
      toast("Đã dừng tải nhạc nền", { description: "Bài chưa tải sẽ được tải khi bạn nghe tới đoạn ấy." });
    },
    onError: (error: Error) => toast.error("Không dừng được việc tải nhạc", { description: error.message }),
  });
  // Đổi bài / Chọn lại nhạc vừa xong: máy bắt đầu tải bài mới ở nền - hỏi lại ngay để hiện tiến độ.
  const refreshSoon = () => window.setTimeout(() => void client.invalidateQueries({ queryKey: key }), 600);
  const rebuild = useMutation({
    mutationFn: () => api<MusicView>(`/api/books/${bookId}/music/rebuild`, { method: "POST" }),
    onSuccess: (result) => {
      client.setQueryData(key, result);
      setSwapping(null);
      announceChange(bookId);
      refreshSoon();
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
  // Màn hẹp: ô chọn không đủ rộng cho tên thể loại dài ("Dị giới / kỳ ảo phương Tây (…)") nên chữ bị cắt - ghi đủ tên bên dưới.
  const genreName = genres.find(([value]) => value === overrides.genre)?.[1].vi ?? "";
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
          <span className="block text-fg-2">Thể loại truyện</span>
          <span className="block text-xs text-fg-2">Chưa chọn thì nhạc lấy từ mọi thể loại</span>
          <select
            id="music-genre"
            value={overrides.genre ?? ""}
            title={genreName || "Chưa chọn"}
            onChange={(event) => change.mutate({ genre: event.target.value || null })}
            // Rộng vừa tên thể loại dài nhất ("Dị giới / kỳ ảo phương Tây (…)") - không cắt chữ; hẹp màn thì thôi ở bề ngang ô.
            className="mt-1 h-9 w-full max-w-full rounded-lg border border-line bg-panel px-2.5 text-sm font-normal text-fg outline-none focus-visible:border-accent sm:w-auto sm:min-w-64"
          >
            <option value="">Chưa chọn</option>
            {genres.map(([value, genre]) => (
              <option key={value} value={value}>
                {genre.vi}
              </option>
            ))}
          </select>
          {genreName.length > 28 && <span className="mt-1 block text-xs text-fg-2 sm:hidden">{genreName}</span>}
        </label>
        <label className="min-w-0 basis-full text-sm sm:basis-auto">
          <span className="block text-fg-2">Mức nhạc dưới giọng đọc</span>
          <span className="block text-xs text-fg-2">Nhỏ hơn giọng đọc bấy nhiêu; máy tự bù bài to hay nhỏ</span>
          <select
            id="music-level"
            value={String(overrides.levelDb)}
            onChange={(event) => change.mutate({ levelDb: Number(event.target.value) })}
            className="mt-1 h-9 w-full rounded-lg border border-line bg-panel px-2.5 text-sm font-normal text-fg outline-none focus-visible:border-accent sm:w-48"
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
        {(change.isPending || rebuild.isPending) && (
          <p role="status" className="basis-full text-sm text-fg-2">
            {rebuild.isPending || change.variables?.genre !== undefined ? REBUILDING : SAVING}
          </p>
        )}
        {data.download?.active && (
          <div role="status" className="flex basis-full flex-wrap items-center gap-x-3 gap-y-1 text-sm text-fg-2">
            <span className="min-w-0 flex-1">{downloadText(data.download)}</span>
            <Button size="sm" variant="ghost" icon={Square} loading={cancelDownload.isPending} onClick={() => cancelDownload.mutate()}>
              Huỷ tải
            </Button>
            <Progress value={downloadShare(data.download)} size="sm" label="Tải sẵn nhạc nền" className="basis-full" />
          </div>
        )}
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

      <MoodsPanel bookId={bookId} moods={data.moods} onCompute={(view) => client.setQueryData(key, view)} />

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
                const follows = isContinuation(scene);
                const swap = swapButton(scene);
                return (
                  <li key={scene.key} className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5 px-3 text-sm", follows ? "py-1.5" : "py-2.5")}>
                    <span className="tabular w-28 shrink-0 text-fg-2">
                      {/* Các đoạn nối liền: đoạn này hết ở đúng chỗ đoạn sau bắt đầu (cùng cách làm tròn). */}
                      {formatClock(scene.start)}–{formatClock(scenes[index + 1]?.start ?? scene.end)}
                    </span>
                    <span className="w-32 shrink-0">
                      {moodOf(scene, taxonomy.emotions)}
                      {(scene.moodSource === "llm" || scene.moodSource === "chapter" || scene.moodSource === "student") && (
                        <span
                          className="ml-1.5 rounded bg-sunken px-1 py-0.5 text-xs text-fg-2"
                          title={
                            scene.moodSource === "student"
                              ? "AI đã đoán đoạn này vui hơn hay buồn hơn, căng hơn hay dịu hơn so với mức của cả chương"
                              : scene.moodSource === "chapter"
                                ? "AI đã đọc cả đoạn này để chấm không khí, rồi cân theo mức của cả chương"
                                : "AI đã đọc cả đoạn này để chấm không khí"
                          }
                        >
                          AI
                        </span>
                      )}
                    </span>
                    <span className="min-w-0 basis-full break-words sm:flex-1 sm:basis-0">
                      {follows ? (
                        <span className="text-fg-2">{CONTINUED_NOTE}</span>
                      ) : scene.link ? (
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
                    {/* Một nút chính + "…": cột nút thẳng hàng ở mọi dòng (trước đây bốn nút, dòng có "Bỏ ghim" lệch cột). */}
                    <span className="flex basis-full items-center gap-1 sm:w-32 sm:shrink-0 sm:basis-auto sm:justify-end">
                      <Button size="sm" variant="ghost" icon={Shuffle} aria-expanded={swapping === scene.key} title={swap.title}
                        onClick={() => setSwapping(swapping === scene.key ? null : scene.key)}>
                        {swap.text}
                      </Button>
                      {follows && <span aria-hidden className="size-8 shrink-0 max-sm:hidden" />}
                      {!follows && <SceneMenu
                        scene={scene}
                        disabled={change.isPending}
                        onSilence={() => change.mutate({ silence: { [scene.key]: !scene.silenced } })}
                        onUnpin={() => change.mutate({ pins: { [scene.key]: null } })}
                        onBan={scene.link ? () => ban(scene.link!, trackLabel(scene.link!, track)) : undefined}
                      />}
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
