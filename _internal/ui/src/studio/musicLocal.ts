import { S } from "../shared/strings.generated";
// "Nhạc của tôi": nhạc người dùng tự nhập (abook/webui/music_local.py, docs/MUSIC_IMPORT.md). Phần thuần (không React) để thử riêng.

import { formatSize } from "@/shared/format";

/** Một bài trong kho của máy (music_local.LocalMusic.info). `analysed` false = chưa có bộ phân tích âm thanh cho ra không khí
 *  của bài: máy không tự chọn nó, nhưng ghim tay được. */
export interface LocalTrack {
  link: string;
  title: string;
  creator: string;
  duration: number;
  analysed: boolean;
  name: string;
  album?: string;
  genre?: string;
  bytes: number;
  /** Đầu dò lời hát (chỉ bài đã phân tích bằng gói có `vox_head.npz`): xác suất 0..1 và cờ "có vẻ có lời". Bài có cờ thì máy không tự chọn nó
   *  làm nền dưới giọng đọc (ghim tay thì được). */
  vocals?: number;
  vocalsLikely?: boolean;
  /** Công tắc tự chọn của người dùng cho bài này: "on" = cho máy tự chọn dù có vẻ có lời, "off" = máy không bao giờ tự chọn (ghim tay thì được);
   *  vắng = mặc định (tự chọn được, trừ bài có vẻ có lời). */
  auto?: "on" | "off";
}

/** Một phần của mô-đun "Phân tích nhạc" (máy tính: công cụ đọc âm thanh, thư viện chạy model, model; điện thoại: thư viện chạy model, model). */
export interface MusicModulePart {
  id: string;
  label: string;
  bytes: number;
  /** current: đúng bản app này mang; outdated: đã tải nhưng app có bản mới hơn; missing: chưa tải. */
  state: "current" | "outdated" | "missing";
  /** Máy đã có sẵn phần này (không do mô-đun tải). */
  external?: boolean;
}

/** Mô-đun "Phân tích nhạc" (máy tính: webui/music_module.py; điện thoại: MusicStudentSetup.kt): nhập nhạc chạy không cần nó, nó chỉ cho
 *  máy NGHE nhạc để hiểu không khí của từng bài. Tải MỘT lần khi người dùng bấm - một nút, một tổng dung lượng, không bao giờ tự tải. */
export interface MusicModuleStatus {
  state: "missing" | "downloading" | "ready" | "outdated" | "error" | "unsupported";
  /** Đang tải: byte đã tải / tổng byte của lần tải này. Còn lại: `total` là dung lượng lần bấm kế sẽ tải. */
  done: number;
  total: number;
  /** Lý do tải hỏng, tiếng Việt; rỗng nếu không lỗi. */
  error: string;
  /** Nguyên văn lỗi của lần tải hỏng, thu trong "Chi tiết". */
  errorDetail?: string;
  /** Bộ phân tích đã cắm (dùng được, kể cả khi có bản mới hơn). */
  ready: boolean;
  /** Đang tải mà mạng vừa hỏng, đang chờ thử lại (RETRYING_NOTE). */
  retrying?: boolean;
  /** Máy này tải được không; không thì `reason` nói vì sao. */
  supported?: boolean;
  reason?: string;
  parts?: MusicModulePart[];
  /** Tên các phần có bản mới (state outdated) và số byte phải tải để cập nhật. */
  outdatedParts?: string[];
  outdatedBytes?: number;
  /** Có bản mới mà bản trên máy không chạy được (thiếu phần chạy model): phân tích nhạc đang tắt cho tới khi tải lại (điện thoại). */
  stopped?: boolean;
  /** Số bài đã phân tích bằng bản model cũ hơn: người dùng tự quyết có phân tích lại không. */
  stale?: number;
  /** Đang phân tích các bài đã nhập. */
  analysing: boolean;
  /** Máy đang dùng dữ liệu di động (tính phí). */
  metered: boolean;
  /** Thư viện mới chỉ dùng được sau khi mở lại app. */
  restart?: boolean;
  /** Lần tải vừa rồi bị người dùng huỷ (phần đã tải giữ, lần sau làm tiếp). */
  cancelled?: boolean;
  /** Có nút Huỷ khi đang tải (máy tính và điện thoại). */
  cancellable?: boolean;
  /** Chỉ máy tính. */
  precise?: PreciseMood;
}

