import { MotionRegion } from "@/shared/MotionRegion";
import { useBackLayer } from "@/shared/backStack";
import { MoreInfo, SettingsRow } from "@/shared/SettingsNav";
import { Switch } from "@/desktop/PhoneSync";
import { MY_MUSIC_HELP } from "./musicLocal";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { Fold, Collapse } from "@/shared/Collapse";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Ban, Download, Music2, MoreHorizontal, Pin, PinOff, Play, RefreshCw, Shuffle, Square, Trash2, Upload, VolumeX } from "lucide-react";
import { toast } from "@/shared/toast";
import { MUSIC_CHANGED_EVENT } from "@/listen/musicBed";
import { cn } from "@/shared/cn";
import { MUSIC_MODIFIED_NOTE, formatClock, musicCreditText, musicNeedsModifiedNote } from "@/shared/format";
import { spokenProgress } from "@/shared/progressSpeech";
import { MUSIC_LEVELS as LEVELS, levelText } from "@/shared/musicLevels";
import { Select, Button, IconButton, LiveText, Progress, ContentSkeleton, InlineError, EmptyState } from "@/shared/ui";
import { api, mediaUrl } from "./api";
import { useAppInfo } from "./data";
import { importMusic } from "./musicImport";
import { CONTINUED_NOTE, downloadShare, downloadText, isContinuation, moodOf, swapButton, type MusicDownload } from "./musicScenes";
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
  license?: string;
  /** "local": bài người dùng tự nhập ("Nhạc của tôi") - không có ghi công / giấy phép, chỉ tên + nghệ sĩ của chính file. */
  source?: string;
}

interface MusicView {
  plan: { enabled: boolean; levelDb: number; genre: string | null; scenes: Scene[]; tracks: Record<string, TrackInfo> } | null;
  overrides: { enabled: boolean; levelDb: number; genre: string | null; pins: Record<string, string>; silenced: string[]; banned: string[] };
  error: string;
  /** Tên các bài đã bỏ (từ danh mục; thiếu thì hiện tên file). */
  bannedTracks?: Record<string, TrackInfo>;
  /** Việc nền "Đọc lại ngữ cảnh" của cuốn này. */
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
const REBUILDING = "Đang chọn lại nhạc, cỡ nửa phút.";
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
        <Button size="sm" variant="ghost" icon={Pin} disabled={busy} loading={choosing === item.link}
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
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["music-alternatives", bookId, sceneKey],
    queryFn: () =>
      api<{ alternatives: Alternative[]; mine?: MineAlternative[] }>(
        `/api/books/${bookId}/music/scenes/${encodeURIComponent(sceneKey)}/alternatives`,
      ),
    staleTime: 0,
    gcTime: 0,
  });
  if (isLoading) return <MotionRegion fadeThrough><ContentSkeleton label="Đang tải bài khác" /></MotionRegion>;
  if (error && !data) return <MotionRegion fadeThrough><InlineError message="Bạn hãy kiểm tra kết nối rồi tìm lại bài nhạc." onRetry={() => void refetch()} /></MotionRegion>;
  const mine = data?.mine ?? [];
  // Nhạc của tôi nằm trên máy tính chủ sách: nghe thử từ máy khác (Studio từ xa) không đi qua đường theo sách.
  const canPreviewMine = !info?.remote;
  const row = { busy, choosing, previewing, onPreview, onChoose };
  return (
    <MotionRegion as="div" className="space-y-3">
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
    </MotionRegion>
  );
}

