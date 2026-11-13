import { S } from "../shared/strings.generated";
import { spokenDuration } from "@/listen/prepareAhead";
import { fileName, formatClock, formatSize } from "@/shared/format";
import { spokenProgress } from "@/shared/progressSpeech";
import { api } from "@/studio/api";
import { BOOK_FILE_SPAN, packError, packView, type PackJob, type PackPhase } from "@/studio/projectPacking";

// "Xuất file sách", "Xuất M4B" và "Xuất MP3" (menu "…" của trang sách): nói trước file sẽ nằm đâu, và trong lúc làm nói điều đổi theo thời gian.
// Việc có báo tiến độ (file sách, gói dự án) nói pha + đã/tổng; việc không báo (M4B) nói thời gian đã trôi - thứ thật duy nhất để nói.

/** Chữ riêng của từng kiểu xuất chạy nền; phần còn lại (hỏi trạng thái, thông báo, nhắc lại khi mở trang) dùng chung. */
export interface ExportCopy {
  busy: string;
  done: string;
  failed: string;
  /** Việc có nút Huỷ: lời khi người dùng đã dừng nó ("Đã dừng xuất…") và điều còn lại ("Phần đã làm được giữ…"). */
  stopped?: string;
  stoppedNote?: string;
  /** Lời dưới "Đang dừng…" khi khác lời chung (sách nói: "phần đã làm được giữ"). */
  stopping?: string;
  /** Việc báo tiến độ theo pha (gói dự án): dòng tiêu đề + thanh 0-1 (null: chưa có mẫu số) thay cho "đã mm:ss". */
  progress?: (job: ExportJob) => { title: string; fraction: number | null };
  /** Lỗi thô của máy chủ -> câu cho người nghe (gói dự án: ổ đầy, thư mục bị khoá...). */
  explain?: (raw: string) => string;
}

/** File sách (.abook): việc nền có pha + "chương X/N" (webui/server.py `post_bookfile_job`, bookfile.pack). */
export const BOOK_FILE_COPY: ExportCopy = {
  busy: S.s_dang_dong_goi_sach_ac7bab85,
  done: S.s_da_xuat_file_sach_242afa05,
  failed: S.s_chua_xuat_duoc_file_sach_43236ec7,
  stopped: S.s_da_dung_xuat_ab8ac9d1,
  stoppedNote: S.s_chua_co_file_sach_nao_duoc_ghi_acffb6e0,
  progress: (job) => packView(job as unknown as PackJob, BOOK_FILE_SPAN),
};
/** M4B: việc nền có Huỷ ở mọi pha (tải nhạc nền, trộn, ghép - webui/server.py `post_m4b_job_cancel`); huỷ thì không còn gì trên đĩa. */
export const M4B_COPY: ExportCopy = {
  busy: S.s_dang_lam_file_m4b_4a95b4ac,
  done: S.s_da_xuat_m4b_76947b3a,
  failed: S.s_chua_xuat_duoc_m4b_5a39de4c,
  stopped: S.s_da_dung_xuat_ab8ac9d1,
  stoppedNote: S.s_chua_co_file_m4b_nao_duoc_ghi_341f690c,
  stopping: S.s_dung_ngay_sau_buoc_dang_lam_khong_ghi_file_52bd285a,
};
/** Thư mục MP3 (Studio, menu Thư viện): việc nền có "chương i/N" và Huỷ ở mọi pha (webui/server.py `post_mp3_job`); huỷ thì thư mục dở bị xoá. */
export const MP3_COPY: ExportCopy = {
  busy: S.s_dang_xuat_mp3_99b61b74,
  done: S.s_da_xuat_mp3_c93fc100,
  failed: S.s_chua_xuat_duoc_mp3_1550e65a,
  stopped: S.s_da_dung_xuat_ab8ac9d1,
  stoppedNote: S.s_cac_chuong_da_ghi_do_duoc_xoa_55c0187f,
  stopping: S.s_dung_ngay_sau_buoc_dang_lam_thu_muc_mp3_do_47cdbf95,
};
/** Gói cả dự án (.abookproj): việc nền ở máy chủ, có pha + đã/tổng và Huỷ (webui/server.py `post_projectfile_job`). */
export const PROJECT_FILE_COPY: ExportCopy = {
  busy: S.s_dang_dong_goi_du_an_59bb0a50,
  done: S.s_da_goi_du_an_9908b445,
  failed: S.s_chua_goi_duoc_du_an_fd3612d5,
  stopped: S.s_da_dung_xuat_ab8ac9d1,
  stoppedNote: S.s_chua_co_file_du_an_nao_duoc_ghi_d4baebaa,
  progress: (job) => packView(job as unknown as PackJob),
  explain: (raw) => packError(raw).summary,
};

