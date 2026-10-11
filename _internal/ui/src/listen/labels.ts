import { formatClock, formatLength, formatPercent } from "@/shared/format";

// Nhãn của phần Nghe mà nhiều màn phải nói GIỐNG nhau (soát UX "Nghe ngay" 03-10): một chỗ chọn chữ, mỗi màn chỉ gọi. Nói theo cái người
// nghe nhận ra (chương, giờ, giọng nào đang đọc), không theo trạng thái bên trong (clip đã đọc sẵn chưa, kịch bản đã có mốc chưa).

/** Đang chờ giọng máy đọc xong đoạn đầu (thanh phát nhỏ, màn "Đang nghe", nhãn nút phát). */
export const PREPARING_VOICE = "Đang chuẩn bị giọng đọc…";
/** Chờ giọng ngắn hơn mức này thì không nói gì (chỉ vòng quay ở nút phát). */
export const PREPARING_VOICE_AFTER_MS = 1500;

/** Câu thoại đã mang ngoặc của sách - bỏ trước khi bọc ngoặc trích (soát UX 29-09: ““…””). Thẻ "Tối qua" và dấu trang (soát a26 L6). */
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
  if (state.finished) return "Đã nghe hết cả cuốn";
  const left = Math.max(0, state.total - state.heard);
  const scope = state.whole ? "cả cuốn" : "phần đã có";
  const remaining = state.rate !== 1 && left > 60 ? `còn khoảng ${formatLength(left / state.rate)} ở tốc độ ${state.speed}` : `còn ${formatLength(left)}`;
  return `Đã nghe ${formatPercent(state.heard / state.total)} ${scope} · ${remaining}`;
}

/** Dòng dưới tên một cuốn trong danh sách mời "Nghe cuốn khác": đã nghe dở thì tiến độ (cùng lời với màn "Đang nghe"), chưa nghe thì độ dài. */
export function otherBookLine(book: { duration: number; chaptersTotal: number; complete: boolean; progress: { heardSeconds: number; totalSeconds: number } }): string {
  const { heardSeconds, totalSeconds } = book.progress;
  if (heardSeconds > 0 && totalSeconds > 0) {
    return bookProgressText({ whole: book.complete, heard: Math.min(heardSeconds, totalSeconds), total: totalSeconds, rate: 1, speed: "" });
  }
  return book.duration > 0 ? `Chưa nghe · ${formatLength(book.duration)}` : `Chưa nghe · ${book.chaptersTotal} chương`;
}

/** Nút chính của trang sách: nói rõ nghe bắt đầu từ đâu. Không đổi theo việc giọng máy đã đọc sẵn tới đâu. */
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
  if (state.playingHere) return "Tạm dừng";
  if (state.finished) return "Nghe lại từ đầu";
  if (state.point && state.point.at > 0) return `Nghe tiếp · ${resumeWhere(state.point.title, state.point.at)}`;
  if (state.heard > 0) return state.point ? `Nghe tiếp · ${state.point.title}` : "Nghe tiếp";
  return state.textOnly ? "Nghe ngay" : "Bắt đầu nghe";
}

/** Nhãn đọc màn hình của nút phát: đang chờ thì nói đang chờ gì - không nói "Tạm dừng" khi chưa có tiếng nào. */
export function toggleLabel(playing: boolean, buffering: boolean, speaking: boolean): string {
  if (playing && buffering) return speaking ? PREPARING_VOICE : "Đang tải âm thanh…";
  return playing ? "Tạm dừng" : "Phát";
}

/** Nút "Chương sau": chương cuối thì nói đó là chương cuối (nút mờ); chương sau có mà chưa nghe được thì nói vì sao (nút vẫn bấm được). */
export function nextChapterLabel(hasNext: boolean, hasLater: boolean): string {
  if (!hasLater) return "Đây là chương cuối";
  return hasNext ? "Chương sau (Shift+→)" : "Chương sau chưa có audio";
}

/** Sách chỉ có chữ: MỘT dòng nói nghe được bằng gì, dùng ở mọi chỗ (thư viện, trang sách, màn đọc) - không còn "chưa có âm thanh" ngay cạnh
 *  nút "Nghe ngay". `speaks`: máy này có giọng đọc. */
export function textBookLine(speaks: boolean): string {
  return speaks ? "Chỉ có chữ · nghe bằng giọng đọc" : "Chỉ có chữ · máy này chưa có giọng đọc";
}

/** Dòng phụ của một chương chỉ có chữ trong danh sách chương: tên giọng đang đọc cuốn ("Hoài My (Edge)"; giọng của máy thì "Giọng đọc của máy").
 *  Cố định: không đổi sang độ dài khi giọng máy đã đọc một phần - độ dài ấy là ước, đổi theo giọng và theo phần đã đọc sẵn, nên nhãn nhảy qua lại
 *  làm người nghe tưởng chương vừa đổi. Tiến độ nghe đã có thanh riêng. */
export function textChapterLine(speaks: boolean, voice = ""): string {
  return speaks ? voice || "Giọng đọc của máy" : "Chỉ có chữ";
}

/** "Bấm" với chuột, "Chạm" với màn cảm ứng. */
export function tapVerb(coarse: boolean): "Bấm" | "Chạm" {
  return coarse ? "Chạm" : "Bấm";
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
    if (!state.canSpeak) return `${textBookLine(false)}.`;
    const reading = state.readings ? ` ${state.coarse ? "Giữ" : "Bấm chuột phải"} vào một chữ đọc sai để sửa cách đọc.` : "";
    return state.tapped ? `${textBookLine(true)}.${reading}` : `${textBookLine(true)}. ${verb} vào một chữ để nghe từ chữ ấy.${reading}`;
  }
  if (!state.timed) return "Chương này chưa thu thành sách nói - chữ vẫn đọc được. Thu xong thì “Nghe từ đây” hiện ra.";
  if (state.tapped) return null;
  const reading = state.readings ? ` ${state.coarse ? "Giữ" : "Bấm chuột phải"} vào một chữ đọc sai để sửa cách đọc.` : "";
  return `${verb} vào một chữ để nghe từ đúng chữ ấy${state.wish ? "; “Sửa câu này” để đổi người nói, cách đọc, tên hay thu lại câu" : ""}.${reading}`;
}

/** "Chương 1" không gãy dòng giữa chữ và số (thẻ hẹp ở 1280 px từng gãy "từ Chương / 1"): dấu cách không ngắt thay cho dấu cách thường. */
export function keepTogether(title: string): string {
  return title.replace(/^(Chương|Tập|Phần|Hồi|Quyển)\s+(\S+)/i, "$1\u00a0$2");
}

/** Lời sau khi nghe hết phần đã có. Chỉ hứa "máy làm xong thì nghe được" khi chắc có máy đang làm (`producing`); không thì nói điều chắc chắn - sách mở từ
 *  file .abook hay tải về điện thoại không có máy nào làm tiếp ở đây (soát UX a9: "việc thu đang dừng" / "khi máy làm xong" sai sự thật). */
export function caughtUpDetail(producing?: boolean): string {
  return producing ? "Chương tiếp theo sẽ nghe được khi máy làm xong chương ấy." : "Các chương sau chưa có audio.";
}

/** Dòng trạng thái của sách chưa đủ chương mà không máy nào đang thu (điện thoại: không biết máy tính còn làm không; file .abook). */
export function partialBookLine(available: number, total: number): string {
  return `Sách này có ${available}/${total} chương đã thu - các chương sau chưa có audio`;
}