/** "Nhạc của tôi": nhạc bạn tự có, làm nhạc nền ngoài danh mục. Nhập, xem, xoá, nghe thử ở đây; ghim cho từng đoạn ở "Đổi bài". */
export function MyMusic({ bookId, previewing, onPreview }: { bookId: string; previewing: string | null; onPreview: (link: string) => void }) {
  const client = useQueryClient();
  const { data: info } = useAppInfo();
  const canImport = Boolean(info?.dialogs); // hộp chọn file là của máy tính chủ sách, không có ở Studio từ xa
  const key = ["music-local"];
  const { data, isLoading, error, refetch } = useQuery({ queryKey: key, queryFn: () => api<LocalMusicView>("/api/music/local"), enabled: canImport });
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const removeBox = useRef<HTMLElement>(null);
  const removeButton = useRef<HTMLButtonElement>(null);
  const removeLink = useRef<string | null>(null);
  useBackLayer(removing !== null, () => setRemoving(null), removeBox, removeButton);
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
      toast("Đã xoá khỏi Nhạc của tôi");
    },
    onError: (error: Error) => toast.error("Không xoá được bài này", { description: error.message }),
  });
  const tracks = data?.tracks ?? [];
  return (
    <MotionRegion as="section" elementRef={removeBox} className="space-y-3">
      <p className="text-sm text-fg-2 text-pretty">{MY_MUSIC_INTRO}</p>
      <MoreInfo label="Nhạc riêng">{MY_MUSIC_HELP}</MoreInfo>
      {!canImport && (
        <p className="text-sm text-fg-2">Nhập/xoá trên máy chủ; ở đây dùng “Đổi bài” để ghim nhạc.</p>
      )}
      {canImport && tracks.length > 0 && (
        <Button size="sm" variant="ghost" icon={Upload} loading={Boolean(progress)} onClick={() => void importFiles()} className="-ml-3">
          {progress ? `Đang nhập ${progress.done}/${progress.total}…` : "Nhập nhạc của tôi…"}
        </Button>
      )}
      <MotionPresence open={canImport && !!tracks.length}><MusicModuleNotice view={data} queryKey={key} /></MotionPresence>
      {canImport && <MotionRegion motionKey={isLoading ? "loading" : error && !data ? "error" : tracks.length ? "ready" : "empty"}>{isLoading ? <ContentSkeleton count={2} label="Đang tải nhạc riêng" /> : error && !data ? <InlineError message="Bạn hãy thử tải lại nhạc của bạn." onRetry={() => void refetch()} /> : !tracks.length ? <EmptyState icon={Music2} title="Thêm nhạc của bạn" className="py-6" action={<Button icon={Upload} onClick={() => void importFiles()} loading={Boolean(progress)}>Nhập nhạc</Button>} /> : null}</MotionRegion>}
      {/* Xoá / nhập bài: hàng khép / mở tại chỗ (DESIGN 5.2); data-motion-live - cả khung không mờ lại theo từng hàng. */}
      <MotionPresence open={!!tracks.length}>
        <div data-motion-live="">
        <AnimatedRows className="divide-y divide-line" items={tracks} keyOf={(track: LocalTrack) => track.link}>
          {(track: LocalTrack) => (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
              <span className="min-w-0 flex-1 break-words">
                <Music2 className="mr-1.5 inline size-4 text-accent-text" />
                {track.title}
                {track.creator && <span className="text-fg-2"> · {track.creator}</span>}
                {track.duration ? <span className="tabular text-fg-2"> · {formatClock(track.duration)}</span> : null}
                <AutoPickNote track={track} canOverride={canImport} onView={refresh} idleLabel={analysisLabel(track)} />
              </span>
              <MotionRegion as="span" className="flex shrink-0 gap-1">
                <Button size="sm" variant="ghost" icon={previewing === track.link ? Square : Play} aria-pressed={previewing === track.link}
                  onClick={() => onPreview(track.link)}>
                  {previewing === track.link ? "Dừng nghe" : "Nghe thử"}
                </Button>
                {removing === track.link ? (
                  <>
                    <Button size="sm" variant="ghost" icon={Trash2} loading={remove.isPending} onClick={() => remove.mutate(track.link)}>
                      Xoá khỏi kho
                    </Button>
                    <Button size="sm" variant="ghost" disabled={remove.isPending} onClick={() => setRemoving(null)}>
                      Giữ lại
                    </Button>
                  </>
                ) : (
                  <Button ref={(el) => { if (removeLink.current === track.link) removeButton.current = el; }} size="sm" variant="ghost" icon={Trash2} onClick={() => { removeLink.current = track.link; setRemoving(track.link); }}>
                    Xoá
                  </Button>
                )}
              </MotionRegion>
            </div>
          )}
        </AnimatedRows>
        </div>
      </MotionPresence>
    </MotionRegion>
  );
}

