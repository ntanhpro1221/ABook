import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { SectionHeading } from "@/shared/SectionHeading";
import { useBackLayer } from "@/shared/backStack";
import { SettingsRow } from "@/shared/SettingsNav";
import { Switch } from "@/desktop/Switch";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { Fold, Collapse } from "@/shared/Collapse";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as DropdownMenu from "@/shared/DropdownMenu";
import { Ban, Download, EighthNote, MoreHorizontal, Pin, PinOff, Play, RefreshCw, Shuffle, Square, VolumeX } from "lucide-react";
import { toast } from "@/shared/toast";
import { MUSIC_CHANGED_EVENT } from "@/listen/musicBed";
import { cn } from "@/shared/cn";
import { MUSIC_MODIFIED_NOTE, formatClock, musicCreditText, musicNeedsModifiedNote } from "@/shared/format";
import { spokenProgress } from "@/shared/progressSpeech";
import { MusicLevelSlider } from "@/shared/MusicLevelSlider";
import { LEVEL_TITLE } from "@/shared/musicLevels";
import { Select, Button, IconButton, LiveText, Progress, ContentSkeleton, InlineError } from "@/shared/ui";
import { api, mediaUrl } from "./api";
import { useAppInfo } from "./data";
import { CONTINUED_NOTE, downloadShare, downloadText, isContinuation, moodOf, swapButton, type MusicDownload } from "./musicScenes";
import { mineNote, previewPath } from "./musicLocal";
import { BrowseLibraryLink } from "@/music/BrowseLibraryLink";
import { OpenMusicRow } from "@/music/OpenMusicRow";

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

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-control px-2 text-sm outline-none data-[highlighted]:bg-hover";

