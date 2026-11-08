import { S } from "./strings.generated";
// Bỏ ghép một máy (docs/EDITING.md, P2d): bỏ ghép xoá thư mục các cuốn nghe thẳng của máy ấy - phần đã tải và phần sửa chưa gửi
// của người nghe nằm trong đó - nên hỏi trước, nói bằng lời người nghe nhận ra (mất gì, giữ gì). Dùng chung cho điện thoại (Peers.kt)
// và máy tính (webui/remote_books.py).
import { formatSize } from "./format";

/** Phần sửa chưa gửi của các cuốn của một máy (`peerUnsent` trên điện thoại, `GET /api/computers/<id>/unsent` trên máy tính). */
export interface UnsentEdits {
  books: { title: string; changes: number }[];
  /** Tổng số thay đổi của mọi cuốn. */
  changes: number;
  /** Máy kia nhận được phần sửa (là máy tính): "Gửi trước" có nghĩa. Điện thoại khác không nhận sửa. */
  sendable: boolean;
  /** Máy kia trả lời NGAY lúc hỏi (máy tính hỏi thật qua GET .../unsent); không có thì dùng trạng thái đã biết của danh sách máy. */
  reachable?: boolean;
  /** Cái máy này sẽ quên khi bỏ ghép: số cuốn của máy kia, byte đã tải về, số cuốn đang có chỗ nghe (những chỗ ấy giữ lại). */
  cache?: { books: number; bytes: number; places: number };
}

export type UnpairChoice = "send" | "discard";

export interface UnpairCopy {
  title: string;
  /** Mỗi ý một dòng: cái gì sẽ mất, và vì sao không gửi được nếu có. */
  lines: string[];
  /** Nhãn nút "gửi trước rồi bỏ ghép"; null khi máy kia không nhận sửa. */
  send: string | null;
  /** Máy kia đang trả lời: "gửi trước" là nút chính. Máy kia tắt thì nút vẫn có (thử lại được) nhưng không là nút chính - nút chính là Huỷ. */
  sendPrimary: boolean;
  discard: string;
  cancel: string;
}

/** Lời báo (toast) sau khi gỡ ghép - cả khi không phải hỏi gì. MỘT dòng: sách của máy ấy rời Thư viện và chỗ nghe còn giữ đã nói ở hộp hỏi (`unpairCopy`). */
export function unpairDone(device: string): string {
  return S.s_da_bo_ghep_0_d1ec976d(device);
}

/** `self`: máy đang cầm sửa ("điện thoại" hay "máy tính"); `reachable`: máy kia đang trả lời. `null` khi không còn gì để mất - gỡ như thường. */
export function unpairCopy(device: string, self: "điện thoại" | "máy tính", unsent: UnsentEdits | null | undefined, reachable: boolean): UnpairCopy | null {
  const edited = !!unsent && unsent.changes > 0 && unsent.books.length > 0;
  const cache = unsent?.cache && unsent.cache.books > 0 ? unsent.cache : null;
  if (!unsent || (!edited && !cache)) return null;
  const lines: string[] = [];
  if (cache) {
    const downloaded = cache.bytes > 0 ? S.s_va_0_da_tai_ve_1_nay_se_bi_xoa_868c13af(cache.bytes < 1024 ** 2 ? S.s_duoi_1_mb_b59395ae : formatSize(cache.bytes), self) : "";
    lines.push(S.s_0_cuon_cua_1_se_roi_thu_vien_2_da517a50(cache.books, device, downloaded));
    if (cache.places > 0) lines.push(S.s_cho_nghe_cua_0_cuon_van_giu_ghep_lai_dung_9f62342f(cache.places, device));
  }
  let send: string | null = null;
  const up = unsent.reachable ?? reachable;
  if (edited) {
    const names = unsent.books.slice(0, 3).map((book) => `“${book.title}”`);
    const rest = unsent.books.length - names.length;
    lines.push(S.s_0_cuon_co_1_thay_doi_chua_gui_ve_2_se_mat_74fdd211(unsent.books.length, unsent.changes, device, names.join(", "), rest > 0 ? S.s_va_0_cuon_khac_718f50c0(rest) : ""));
    if (!unsent.sendable) {
      lines.push(S.s_0_khong_nhan_phan_sua_nhung_thay_doi_nay_c_e1132d7d(device, self));
    } else if (up) {
      send = S.s_gui_truoc_roi_bo_ghep_99e6d1f1;
    } else {
      send = S.s_thu_gui_truoc_roi_bo_ghep_f12544da;
      lines.push(S.s_0_dang_tat_hay_khac_mang_luc_nay_nen_chua_ebd45cfe(device));
    }
  }
  return { title: S.s_bo_ghep_0_e98b86ca(device), lines, send, sendPrimary: edited && up, discard: edited ? S.s_van_bo_ghep_bo_thay_doi_64cb2e74 : S.s_bo_ghep_64f921f9, cancel: S.s_giu_lai_3c3ba2db };
}
