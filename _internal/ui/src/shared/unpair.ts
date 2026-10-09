// Gỡ ghép một máy khi còn sửa chưa gửi (docs/EDITING.md, P2d): thôi ghép xoá thư mục các cuốn nghe thẳng của máy ấy, và phần sửa
// của người nghe nằm trong đó - nên hỏi trước, nói bằng lời người nghe nhận ra. Dùng chung cho điện thoại (Peers.kt) và máy tính
// (webui/remote_books.py).

/** Phần sửa chưa gửi của các cuốn của một máy (`peerUnsent` trên điện thoại, `GET /api/computers/<id>/unsent` trên máy tính). */
export interface UnsentEdits {
  books: { title: string; changes: number }[];
  /** Tổng số thay đổi của mọi cuốn. */
  changes: number;
  /** Máy kia nhận được phần sửa (là máy tính): "Gửi trước" có nghĩa. Điện thoại khác không nhận sửa. */
  sendable: boolean;
}

export type UnpairChoice = "send" | "discard";

export interface UnpairCopy {
  title: string;
  /** Mỗi ý một dòng: cái gì sẽ mất, và vì sao không gửi được nếu có. */
  lines: string[];
  /** Nhãn nút "gửi trước rồi gỡ"; null khi không gửi được lúc này. */
  send: string | null;
  discard: string;
  cancel: string;
}

/** `self`: máy đang cầm sửa ("điện thoại" hay "máy tính"); `reachable`: máy kia đang trả lời. `null` khi không còn sửa nào - gỡ như thường. */
export function unpairCopy(device: string, self: "điện thoại" | "máy tính", unsent: UnsentEdits | null | undefined, reachable: boolean): UnpairCopy | null {
  if (!unsent || unsent.changes <= 0 || unsent.books.length === 0) return null;
  const names = unsent.books.slice(0, 3).map((book) => `“${book.title}”`);
  const rest = unsent.books.length - names.length;
  const lines = [`${unsent.books.length} cuốn có ${unsent.changes} thay đổi chưa gửi về ${device} sẽ mất: ${names.join(", ")}${rest > 0 ? ` và ${rest} cuốn khác` : ""}.`];
  let send: string | null = null;
  if (!unsent.sendable) {
    lines.push(`${device} không nhận phần sửa - những thay đổi này chỉ có trên ${self} này.`);
  } else if (reachable) {
    send = "Gửi trước rồi gỡ";
  } else {
    lines.push(`Chưa tới được ${device} lúc này nên chưa gửi được - mở lại khi cùng mạng với máy ấy.`);
  }
  return { title: `Gỡ ghép ${device}?`, lines, send, discard: "Vẫn gỡ, bỏ thay đổi", cancel: "Huỷ" };
}