/** "Nhạc theo ngữ cảnh": model nhỏ (tuỳ chọn, tải khi bấm) đọc nguyên đoạn để chọn nhạc sát không khí hơn. Chưa tải:
 *  nút "Tải thêm"; đang tải: tiến độ; đã tải: "Đọc lại ngữ cảnh" cho cuốn này. */
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
  if (!data) return <MotionRegion />;
  const running = Boolean(moods?.running) || compute.isPending;
  const percent = data.progress && data.progress.total > 0 ? Math.round((data.progress.done * 100) / data.progress.total) : null;
  return (
    <MotionRegion as="section" className="space-y-2">
      <p className="text-sm text-fg-2 text-pretty">
        Hiểu ngữ cảnh để chọn nhạc; ~1 phút mỗi giờ sách.
      </p>
      {data.installed ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" variant="ghost" icon={RefreshCw} loading={running} onClick={() => compute.mutate()}>
            {running ? "Đang đọc không khí…" : "Đọc lại ngữ cảnh"}
          </Button>
          {moods?.error && <span className="text-sm text-warning">{moods.error}</span>}
        </div>
      ) : data.downloading ? (
        <p className="text-sm">Đang tải phần đọc không khí{percent !== null ? ` - ${percent}%` : "…"}</p>
      ) : data.downloadable && !info?.remote ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" variant="ghost" icon={Download} loading={download.isPending} onClick={() => download.mutate()}>
            Tải thêm (3,2 GB)
          </Button>
          {data.error && <span className="text-sm text-warning">{data.error}</span>}
        </div>
      ) : (
        <p className="text-sm text-fg-2">
          {data.downloadable ? "Tải phần đọc không khí trên máy tính chủ sách." : "Máy này chưa có phần đọc không khí (cài qua Ollama)."}
        </p>
      )}
    </MotionRegion>
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
        <DropdownMenu.Content align="end" sideOffset={4} collisionPadding={12} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-56 rounded-xl border border-line bg-panel p-1.5 shadow-float">
          <DropdownMenu.Item onSelect={onSilence} className={MENU_ITEM}>
            <VolumeX className="size-4" /> {scene.silenced ? "Bật nhạc đoạn này" : "Tắt nhạc đoạn này"}
          </DropdownMenu.Item>
          {scene.pinned && (
            <DropdownMenu.Item onSelect={onUnpin} className={MENU_ITEM}>
              <PinOff className="size-4" /> Bỏ ghim
            </DropdownMenu.Item>
          )}
          {onBan && (
            <>
              <DropdownMenu.Separator className="my-1 h-px bg-line" />
              <DropdownMenu.Item onSelect={onBan} className={cn(MENU_ITEM, "text-danger")}>
                <Ban className="size-4" /> Loại khỏi cuốn
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
  const [swapping, setSwapping] = useState<string | null>(null);
  const swapBox = useRef<HTMLDivElement>(null);
  const swapTrigger = useRef<HTMLButtonElement>(null);
  useBackLayer(swapping !== null, () => setSwapping(null), swapBox, swapTrigger); // khoá đoạn đang mở "Đổi bài"
  const preview = usePreview();
  const key = ["music", bookId];
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: key,
    queryFn: () => api<MusicView>(`/api/books/${bookId}/music`),
    // Đang đọc không khí / đang tải sẵn nhạc: hỏi lại tới khi xong.
    refetchInterval: (query) => (query.state.data?.moods?.running ? 3000 : query.state.data?.download?.active ? 2000 : false),
  });
  // Việc "Đọc lại ngữ cảnh" vừa xong: nhạc đã dựng lại, báo trình phát nạp lại mốc nhạc.
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
  // Lượt tải sẵn vừa dừng vì mất mạng (máy chủ giữ nhạc cũ và ghi lý do vào `error`): báo ngay, không để dòng chữ cuối trang nằm im.
  const downloading = useRef(false);
  useEffect(() => {
    const active = Boolean(data?.download?.active);
    if (downloading.current && !active && data?.error) toast.warning("Chưa tải được nhạc", { description: data.error });
    downloading.current = active;
  }, [data?.download?.active, data?.error]);
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
      toast("Đã dừng tải nhạc nền");
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
          toast(`Đã bỏ “${label}” cho cả cuốn (đang dùng ở ${used} đoạn)`, {
            action: { label: "Hoàn tác", onClick: () => change.mutate({ unban: [link] }) },
          }),
      },
    );
  };

  // Lần đầu (danh mục chưa có trên máy) mất cỡ 10 giây - bài nhạc tải sau ở nền, không chờ ở đây (soát UX a60: từng mất 2,7 phút).
  if (error && !data) return <MotionRegion fadeThrough><InlineError className="mt-6" message="Bạn hãy kiểm tra kết nối rồi tải lại nhạc nền." onRetry={() => void refetch()} /></MotionRegion>;
  if (isLoading || !data) return <MotionRegion fadeThrough><ContentSkeleton shape="cards" label="Đang tải nhạc nền" className="mt-6" /></MotionRegion>;
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
    <MotionRegion as="div" className="mt-6 space-y-6">
      {/* Cài đặt nhạc của cuốn: một hàng một việc, công tắc / ô chọn bên phải như trang Cài đặt - không khung bao (DESIGN 4, 6). */}
      <section className="flex flex-wrap items-end gap-x-4">
        <div className="basis-full divide-y divide-line">
          <SettingsRow label={<span id="music-enabled-name">Nhạc nền</span>} hint={<span id="music-enabled-hint">{overrides.enabled ? "Đang bật cho cuốn này." : "Đang tắt: các đoạn dưới đây sẽ không phát."}</span>}>
            <Switch id="music-enabled" labelledBy="music-enabled-name" describedBy="music-enabled-hint" checked={overrides.enabled} disabled={change.isPending} onCheckedChange={(enabled) => change.mutate({ enabled })} />
          </SettingsRow>
          <SettingsRow
            label={<label htmlFor="music-genre">Thể loại truyện</label>}
            hint={
              <>
                Chưa chọn thì nhạc lấy từ mọi thể loại
                {genreName.length > 28 && <span className="mt-0.5 block sm:hidden">{genreName}</span>}
              </>
            }
          >
            <Select
              id="music-genre"
              value={overrides.genre ?? ""}
              title={genreName || "Chưa chọn"}
              onChange={(event) => change.mutate({ genre: event.target.value || null })}
              // Rộng vừa tên thể loại dài nhất ("Dị giới / kỳ ảo phương Tây (…)") - không cắt chữ; hẹp màn thì thôi ở bề ngang ô.
              className="max-w-full sm:w-auto sm:min-w-64"
            >
              <option value="">Chưa chọn</option>
              {genres.map(([value, genre]) => (
                <option key={value} value={value}>
                  {genre.vi}
                </option>
              ))}
            </Select>
          </SettingsRow>
          <SettingsRow label={<label htmlFor="music-level">Mức nhạc dưới giọng đọc</label>} hint="Nhỏ hơn giọng đọc bấy nhiêu; máy tự bù bài to hay nhỏ">
            <Select
              id="music-level"
              value={String(overrides.levelDb)}
              onChange={(event) => change.mutate({ levelDb: Number(event.target.value) })}

            >
              {LEVELS.map(([value, label]) => (
                <option key={value} value={String(value)}>
                  {levelText(value, label)}
                </option>
              ))}
            </Select>
          </SettingsRow>
          <SettingsRow label="Bài cho từng đoạn" hint="Máy chọn lại theo thể loại và mức nhạc ở trên.">
            <Button variant="ghost" icon={RefreshCw} loading={rebuild.isPending} onClick={() => rebuild.mutate()} className="-mr-3.5">
              {rebuild.isPending ? "Đang chọn lại…" : "Chọn lại nhạc"}
            </Button>
          </SettingsRow>
        </div>
        <MotionPresence className="mt-2 basis-full" open={change.isPending || rebuild.isPending}>
          <p role="status" className="text-sm text-fg-2">
            {rebuild.isPending || change.variables?.genre !== undefined ? REBUILDING : SAVING}
          </p>
        </MotionPresence>
        <MotionPresence className="basis-full" open={Boolean(data.download?.active)}>
          {data.download && <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-fg-2">
            {/* MB đổi mỗi 2 giây: trình đọc màn hình chỉ đọc mốc 25 % (soát a31 A6). */}
            <span role="status" className="min-w-0 flex-1">
              <LiveText shown={downloadText(data.download)} spoken={spokenProgress("Đang tải sẵn nhạc nền", downloadShare(data.download))} />
            </span>
            <Button size="sm" variant="ghost" icon={Square} loading={cancelDownload.isPending} onClick={() => cancelDownload.mutate()}>
              Huỷ tải
            </Button>
            <Progress value={downloadShare(data.download)} size="sm" label="Tải sẵn nhạc nền" className="basis-full" />
          </div>}
        </MotionPresence>
        {/* "Dùng lại": dòng khép tại chỗ; bỏ hết thì cả mục khép lại. */}
        <MotionPresence className="basis-full" open={overrides.banned.length > 0}>
          <details className="text-sm">
            <summary className="cursor-pointer text-fg-2">Bài đã bỏ ({overrides.banned.length})</summary>
            <div data-motion-live="">
            <AnimatedRows className="mt-2" items={overrides.banned} keyOf={(link) => link}>
              {(link) => (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pb-1">
                  <span className="min-w-0 flex-1 break-words">{trackLabel(link, data.bannedTracks?.[link] ?? plan?.tracks[link])}</span>
                  <Button size="sm" variant="ghost" disabled={change.isPending} onClick={() => change.mutate({ unban: [link] })}>
                    Dùng lại
                  </Button>
                </div>
              )}
            </AnimatedRows>
            </div>
          </details>
        </MotionPresence>
      </section>

      <Fold storageKey="studio.music.moods" title="Nhạc theo ngữ cảnh" heading="h3">
        <MoodsPanel bookId={bookId} moods={data.moods} onCompute={(view) => client.setQueryData(key, view)} />
      </Fold>

      <Fold storageKey="studio.music.local" title="Nhạc của tôi" heading="h3">
        <MyMusic bookId={bookId} previewing={preview.playing} onPreview={preview.toggle} />
      </Fold>

      {data.error && <p className="text-sm text-warning">{data.error}</p>}
      {!overrides.enabled && !!plan?.scenes.length && (
        <p className="text-sm text-fg-2">Nhạc nền đang tắt - các đoạn dưới đây sẽ không phát.</p>
      )}
      {!plan?.scenes.length ? (
        <p className="text-sm text-fg-2">Chưa có đoạn nào - nhạc nền dựng sau khi sách đã phân tích.</p>
      ) : (
        [...byChapter.entries()].map(([chapterId, scenes]) => (
          <Fold key={chapterId} storageKey={`studio.music.${bookId}.${chapterId}`} title={chapterTitle(chapterId)} summary={`${scenes.length}`} heading="h3" className={overrides.enabled ? undefined : "opacity-50"}>
            <ul className="divide-y divide-line">
              {scenes.map((scene, index) => {
                const track = scene.link ? plan.tracks[scene.link] : undefined;
                const follows = isContinuation(scene);
                const swap = swapButton(scene);
                return (
                  <li key={scene.key} className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm", follows ? "py-1.5" : "py-2.5")}>
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
                        onClick={(event) => { swapTrigger.current = event.currentTarget; setSwapping(swapping === scene.key ? null : scene.key); }}>
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
                    <div ref={swapping === scene.key ? swapBox : undefined} className="basis-full"><Collapse open={swapping === scene.key} className="py-2.5 text-sm">
                      <MotionPresence open={swapping === scene.key}>
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
                      </MotionPresence>
                    </Collapse></div>
                  </li>
                );
              })}
            </ul>
          </Fold>
        ))
      )}
      {plan && Object.keys(plan.tracks).length > 0 && (
        <details className="text-xs text-fg-2">
          <summary className="cursor-pointer">Ghi công ({Object.keys(plan.tracks).length})</summary>
          <ul className="mt-2 space-y-1">
            {Object.entries(plan.tracks).map(([link, track]) => (
              <li key={link} className="break-words">
                {track.source === "local"
                  ? `${[track.title, track.creator].filter(Boolean).join(" · ")} - nhạc của bạn, không có thông tin giấy phép`
                  : musicCreditText(track) || link}
              </li>
            ))}
          </ul>
          {Object.values(plan.tracks).some((track) => musicNeedsModifiedNote(track.license)) && <p className="mt-2">{MUSIC_MODIFIED_NOTE}</p>}
        </details>
      )}
    </MotionRegion>
  );
}
