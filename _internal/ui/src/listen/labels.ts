import { S } from "../shared/strings.generated";
import { formatClock, formatLength, formatPercent } from "@/shared/format";
import type { ListenChapter } from "./model";

// Nhãn của phần Nghe mà nhiều màn phải nói GIỐNG nhau (soát UX "Nghe ngay" 03-10): một chỗ chọn chữ, mỗi màn chỉ gọi. Nói theo cái người
// nghe nhận ra (chương, giờ, giọng nào đang đọc), không theo trạng thái bên trong (clip đã đọc sẵn chưa, kịch bản đã có mốc chưa).

/** Đang chờ giọng máy đọc xong đoạn đầu (thanh phát nhỏ, màn "Đang nghe", nhãn nút phát). */
export const PREPARING_VOICE = S.s_dang_chuan_bi_giong_doc_69f1b51a;
/** Chờ giọng ngắn hơn mức này thì không nói gì (chỉ vòng quay ở nút phát). */
export const PREPARING_VOICE_AFTER_MS = 1500;

/** Câu thoại đã mang ngoặc của sách - bỏ trước khi bọc ngoặc trích (soát UX 29-09: ““…””). Thẻ "Tối qua" (soát a26 L6). */
/** Số có dấu của Âm thanh / Âm sắc (Android/Qt PlayerLabels.signed): dấu trừ thật "−" (không gạch nối), "+" khi dương, phẩy thập phân, tối đa một số lẻ. */
export function signedNumber(value: number): string {
  const text = Math.abs(value).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
  return text === "0" ? "0" : `${value < 0 ? "−" : "+"}${text}`;
}

export function unquoted(sentence: string): string {
  return sentence.replace(/^[\s“"«「『]+|[\s”"»」』]+$/g, "");
}

/** Chỗ nghe tiếp: "Chương 3 · 12:04" - cùng một dạng ở thẻ "Đang nghe dở" của Thư viện và nút chính của trang sách. */
export function resumeWhere(chapterTitle: string, seconds: number): string {
  return chapterTitle ? `${chapterTitle} · ${formatClock(seconds)}` : formatClock(seconds);
}

/** Dòng tiến độ ở màn "Đang nghe": đã nghe bao nhiêu, còn bao lâu ở tốc độ đang chọn.
 *  "Đã nghe 10% phần đã có · còn khoảng 27 phút ở tốc độ 1,5×" (tốc độ thường: "còn 41 phút"). `speed`: nhãn tốc độ đã định dạng. */
export function bookProgressText(state: { whole: boolean; heard: number; total: number; rate: number; speed: string; finished?: boolean }): string {
  // Phát hết chương cuối của cuốn đã đủ: nói là đã hết, không để "98%" (đồng hồ chương cuối dừng trước mốc tròn) đọc như còn dở.
  if (state.finished) return S.s_da_nghe_het_ca_cuon_11fdce7b;
  const left = Math.max(0, state.total - state.heard);
  const scope = state.whole ? S.s_ca_cuon_b841210a : S.s_phan_da_co_69a9b13c;
  const remaining = state.rate !== 1 && left > 60 ? S.s_con_khoang_0_o_toc_do_1_21ae4e35(formatLength(left / state.rate), state.speed) : S.s_con_0_46699fed(formatLength(left));
  return S.s_da_nghe_0_1_2_8f416814(formatPercent(state.heard / state.total), scope, remaining);
}

/** Phần audio của cả cuốn trước chương đang nghe và tổng phần audio đã có (giây) - nền cho `bookProgressText`. `inside`: chương đang nghe là một
 *  phần của tổng ấy (có audio) - chương chỉ có chữ (giọng máy đọc) thì đồng hồ của nó không cộng vào. */
export function bookHeardBase(
  queue: ReadonlyArray<Pick<ListenChapter, "id" | "available" | "duration">>,
  chapterId: number | undefined,
): { before: number; total: number; inside: boolean } {
  let before = 0;
  let total = 0;
  let reached = false;
  let inside = false;
  for (const chapter of queue) {
    // Tìm chương đang nghe TRƯỚC khi bỏ chương chưa có audio: chương chỉ có chữ đang đọc mà bị bỏ qua thì mọi chương sau nó tính là đã nghe (100%).
    if (chapter.id === chapterId) {
      reached = true;
      inside = chapter.available;
    }
    if (!chapter.available) continue;
    if (!reached) before += chapter.duration;
    total += chapter.duration;
  }
  return { before, total, inside };
}

/** Dòng dưới tên một cuốn trong danh sách mời "Nghe cuốn khác": đã nghe dở thì tiến độ (cùng lời với màn "Đang nghe"), chưa nghe thì độ dài. */
export function otherBookLine(book: { duration: number; chaptersTotal: number; complete: boolean; progress: { heardSeconds: number; totalSeconds: number } }): string {
  const { heardSeconds, totalSeconds } = book.progress;
  if (heardSeconds > 0 && totalSeconds > 0) {
    return bookProgressText({ whole: book.complete, heard: Math.min(heardSeconds, totalSeconds), total: totalSeconds, rate: 1, speed: "" });
  }
  return book.duration > 0 ? S.s_chua_nghe_0_dd595dec(formatLength(book.duration)) : S.s_chua_nghe_0_chuong_fbac7a78(book.chaptersTotal);
}

