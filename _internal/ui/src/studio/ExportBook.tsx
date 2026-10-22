import { AlertTriangle, BookAudio, CheckCircle2, FileAudio, FolderArchive, FolderDown, FolderOpen, RefreshCw } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { listenOnlyOwner } from "@/shared/peerStudio";
import { coverArtwork } from "@/shared/cover";
import { fileName, formatNumber, formatSize } from "@/shared/format";
import { spokenProgress } from "@/shared/progressSpeech";
import { Button, Dialog, LiveText, Progress, radioGroupKeys, radioTabIndex } from "@/shared/ui";
import { FfmpegNeeded } from "@/desktop/AudiobookDialog";
import { MusicMixOption, useMusicChoice } from "@/desktop/musicMix";
import { exportedOnComputer } from "@/desktop/bookFileExport";
import { startExport, trackExport } from "@/desktop/ExportBookFileJob";
import { ffmpegCancel, ffmpegStart, ffmpegStatus, type MusicExportState } from "@/desktop/listenExport";
import { api, ApiError, type BookSummary } from "./api";
import { packBookFile } from "./bookFilePacking";
import { pickFolder, useAppInfo, useParts } from "./data";
import { redoExportNote } from "./exportText";
import { BOOK_FILE_SPAN, followPackJob, PackCancelled, PackDetached, packError, packView, type PackJob } from "./projectPacking";
import { WordTimingsRow } from "./WordTimings";

// Xuất ngay trong Studio (soát UX a6 01-10, H1-H2: người làm sách phải sang Thư viện nghe mới tìm thấy "Xuất", và bản xuất
// lặng lẽ thiếu chương / bỏ qua sửa chưa áp). Hộp nói trước bản xuất sẽ có gì, rồi mới hỏi chỗ lưu.

type Kind = "mp3" | "abook" | "m4b" | "abookproj";
type ExportHistory = { kind: string; target: string; chapters: Record<string, string>; changed: number[] };
/** Truyện chia nhiều phần bằng "Làm tiếp cuốn này": xuất riêng phần đang xem hay cả bộ. */
type Scope = "part" | "series";
/** Cả bộ ra `.abook`: gộp một file (mặc định), hay mỗi phần một file. */
type Layout = "single" | "perPart";

/** Thẻ nhớ / USB định dạng FAT32 không chứa nổi file lớn hơn 4 GiB. */
const FAT32_LIMIT = 4 * 1024 ** 3;

type PartResult = { part: number; title: string };
type SeriesResult = {
  folder: string;
  parts: PartResult[];
  skipped: PartResult[];
  partsTotal: number;
  size?: number;
  /** Chỉ có khi cả bộ nằm trong MỘT file. */
  file?: string;
};

const KINDS: { value: Kind; title: string; detail: string; icon: typeof FolderDown }[] = [
  { value: "mp3", title: "Thư mục MP3", detail: "Mỗi chương một file, có tên sách, tên chương, bìa - nghe bằng mọi trình phát.", icon: FolderDown },
  { value: "abook", title: "File .abook", detail: "Cả cuốn trong một file: bìa, chữ đọc theo, nhân vật - mở bằng ABook ở máy khác.", icon: FileAudio },
  {
    // Cùng đường với mục "Xuất M4B cho app sách nói" ở menu Thư viện (desktop/ExportBookFileJob.tsx): việc nền, báo tiến độ ngoài hộp.
    value: "m4b",
    title: "Sách nói M4B",
    detail: "Cả cuốn trong một file có mục lục chương - app sách nói (Apple Books, Smart AudioBook Player...) mở là thấy đủ chương.",
    icon: BookAudio,
  },
  {
    value: "abookproj",
    title: "Cả dự án (.abookproj)",
    detail:
      "Sổ dự án, audio đã thu, nguồn chương, nhạc nền - để sao lưu hay làm tiếp ở máy khác. Mở file là có lại dự án trong Studio; điện thoại mở file này cũng nghe được các chương đã xong.",
    icon: FolderArchive,
  },
];

