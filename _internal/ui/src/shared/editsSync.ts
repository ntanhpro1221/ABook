import { formatWhen } from "./format";

// Phần sửa của cuốn tải từ máy tính được gửi về máy tính (docs/EDITING.md, P2b; EditsSync.kt trên điện thoại, webui/edits_inbox.py
// trên máy tính). Giao diện chỉ nói tình trạng bằng lời người nghe nhận ra: chưa gửi, đã gửi, máy tính đã làm gì với nó.

/** Kết quả lần gửi gần nhất (EditsSync.kt). `error` có khi `state` là "error". */
export interface EditsSyncLast {
  state: "sent" | "error";
  at: number;
  error?: string;
  /** Sửa "áp ngay" máy tính đã áp. */
  applied?: number;
  /** Sửa không còn chỗ trên máy tính (nhân vật / chương đã không còn...) - bị bỏ qua. */
  skipped?: number;
  /** Ý muốn chờ Studio đã thành yêu cầu thật (thiết bị được điều khiển sản xuất từ xa). */
  requests?: number;
  /** Ý muốn đang nằm trong hộp thư chờ duyệt trên máy tính. */
  waiting?: number;
  skippedWishes?: number;
  /** Khoá chủ máy đã đổi từ lần trước: bản gửi từ điện thoại vẫn thắng, nhưng người dùng được báo. */
  conflicts?: string[];
}

export interface EditsSyncState {
  /** Số thay đổi CHƯA gửi (gửi xong là gỡ khỏi lớp sửa của điện thoại). */
  pending: number;
  last: EditsSyncLast | null;
}

export type EditsSyncTone = "pending" | "error" | "sent";

export interface EditsSyncNote {
  tone: EditsSyncTone;
  title: string;
  /** Từng điều máy tính đã làm / còn chờ - mỗi điều một dòng. */
  lines: string[];
}

/** Tên máy giữ sách để nói trong lời báo: máy tính khác thì tên thật của nó (hai máy đều là máy tính, "máy tính" không nói máy nào), không thì "máy tính". */
export function holderName(remote: boolean | { computer: string } | undefined): string {
  return typeof remote === "object" && remote.computer ? remote.computer : "máy tính";
}

/** Điều đáng nói về một cuốn tải từ máy tính: chưa gửi (kèm lý do nếu lần gửi trước hỏng), hay đã gửi và máy tính đã làm gì.
 *  `where`: tên máy giữ sách (`holderName`). `null` khi chưa có gì để nói (chưa sửa gì, chưa gửi bao giờ). */
export function editsSyncNote(state: EditsSyncState | null | undefined, where = "máy tính"): EditsSyncNote | null {
  if (!state) return null;
  const { pending, last } = state;
  if (pending > 0) {
    if (last?.state === "error") {
      return { tone: "error", title: `${pending} thay đổi chưa gửi về ${where}`, lines: [last.error ?? "Chưa gửi được - sẽ thử lại."] };
    }
    return {
      tone: "pending",
      title: `${pending} thay đổi đang chờ gửi về ${where}`,
      lines: [`Tự gửi khi tới được ${where}; bấm “Gửi về ${where}” để gửi ngay.`],
    };
  }
  if (last?.state !== "sent") return null;
  const lines: string[] = [];
  if (last.applied) lines.push(`${last.applied} thay đổi đã áp trên ${where}`);
  if (last.requests) lines.push(`${last.requests} việc đã thành yêu cầu trên ${where}, chờ áp dụng ở Studio`);
  if (last.waiting) lines.push(`${last.waiting} việc đang chờ duyệt trên ${where} - chưa làm gì cho tới khi bạn đồng ý trên ${where}`);
  const skipped = (last.skipped ?? 0) + (last.skippedWishes ?? 0);
  if (skipped) lines.push(`${skipped} thay đổi không còn chỗ trong sách trên ${where} nên bị bỏ qua`);
  lines.push(...(last.conflicts ?? []));
  return { tone: "sent", title: `Đã gửi về ${where} ${formatWhen(last.at)}`.trim(), lines };
}

/** Thông báo ngay sau khi bấm Gửi: nói điều vừa xảy ra, không lặp lời dặn "tự gửi khi..." của dòng tình trạng (soát UX a11). */
export function sentToast(state: EditsSyncState, where = "máy tính"): { title: string; description?: string } {
  const description =
    state.pending > 0
      ? `Còn ${state.pending} thay đổi chưa gửi được - sẽ thử lại khi tới được ${where}.`
      : editsSyncNote({ ...state, pending: 0 }, where)?.lines.join(" · ") || undefined;
  return { title: `Đã gửi về ${where}`, description };
}