/** Nút chính của trang sách: "Nghe tiếp · Chương 4" hay "Nghe". Không đổi theo việc giọng máy đã đọc sẵn tới đâu. */
export function primaryListenLabel(state: {
  /** Cuốn này đang phát trong trình phát. */
  playingHere: boolean;
  /** Đã nghe hết cả cuốn (cuốn đã đủ). */
  finished: boolean;
  /** Chỗ sẽ phát khi bấm (model.resumePoint). */
  point: { title: string; at: number } | null;
  /** Đã nghe được bao nhiêu giây cả cuốn. */
  heard: number;
  /** Sách chỉ có chữ (giọng máy đọc). */
  textOnly: boolean;
}): string {
  if (state.playingHere) return S.s_tam_dung_67635815;
  if (state.finished) return S.s_nghe_lai_tu_dau_e251d632;
  // Nhãn ngắn (docs/DESIGN.md mục 7): chương là đủ - giờ phút đã ở dòng tiến độ ngay trên.
  if (state.point && (state.point.at > 0 || state.heard > 0)) return S.s_nghe_tiep_0_fd77c5f2(state.point.title);
  return state.heard > 0 ? S.s_nghe_tiep_403b90a5 : S.s_nghe_a43aafef;
}

/** Nhãn đọc màn hình của nút phát: đang chờ thì nói đang chờ gì - không nói "Tạm dừng" khi chưa có tiếng nào. */
export function toggleLabel(playing: boolean, buffering: boolean, speaking: boolean): string {
  if (playing && buffering) return speaking ? PREPARING_VOICE : S.s_dang_tai_am_thanh_6c7cb62f;
  return playing ? S.s_tam_dung_67635815 : S.s_phat_343e7e48;
}

/** Tên nút kèm phím tắt ("Lùi 15 giây (←)"); `keys` false thì chỉ tên. */
export function withShortcut(label: string, key: string, keys = true): string {
  return keys ? `${label} (${key})` : label;
}

/** Nút "Chương sau": chương cuối thì nói đó là chương cuối (nút mờ); chương sau có mà chưa nghe được thì nói vì sao (nút vẫn bấm được). */
export function nextChapterLabel(hasNext: boolean, hasLater: boolean, keys = true): string {
  if (!hasLater) return S.s_day_la_chuong_cuoi_e4e693d4;
  return hasNext ? withShortcut(S.s_chuong_sau_17d1bd20, "Shift+→", keys) : S.s_chuong_sau_chua_co_audio_e17e3d72;
}

/** Sách chỉ có chữ: MỘT dòng nói nghe được bằng gì, dùng ở mọi chỗ (thư viện, trang sách, màn đọc) - không còn "chưa có âm thanh" ngay cạnh
 *  nút "Nghe ngay". `speaks`: máy này có giọng đọc. */
export function textBookLine(speaks: boolean): string {
  return speaks ? S.s_chi_co_chu_nghe_bang_giong_doc_edf36d64 : S.s_chi_co_chu_may_nay_chua_co_giong_doc_5203960b;
}

export function chapterStatusLabel(producing: boolean): string {
  return producing ? S.s_dang_thu_am_96160328 : S.s_chua_co_audio_4b0d19a4;
}

/** Dòng phụ của một chương trong danh sách: "Chương 3 · 26 phút". Chương chỉ có chữ không có gì riêng để nói (giọng đọc là của cả cuốn và đã ở đầu
 *  trang sách; chữ giống nhau trên mọi hàng thì không ghi trên hàng nào), nên chỉ còn số chương khi tên chương đã là tên riêng. */
export function chapterSubline(chapter: Pick<ListenChapter, "title" | "subtitle" | "available" | "duration" | "state">, producing: boolean): string {
  const tail = chapter.available ? formatLength(chapter.duration) : chapter.state === "text" ? "" : chapterStatusLabel(producing);
  return [chapter.subtitle ? chapter.title : "", tail].filter(Boolean).join(" · ");
}

/** "Bấm" với chuột, "Chạm" với màn cảm ứng. */
export function tapVerb(coarse: boolean): "Bấm" | "Chạm" {
  return coarse ? S.s_cham_36a8bd9a : S.s_bam_457e5bf3;
}

/** Lời nhắc ở đầu màn đọc (null: không nhắc). Theo LOẠI chương - không theo việc kịch bản đã có mốc chưa (chương đọc to có mốc ngay khi giọng
 *  máy đọc xong đoạn đầu, nhãn từng đổi giữa chừng). */