/** Thư mục máy chủ lưu khi không có hộp chọn thư mục (trình duyệt, Studio từ xa): "Đã xuất" trong thư viện (webui/server.py post_bookfile).
 *  Giữ kiểu dấu ngăn của chính đường dẫn thư viện (Windows `\`, còn lại `/`). */
export function defaultExportFolder(libraryRoot: string | undefined): string | null {
  if (!libraryRoot) return null;
  const separator = libraryRoot.includes("\\") ? "\\" : "/";
  return S.s_0_1_da_xuat_56482390(libraryRoot.replace(/[\\/]+$/, ""), separator);
}

/** Dòng phụ dưới "Xuất file sách": chọn thư mục (cửa sổ app) hay thư mục sẽ lưu (nơi khác). */
export function exportWhereHint(dialogs: boolean, libraryRoot: string | undefined): string {
  if (dialogs) return S.s_ban_chon_thu_muc_luu_o_buoc_ke_c54f45be;
  const folder = defaultExportFolder(libraryRoot);
  return folder ? S.s_luu_vao_0_278caa24(folder) : S.s_luu_vao_thu_muc_da_xuat_trong_thu_vien_49db80bb;
}

/** Chữ của thông báo đang đóng gói: số chương và thời gian đã trôi - đổi mỗi giây nên người xem biết máy chưa treo. */
export function packingText(chapters: number, elapsedSeconds: number): string {
  return S.s_0_chuong_da_1_b2b5fca7(chapters, formatClock(elapsedSeconds));
}

// ---- việc xuất chạy nền (webui/export_jobs.py: GET /api/books/<id>/bookfile-job) ----------------------------------------------
// Máy chủ nhớ lần xuất gần nhất của mỗi cuốn: tải lại trang giữa chừng hay sau khi xong, giao diện hỏi lại và hiện đúng chỗ ấy.

/** Kết quả của một lượt xuất: một file (`file`), hay cả bộ mỗi phần một file (chỉ có `folder` + `parts`). M4B kể thêm số chương
 *  có trong file / của cả cuốn - chương chưa làm xong không vào file. */
export interface ExportResult {
  folder?: string;
  file?: string;
  size?: number;
  parts?: unknown[];
  /** Số file trong thư mục kết quả (xuất sách nói MP3: mỗi chương một file). */
  files?: number;
  chapters?: number;
  chaptersTotal?: number;
  /** Gói dự án: file nguồn chương đã bị dời hay xoá nên không có trong gói. */
  missingSources?: string[];
  /** Xuất sách nói: "mp3" hay "m4b". */
  format?: string;
  /** Ảnh bìa của sách hỏng: bản xuất mang bìa vẽ từ tên (export.usable_cover). */
  coverBroken?: boolean;
  /** Xuất "Kèm nhạc nền": số đoạn không có nhạc vì bài không tải / không đọc được (webui/music_export.py). */
  musicMissing?: number;
  /** Xuất cả bộ: các phần chưa có chương nào nên bị bỏ qua (export.export_series). */
  skipped?: { part: number }[];
}