/** "Đo cảm xúc nhạc chính xác hơn" (chỉ máy tính, webui/music_valence.py): tuỳ chọn tải thêm một model lớn, người dùng bật mới tải. `unavailable` = máy
 *  không bật được (ít RAM) - giao diện không mời. `working`: đang nghe kỹ lại các bài đã nhập (`pending` bài còn chờ). */
export interface PreciseMood {
  state: "unavailable" | "off" | "missing" | "downloading" | "error" | "ready";
  enabled: boolean;
  /** Đã có đủ file trên máy: bật không phải tải. */
  present: boolean;
  /** Đã tắt mà file còn trên đĩa: hiện nút "Xoá file". */
  removable: boolean;
  reason: string;
  bytes: number;
  done: number;
  total: number;
  error: string;
  errorDetail?: string;
  working: boolean;
  pending: number;
  /** Lần tải vừa rồi bị huỷ (công tắc đã tắt, file dở giữ lại). */
  cancelled?: boolean;
}

export interface LocalMusicView {
  tracks: LocalTrack[];
  /** Đã có bộ phân tích âm thanh trên máy này chưa. */
  analyzer: boolean;
  /** Mô-đun "Phân tích nhạc" (cả máy tính lẫn điện thoại). */
  module?: MusicModuleStatus;
}

/** Lời báo lần tải vừa rồi bị huỷ - đứng đầu câu mô tả của thẻ để người dùng biết chuyện gì đã xảy ra và lần sau thế nào. */
export const CANCELLED_NOTE = S.s_da_huy_lan_tai_sau_lam_tiep_tu_cho_dung_a3bd5f77;

/** Đang tải mà mạng vừa hỏng, máy đang chờ để thử lại (`retrying` của máy chủ, studio_setup.retrying): nói ra thay vì đứng ở "Đang tải 62%"
 *  suốt ~30 giây rồi mới báo lỗi (soát a64). Mọi thẻ tải (giọng, Phân tích nhạc, công cụ ghép âm thanh) dùng chung câu này. */
export const RETRYING_NOTE = S.s_mang_chap_chon_dang_thu_lai_e0ce6cbb;

export function modulePercent(module: Pick<MusicModuleStatus, "done" | "total">): number {
  return module.total > 0 ? Math.min(100, Math.floor((module.done / module.total) * 100)) : 0;
}

/** Câu báo về mô-đun, nói bằng điều người nghe cần biết (không nói model nào). */
export function moduleLabel(module: MusicModuleStatus): string {
  if (module.state === "error") return module.error;
  if (module.state === "downloading") return module.retrying ? S.s_0_phan_tich_nhac_1_4795cbd9(RETRYING_NOTE, modulePercent(module)) : S.s_dang_tai_phan_tich_nhac_0_mot_lan_1_97be1ac5(formatSize(module.total), modulePercent(module));
  if (module.analysing) return S.s_dang_phan_tich_nhac_da_them_a2a6a13b;
  if (module.state === "unsupported") return module.reason ? S.s_may_nay_chua_phan_tich_duoc_nhac_0_c5fb4f61(module.reason) : S.s_may_nay_chua_phan_tich_duoc_nhac_15442fa6;
  if (module.state === "outdated" && module.stopped)
    return S.s_phan_tich_nhac_dang_tat_tai_lai_0_van_ghim_692f7c6c(formatSize(module.outdatedBytes ?? module.total));
  if (module.state === "outdated") return S.s_0_co_ban_moi_1_ban_hien_tai_van_dung_duoc_dba6b14f(module.cancelled ? `${CANCELLED_NOTE} ` : "", formatSize(module.outdatedBytes ?? module.total));
  if (module.state === "ready") {
    if (module.restart) return S.s_phan_tich_nhac_da_cap_nhat_mo_lai_abook_de_0fe3cd00;
    if ((module.stale ?? 0) > 0) return S.s_0_bai_dung_phan_tich_cu_co_the_phan_tich_l_f009376f(module.stale);
    return "";
  }
  // Dung lượng chỉ ở nút "Tải (… MB)", câu này nói lợi ích.
  return S.s_0_may_tu_chon_nhac_hop_tung_doan_65c553a9(module.cancelled ? `${CANCELLED_NOTE} ` : "");
}

