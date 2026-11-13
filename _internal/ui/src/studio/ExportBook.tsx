import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence, Reveal } from "@/shared/MotionPresence";
import { SlidingIndicator } from "@/shared/SlidingIndicator";
import { useMotionState } from "@/shared/motion";
import { AlertTriangle, BookAudio, CheckCircle2, FileAudio, FolderArchive, FolderDown, FolderOpen, RefreshCw } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast, toastDone } from "@/shared/toast";
import { cn } from "@/shared/cn";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { listenOnlyOwner } from "@/shared/peerStudio";
import { coverArtwork } from "@/shared/cover";
import { fileName, formatNumber, formatSize } from "@/shared/format";
import { spokenProgress } from "@/shared/progressSpeech";
import { DialogActions, Button, Dialog, LiveText, Progress, radioGroupKeys, radioTabIndex } from "@/shared/ui";
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
  { value: "mp3", title: S.s_thu_muc_mp3_2eea06d7, detail: S.s_moi_chuong_mot_file_co_ten_va_bia_97cf9d56, icon: FolderDown },
  { value: "abook", title: S.s_copy_af47db37cfcc, detail: S.s_mot_file_chua_ca_sach_mo_bang_abook_c88beb23, icon: FileAudio },
  {
    // Cùng đường với mục "Xuất M4B cho app sách nói" ở menu Thư viện (desktop/ExportBookFileJob.tsx): việc nền, báo tiến độ ngoài hộp.
    value: "m4b",
    title: S.s_sach_noi_m4b_01d29e1d,
    detail: S.s_mot_file_co_muc_luc_chuong_cho_app_sach_no_a73ffb74,
    icon: BookAudio,
  },
  {
    value: "abookproj",
    title: S.s_ca_du_an_abookproj_ff1824d8,
    detail:
      S.s_ca_du_an_va_audio_de_sao_luu_hay_lam_tiep_e5b95d4c,
    icon: FolderArchive,
  },
];