export interface ExportJob {
  state: "idle" | "running" | "done" | "error" | "cancelled";
  id?: string;
  /** Xuất sách nói (listen_export.py) báo tiến độ: pha ("voice" đọc / "music" trộn nhạc nền / "encode" ghép file), chương i/N, % theo số chữ, ước còn lại (giây),
   *  đang nhường người nghe (`waiting` "listening") hay đang chờ mạng về ("network"). Xuất M4B kèm nhạc nền báo "music-fetch" (dưới đây) rồi pha "music" + chương i/N. Mọi M4B: "peaks" đang kiểm đỉnh âm sau mã hoá, "reencode"
   *  mã hoá lại lượt `peakRound` vì `peakOver` chương vượt đỉnh (export.m4b_from_files). Gói dự án báo pha riêng (`PackPhase`) cùng `done`/`total`.
   *  "chapters": xuất MP3 đang ghi chương `chapter`/`chapters` (cả bộ: đếm lại ở mỗi phần).
   *  "music-fetch": đang tải bài nhạc thiếu thứ `done` + 1 trong `total` trước khi trộn (điện thoại: ExportMusic.kt; máy tính: M4B kèm nhạc nền). */
  phase?: "voice" | "music" | "music-fetch" | "encode" | "peaks" | "reencode" | "chapters" | PackPhase;
  peakRound?: number;
  peakOver?: number;
  done?: number;
  total?: number;
  chapter?: number;
  chapters?: number;
  percent?: number;
  secondsLeft?: number | null;
  waiting?: "listening" | "network" | null;
  /** Giây đã đóng gói (đang chạy). */
  elapsed?: number;
  /** Giây kể từ lúc xong / hỏng. */
  finishedAgo?: number;
  result?: ExportResult;
  error?: string;
}

/** Xong cách đây không quá chừng này thì mở trang sách là báo lại; xa hơn thì chỉ còn dòng "lần xuất gần nhất" trong menu. */
export const RECENT_SECONDS = 30 * 60;

export type JobView =
  | { kind: "none" }
  | {
      kind: "loading" | "success" | "error" | "info";
      title: string;
      description: string;
      /** Xong mà thiếu gì đó (chương, nhạc, nguồn, bìa): riêng phần lưu ý của `description` - thông báo nói nó bằng cảnh báo, còn "xong" trơn chỉ một dòng. */
      note?: string;
      /** Đường đầy đủ của file vừa xuất: để ở gợi ý khi rê chuột, thông báo chỉ nói tên file. */
      place?: string;
      /** Việc báo được tiến độ: thanh phần trăm (0-1) dưới dòng mô tả. */
      progress?: number;
      /** Đang làm: lời cho trình đọc màn hình - chỉ đổi khi đổi pha hay qua mốc 25 % (dòng mô tả có đồng hồ chạy từng giây; soát a31 A6). */
      spoken?: string;
    };

/** Việc tự báo tiến độ (xuất sách nói): chữ + phần trăm 0-1 + lời đọc (pha / mốc 25 %); không báo thì null. */
function reportedProgress(job: ExportJob): { fraction: number; text: string; spoken: string } | null {
  if (job.phase === "music-fetch" && job.total) {
    const done = job.done ?? 0;
    const fraction = done / job.total;
    return { fraction, text: S.s_dang_tai_nhac_nen_0_1_bai_2a186c13(Math.min(done + 1, job.total), job.total), spoken: spokenProgress(S.s_dang_tai_nhac_nen_0b8c4795, fraction) };
  }
  if (job.phase === "peaks") return { fraction: 1, text: S.s_dang_kiem_dinh_am_fddf3cc5, spoken: S.s_dang_kiem_dinh_am_fddf3cc5 };
  // Lượt mã hoá lại chạy lại từng chương (pha "encode" / "music" báo chương) - vẫn nói vì sao.
  const again = job.peakOver ? S.s_ma_hoa_lai_vi_0_chuong_vuot_dinh_luot_1_04047057(job.peakOver, job.peakRound ?? 1) : "";
  if (job.phase === "reencode") return { fraction: 1, text: again, spoken: again };
  if (job.chapter === undefined || !job.chapters) return null;
  const where = S.s_chuong_0_1_7e729467(job.chapter, job.chapters);
  if (job.phase === "encode") {
    return { fraction: 1, text: again ? `${again} · ${where}` : S.s_dang_ghep_file_am_thanh_0_a01e1ed9(where), spoken: again || S.s_dang_ghep_file_am_thanh_c3a409b3 };
  }
  if (job.phase === "chapters") {
    const fraction = (job.chapter - 1) / job.chapters;
    return { fraction, text: S.s_dang_ghi_chuong_0_1_41650b16(job.chapter, job.chapters), spoken: spokenProgress(S.s_dang_xuat_mp3_99b61b74, fraction) };
  }
  if (job.phase === "music") {
    const text = S.s_dang_tron_nhac_chuong_0_1_1216281a(job.chapter, job.chapters);
    const fraction = job.percent !== undefined ? job.percent / 100 : (job.chapter - 1) / job.chapters;
    return { fraction, text: again ? `${again} · ${text}` : text, spoken: again || spokenProgress(S.s_dang_tron_nhac_nen_97fb2b7d, fraction) };
  }
  const parts = [where, `${job.percent ?? 0}%`];
  if (job.waiting === "listening") parts.push(S.s_nhuong_cho_chuong_dang_nghe_93babd54);
  else if (job.waiting === "network") parts.push(S.s_dang_cho_mang_4e41560e);
  else if (job.secondsLeft != null) parts.push(S.s_con_0_46699fed(spokenDuration(job.secondsLeft)));
  const fraction = (job.percent ?? 0) / 100;
  const spoken =
    job.waiting === "listening"
      ? S.s_tam_nhuong_cho_chuong_dang_nghe_258d655c
      : job.waiting === "network"
        ? S.s_mat_mang_dang_cho_mang_ve_de_lam_tiep_34393630
        : spokenProgress(S.s_dang_xuat_0_chuong_46b78449(job.chapters), fraction);
  return { fraction, text: parts.join(" · "), spoken };
}