const SAVING: Record<Kind, [string, string, string]> = {
  mp3: ["Chọn nơi lưu bản xuất", "Đang xuất MP3…", "Không xuất được MP3"],
  abook: ["Chọn nơi lưu file sách", "Đang đóng gói sách…", "Không xuất được"],
  m4b: ["Chọn nơi lưu file M4B", "Đang làm file M4B…", "Không xuất được M4B"],
  abookproj: ["Chọn nơi lưu file dự án", "Đang đóng gói dự án…", "Không gói được dự án"],
};

/** Truy vấn chọn trạng thái tải nhạc / Huỷ của đúng kiểu xuất ở máy chủ (server.py `_music_key`); `.abook` không cần. MP3 / M4B là việc nền riêng (ExportJobHost). */
const musicKind = (kind: Kind) => (kind === "abookproj" ? "?kind=projectfile" : "");

/** Bản xuất đã xong, hiện ngay trong hộp: nói đã lưu ở đâu và cho mở thư mục (trước đây chỉ có một thông báo thoáng qua). */
type Finished = { title: string; detail: string; folder: string };

const revealFolder = (folder: string) => void api("/api/reveal-export", { method: "POST", body: { folder } });

export function ExportDialog({
  book,
  open,
  onOpenChange,
  onApplyFirst,
}: {
  book: BookSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Còn thay đổi chờ áp: đóng hộp này, mở hộp "Áp dụng N thay đổi". */
  onApplyFirst: () => void;
}) {
  const { data: info } = useAppInfo();
  const [kind, setKind] = useState<Kind>("mp3");
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useState<Scope>("part");
  const [layout, setLayout] = useState<Layout>("single");
  const [changedOnly, setChangedOnly] = useState(false);
  const history = useQuery({
    queryKey: ["export-history", book.id], enabled: open,
    queryFn: () => api<ExportHistory[]>(`/api/books/${book.id}/export-history`),
    staleTime: 0, refetchInterval: 5000,
  });
  const staleExports = (history.data ?? []).filter((item) => item.changed.length > 0);
  const changedChapters = [...new Set(staleExports.filter((item) => item.kind === "mp3").flatMap((item) => item.changed))];
  const [finished, setFinished] = useState<Finished | null>(null);
  // Đóng hộp giữa lúc đang đóng gói: việc vẫn chạy, báo bằng thông báo nổi; hộp còn mở lúc xong thì báo ngay trong hộp.
  const openRef = useRef(open);
  openRef.current = open;
  const loadingToast = useRef<string | number | null>(null);
  const parts = useParts(book.id).data?.parts ?? [];
  // Giữa lúc đóng gói .abook / .abookproj, máy có thể đang TẢI nhạc nền (vài phút): hỏi để nói bài thứ mấy và cho Huỷ.
  const packing = busy && (kind === "abook" || kind === "abookproj");
  // Gói cả dự án (.abookproj) và file sách (.abook), một cuốn hay cả bộ, là việc nền ở máy chủ: hỏi pha + đã/tổng ("chương X/N")
  // để hiện thanh tiến độ; đóng hộp hay chuyển trang thì việc vẫn chạy.
  const [packJob, setPackJob] = useState<PackJob | null>(null);
  const bookJob = useRef(false); // lượt đang chạy là file sách theo việc nền, kể cả cả bộ
  const alive = useRef(true);
  // Gỡ màn hình giữa lúc gói: việc vẫn chạy ở máy chủ - giao cho ExportJobHost (thông báo có tiến độ, Huỷ, báo khi xong) thay vì để thông báo "đang gói" của hộp treo mãi.
  const handoff = useRef<{ packing: boolean; id: string; kind: "projectfile" | "bookfile" }>({ packing: false, id: book.id, kind: "projectfile" });
  handoff.current = { packing: busy && (kind === "abookproj" || bookJob.current), id: book.id, kind: kind === "abookproj" ? "projectfile" : "bookfile" };
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (!handoff.current.packing) return;
      if (loadingToast.current !== null) toast.dismiss(loadingToast.current);
      loadingToast.current = null;
      trackExport(handoff.current.kind, handoff.current.id);
    };
  }, []);
  const musicTransfer = useQuery({
    queryKey: ["music-export", book.id, kind],
    enabled: packing,
    // `.abook` và `.abookproj` có trạng thái nhạc riêng ở máy chủ (khoá theo kiểu xuất): hỏi đúng cái của kiểu đang gói.
    queryFn: () => api<{ active: boolean; done: number; total: number }>(`/api/books/${book.id}/music-export${musicKind(kind)}`),
    refetchInterval: 1000,
    retry: false,
    gcTime: 0,
  });
  const downloading = packing && musicTransfer.data?.active && musicTransfer.data.total > 0 ? musicTransfer.data : null;
  const [cancelling, setCancelling] = useState(false);
  useEffect(() => {
    if (!busy) setCancelling(false);
  }, [busy]);
  const cancelPacking = () => {
    setCancelling(true);
    const url = `/api/books/${book.id}/${kind === "abookproj" ? "projectfile" : "bookfile"}-job/cancel`;
    void api(url, { method: "POST", body: {} }).catch(() => setCancelling(false));
  };
  /** Theo việc gói dự án của cuốn này tới khi xong; trả kết quả, hay ném `PackCancelled` / `PackDetached` (màn hình đã gỡ) / lỗi của máy chủ. */
  const followPacking = (job: "projectfile" | "bookfile" = "projectfile") =>
    followPackJob({ fetchJob: () => api<PackJob>(`/api/books/${book.id}/${job}-job`), alive: () => alive.current, onJob: setPackJob });
  const missing = book.chapters.missingAudio ?? 0;
  const ready = Math.max(0, book.chapters.completed - missing);
  const total = book.chapters.total;
  const wholeSeries = scope === "series" && parts.length > 1 && kind !== "abookproj" && kind !== "m4b"; // M4B: mỗi phần một file riêng, như menu Thư viện
  const oneFile = kind === "abook" && (!wholeSeries || layout === "single");
  // Dự án chỉ có chữ (chưa chương nào xong audio): `.abook` vẫn xuất được - gói mang chữ các chương (bookfile._add_texts); MP3 / M4B thì cần audio.
  const textOnly = kind === "abook" && !wholeSeries && !ready && total > 0;
  // Cỡ ước lượng của file .abook (audio các chương nghe được): báo trước, và cảnh báo khi vượt giới hạn FAT32.
  const estimate = useQuery({
    queryKey: ["export-size", book.id, wholeSeries],
    enabled: open && kind === "abook",
    queryFn: () => api<{ bytes: number; parts: number; musicPending?: number }>(`/api/books/${book.id}/export-size${wholeSeries ? "?series=1" : ""}`),
    staleTime: 10_000,
  });
  // "Kèm nhạc nền" (MP3 / M4B): ô chỉ hiện khi cuốn có kế hoạch nhạc, mặc định theo công tắc ở tab Nhạc nền (webui/music_export.py).
  const audioKind = kind === "mp3" || kind === "m4b";
  const musicState = useQuery({
    queryKey: ["export-music", book.id],
    enabled: open && audioKind,
    queryFn: () => api<MusicExportState>(`/api/books/${book.id}/export-music`),
    staleTime: 10_000,
  });
  const [withMusic, setWithMusic] = useMusicChoice(musicState.data, book.id);
  const mixes = audioKind && withMusic;
  // M4B cần ffmpeg (MP3 / .abook thì không - trừ MP3 kèm nhạc nền, phải mã hoá lại): máy chưa có thì mời tải ngay trong hộp, như hộp "Xuất sách nói" của Nghe ngay.
  const client = useQueryClient();
  const ffmpeg = useQuery({
    queryKey: ["ffmpeg"],
    enabled: open && (kind === "m4b" || mixes),
    queryFn: ffmpegStatus,
    staleTime: 0,
    retry: false,
    refetchInterval: (query) => (query.state.data?.downloading ? 800 : false),
  });
  const refreshFfmpeg = () => void client.invalidateQueries({ queryKey: ["ffmpeg"] });
  const needsFfmpeg = (kind === "m4b" || mixes) && ffmpeg.data !== undefined && !ffmpeg.data.ready;
  const bytes = estimate.data?.bytes ?? 0;
  const musicPending = estimate.data?.musicPending ?? 0;
  const selectedCount = kind === "mp3" && !wholeSeries && changedOnly && changedChapters.length ? changedChapters.length : ready;
  const countText = kind === "abookproj" ? undefined : wholeSeries ? `${parts.length} phần` : `${selectedCount} chương`;
  // Chỗ lưu nói trước khi bấm "Xuất": có hộp chọn thư mục của máy thì người dùng tự chọn, không thì vào thư mục "Đã xuất" của thư viện.
  const root = info?.libraryRoot ?? "";
  const computer = info?.remote ? listenOnlyOwner(info) : "";
  const savePlace = info?.dialogs
    ? "Bấm nút bên dưới rồi chọn thư mục để lưu."
    : info?.remote
      ? `Sẽ lưu vào thư mục “Đã xuất” trong thư viện của máy tính${computer && computer !== "máy tính" ? ` ${computer}` : ""} - file nằm ở máy tính, không tải về máy này.`
      : root
      ? `Sẽ lưu vào thư mục “Đã xuất” trong thư viện: ${root}${root.includes("\\") ? "\\" : "/"}Đã xuất`
      : "Sẽ lưu vào thư mục “Đã xuất” trong thư viện.";
  const handleOpenChange = (next: boolean) => {
    if (!next && busy && loadingToast.current === null) {
      loadingToast.current = toast.loading(SAVING[kind][1], { description: countText });
    }
    if (!next) setFinished(null);
    onOpenChange(next);
  };
  useEffect(() => {
    if (open && loadingToast.current !== null) {
      toast.dismiss(loadingToast.current);
      loadingToast.current = null;
    }
    if (!open) setFinished(null);
  }, [open]);
  const run = async (attach = false, chosen: Kind = kind) => {
    const kind = chosen; // "attach": mở hộp lúc máy chủ đang gói dự án - `kind` của hộp chưa kịp đổi theo
    let target = "";
    if (info?.dialogs && !attach) {
      const picked = await pickFolder(SAVING[kind][0], "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    if (kind === "m4b" || kind === "mp3") {
      // Việc nền do ExportJobHost (desktop/App.tsx) giữ: tiến độ, Huỷ và kết quả hiện ở thông báo nổi, nên đóng hộp ngay.
      const extra = { ...(mixes ? { music: true } : {}), ...(kind === "mp3" && wholeSeries ? { series: true } : {}),
        ...(kind === "mp3" && !wholeSeries && changedOnly && changedChapters.length ? { chapterIds: changedChapters } : {}) };
      startExport(kind, { id: book.id, chapters: wholeSeries ? 0 : selectedCount, target, cover: coverArtwork(book.title), ...(Object.keys(extra).length ? { extra } : {}) });
      onOpenChange(false);
      return;
    }
    bookJob.current = kind === "abook";
    setBusy(true);
    setFinished(null);
    setPackJob(null);
    try {
      type Packed = { folder: string; file: string; size: number; missingSources?: string[] } & Partial<SeriesResult>;
      const result =
        kind === "abookproj"
          ? await (attach ? Promise.resolve() : api(`/api/books/${book.id}/projectfile-job`, { method: "POST", body: { target } })).then(
              () => followPacking() as Promise<Packed>,
            )
          : await packBookFile(book.id, { target, series: wholeSeries, ...(wholeSeries ? { single: layout === "single" } : {}) },
                               () => followPacking("bookfile") as Promise<Packed>, attach);
      const lost = "missingSources" in result ? (result.missingSources?.length ?? 0) : 0;
      const skipped = result.skipped?.length ? ` · chưa có chương nào nên bỏ qua: ${result.skipped.map((part) => `Phần ${part.part}`).join(", ")}` : "";
      // `file` chỉ có khi cả bộ (hay một phần) nằm trong MỘT file; cả bộ mỗi phần một file thì có `parts` mà không có `file`.
      const single = "file" in result && typeof result.file === "string";
      const filePath = single ? String((result as { file?: string }).file) : "";
      const title = result.parts
        ? single
          ? `Đã xuất cả bộ ${result.parts.length} phần trong một file sách`
          : `Đã xuất ${result.parts.length} file sách`
        : kind === "abook"
          ? "Đã xuất file sách"
          : "Đã gói dự án";
      // Studio từ xa: máy chủ chỉ trả TÊN file / thư mục (hay không trả thư mục) - nói file nằm ở máy tính nào.
      const perPart = Boolean(result.parts && kind === "abook" && !single);
      const placeText = perPart ? `${result.folder} · mỗi phần một file .abook riêng` : single ? `${result.file} · ${formatSize(result.size ?? 0)}` : result.folder;
      const detail =
        (info?.remote
          ? exportedOnComputer(computer, perPart ? "" : single ? fileName(result.file as string) : fileName(result.folder ?? ""), [perPart ? "mỗi phần một file .abook riêng" : "", single ? formatSize(result.size ?? 0) : ""].filter(Boolean).join(" · "))
          : placeText) +
        skipped +
        (lost ? ` · ${lost} file nguồn chương đã bị dời hay xoá nên không có trong gói` : "");
      const pending = loadingToast.current;
      loadingToast.current = null;
      if (openRef.current) {
        setFinished({ title, detail, folder: result.folder });
      } else {
        toast.success(title, {
          id: pending ?? undefined,
          // Thông báo chỉ nói tên file khi cả bộ nằm trong một file; đường đầy đủ hiện khi rê chuột.
          description: filePath ? <span title={filePath}>{detail.replace(filePath, fileName(filePath))}</span> : detail,
          action: info?.remote ? undefined : { label: "Mở thư mục", onClick: () => revealFolder(result.folder) },
        });
      }
    } catch (error) {
      if (error instanceof PackDetached) return; // màn hình đã gỡ, việc vẫn chạy: ExportJobHost báo khi xong - không phải huỷ, không đụng thông báo
      const pending = loadingToast.current;
      loadingToast.current = null;
      if (error instanceof PackCancelled || (error instanceof ApiError && error.detail.reason === "cancelled")) {
        const left = `Chưa có file ${kind === "abookproj" ? "dự án" : "sách"} nào được ghi.`;
        toast.info("Đã huỷ xuất", { id: pending ?? undefined, description: left, duration: 6000 });
      } else if (kind === "abookproj") {
        const shown = packError((error as Error).message);
        toast.error(SAVING[kind][2], {
          id: pending ?? undefined,
          duration: 15000,
          description: (
            <div className="flex flex-col gap-1">
              <span>{shown.summary}</span>
              {shown.detail && (
                <details className="text-xs">
                  <summary className="cursor-pointer select-none">Chi tiết</summary>
                  <p className="mt-1 select-text break-words font-mono">{shown.detail}</p>
                </details>
              )}
            </div>
          ),
        });
      } else {
        toast.error(SAVING[kind][2], { id: pending ?? undefined, description: (error as Error).message });
      }
    } finally {
      bookJob.current = false;
      setBusy(false);
    }
  };
  // Mở hộp (hay trang dự án) khi máy chủ đang gói dự án này: theo tiếp thay vì cho bấm gói lần nữa - tiến độ hiện lại trong hộp.
  // Studio từ xa không gói dự án (chỉ máy tính làm được): không hỏi, khỏi một lời 403 ở mỗi lần mở hộp.
  useEffect(() => {
    if (book.running || info?.remote) return;
    let current = true;
    api<PackJob>(`/api/books/${book.id}/projectfile-job`)
      .then((job) => {
        if (current && job.state === "running") {
          setKind("abookproj");
          void run(true, "abookproj");
        }
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
    // Chỉ khi vào trang của cuốn này; `run` đổi theo từng lần vẽ nhưng việc theo tiếp chỉ cần một lần.
  }, [book.id]);
  const packShown = kind === "abookproj" ? packView(packJob) : busy && bookJob.current ? packView(packJob, BOOK_FILE_SPAN) : null;
  const whole = kind === "abookproj";
  const warnings = (
    whole
      ? [book.running && "Dự án đang chạy - gói khi nó đã chạy xong hoặc đã dừng."]
      : [
          textOnly && `Chưa chương nào có audio: file .abook chỉ mang chữ của ${formatNumber(total)} chương (đọc được, chưa nghe được). Có audio rồi, bạn xuất lại để file mang cả giọng đọc.`,
          !wholeSeries && !textOnly && ready < total && `${formatNumber(total - ready)}/${formatNumber(total)} chương chưa có audio${missing ? ` (${missing} chương mất file)` : ""} - không có trong bản xuất.`,
          wholeSeries && "Phần nào chưa có chương xong sẽ bị bỏ qua; phần đang chạy chỉ có các chương đã xong tới lúc này.",
          !wholeSeries && book.running && "Sách đang chạy - bản xuất chỉ gồm các chương đã xong tới lúc này.",
          !wholeSeries && redoExportNote(book.chapters.redo ?? 0, kind === "abook"),
          oneFile &&
            bytes > FAT32_LIMIT &&
            `File này sẽ lớn hơn 4 GB - thẻ nhớ hay USB định dạng FAT32 không chứa nổi.${wholeSeries ? " Chọn “Mỗi phần một file” nếu định chép vào đó." : ""}`,
        ]
  ).filter(Boolean) as string[];
  // Studio từ xa (trình duyệt máy khác) không gói dự án: file nằm ở máy tính, việc của người ngồi trước nó.
  const kinds = info?.remote ? KINDS.filter((item) => item.value !== "abookproj") : KINDS;
  const kindValues = kinds.map((item) => item.value);
  const scopeValues: Scope[] = ["part", "series"];
  const layoutValues: Layout[] = ["single", "perPart"];
  return (
    <Dialog open={open} onOpenChange={handleOpenChange} width="max-w-lg" title={`Xuất “${book.title}”`}
      description={wholeSeries ? `Các chương nghe được của cả ${parts.length} phần sẽ vào bản xuất.` : `${formatNumber(selectedCount)} chương sẽ vào bản xuất.`}>
      {busy ? (
        <div className="py-2" role="status">
          {packShown && !downloading && packShown.fraction !== null ? (
            <Progress value={packShown.fraction} size="md" label={packShown.title} />
          ) : (
            <Progress value={0} indeterminate size="md" label={SAVING[kind][1]} />
          )}
          <p className="mt-3 text-sm font-semibold">
            {cancelling
              ? "Đang huỷ…"
              : downloading
                ? <LiveText shown={`Đang tải nhạc nền (${downloading.done}/${downloading.total})…`} spoken={spokenProgress("Đang tải nhạc nền", downloading.done / downloading.total)} />
                : (packShown?.title ?? SAVING[kind][1])}
          </p>
          <p className="mt-1 text-sm text-fg-2 text-pretty">
            {downloading
              ? "Nhạc nền chưa có trên máy nên phải tải về để đóng kèm vào file - bài nào xong rồi lần sau không phải tải lại. "
              : countText
                ? `${countText}. `
                : ""}
            Sách dài thì có thể mất vài phút. Đóng hộp này cũng được - việc vẫn chạy và báo khi xong.
          </p>
          <div className="mt-5 dialog-actions">
            {packing && (
              <Button variant="secondary" disabled={cancelling} onClick={cancelPacking}>
                Huỷ xuất
              </Button>
            )}
            <Button variant="ghost" onClick={() => handleOpenChange(false)}>
              Đóng, cứ để chạy
            </Button>
          </div>
        </div>
      ) : finished ? (
        <div className="py-2">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <CheckCircle2 className="size-4 shrink-0 text-success" />
            {finished.title}
          </p>
          <p className="mt-2 break-all rounded-xl bg-sunken p-3 text-sm text-fg-2">{finished.detail}</p>
          <div className="mt-5 dialog-actions">
            {!info?.remote && (
              <Button variant="secondary" icon={FolderOpen} onClick={() => revealFolder(finished.folder)}>
                Mở thư mục
              </Button>
            )}
            <Button variant="primary" onClick={() => handleOpenChange(false)}>
              Xong
            </Button>
          </div>
        </div>
      ) : (
      <>
      {parts.length > 1 && !whole && kind !== "m4b" && (
        <div
          className="mb-3 grid grid-cols-2 gap-1 rounded-xl bg-sunken p-1 text-sm"
          role="radiogroup"
          aria-label="Phạm vi bản xuất"
          onKeyDown={radioGroupKeys(scopeValues, scope, setScope)}
        >
          {(
            [
              ["part", "Phần này"],
              ["series", `Cả bộ (${parts.length} phần)`],
            ] as const
          ).map(([value, label], index) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={scope === value}
              tabIndex={radioTabIndex(scopeValues, scope, index)}
              onClick={() => setScope(value)}
              className={cn("rounded-lg px-3 py-1.5 font-medium", scope === value ? "bg-panel shadow-sm" : "text-fg-2")}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="grid gap-2" role="radiogroup" aria-label="Kiểu bản xuất" onKeyDown={radioGroupKeys(kindValues, kind, setKind)}>
        {kinds.map(({ value, title, detail, icon: Icon }, index) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={kind === value}
            tabIndex={radioTabIndex(kindValues, kind, index)}
            onClick={() => setKind(value)}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-3 text-left text-sm",
              kind === value ? "border-focus bg-accent-soft" : "border-line hover:bg-hover",
            )}
          >
            <Icon className="mt-0.5 size-4 shrink-0 text-accent-text" />
            <span className="min-w-0">
              <span className="block font-semibold">{title}</span>
              <span className="block text-fg-2">{detail}</span>
            </span>
          </button>
        ))}
      </div>
      {wholeSeries && kind === "abook" && (
        <>
          <div
            className="mt-3 grid grid-cols-2 gap-1 rounded-xl bg-sunken p-1 text-sm"
            role="radiogroup"
            aria-label="Cách chia file"
            onKeyDown={radioGroupKeys(layoutValues, layout, setLayout)}
          >
            {(
              [
                ["single", "Một file"],
                ["perPart", "Mỗi phần một file"],
              ] as const
            ).map(([value, label], index) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={layout === value}
                tabIndex={radioTabIndex(layoutValues, layout, index)}
                onClick={() => setLayout(value)}
                className={cn("rounded-lg px-3 py-1.5 font-medium", layout === value ? "bg-panel shadow-sm" : "text-fg-2")}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-sm text-fg-2 text-pretty">
            {layout === "single"
              ? "Cả bộ trong một file .abook: nghe liền từ phần này sang phần khác, chỉ cần chép một file sang máy khác."
              : "Mỗi phần là một file .abook riêng, cùng nằm trong một thư mục của bộ."}
          </p>
        </>
      )}
      {audioKind && musicState.data?.available && (
        <div className="mt-3">
          <MusicMixOption checked={withMusic} onChange={setWithMusic} />
        </div>
      )}
      <p className="mt-3 text-sm text-fg-2 text-pretty">{savePlace}</p>
      {kind === "abook" && bytes > 0 && (
        <p className="mt-2 text-sm text-fg-2">
          Cỡ ước tính: khoảng {formatSize(bytes)}.
          {musicPending > 0 && ` Còn ${musicPending} bài nhạc nền chưa tải về máy - khi xuất sẽ tải và cộng thêm.`}
        </p>
      )}
      {needsFfmpeg && ffmpeg.data && (
        <div className="mt-3">
          <FfmpegNeeded
            status={ffmpeg.data}
            remote={Boolean(info?.remote)}
            onDownload={() => void ffmpegStart().then(refreshFfmpeg, (error: Error) => toast.error("Chưa tải được công cụ", { description: error.message }))}
            onStop={() => void ffmpegCancel().then(refreshFfmpeg, () => undefined)}
          />
        </div>
      )}
      {kind === "abook" &&
        (info?.remote ? (
          <p className="mt-3">
            <OnComputerOnly verb="Thêm chữ sáng theo giọng đọc" />
          </p>
        ) : (
          <WordTimingsRow bookId={book.id} running={Boolean(book.running)} />
        ))}
      {wholeSeries && kind === "mp3" && (
        <p className="mt-3 text-sm text-fg-2 text-pretty">Mỗi phần một thư mục con (“Phần 1 - …”, “Phần 2 - …”), cùng nằm trong một thư mục của bộ.</p>
      )}
      {staleExports.length > 0 && <div className="mt-3 space-y-2 rounded-xl bg-warning-soft p-3 text-sm">
        <p className="font-semibold">Bạn có bản xuất đã cũ sau khi sửa và thu lại:</p>
        {staleExports.map((item) => <div key={item.target}>
          <p className="break-all">{item.target} · {item.changed.length} chương đã đổi</p>
          <Button size="sm" variant="secondary" onClick={() => { setKind(item.kind as Kind); setScope("part"); setChangedOnly(item.kind === "mp3"); }}>Xuất lại {item.kind === "m4b" ? "cả file M4B" : item.kind === "mp3" ? "các chương đã đổi" : "file sách"}</Button>
          {item.kind === "m4b" && <p>M4B gộp cả cuốn: bạn cần dựng lại cả file và thay bản đã chép hoặc gửi.</p>}
        </div>)}
      </div>}
      {kind === "mp3" && !wholeSeries && changedChapters.length > 0 && <label className="mt-3 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={changedOnly} onChange={(event) => setChangedOnly(event.target.checked)} />
        Chỉ xuất {changedChapters.length} chương đã đổi (giữ số chương trong sách)
      </label>}
      {(warnings.length > 0 || (!whole && Boolean(book.pendingChanges))) && (
        <div className="mt-3 space-y-1.5 rounded-xl bg-warning-soft p-3 text-sm">
          {warnings.map((line) => (
            <p key={line} className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
              <span className="text-pretty">{line}</span>
            </p>
          ))}
          {!whole && Boolean(book.pendingChanges) && (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
              <AlertTriangle className="size-4 shrink-0 text-warning" />
              <span className="min-w-0 flex-1 text-pretty">
                Còn {book.pendingChanges} thay đổi chưa áp - bản xuất đọc như TRƯỚC khi sửa.
              </span>
              <Button size="sm" variant="secondary" icon={RefreshCw} onClick={() => { onOpenChange(false); onApplyFirst(); }}>
                Áp dụng trước
              </Button>
            </div>
          )}
        </div>
      )}
      <div className="mt-5 dialog-actions">
        <Button variant="ghost" onClick={() => handleOpenChange(false)}>
          Thôi
        </Button>
        <Button
          variant="primary"
          icon={KINDS.find((item) => item.value === kind)?.icon ?? FolderDown}
          loading={busy}
          disabled={whole ? Boolean(book.running) : needsFfmpeg || (!wholeSeries && !ready && !textOnly)}
          onClick={() => void run()}
        >
          {info?.dialogs ? "Chọn nơi lưu và xuất" : "Xuất"}
        </Button>
      </div>
      </>
      )}
    </Dialog>
  );
}
