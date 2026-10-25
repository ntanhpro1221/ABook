import { Capacitor } from "@capacitor/core";
import { formatClock, formatLength, formatPercent } from "@/shared/format";
import type { ListenChapter } from "./model";

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
  if (state.playingHere) return "Tạm dừng";
  if (state.finished) return "Nghe lại từ đầu";
  // Nhãn ngắn (docs/DESIGN.md mục 7): chương là đủ - giờ phút đã ở dòng tiến độ ngay trên.
  if (state.point && (state.point.at > 0 || state.heard > 0)) return `Nghe tiếp · ${state.point.title}`;
  return state.heard > 0 ? "Nghe tiếp" : "Nghe";
}

/** Nhãn đọc màn hình của nút phát: đang chờ thì nói đang chờ gì - không nói "Tạm dừng" khi chưa có tiếng nào. */
export function toggleLabel(playing: boolean, buffering: boolean, speaking: boolean): string {
  if (playing && buffering) return speaking ? PREPARING_VOICE : "Đang tải âm thanh…";
  return playing ? "Tạm dừng" : "Phát";
}

/** Máy này có phím tắt của trình phát: chỉ máy tính - trên app điện thoại trình phát không bắt phím (player.tsx). */
export const SHORTCUTS = !Capacitor.isNativePlatform();

/** Tên nút kèm phím tắt ("Lùi 15 giây (←)") ở máy tính; điện thoại chỉ tên - TalkBack từng đọc cả "(Shift+←)" (soát a67). */
export function withShortcut(label: string, key: string, keys = SHORTCUTS): string {
  return keys ? `${label} (${key})` : label;
}

/** Nút "Chương sau": chương cuối thì nói đó là chương cuối (nút mờ); chương sau có mà chưa nghe được thì nói vì sao (nút vẫn bấm được). */
export function nextChapterLabel(hasNext: boolean, hasLater: boolean, keys = SHORTCUTS): string {
  if (!hasLater) return "Đây là chương cuối";
  return hasNext ? withShortcut("Chương sau", "Shift+→", keys) : "Chương sau chưa có audio";
}

/** Sách chỉ có chữ: MỘT dòng nói nghe được bằng gì, dùng ở mọi chỗ (thư viện, trang sách, màn đọc) - không còn "chưa có âm thanh" ngay cạnh
 *  nút "Nghe ngay". `speaks`: máy này có giọng đọc. */
export function textBookLine(speaks: boolean): string {
  return speaks ? "Chỉ có chữ · nghe bằng giọng đọc" : "Chỉ có chữ · máy này chưa có giọng đọc";
}

export function chapterStatusLabel(producing: boolean): string {
  return producing ? "Đang thu âm…" : "Chưa có audio";
}

/** Dòng phụ của một chương trong danh sách: "Chương 3 · 26 phút". Chương chỉ có chữ không có gì riêng để nói (giọng đọc là của cả cuốn và đã ở đầu
 *  trang sách; chữ giống nhau trên mọi hàng thì không ghi trên hàng nào), nên chỉ còn số chương khi tên chương đã là tên riêng. */
export function chapterSubline(chapter: Pick<ListenChapter, "title" | "subtitle" | "available" | "duration" | "state">, producing: boolean): string {
  const tail = chapter.available ? formatLength(chapter.duration) : chapter.state === "text" ? "" : chapterStatusLabel(producing);
  return [chapter.subtitle ? chapter.title : "", tail].filter(Boolean).join(" · ");
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
    if (!state.canSpeak) return "Máy này chưa có giọng đọc.";
    const reading = state.readings ? ` ${state.coarse ? "Giữ chữ" : "Bấm chuột phải vào chữ"} để sửa cách đọc.` : "";
    return state.tapped ? `Nghe bằng giọng đọc.${reading}` : `${verb} chữ để nghe từ đó.${reading}`;
  }
  if (!state.timed) return "Chưa có audio; bạn vẫn đọc được chữ.";
  if (state.tapped) return null;
  const reading = state.readings ? ` ${state.coarse ? "Giữ chữ" : "Bấm chuột phải vào chữ"} để sửa cách đọc.` : "";
  return `${verb} chữ để nghe từ đó.${state.wish ? " “Sửa câu này”: đổi người nói, cách đọc hoặc thu lại." : ""}${reading}`;
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
  return producing ? "Chương tiếp theo sẽ nghe được khi máy làm xong chương ấy." : "Các chương sau chưa có audio.";
}

/** Thông báo sau khi nghe hết phần đã có: MỘT dòng - `caughtUpDetail` nối vào sau dấu gạch. */
export function caughtUpLine(producing?: boolean): string {
  const detail = caughtUpDetail(producing);
  return `Đã nghe hết phần đã có - ${detail.charAt(0).toLowerCase()}${detail.slice(1).replace(/\.$/, "")}`;
}

/** Dòng trạng thái của sách chưa đủ chương mà không máy nào đang thu (điện thoại: không biết máy tính còn làm không; file .abook). */
export function partialBookLine(available: number, total: number): string {
  return `Sách này có ${available}/${total} chương đã thu - các chương sau chưa có audio`;
}

/** Màn đọc không mở được chữ một chương: máy giữ sách không trả lời (503 - sách của máy khác, chữ chương chưa về máy này) thì nói đúng lời
 *  máy chủ, không thì chương không còn (soát a27 lỗi 12). */
export function chapterOpenProblem(error: unknown): string {
  const problem = error as { status?: number; message?: string } | null;
  return problem?.status === 503 && problem.message ? `${problem.message.replace(/\.$/, "")}.` : "Chương có thể không còn trong sách.";
}

/** Hỏi lại chữ chương sau lỗi: không khi chương không có (404) hay máy giữ sách không trả lời (503 - đã chờ máy ấy rồi). */
export function retryChapterText(count: number, error: unknown): boolean {
  const status = (error as { status?: number } | null)?.status;
  return status !== 404 && status !== 503 && count < 2;
}