/** Nơi file nằm: file sách, hay thư mục khi cả bộ mỗi phần một file. */
export function exportedPlace(result: ExportResult): string {
  return result.file ?? result.folder ?? ""; // Studio từ xa: cả bộ mỗi phần một file thì máy chủ không trả thư mục
}

/** "4/6 chương - chương chưa xong không có trong file" khi bản xuất thiếu chương; rỗng khi đủ hay không biết. */
export function missingChaptersNote(result: ExportResult): string {
  const { chapters, chaptersTotal } = result;
  if (chapters === undefined || chaptersTotal === undefined || chapters >= chaptersTotal) return "";
  return S.s_0_1_chuong_chuong_chua_xong_khong_co_trong_35795edf(chapters, chaptersTotal);
}

/** "3 đoạn thiếu nhạc vì chưa tải được bài" khi bản xuất kèm nhạc nền thiếu đoạn nào; rỗng khi đủ. */
export function musicMissingNote(result: ExportResult): string {
  return result.musicMissing ? S.s_0_doan_thieu_nhac_vi_chua_tai_duoc_bai_66255efe(result.musicMissing) : "";
}

/** "chưa có chương nào nên bỏ qua: Phần 2" khi xuất cả bộ bỏ qua phần nào; rỗng khi không. */
export function skippedPartsNote(result: ExportResult): string {
  return result.skipped?.length ? S.s_chua_co_chuong_nao_nen_bo_qua_0_56da88e7(result.skipped.map((part) => S.s_phan_0_7c77642d(part.part)).join(", ")) : "";
}

/** "3 file nguồn chương đã bị dời hay xoá nên không có trong gói" khi gói dự án thiếu file nguồn; rỗng khi đủ. */
export function missingSourcesNote(result: ExportResult): string {
  const lost = result.missingSources?.length ?? 0;
  return lost ? S.s_0_file_nguon_chuong_da_bi_doi_hay_xoa_nen_a83aaefb(lost) : "";
}