/** "Chọn lại nhạc" (và đổi thể loại) dựng lại nhạc cả cuốn - sách 43 chương mất cỡ nửa phút: nói ra để các nút mờ không có vẻ như bị treo. */
const REBUILDING = S.s_dang_chon_lai_nhac_co_nua_phut_4166612f;
/** Sửa một đoạn (chọn bài, ghim, im lặng, bỏ bài) chỉ mất chốc lát: chỉ báo bận nhẹ, không hứa nửa phút. */
const SAVING = S.s_dang_luu_lua_chon_d37252de;

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
        <EighthNote className="mr-2 inline size-4 text-fg-2" />
        {item.title || S.s_bai_nhac_5d07657e}
        {item.creator && <span className="text-fg-2"> · {item.creator}</span>}
        {item.duration ? <span className="text-fg-2"> · {formatClock(item.duration)}</span> : null}
        {note && <span className="block text-xs text-fg-2">{note}</span>}
      </span>
      <span className="flex shrink-0 gap-1">
        {canPreview && (
          <Button size="sm" variant="ghost" icon={previewing === item.link ? Square : Play} aria-pressed={previewing === item.link}
            onClick={() => onPreview(item.link)}>
            {previewing === item.link ? S.s_dung_nghe_f20939be : S.s_nghe_thu_fa024065}
          </Button>
        )}
        <Button size="sm" variant="ghost" icon={Pin} disabled={busy} loading={choosing === item.link}
          onClick={() => onChoose(item.link)}>
          {choosing === item.link ? S.s_dang_doi_b4190199 : S.s_chon_1171ca97}
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
  if (isLoading) return <MotionRegion fadeThrough><ContentSkeleton label={S.s_dang_tai_bai_khac_2c0e1ec8} /></MotionRegion>;
  if (error && !data) return <MotionRegion fadeThrough><InlineError message={S.s_ban_hay_kiem_tra_ket_noi_roi_tim_lai_bai_n_acc346b4} onRetry={() => void refetch()} /></MotionRegion>;
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
        <p className="text-fg-2">{S.s_khong_con_bai_nao_khac_trong_danh_muc_du_h_970fe053}</p>
      )}
      <div>
        <SectionHeading as="h4">{S.s_nhac_cua_toi_f65b7ac6}</SectionHeading>
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
              ? S.s_chua_co_bai_nao_them_nhac_cua_ban_tren_may_0f4b6b30
              : S.s_chua_co_bai_nao_them_nhac_cua_ban_o_man_nh_abedf8f3}
          </p>
        )}
      </div>
      {/* Cuối danh sách gợi ý: cả kho nhạc ở chế độ chọn cho đúng đoạn này ("Dùng" ghim bài như "Chọn" ở trên). */}
      {!info?.remote && (
        <BrowseLibraryLink bookId={bookId} scene={sceneKey} />
      )}
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
    onError: (error: Error) => toast.error(S.s_chua_tai_duoc_phan_doc_khong_khi_583857f2, { description: error.message }),
  });
  const compute = useMutation({
    mutationFn: () => api<MusicView>(`/api/books/${bookId}/music/moods`, { method: "POST" }),
    onSuccess: onCompute,
    onError: (error: Error) => toast.error(S.s_chua_doc_lai_duoc_khong_khi_cac_doan_b14d92fd, { description: error.message }),
  });
  if (!data) return <MotionRegion />;
  const running = Boolean(moods?.running) || compute.isPending;
  const percent = data.progress && data.progress.total > 0 ? Math.round((data.progress.done * 100) / data.progress.total) : null;
  return (
    <MotionRegion as="section" className="space-y-2">
      <p className="text-sm text-fg-2 text-pretty">{S.s_hieu_ngu_canh_de_chon_nhac_1_phut_moi_gio_1ed08581}</p>
      {data.installed ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" variant="ghost" icon={RefreshCw} loading={running} onClick={() => compute.mutate()}>
            {running ? S.s_dang_doc_khong_khi_0640731b : S.s_doc_lai_ngu_canh_edb18d3a}
          </Button>
          {moods?.error && <span className="text-sm text-warning">{moods.error}</span>}
        </div>
      ) : data.downloading ? (
        <p data-motion-live className="text-sm">{S.s_dang_tai_phan_doc_khong_khi_a6481b11}{percent !== null ? ` - ${percent}%` : ""}</p>
      ) : data.downloadable && !info?.remote ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" variant="ghost" icon={Download} loading={download.isPending} onClick={() => download.mutate()}>{S.s_tai_them_3_2_gb_338f648d}</Button>
          {data.error && <span className="text-sm text-warning">{data.error}</span>}
        </div>
      ) : (
        <p className="text-sm text-fg-2">
          {data.downloadable ? S.s_tai_phan_doc_khong_khi_tren_may_tinh_chu_s_f52208a6 : S.s_may_nay_chua_co_phan_doc_khong_khi_cai_qua_5174e4ee}
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
        <IconButton label={S.s_them_tuy_chon_a0b4bb6e} icon={MoreHorizontal} size="sm" disabled={disabled} className="data-[state=open]:bg-hover" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={4} collisionPadding={12} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-56 rounded-cover border border-line bg-panel p-2 shadow-float">
          <DropdownMenu.Item onSelect={onSilence} className={MENU_ITEM}>
            <VolumeX className="size-4" /> {scene.silenced ? S.s_bat_nhac_doan_nay_57d716ef : S.s_tat_nhac_doan_nay_8fb1136b}
          </DropdownMenu.Item>
          {scene.pinned && (
            <DropdownMenu.Item onSelect={onUnpin} className={MENU_ITEM}>
              <PinOff className="size-4" />{S.s_bo_ghim_034b5c81}</DropdownMenu.Item>
          )}
          {onBan && (
            <>
              <DropdownMenu.Separator className="my-1 h-px bg-line" />
              <DropdownMenu.Item onSelect={onBan} className={cn(MENU_ITEM, "text-danger")}>
                <Ban className="size-4" />{S.s_loai_khoi_cuon_2426f728}</DropdownMenu.Item>
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
      if (data?.moods?.error) toast.error(S.s_khong_doc_xong_khong_khi_cac_doan_f279af25, { description: data.moods.error });
      else toast(S.s_da_doc_xong_khong_khi_cac_doan_nhac_da_cho_487aac39);
    }
    moodsRunning.current = running;
  }, [bookId, data?.moods?.running, data?.moods?.error]);
  // Lượt tải sẵn vừa dừng vì mất mạng (máy chủ giữ nhạc cũ và ghi lý do vào `error`): báo ngay, không để dòng chữ cuối trang nằm im.
  const downloading = useRef(false);
  useEffect(() => {
    const active = Boolean(data?.download?.active);
    if (downloading.current && !active && data?.error) toast.warning(S.s_chua_tai_duoc_nhac_e5f3ccb5, { description: data.error });
    downloading.current = active;
  }, [data?.download?.active, data?.error]);
  const change = useMutation({
    scope: { id: `book-music:${bookId}` },
    mutationFn: (body: Record<string, unknown>) => api<MusicView>(`/api/books/${bookId}/music`, { method: "PUT", body }),
    onSuccess: (result) => {
      client.setQueryData(key, result);
      setSwapping(null);
      announceChange(bookId);
      refreshSoon();
      if (result.error) toast.warning(S.s_da_luu_lua_chon_3dbba0c5, { description: result.error });
    },
    onError: (error: Error) => toast.error(S.s_chua_doi_duoc_nhac_nen_b5d19c42, { description: error.message }),
  });
  const cancelDownload = useMutation({
    mutationFn: () => api<MusicView>(`/api/books/${bookId}/music/download/cancel`, { method: "POST" }),
    onSuccess: (result) => {
      // Máy chủ dừng ở khúc kế (một phần giây): ẩn dòng tiến độ ngay thay vì đợi lần hỏi sau.
      client.setQueryData(key, { ...result, download: undefined });
      toast(S.s_da_dung_tai_nhac_nen_6addc23d);
    },
    onError: (error: Error) => toast.error(S.s_chua_dung_duoc_viec_tai_nhac_76d30d55, { description: error.message }),
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
    onError: (error: Error) => toast.error(S.s_chua_chon_lai_duoc_nhac_f442d032, { description: error.message }),
  });

  /** Bỏ một bài cho cả cuốn: lặng lẽ thì khó hiểu vì sao các đoạn khác cũng đổi bài, nên báo (kèm số đoạn đang dùng bài
   *  ấy, đếm trước khi đổi) và cho "Hoàn tác". */
  const ban = (link: string, label: string) => {
    const used = (data?.plan?.scenes ?? []).filter((scene) => scene.link === link).length;
    change.mutate(
      { ban: [link] },
      {
        onSuccess: () =>
          toast(S.s_da_bo_0_cho_ca_cuon_dang_dung_o_1_doan_388eec18(label, used), {
            action: { label: S.s_hoan_tac_e72ff675, onClick: () => change.mutate({ unban: [link] }) },
          }),
      },
    );
  };

  // Lần đầu (danh mục chưa có trên máy) mất cỡ 10 giây - bài nhạc tải sau ở nền, không chờ ở đây (soát UX a60: từng mất 2,7 phút).
  if (error && !data) return <MotionRegion fadeThrough><InlineError className="mt-6" message={S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_nhac_9a91e125} onRetry={() => void refetch()} /></MotionRegion>;
  if (isLoading || !data) return <MotionRegion fadeThrough><ContentSkeleton shape="cards" label={S.s_dang_tai_nhac_nen_0b8c4795} className="mt-6" /></MotionRegion>;
  const { plan, overrides, taxonomy } = data;
  const genres = Object.entries(taxonomy.genres ?? {});
  // Màn hẹp: ô chọn không đủ rộng cho tên thể loại dài ("Dị giới / kỳ ảo phương Tây (…)") nên chữ bị cắt - ghi đủ tên bên dưới.
  const genreName = genres.find(([value]) => value === overrides.genre)?.[1].vi ?? "";
  const byChapter = new Map<number, Scene[]>();
  for (const scene of plan?.scenes ?? []) byChapter.set(scene.chapterId, [...(byChapter.get(scene.chapterId) ?? []), scene]);
  // Bài đang được đổi sang (nút "Chọn" của nó hiện "Đang đổi").
  const pending = change.isPending ? (change.variables?.pins as Record<string, string | null> | undefined) : undefined;
  const choosing = Object.values(pending ?? {}).find((link): link is string => !!link) ?? null;

  return (
    <MotionRegion as="div" className="mt-6 space-y-6">
      {/* Cài đặt nhạc của cuốn: một hàng một việc, công tắc / ô chọn bên phải như trang Cài đặt - không khung bao (DESIGN 4, 6). */}
      <section className="flex flex-wrap items-end gap-x-4">
        <div className="basis-full divide-y divide-line">
          <SettingsRow label={<span id="music-enabled-name">{S.s_nhac_nen_271fb292}</span>} hint={<span id="music-enabled-hint">{overrides.enabled ? S.s_dang_bat_cho_cuon_nay_6752e54b : S.s_dang_tat_cac_doan_duoi_day_se_khong_phat_e93d8c97}</span>}>
            <Switch id="music-enabled" labelledBy="music-enabled-name" describedBy="music-enabled-hint" checked={overrides.enabled} disabled={change.isPending} onCheckedChange={(enabled) => change.mutate({ enabled })} />
          </SettingsRow>
          <SettingsRow
            label={<label htmlFor="music-genre">{S.s_the_loai_truyen_9c821aa0}</label>}
            hint={
              <>{S.s_chua_chon_thi_nhac_lay_tu_moi_the_loai_a144c9d2}{genreName.length > 28 && <span className="mt-1 block sm:hidden">{genreName}</span>}
              </>
            }
          >
            <Select
              id="music-genre"
              value={overrides.genre ?? ""}
              title={genreName || S.s_chua_chon_e5f50074}
              onChange={(event) => change.mutate({ genre: event.target.value || null })}
              // Rộng vừa tên thể loại dài nhất ("Dị giới / kỳ ảo phương Tây (…)") - không cắt chữ; hẹp màn thì thôi ở bề ngang ô.
              className="max-w-full sm:w-auto sm:min-w-64"
            >
              <option value="">{S.s_chua_chon_e5f50074}</option>
              {genres.map(([value, genre]) => (
                <option key={value} value={value}>
                  {genre.vi}
                </option>
              ))}
            </Select>
          </SettingsRow>
          {/* Thanh trượt nằm dưới tên hàng, không bên phải: chữ mức của nó không đứng cạnh tên hàng (hai dòng chữ cạnh nhau phải cùng đường chân chữ). */}
          <div>
            <SettingsRow label={LEVEL_TITLE} hint={S.s_nho_hon_giong_doc_bay_nhieu_may_tu_bu_bai_e1b269b4} />
            <MusicLevelSlider value={overrides.levelDb} saving={change.isPending} onChange={(levelDb) => change.mutate({ levelDb })} className="max-w-md pb-2" />
          </div>
          <SettingsRow label={S.s_bai_cho_tung_doan_f2d49b48} hint={S.s_may_chon_lai_theo_the_loai_va_muc_nhac_o_t_927c2f67}>
            <Button variant="ghost" icon={RefreshCw} loading={rebuild.isPending} onClick={() => rebuild.mutate()} className="-mr-4">
              {rebuild.isPending ? S.s_dang_chon_lai_16e4af51 : S.s_chon_lai_nhac_ebe26dde}
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
              <LiveText shown={downloadText(data.download)} spoken={spokenProgress(S.s_dang_tai_san_nhac_nen_3d38ca5b, downloadShare(data.download))} />
            </span>
            <Button size="sm" variant="ghost" icon={Square} loading={cancelDownload.isPending} onClick={() => cancelDownload.mutate()}>{S.s_huy_tai_1a9ff73d}</Button>
            <Progress value={downloadShare(data.download)} indeterminate={!data.download.totalBytes && !data.download.total} size="sm" label={S.s_tai_san_nhac_nen_4474e87f} className="basis-full" />
          </div>}
        </MotionPresence>
        {/* "Dùng lại": dòng khép tại chỗ; bỏ hết thì cả mục khép lại. */}
        <MotionPresence className="basis-full" open={overrides.banned.length > 0}>
          <details className="text-sm">
            <summary className="cursor-pointer text-fg-2">{S.s_bai_da_bo_4d06ea6e}{overrides.banned.length})</summary>
            <div data-motion-live="">
            <AnimatedRows className="mt-2" items={overrides.banned} keyOf={(link) => link}>
              {(link) => (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pb-1">
                  <span className="min-w-0 flex-1 break-words">{trackLabel(link, data.bannedTracks?.[link] ?? plan?.tracks[link])}</span>
                  <Button size="sm" variant="ghost" disabled={change.isPending} onClick={() => change.mutate({ unban: [link] })}>{S.s_dung_lai_01a1973f}</Button>
                </div>
              )}
            </AnimatedRows>
            </div>
          </details>
        </MotionPresence>
      </section>

      <Fold storageKey="studio.music.moods" title={S.s_nhac_theo_ngu_canh_566500d8} heading="h3">
        <MoodsPanel bookId={bookId} moods={data.moods} onCompute={(view) => client.setQueryData(key, view)} />
      </Fold>

      <OpenMusicRow />

      {data.error && <p className="text-sm text-warning">{data.error}</p>}
      {!overrides.enabled && !!plan?.scenes.length && (
        <p className="text-sm text-fg-2">{S.s_nhac_nen_dang_tat_cac_doan_duoi_day_se_kho_2cc431ba}</p>
      )}
      {!plan?.scenes.length ? (
        <p className="text-sm text-fg-2">{S.s_chua_co_doan_nao_nhac_nen_dung_sau_khi_sac_b1bdaf8e}</p>
      ) : (
        [...byChapter.entries()].map(([chapterId, scenes]) => (
          <Fold key={chapterId} storageKey={`studio.music.${bookId}.${chapterId}`} title={chapterTitle(chapterId)} summary={S.s_0_doan_c2eb5200(scenes.length)} heading="h3" className={overrides.enabled ? undefined : "opacity-50"}>
            <ul className="divide-y divide-line">
              {scenes.map((scene, index) => {
                const track = scene.link ? plan.tracks[scene.link] : undefined;
                const follows = isContinuation(scene);
                const swap = swapButton(scene);
                return (
                  <li key={scene.key} className={cn("flex flex-wrap items-center gap-x-4 gap-y-2 text-sm", follows ? "py-2" : "py-3")}>
                    <span className="tabular-cell w-28 shrink-0 text-fg-2">
                      {/* Các đoạn nối liền: đoạn này hết ở đúng chỗ đoạn sau bắt đầu (cùng cách làm tròn). */}
                      {formatClock(scene.start)}–{formatClock(scenes[index + 1]?.start ?? scene.end)}
                    </span>
                    <span className="w-32 shrink-0">
                      {moodOf(scene, taxonomy.emotions)}
                      {(scene.moodSource === "llm" || scene.moodSource === "chapter" || scene.moodSource === "student") && (
                        <span
                          className="ml-2 rounded-control bg-sunken px-1 py-1 text-xs text-fg-2"
                          title={
                            scene.moodSource === "student"
                              ? S.s_ai_da_doan_doan_nay_vui_hon_hay_buon_hon_c_e68274f5
                              : scene.moodSource === "chapter"
                                ? S.s_ai_da_doc_ca_doan_nay_de_cham_khong_khi_ro_e5ef84d5
                                : S.s_ai_da_doc_ca_doan_nay_de_cham_khong_khi_61bd9b9d
                          }
                        >{S.s_ai_11fb682b}</span>
                      )}
                    </span>
                    <span className="min-w-0 basis-full break-words sm:flex-1 sm:basis-0">
                      {follows ? (
                        <span className="text-fg-2">{CONTINUED_NOTE}</span>
                      ) : scene.link ? (
                        <>
                          <EighthNote className="mr-2 inline size-4 text-accent-text" />
                          {track?.title ?? S.s_bai_nhac_5d07657e}
                          {track?.creator && <span className="text-fg-2"> · {track.creator}</span>}
                          {track?.source === "local" && (
                            <span className="ml-2 rounded-control bg-sunken px-2 py-1 text-xs text-fg-2">{S.s_nhac_cua_toi_f65b7ac6}</span>
                          )}
                          {scene.pinned && <Pin className="ml-2 inline size-3.5 text-fg-2" aria-label={S.s_da_ghim_f1645be7} />}
                          {scene.pinUnavailable && (
                            <span className="block text-xs text-warning">{S.s_bai_ban_ghim_khong_con_tren_may_nay_doan_d_09b8894e}</span>
                          )}
                        </>
                      ) : (
                        <span className="text-fg-2">{scene.silenced ? S.s_im_lang_ban_chon_356a628b : S.s_im_lang_khong_bai_nao_du_hop_6881c83f}</span>
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
                    <div ref={swapping === scene.key ? swapBox : undefined} className="basis-full"><Collapse open={swapping === scene.key} className="py-3 text-sm">
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
          <summary className="cursor-pointer">{S.s_ghi_cong_153d3665}{Object.keys(plan.tracks).length})</summary>
          <ul className="mt-2 space-y-1">
            {Object.entries(plan.tracks).map(([link, track]) => (
              <li key={link} className="break-words">
                {track.source === "local"
                  ? S.s_0_nhac_cua_ban_khong_co_thong_tin_giay_phe_71454f92([track.title, track.creator].filter(Boolean).join(" · "))
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
