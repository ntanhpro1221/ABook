import { S } from "../shared/strings.generated";
import { endSentence } from "@/shared/format";

// "Tải về máy" cho sách "Trên máy khác" (webui/remote_books.py `Downloads`, như điện thoại tải sách của máy tính): chữ nói tình trạng
// bằng lời người nghe nhận ra - đang tải bao nhiêu, đã xong thì nghe được cả khi máy kia tắt, hỏng thì phần đã tải vẫn giữ.

/** Tình trạng tải của một cuốn (GET /api/listen/books/<mã>/download). */
export interface RemoteDownload {
  state: "none" | "running" | "done" | "failed" | "cancelled";
  files: number;
  filesDone: number;
  bytes: number;
  bytesDone: number;
  error: string;
  /** Đứt vì mất kết nối với máy kia: máy kia lên lại thì máy này tự tải tiếp (webui/remote_books.py `Downloads.resume_interrupted`). */
  retry?: boolean;
}

/** Phần đã tải, 0..1: theo byte (chương, nhạc) khi biết cỡ, không thì theo số file. Chữ đọc theo, dàn nhân vật và file không ghi cỡ
 *  không có trong số byte: còn thiếu file nào thì chưa bao giờ là 100% (soát a27 lỗi 8 - "Đã có 100%" khi chữ và nhạc chưa tải). */
export function downloadFraction(status: RemoteDownload): number {
  if (status.state === "done") return 1;
  const fraction = status.bytes > 0 ? status.bytesDone / status.bytes : status.files > 0 ? status.filesDone / status.files : 0;
  // Máy chủ còn báo đang chạy (kiểm file, chuyển chỗ sau byte cuối) thì cũng chưa xong: "Đang tải… 100%" kèm nút dừng là tự mâu thuẫn.
  return Math.max(0, Math.min(status.filesDone < status.files || status.state === "running" ? 0.99 : 1, fraction));
}

export interface DownloadNote {
  tone: "running" | "done" | "error" | "paused";
  title: string;
  /** Câu phụ - để trống khi không cần. */
  detail: string;
  /** Nút trên dòng tình trạng: dừng khi đang tải, tải tiếp khi đã dừng / hỏng. */
  action: "cancel" | "resume" | null;
}

/** Dòng tình trạng dưới tên sách; `null` khi chưa tải gì và không có gì để nói. `computer`: tên máy giữ sách. */
export function downloadNote(status: RemoteDownload | null | undefined, computer: string): DownloadNote | null {
  if (!status) return null;
  const where = computer || S.s_may_kia_d1eb7142;
  const percent = `${Math.floor(downloadFraction(status) * 100)}%`;
  switch (status.state) {
    case "running":
      return { tone: "running", title: S.s_dang_tai_ve_may_0_d19b4333(percent), detail: S.s_van_nghe_duoc_trong_luc_tai_12c4a3a5, action: "cancel" };
    case "done":
      return { tone: "done", title: S.s_da_tai_ve_may_a3ac321b, detail: S.s_nghe_duoc_ca_khi_0_tat_d0f7626b(where), action: null };
    case "failed": {
      // Chỉ nói “vẫn giữ” khi thật sự đã có phần tải được; đứt ở 0% thì không có gì để giữ.
      const kept = status.bytesDone > 0 || status.filesDone > 0 ? S.s_phan_da_tai_van_giu_tren_may_nay_79d4dcb7 : "";
      const again = status.retry ? S.s_tu_tai_tiep_khi_0_tra_loi_lai_5e0e8b25(where) : "";
      return {
        tone: "error",
        title: S.s_chua_tai_xong_ve_may_0_4e6343f2(percent),
        detail: `${endSentence(status.error || S.s_0_khong_tra_loi_412cfadc(where))}${kept}${again}`,
        action: "resume",
      };
    }
    case "cancelled":
      return {
        tone: "paused",
        title: S.s_da_dung_tai_0_c6869240(percent),
        detail: status.bytesDone > 0 || status.filesDone > 0 ? S.s_phan_da_tai_van_giu_tren_may_nay_7a0ab6ab : "",
        action: "resume",
      };
    default:
      return null;
  }
}

/** Mục trong menu của sách: tên + câu phụ, tuỳ tình trạng. */
export function downloadMenuLabel(status: RemoteDownload | null | undefined, computer: string): { label: string; hint: string; disabled: boolean } {
  const where = computer || S.s_may_kia_d1eb7142;
  if (status?.state === "running") return { label: S.s_huy_tai_1a9ff73d, hint: S.s_da_tai_0_12412428(Math.floor(downloadFraction(status) * 100)), disabled: false };
  if (status?.state === "done") return { label: S.s_da_tai_ve_may_a3ac321b, hint: S.s_nghe_duoc_ca_khi_0_tat_d0f7626b(where), disabled: true };
  // “Tải nốt” chỉ khi đã có phần thật; 0% thì vẫn là tải từ đầu.
  if (status && Math.floor(downloadFraction(status) * 100) > 0) {
    // Đủ audio mà còn thiếu file: phần còn lại là chữ đọc theo hay nhạc nền - nói ra, "99%" không cho biết vì sao chưa xong.
    const rest = status.bytes > 0 && status.bytesDone >= status.bytes ? S.s_con_chu_doc_theo_hay_nhac_nen_39189ff1 : "";
    return { label: S.s_tai_not_ve_may_8235a2a9, hint: S.s_da_co_0_tren_may_nay_1_86511a91(Math.floor(downloadFraction(status) * 100), rest), disabled: false };
  }
  return { label: S.s_tai_ve_may_41e0b494, hint: S.s_de_nghe_ca_khi_0_tat_7052488a(where), disabled: false };
}