/** Có mời người dùng bật "Đo cảm xúc nhạc chính xác hơn" không: máy đủ sức, và đã có bộ phân tích nhạc (nó dùng lại phần nghe của bộ ấy). */
export function preciseOffered(module: MusicModuleStatus | undefined): module is MusicModuleStatus & { precise: PreciseMood } {
  return Boolean(module?.precise && module.precise.state !== "unavailable" && module.ready);
}

/** Đang tải hay đang nghe kỹ lại: giao diện hỏi lại view mỗi giây. */
export function preciseBusy(precise: PreciseMood | undefined): boolean {
  return precise?.state === "downloading" || Boolean(precise?.working);
}

/** Câu mô tả tuỳ chọn, nói bằng điều người nghe thấy. */
export function preciseLabel(precise: PreciseMood): string {
  const size = formatSize(precise.bytes);
  if (precise.state === "downloading") {
    const percent = precise.total > 0 ? Math.min(100, Math.floor((precise.done / precise.total) * 100)) : 0;
    return S.s_dang_tai_bo_do_cam_xuc_chinh_xac_hon_0_mot_cff7aba8(size, percent);
  }
  if (precise.state === "error") return precise.error;
  if (precise.state === "missing") return S.s_da_bat_nhung_chua_tai_xong_bai_moi_them_ta_467bc3b6;
  if (precise.state === "ready") {
    if (precise.working) {
      return precise.pending > 0
        ? S.s_dang_nghe_ky_0_bai_ban_da_them_bai_chua_to_9abc9e92(precise.pending)
        : S.s_dang_nghe_ky_bai_vua_them_9d3cd7fd;
    }
    return S.s_dang_bat_bai_moi_them_se_duoc_nghe_ky_ngam_66f8653c;
  }
  const how = precise.present ? S.s_chay_67d64a17 : S.s_tai_them_0_mot_lan_sau_do_chay_23e89e1e(size);
  return S.s_0_may_nghe_ky_hon_tung_bai_ban_them_de_cho_742e5d20(precise.cancelled ? `${CANCELLED_NOTE} ` : "", how);
}

export interface ImportResult extends LocalMusicView {
  added: LocalTrack[];
  existing: LocalTrack[];
  failed: string[];
}

export const LOCAL_PREFIX = "local:";

export function isLocal(link: string): boolean {
  return link.startsWith(LOCAL_PREFIX);
}

/** Mã sha1 (40 hex) của file trong link `local:<sha1>`; link khác dạng -> null. */
export function localDigest(link: string): string | null {
  const digest = isLocal(link) ? link.slice(LOCAL_PREFIX.length) : "";
  return /^[0-9a-f]{40}$/.test(digest) ? digest : null;
}

/** Đường "Nghe thử" một bài: bài của tôi qua kho của máy này, bài danh mục qua đường danh mục. */
export function previewPath(link: string): string {
  const digest = localDigest(link);
  return digest ? `/api/music/local/${digest}/file` : `/api/music/track?link=${encodeURIComponent(link)}`;
}

/** Bài này có vẻ có lời hát (đầu dò lời hát báo): hiện nhãn "Có vẻ có lời". */
export function hasVocals(track: Pick<LocalTrack, "analysed" | "vocalsLikely">): boolean {
  return track.analysed && track.vocalsLikely === true;
}

type AutoTrack = Pick<LocalTrack, "analysed" | "vocalsLikely" | "auto">;