const SAVING: Record<Kind, [string, string, string]> = {
  mp3: [S.s_chon_noi_luu_2965936c, S.s_dang_xuat_mp3_1f5f6554, S.s_chua_xuat_duoc_mp3_1550e65a],
  abook: [S.s_chon_noi_luu_2965936c, S.s_dang_dong_goi_sach_c372ab53, S.s_chua_xuat_duoc_file_sach_43236ec7],
  m4b: [S.s_chon_noi_luu_2965936c, S.s_dang_lam_file_m4b_01a34d3b, S.s_chua_xuat_duoc_m4b_5a39de4c],
  abookproj: [S.s_chon_noi_luu_2965936c, S.s_dang_dong_goi_du_an_59bb0a50, S.s_chua_goi_duoc_du_an_fd3612d5],
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
  const [kind, setKind] = useMotionState<Kind>("mp3");
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useMotionState<Scope>("part");
  const [layout, setLayout] = useMotionState<Layout>("single");
  const [changedOnly, setChangedOnly] = useState(false);
  const [partial, setPartial] = useState(false);
  useEffect(() => setPartial(false), [book.id, open]);
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
  const countText = kind === "abookproj" ? undefined : wholeSeries ? S.s_0_phan_40e8af8c(parts.length) : S.s_0_chuong_04093412(selectedCount);
  // Chỗ lưu nói trước khi bấm "Xuất": có hộp chọn thư mục của máy thì người dùng tự chọn, không thì vào thư mục "Đã xuất" của thư viện.
  const root = info?.libraryRoot ?? "";
  const computer = info?.remote ? listenOnlyOwner(info) : "";
  const savePlace = info?.dialogs
    ? S.s_bam_nut_ben_duoi_roi_chon_thu_muc_de_luu_e266290b
    : info?.remote
      ? S.s_se_luu_vao_thu_muc_da_xuat_trong_thu_vien_fb4d5397(computer && computer !== S.s_may_tinh_8eafc226 ? ` ${computer}` : "")
      : root
      ? S.s_se_luu_vao_thu_muc_da_xuat_trong_thu_vien_d0a73045(root, root.includes("\\") ? "\\" : "/")
      : S.s_se_luu_vao_thu_muc_da_xuat_trong_thu_vien_a78ada3d;
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
      type Packed = { folder: string; file: string; size: number; missingSources?: string[]; coverage?: string } & Partial<SeriesResult>;
      const result =
        kind === "abookproj"
          ? await (attach ? Promise.resolve() : api(`/api/books/${book.id}/projectfile-job`, { method: "POST", body: { target } })).then(
              () => followPacking() as Promise<Packed>,
            )
          : await packBookFile(book.id, { target, series: wholeSeries, partial, ...(wholeSeries ? { single: layout === "single" } : {}) },
                               () => followPacking("bookfile") as Promise<Packed>, attach);
      const lost = "missingSources" in result ? (result.missingSources?.length ?? 0) : 0;
      const skippedNote = result.skipped?.length ? S.s_chua_co_chuong_nao_nen_bo_qua_0_56da88e7(result.skipped.map((part) => S.s_phan_0_7c77642d(part.part)).join(", ")) : "";
      const skipped = skippedNote ? ` · ${skippedNote}` : "";
      const lostNote = lost ? S.s_0_file_nguon_chuong_da_bi_doi_hay_xoa_nen_a83aaefb(lost) : "";
      // `file` chỉ có khi cả bộ (hay một phần) nằm trong MỘT file; cả bộ mỗi phần một file thì có `parts` mà không có `file`.
      const single = "file" in result && typeof result.file === "string";
      const title = result.parts
        ? single
          ? S.s_da_xuat_ca_bo_0_phan_trong_mot_file_sach_720c8181(result.parts.length)
          : S.s_da_xuat_0_file_sach_9d6f2abd(result.parts.length)
        : kind === "abook"
          ? S.s_da_xuat_file_sach_242afa05
          : S.s_da_goi_du_an_9908b445;
      // Studio từ xa: máy chủ chỉ trả TÊN file / thư mục (hay không trả thư mục) - nói file nằm ở máy tính nào.
      const perPart = Boolean(result.parts && kind === "abook" && !single);
      const placeText = perPart ? S.s_0_moi_phan_mot_file_abook_rieng_d57434af(result.folder) : single ? `${result.file} · ${formatSize(result.size ?? 0)}` : result.folder;
      const detail =
        (info?.remote
          ? exportedOnComputer(computer, perPart ? "" : single ? fileName(result.file as string) : fileName(result.folder ?? ""), [perPart ? S.s_moi_phan_mot_file_abook_rieng_e768e635 : "", single ? formatSize(result.size ?? 0) : ""].filter(Boolean).join(" · "))
          : placeText) +
        skipped +
        (lostNote ? ` · ${lostNote}` : "") + (result.coverage ? ` · ${result.coverage}` : "");
      const pending = loadingToast.current;
      loadingToast.current = null;
      if (openRef.current) {
        setFinished({ title, detail, folder: result.folder });
      } else {
        // MỘT dòng + nút “Mở thư mục” (chỗ file nằm); thiếu gì (phần bỏ qua, nguồn chương) thì cảnh báo với đúng phần thiếu. Studio từ xa: file nằm ở máy tính.
        toastDone(info?.remote ? exportedOnComputer(computer, "") : title, [skippedNote, lostNote, result.coverage].filter(Boolean).join(" · ") || undefined, {
          id: pending ?? undefined,
          action: info?.remote ? undefined : { label: S.s_mo_thu_muc_4bf5b127, onClick: () => revealFolder(result.folder) },
        });
      }
    } catch (error) {
      if (error instanceof PackDetached) return; // màn hình đã gỡ, việc vẫn chạy: ExportJobHost báo khi xong - không phải huỷ, không đụng thông báo
      const pending = loadingToast.current;
      loadingToast.current = null;
      if (error instanceof PackCancelled || (error instanceof ApiError && error.detail.reason === "cancelled")) {
        toast.info(S.s_da_dung_xuat_ab8ac9d1, { id: pending ?? undefined, duration: 6000 });
      } else if (kind === "abookproj") {
        const shown = packError((error as Error).message);
        toast.error(SAVING[kind][2], {
          id: pending ?? undefined,
          duration: 15000,
          description: (
            <div className="flex flex-col gap-1">
              <span>{shown.summary}</span>
              <Reveal when={shown.detail}><details className="text-xs">
                  <summary className="cursor-pointer select-none">{S.s_chi_tiet_e762d926}</summary>
                  <p className="mt-1 select-text break-words font-mono">{shown.detail}</p>
                </details></Reveal>
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
      ? [book.running && S.s_du_an_dang_chay_goi_khi_no_da_chay_xong_ho_b4407187]
      : [
          textOnly && S.s_chua_chuong_nao_co_audio_file_abook_chi_ma_7b9001f4(formatNumber(total)),
          !wholeSeries && !textOnly && ready < total && S.s_0_1_chuong_co_audio_2_3_3ee25355(formatNumber(ready), formatNumber(total), missing ? S.s_0_chuong_mat_file_8c87f657(missing) : "", kind === "abook" ? S.s_chon_xuat_mot_phan_de_xuat_khi_thieu_chuon_286cd8c0 : S.s_khong_co_trong_ban_xuat_2fda2fce),
          wholeSeries && (kind === "abook" ? S.s_file_sach_can_du_chuong_chon_xuat_mot_phan_95692f80 : S.s_phan_nao_chua_co_chuong_xong_se_bi_bo_qua_4d9cf695),
          !wholeSeries && book.running && (kind === "abook" ? S.s_sach_dang_chay_file_sach_can_du_chuong_hoa_d628b896 : S.s_sach_dang_chay_ban_xuat_chi_gom_cac_chuong_8941cd4a),
          !wholeSeries && redoExportNote(book.chapters.redo ?? 0, kind === "abook"),
          oneFile &&
            bytes > FAT32_LIMIT &&
            S.s_file_nay_se_lon_hon_4_gb_the_nho_hay_usb_d_0ed52ab5(wholeSeries ? S.s_chon_moi_phan_mot_file_neu_dinh_chep_vao_d_812841f9 : ""),
        ]
  ).filter(Boolean) as string[];
  // Studio từ xa (trình duyệt máy khác) không gói dự án: file nằm ở máy tính, việc của người ngồi trước nó.
  const kinds = info?.remote ? KINDS.filter((item) => item.value !== "abookproj") : KINDS;
  const kindValues = kinds.map((item) => item.value);
  const scopeValues: Scope[] = ["part", "series"];
  const layoutValues: Layout[] = ["single", "perPart"];
  return (
    <Dialog footer={busy ? (<DialogActions>
            <Reveal when={packing}><Button variant="ghost" disabled={cancelling} onClick={cancelPacking}>{S.s_huy_xuat_ca425e96}</Button></Reveal>
            <Button variant="ghost" onClick={() => handleOpenChange(false)}>{S.s_dong_cu_de_chay_9a342df0}</Button>
          </DialogActions>) : (finished ? (<DialogActions>
            <Reveal when={!info?.remote}><Button variant="ghost" icon={FolderOpen} onClick={() => revealFolder(finished.folder)}>{S.s_mo_thu_muc_4bf5b127}</Button></Reveal>
            <Button variant="primary" onClick={() => handleOpenChange(false)}>{S.s_xong_a6f4543a}</Button>
          </DialogActions>) : (<DialogActions>
        <Button variant="ghost" onClick={() => handleOpenChange(false)}>{S.s_thoi_e68f9e88}</Button>
        <Button
          variant="primary"
          icon={KINDS.find((item) => item.value === kind)?.icon ?? FolderDown}
          loading={busy}
          disabled={whole ? Boolean(book.running) : needsFfmpeg || (!wholeSeries && !ready && !textOnly)}
          onClick={() => void run()}
        >
          {info?.dialogs ? S.s_luu_va_xuat_e274cff0 : S.s_xuat_b2ebc56b}
        </Button>
      </DialogActions>))} open={open} onOpenChange={handleOpenChange} width="max-w-lg" title={S.s_xuat_0_387e7d8f(book.title)}
      description={wholeSeries ? S.s_cac_chuong_nghe_duoc_cua_ca_0_phan_se_vao_cf4e1648(parts.length) : S.s_0_chuong_se_vao_ban_xuat_4d6ae334(formatNumber(selectedCount))}>
      <MotionRegion fadeThrough>
      {busy ? (
        <MotionRegion className="py-2" role="status" motionKey={[cancelling, Boolean(downloading), Boolean(packing), Boolean(packShown), packShown?.fraction === null]}>
          {packShown && !downloading && packShown.fraction !== null ? (
            <Progress value={packShown.fraction} size="md" label={packShown.title} />
          ) : (
            <Progress value={0} indeterminate size="md" label={SAVING[kind][1]} />
          )}
          <p className="mt-3 text-sm font-medium">
            {cancelling
              ? S.s_dang_huy_c25a0214
              : downloading
                ? <LiveText shown={S.s_dang_tai_nhac_nen_0_1_124fda76(downloading.done, downloading.total)} spoken={spokenProgress(S.s_dang_tai_nhac_nen_0b8c4795, downloading.done / downloading.total)} />
                : (packShown?.title ?? SAVING[kind][1])}
          </p>
          <p className="mt-1 text-sm text-fg-2 text-pretty">
            {downloading
              ? S.s_tai_nhac_con_thieu_d1ac2c2f
              : countText
                ? `${countText}; `
                : ""}{S.s_dong_hop_van_xuat_nen_va_bao_khi_xong_604904f6}</p>

        </MotionRegion>
      ) : finished ? (
        <div className="py-2">
          <p className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="size-4 shrink-0 text-success" />
            {finished.title}
          </p>
          <p className="mt-2 break-all py-3 text-sm text-fg-2">{finished.detail}</p>

        </div>
      ) : (
      <>
      {parts.length > 1 && !whole && kind !== "m4b" && (
        <div
          className="relative mb-3 flex flex-wrap gap-6 text-sm"
          role="radiogroup"
          aria-label={S.s_pham_vi_ban_xuat_bcfd596b}
          onKeyDown={radioGroupKeys(scopeValues, scope, setScope)}
        >
          <SlidingIndicator variant="line" />
          {(
            [
              ["part", S.s_phan_nay_20fb3a86],
              ["series", S.s_ca_bo_0_phan_5bfa9de3(parts.length)],
            ] as const
          ).map(([value, label], index) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={scope === value}
              tabIndex={radioTabIndex(scopeValues, scope, index)}
              onClick={() => setScope(value)}
              className={cn("relative min-h-10 border-b-2 border-transparent font-medium transition-colors duration-motion-medium", scope === value ? "" : "text-fg-2")}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="relative grid divide-y divide-line" role="radiogroup" aria-label={S.s_kieu_ban_xuat_c2b4cb1e} onKeyDown={radioGroupKeys(kindValues, kind, setKind)}>
        <SlidingIndicator variant="line" />
        {kinds.map(({ value, title, detail, icon: Icon }, index) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={kind === value}
            tabIndex={radioTabIndex(kindValues, kind, index)}
            onClick={() => setKind(value)}
            className={cn(
              "relative flex min-h-10 items-start gap-3 py-3 text-left text-sm transition-colors duration-motion-medium",
              kind === value ? "text-accent-text" : "text-fg-2 hover:bg-hover",
            )}
          >
            <Icon className="mt-line-icon size-4 shrink-0 text-accent-text" />
            <span className="min-w-0">
              <span className="block font-medium">{title}</span>
              <span className="block text-fg-2">{detail}</span>
            </span>
          </button>
        ))}
      </div>
      {wholeSeries && kind === "abook" && (
        <>
          <div
            className="relative mt-3 flex flex-wrap gap-6 text-sm"
            role="radiogroup"
            aria-label={S.s_cach_chia_file_14e62e54}
            onKeyDown={radioGroupKeys(layoutValues, layout, setLayout)}
          >
            <SlidingIndicator variant="line" />
            {(
              [
                ["single", S.s_mot_file_774a88e2],
                ["perPart", S.s_moi_phan_mot_file_055af8d9],
              ] as const
            ).map(([value, label], index) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={layout === value}
                tabIndex={radioTabIndex(layoutValues, layout, index)}
                onClick={() => setLayout(value)}
                className={cn("relative min-h-10 border-b-2 border-transparent font-medium transition-colors duration-motion-medium", layout === value ? "" : "text-fg-2")}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-sm text-fg-2 text-pretty">
            {layout === "single"
              ? S.s_ca_bo_trong_mot_file_abook_nghe_noi_tiep_c_a02fc82b
              : S.s_moi_phan_mot_file_cung_thu_muc_cua_bo_4e8f08b0}
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
        <p className="mt-2 text-sm text-fg-2">{S.s_co_uoc_tinh_khoang_a6ece2b0}{formatSize(bytes)}
          {musicPending > 0 && S.s_cong_them_0_bai_nhac_khi_xuat_725f787e(musicPending)}
        </p>
      )}
      {needsFfmpeg && ffmpeg.data && (
        <div className="mt-3">
          <FfmpegNeeded
            status={ffmpeg.data}
            remote={Boolean(info?.remote)}
            onDownload={() => void ffmpegStart().then(refreshFfmpeg, (error: Error) => toast.error(S.s_chua_tai_duoc_cong_cu_cfe422f9, { description: error.message }))}
            onStop={() => void ffmpegCancel().then(refreshFfmpeg, () => undefined)}
          />
        </div>
      )}
      {kind === "abook" &&
        (info?.remote ? (
          <p className="mt-3">
            <OnComputerOnly verb={S.s_chu_sang_theo_giong_57fb4327} />
          </p>
        ) : (
          <WordTimingsRow bookId={book.id} running={Boolean(book.running)} />
        ))}
      {wholeSeries && kind === "mp3" && (
        <p className="mt-3 text-sm text-fg-2 text-pretty">{S.s_moi_phan_mot_thu_muc_con_trong_thu_muc_cua_7e868eba}</p>
      )}
      {/* Hỏi lại mỗi 5 giây: xuất lại xong thì hàng khép tại chỗ, hết hàng thì cả khung khép - không mất cứng. */}
      <MotionPresence open={staleExports.length > 0}>
      <div className="mt-3 py-3 text-sm">
        <p className="font-medium">{S.s_ban_xuat_da_cu_7e726524}</p>
        <div data-motion-live="">
        <AnimatedRows items={staleExports} keyOf={(item) => item.target}>
        {(item) => <div className="space-y-2 pt-2">
          <p className="break-all">{item.target} · {item.changed.length}{S.s_chuong_da_doi_a6114cc0}</p>
          <Button size="sm" variant="ghost" onClick={() => { setKind(item.kind as Kind); setScope("part"); setChangedOnly(item.kind === "mp3"); }}>{item.kind === "m4b" ? S.s_xuat_lai_m4b_07ad2a50 : item.kind === "mp3" ? S.s_xuat_chuong_doi_7eb1033d : S.s_xuat_file_sach_02b848a2}</Button>
          <Reveal when={item.kind === "m4b"}><p>{S.s_m4b_gop_ca_cuon_ban_can_dung_lai_ca_file_v_6adad4ec}</p></Reveal>
        </div>}
        </AnimatedRows>
        </div>
      </div>
      </MotionPresence>
      {kind === "abook" && <label className="mt-3 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={partial} onChange={(event) => setPartial(event.target.checked)} />{S.s_xuat_mot_phan_fc85b7e5}</label>}
      {kind === "mp3" && !wholeSeries && changedChapters.length > 0 && <label className="mt-3 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={changedOnly} onChange={(event) => setChangedOnly(event.target.checked)} />{S.s_xuat_00fa2c47}{changedChapters.length}{S.s_chuong_doi_e42b9885}</label>}
      {(warnings.length > 0 || (!whole && Boolean(book.pendingChanges))) && (
        <div className="mt-3 space-y-2 py-3 text-sm">
          {warnings.map((line) => (
            <p key={line} className="flex items-start gap-2">
              <AlertTriangle className="mt-line-icon size-4 shrink-0 text-warning" />
              <span className="text-pretty">{line}</span>
            </p>
          ))}
          {!whole && Boolean(book.pendingChanges) && (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
              <AlertTriangle className="size-4 shrink-0 text-warning" />
              <span className="min-w-0 flex-1 text-pretty">{S.s_con_71d0e2b2}{book.pendingChanges}{S.s_thay_doi_chua_ap_ban_xuat_doc_nhu_truoc_kh_3a7b1e79}</span>
              <Button size="sm" variant="ghost" icon={RefreshCw} onClick={() => { onOpenChange(false); onApplyFirst(); }}>{S.s_ap_dung_truoc_fec0937b}</Button>
            </div>
          )}
        </div>
      )}

      </>
      )}
      </MotionRegion>
    </Dialog>
  );
}