export function readerHint(state: {
  textOnly: boolean;
  canSpeak: boolean;
  timed: boolean;
  /** Người đọc đã nghe từ một chữ ít nhất một lần. */
  tapped: boolean;
  coarse: boolean;
  /** Sửa câu ghi thành ý muốn chờ Studio. */
  wish: boolean;
  /** Giữ / bấm chuột phải một chữ để sửa cách đọc nó ("Đọc từ này là…", cuốn chỉ có chữ của máy này). */
  readings?: boolean;
}): string | null {
  const verb = tapVerb(state.coarse);
  if (state.textOnly) {
    if (!state.canSpeak) return S.s_may_nay_chua_co_giong_doc_3449f846;
    const reading = state.readings ? S.s_0_de_sua_cach_doc_20a6386a(state.coarse ? S.s_giu_chu_2cfa3331 : S.s_bam_chuot_phai_vao_chu_4c8f72be) : "";
    return state.tapped ? S.s_nghe_bang_giong_doc_0_7e4bfabe(reading) : S.s_0_chu_de_nghe_tu_do_1_cb228268(verb, reading);
  }
  if (!state.timed) return S.s_chua_co_audio_ban_van_doc_duoc_chu_6b728db5;
  if (state.tapped) return null;
  const reading = state.readings ? S.s_0_de_sua_cach_doc_20a6386a(state.coarse ? S.s_giu_chu_2cfa3331 : S.s_bam_chuot_phai_vao_chu_4c8f72be) : "";
  return S.s_0_chu_de_nghe_tu_do_1_2_8fdb8acd(verb, state.wish ? S.s_sua_cau_nay_doi_nguoi_noi_cach_doc_hoac_th_58f4f1af : "", reading);
}

/** "Chương 1" không gãy dòng giữa chữ và số (thẻ hẹp ở 1280 px từng gãy "từ Chương / 1"): dấu cách không ngắt thay cho dấu cách thường. */
export function keepTogether(title: string): string {
  return title.replace(/^(Chương|Tập|Phần|Hồi|Quyển)\s+(\S+)/i, "$1\u00a0$2");
}

/** Tên sách khi hiển thị: dấu "·" dính hai chữ bên cạnh và "Tập 1" không tách, để không dòng nào kết thúc hay mở đầu bằng "·"
 *  ("Thành Phố Sương Mù · / Tập 1" - soát 24-10 T02). Chỉ đổi dấu cách lúc vẽ, tên lưu giữ nguyên. */
export function displayTitle(title: string): string {
  return title.replace(/\s+·\s+/g, "\u00a0·\u00a0").replace(/(^|\s)(Chương|Tập|Phần|Hồi|Quyển)\s+(\S+)/gi, "$1$2\u00a0$3");
}

/** Lời sau khi nghe hết phần đã có. Chỉ hứa "máy làm xong thì nghe được" khi chắc có máy đang làm (`producing`); không thì nói điều chắc chắn - sách mở từ
 *  file .abook hay tải về điện thoại không có máy nào làm tiếp ở đây (soát UX a9: "việc thu đang dừng" / "khi máy làm xong" sai sự thật). */
export function caughtUpDetail(producing?: boolean): string {
  return producing ? S.s_chuong_tiep_theo_se_nghe_duoc_khi_may_lam_2d887378 : S.s_cac_chuong_sau_chua_co_audio_44723dd5;
}

/** Thông báo sau khi nghe hết phần đã có: MỘT dòng - `caughtUpDetail` nối vào sau dấu gạch. */
export function caughtUpLine(producing?: boolean): string {
  const detail = caughtUpDetail(producing);
  return S.s_da_nghe_het_phan_da_co_0_1_04c94a21(detail.charAt(0).toLowerCase(), detail.slice(1).replace(/\.$/, ""));
}

/** Dòng trạng thái của sách chưa đủ chương mà không máy nào đang thu (điện thoại: không biết máy tính còn làm không; file .abook). */
export function partialBookLine(available: number, total: number): string {
  return S.s_sach_nay_co_0_1_chuong_da_thu_cac_chuong_s_b799aec1(available, total);
}

/** Màn đọc không mở được chữ một chương: máy giữ sách không trả lời (503 - sách của máy khác, chữ chương chưa về máy này) thì nói đúng lời
 *  máy chủ, không thì chương không còn (soát a27 lỗi 12). */
export function chapterOpenProblem(error: unknown): string {
  const problem = error as { status?: number; message?: string } | null;
  return problem?.status === 503 && problem.message ? `${problem.message.replace(/\.$/, "")}.` : S.s_chuong_co_the_khong_con_trong_sach_490f82b5;
}

/** Hỏi lại chữ chương sau lỗi: không khi chương không có (404) hay máy giữ sách không trả lời (503 - đã chờ máy ấy rồi). */
export function retryChapterText(count: number, error: unknown): boolean {
  const status = (error as { status?: number } | null)?.status;
  return status !== 404 && status !== 503 && count < 2;
}