/** Công tắc "Tự chọn" của một bài (công tắc `auto`, music_local.py): bật = máy được tự chọn bài này. Mặc định máy tự chọn bài thường, bỏ qua bài có lời. */
export const AUTO_PICK_LABEL = S.s_tu_chon_90506961;
export const UNANALYSED = S.s_chua_phan_tich_5c1c27fb;
export function autoOn(track: AutoTrack): boolean {
  return track.auto === "on" || (track.auto !== "off" && !hasVocals(track));
}
/** Giá trị `auto` gửi đi khi gạt công tắc: trùng mặc định thì về mặc định (null). */
export function autoNext(track: AutoTrack): "on" | "off" | null {
  const on = !autoOn(track);
  return on === !hasVocals(track) ? null : on ? "on" : "off";
}
/** Nhãn ngắn cạnh công tắc - điều công tắc không nói: bài chưa phân tích (máy chưa tự chọn được), bài có lời. */
export function trackNote(track: Pick<LocalTrack, "analysed" | "vocalsLikely">): string {
  return !track.analysed ? UNANALYSED : hasVocals(track) ? S.s_co_loi_4b381f10 : "";
}

/** Lời giới thiệu "Nhạc của tôi" - MỘT câu cho mọi nơi nói về nó (tab Nhạc nền của dự án, Cài đặt, Sửa sách), kể cả chuyện bài ghim đi cùng file
 *  sách: người dùng không phải đoán chỗ này khác chỗ kia ra sao (soát UX a8 02-10). */
export const MY_MUSIC_INTRO =
  S.s_them_nhac_lam_nen_bai_da_chon_di_cung_file_eefa0e8d;
export const MY_MUSIC_HELP = S.s_nhac_duoc_chep_vao_kho_may_nay_dung_doi_ba_00b59983;

/** Dòng phụ của một bài trong "Đổi bài" của một đoạn (không có công tắc ở đó): có lời, đã tắt tự chọn, hợp không khí đoạn này hay chưa phân tích - cùng chữ
 *  ngắn với Cài đặt và tab Nhạc của dự án. Không có gì đáng nói thì undefined. */
export function mineNote(item: AutoTrack & { fits?: boolean }): string | undefined {
  const notes = [hasVocals(item) ? S.s_co_loi_4b381f10 : null, item.auto === "off" ? S.s_khong_tu_chon_02ae1742 : null, item.analysed ? (item.fits ? S.s_hop_khong_khi_doan_nay_44c3025b : null) : UNANALYSED]
    .filter((note): note is NonNullable<typeof note> => Boolean(note));
  return notes.length ? notes.join(" · ") : undefined;
}

/** Gộp kết quả của nhiều lượt nhập (mỗi file một lượt, để thấy tiến độ). Danh sách bài và trạng thái mô-đun "Phân tích nhạc" lấy của lượt
 *  cuối - thiếu `module` thì lời mời "Tải Phân tích nhạc" chỉ hiện sau khi tải lại trang (soát a64). */
export function mergeImports(results: ImportResult[]): ImportResult {
  const last = results[results.length - 1];
  return {
    tracks: last?.tracks ?? [],
    analyzer: last?.analyzer ?? false,
    ...(last?.module ? { module: last.module } : {}),
    added: results.flatMap((result) => result.added),
    existing: results.flatMap((result) => result.existing),
    failed: results.flatMap((result) => result.failed),
  };
}

/** Câu báo sau khi nhập: nói rõ bao nhiêu bài đã vào, bao nhiêu đã có sẵn, file nào không nhập được và vì sao. */
export function importSummary(result: Pick<ImportResult, "added" | "existing" | "failed">): {
  kind: "success" | "warning" | "error";
  title: string;
  description?: string;
} {
  const { added, existing, failed } = result;
  const parts: string[] = [];
  if (added.length) parts.push(S.s_0_bai_moi_0344fbff(added.length));
  if (existing.length) parts.push(S.s_0_bai_da_co_tu_truoc_37a68de3(existing.length));
  if (!added.length && !existing.length) {
    return { kind: "error", title: S.s_chua_them_duoc_nhac_5565bc66, description: failed.join("\n") };
  }
  const title = S.s_da_them_0_2918e530(parts.join(", "));
  const unanalysed = added.filter((track) => !track.analysed).length;
  const notes: string[] = [];
  if (failed.length) notes.push(failed.join("\n"));
  if (unanalysed) notes.push(S.s_0_bai_chua_phan_tich_may_chua_tu_chon_ban_43a21157(unanalysed));
  return { kind: failed.length ? "warning" : "success", title, description: notes.join("\n") || undefined };
}