/** Thông báo cho một trạng thái; `announce` (mở lại trang sách): chỉ nhắc cái đã xong gần đây, không nhắc lần xuất từ lâu. */
export function jobView(job: ExportJob, chapters = 0, announce = false, copy: ExportCopy = BOOK_FILE_COPY): JobView {
  if (job.state === "running") {
    const elapsed = job.elapsed ?? 0;
    const reported = reportedProgress(job);
    if (reported) return { kind: "loading", title: copy.busy, description: reported.text, progress: reported.fraction, spoken: reported.spoken };
    // Chưa có pha nào (cả bộ không báo tiến độ, hay lượt vừa bắt đầu): nói như việc không báo tiến độ.
    if (copy.progress && job.phase) {
      const packing = copy.progress(job);
      return {
        kind: "loading",
        title: packing.title,
        description: S.s_da_0_0e900305(formatClock(elapsed)),
        spoken: spokenProgress(packing.title, packing.fraction),
        ...(packing.fraction !== null ? { progress: packing.fraction } : {}),
      };
    }
    return { kind: "loading", title: copy.busy, description: chapters ? packingText(chapters, elapsed) : S.s_da_0_0e900305(formatClock(elapsed)), spoken: copy.busy };
  }
  if (announce && (job.finishedAgo ?? 0) > RECENT_SECONDS) return { kind: "none" };
  if (job.state === "cancelled") return copy.stopped ? { kind: "info", title: copy.stopped, description: copy.stoppedNote ?? "" } : { kind: "none" };
  if (job.state === "done" && job.result) {
    // Thông báo chỉ nói TÊN (file, hay thư mục khi mỗi phần một file + số file); đường đầy đủ ở gợi ý khi rê chuột và nút "Mở thư mục".
    const { file, folder } = job.result;
    const count = job.result.files ?? job.result.parts?.length;
    const partsNote = !file && job.result.files !== undefined && job.result.parts ? S.s_0_phan_40e8af8c(job.result.parts.length) : ""; // MP3 cả bộ: file đếm theo chương, phần đếm riêng
    // `note`: riêng phần LƯU Ý (thiếu chương / nhạc / nguồn / bìa) - thông báo "xong" chỉ một dòng, lưu ý đổi thành cảnh báo (toastDone).
    const skipped = skippedPartsNote(job.result);
    const lacks = [missingChaptersNote(job.result), missingSourcesNote(job.result), musicMissingNote(job.result),
      job.result.coverBroken ? S.s_anh_bia_cua_sach_bi_hong_nen_dung_bia_ve_t_782534c3 : ""].filter(Boolean);
    const details = [partsNote, !file && count ? `${count} file` : "", skipped, job.result.size ? formatSize(job.result.size) : "", ...lacks].filter(Boolean);
    const place = file ?? folder ?? "";
    return { kind: "success", title: copy.done, description: [fileName(place), ...details].filter(Boolean).join(" · "), ...(skipped || lacks.length ? { note: [skipped, ...lacks].filter(Boolean).join(" · ") } : {}), ...(fileName(place) !== place ? { place } : {}) };
  }
  if (job.state === "error") return { kind: "error", title: copy.failed, description: copy.explain ? copy.explain(job.error ?? "") : (job.error ?? "") };
  return { kind: "none" };
}

/** Chữ dài quá `max` ký tự thì cắt Ở ĐẦU (giữ phần đuôi: đuôi file và số tập là chỗ phân biệt các lần xuất), thêm "…". */
export function clipStart(text: string, max: number): string {
  return text.length > max ? `…${text.slice(text.length - (max - 1))}` : text;
}

/** Số ký tự tối đa của tên file / thư mục trong dòng phụ của menu (dòng phụ cắt ở cuối khi quá rộng - tên không được nằm ở chỗ bị cắt). */
const HINT_NAME_MAX = 34;

/** Studio từ xa: file xuất nằm trên máy tính, không về máy đang xem - nói thẳng máy nào và (nếu biết) tên file / thư mục. Máy chủ chỉ trả TÊN
 *  (server.without_local_paths), không đường dẫn. `detail`: phần còn lại của dòng ("5 MB", "6 file"). */
export function exportedOnComputer(computer: string, name: string, detail = ""): string {
  const where = computer && computer !== S.s_may_tinh_8eafc226 ? S.s_da_xuat_vao_may_tinh_0_19bf0167(computer) : S.s_da_xuat_vao_may_tinh_d121586e;
  return [name ? `${where}: ${name}` : where, detail].filter(Boolean).join(" · ");
}

/** Loại file của một lần xuất, nói bằng cái người dùng nhận ra: "MP3" / "M4B" (xuất sách nói ghi `format`; file .m4b), "File sách" (.abook), "Dự án" (.abookproj). */
export function exportFormatLabel(result: ExportResult): string {
  if (result.format) return result.format.toUpperCase();
  const extension = (result.file ?? "").toLowerCase().match(/\.([a-z0-9]+)$/)?.[1];
  if (extension === "m4b") return S.s_m4b_c793d08a;
  if (extension === "abookproj") return S.s_du_an_4f139d43;
  if (extension === "abook") return S.s_file_sach_ccdcf961;
  return result.file ? "" : S.s_mp3_b84e4872; // cả thư mục, mỗi chương một file
}

