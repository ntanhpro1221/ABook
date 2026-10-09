// Gỡ ghép một máy (docs/EDITING.md, P2d): thôi ghép xoá thư mục các cuốn nghe thẳng của máy ấy - phần đã tải và phần sửa chưa gửi
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
  /** Cái máy này sẽ quên khi thôi ghép: số cuốn của máy kia, byte đã tải về, số cuốn đang có chỗ nghe / dấu trang (những chỗ ấy giữ lại). */
  cache?: { books: number; bytes: number; places: number };
}

export type UnpairChoice = "send" | "discard";

export interface UnpairCopy {
  title: string;
  /** Mỗi ý một dòng: cái gì sẽ mất, và vì sao không gửi được nếu có. */
  lines: string[];
  /** Nhãn nút "gửi trước rồi gỡ"; null khi máy kia không nhận sửa. */
  send: string | null;
  /** Máy kia đang trả lời: "gửi trước" là nút chính. Máy kia tắt thì nút vẫn có (thử lại được) nhưng không là nút chính - nút chính là Huỷ. */
  sendPrimary: boolean;
  discard: string;
  cancel: string;
}

/** Lời báo (toast) sau khi gỡ ghép - cả khi không phải hỏi gì: máy đã rời Thư viện, và chỗ nghe còn giữ nếu có. */
export function unpairDone(device: string, unsent: UnsentEdits | null | undefined): { title: string; description: string } {
  const places = unsent?.cache?.places ?? 0;
  return {
    title: `Đã thôi ghép ${device}`,
    description: `Sách của máy ấy không còn trong Thư viện.${places > 0 ? " Chỗ nghe và dấu trang vẫn giữ - ghép lại là nghe tiếp được." : ""}`,
  };
}

/** `self`: máy đang cầm sửa ("điện thoại" hay "máy tính"); `reachable`: máy kia đang trả lời. `null` khi không còn gì để mất - gỡ như thường. */
export function unpairCopy(device: string, self: "điện thoại" | "máy tính", unsent: UnsentEdits | null | undefined, reachable: boolean): UnpairCopy | null {
  const edited = !!unsent && unsent.changes > 0 && unsent.books.length > 0;
  const cache = unsent?.cache && unsent.cache.books > 0 ? unsent.cache : null;
  if (!unsent || (!edited && !cache)) return null;
  const lines: string[] = [];
  if (cache) {
    const downloaded = cache.bytes > 0 ? `, và ${cache.bytes < 1024 ** 2 ? "dưới 1 MB" : formatSize(cache.bytes)} đã tải về ${self} này sẽ bị xoá` : "";
    lines.push(`${cache.books} cuốn của ${device} sẽ rời Thư viện${downloaded}.`);
    if (cache.places > 0) lines.push(`Chỗ nghe và dấu trang của ${cache.places} cuốn vẫn giữ - ghép lại đúng ${device} là nghe tiếp được.`);
  }
  let send: string | null = null;
  const up = unsent.reachable ?? reachable;
  if (edited) {
    const names = unsent.books.slice(0, 3).map((book) => `“${book.title}”`);
    const rest = unsent.books.length - names.length;
    lines.push(`${unsent.books.length} cuốn có ${unsent.changes} thay đổi chưa gửi về ${device} sẽ mất: ${names.join(", ")}${rest > 0 ? ` và ${rest} cuốn khác` : ""}.`);
    if (!unsent.sendable) {
      lines.push(`${device} không nhận phần sửa - những thay đổi này chỉ có trên ${self} này.`);
    } else if (up) {
      send = "Gửi trước rồi gỡ";
    } else {
      send = "Thử gửi trước rồi gỡ";
      lines.push(`${device} đang tắt hay khác mạng lúc này nên chưa gửi được - mở máy ấy rồi gửi, hay bỏ thay đổi.`);
    }
  }
  return { title: `Gỡ ghép ${device}?`, lines, send, sendPrimary: edited && up, discard: edited ? "Vẫn gỡ, bỏ thay đổi" : "Thôi ghép", cancel: "Huỷ" };
}