/** "10/10 14:05" - ngày/tháng giờ:phút theo giờ máy. */
export function shortWhen(at: Date): string {
  const two = (value: number) => String(value).padStart(2, "0");
  return `${two(at.getDate())}/${two(at.getMonth() + 1)} ${two(at.getHours())}:${two(at.getMinutes())}`;
}

/** Dòng phụ trong menu: lần xuất gần nhất của cuốn này (nếu có), thay cho "Bạn chọn thư mục lưu ở bước kế": loại file, lúc xuất, TÊN file /
 *  thư mục ("MP3 · 10/10 14:05 · Chuyện thử"). Đường đầy đủ ở `lastExportPlace`, hiện khi rê chuột: đường dài bị cắt ngay đầu thì chỉ còn
 *  thấy ổ đĩa và thư mục cha. `now`: lúc job được hỏi (giây xong cách đây `finishedAgo` tính từ đó). */
export function lastExportHint(job: ExportJob | undefined, copy: ExportCopy = BOOK_FILE_COPY, now: number = Date.now()): string | null {
  if (job?.state === "running") {
    // Có phần trăm thì nói thẳng (như hàng "Đang xuất · 45%" của điện thoại); chưa có thì chỉ đường tới thông báo.
    if (job.percent !== undefined) return S.s_dang_xuat_0_20b7b18c(Math.min(99, Math.max(0, Math.round(job.percent))));
    return S.s_0_xem_thong_bao_o_goc_man_hinh_55cc357e(copy.busy.replace(/…$/, ""));
  }
  if (job?.state === "done" && job.result) {
    const when = job.finishedAgo === undefined ? "" : shortWhen(new Date(now - job.finishedAgo * 1000));
    const parts = [exportFormatLabel(job.result), when, clipStart(fileName(exportedPlace(job.result)), HINT_NAME_MAX)].filter(Boolean);
    return S.s_lan_xuat_gan_nhat_0_f94c1bcb(parts.join(" · "));
  }
  return null;
}

/** Đường đầy đủ của lần xuất gần nhất (cho gợi ý khi rê chuột trên dòng phụ); chưa có thì undefined. */
export function lastExportPlace(job: ExportJob | undefined): string | undefined {
  return job?.state === "done" && job.result ? exportedPlace(job.result) : undefined;
}

/** Mã các cuốn đang có lượt xuất `kind` chạy ở máy chủ (GET /api/export-jobs). Mở (hay tải lại) app ở trang khác trang sách: đây là cách duy nhất
 *  biết có việc để hiện lại tiến độ. Hỏi hụt thì coi như không có (nhịp sau, hay trang sách, sẽ hỏi lại). */
export async function runningExports(kind: "bookfile" | "m4b" | "mp3" | "audiobook" | "projectfile"): Promise<string[]> {
  try {
    const all = await allExportJobs();
    return (all[kind] ?? []).filter((job) => job.state === "running").map((job) => job.bookId);
  } catch {
    return [];
  }
}

type AllExportJobs = Partial<Record<string, (ExportJob & { bookId: string })[]>>;
let asking: Promise<AllExportJobs> | null = null;

/** Một lượt GET /api/export-jobs cho mọi kiểu xuất hỏi cùng lúc (mở app: bốn kiểu xuất cùng hỏi - soát UX a23 thấy bốn lượt
 *  gọi giống hệt); xong thì lần hỏi sau gọi lại máy chủ. */
function allExportJobs(): Promise<AllExportJobs> {
  asking ??= api<AllExportJobs>("/api/export-jobs").finally(() => {
    asking = null;
  });
  return asking;
}

/** Mục xuất trong menu sách có việc để làm không? File sách (`.abook`) mang cả chữ của chương chưa có audio (bookfile._add_texts), nên sách chỉ có chữ
 *  vẫn xuất được; MP3 / M4B / sách nói cần chương đã nghe được. */
export function exportable(kind: "bookfile" | "m4b" | "mp3" | "audiobook" | "projectfile", book: { chaptersAvailable: number; chaptersTotal: number }): boolean {
  return kind === "bookfile" ? book.chaptersAvailable > 0 || book.chaptersTotal > 0 : book.chaptersAvailable > 0;
}
