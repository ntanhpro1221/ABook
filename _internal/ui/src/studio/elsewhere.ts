import { toast } from "sonner";

// Hai máy (hay hai cửa sổ) cùng sửa một chỗ: người nói của câu, cách đọc một tên, phán quyết "Nghe lại". Mỗi lần ghi gửi kèm `seen` - điều
// giao diện này đang thấy - và máy chủ trả `elsewhere` khi điều đang ghi đã khác (server `_edited_elsewhere`, `_reading_elsewhere`, post_review).
// Lần ghi vẫn vào, không bao giờ chặn; nhưng không được thay im lặng một lựa chọn mới hơn: hỏi giữ của mình hay lấy của máy kia (soát a23 B19,
// a27 lỗi 4).

/** Câu báo: `count` chỗ vừa được sửa ở nơi khác, `was` là điều nơi ấy đã đặt (nói bằng lời; "" = chưa ai quyết). */
export function elsewhereNote(count: number, was: string): { title: string; description: string } {
  return {
    title: count > 1 ? `${count} câu vừa được sửa ở máy hay cửa sổ khác` : "Chỗ này vừa được sửa ở máy hay cửa sổ khác",
    description: `${was ? `Trước đó đang là ${was}` : "Trước đó chưa ai quyết khác"} - lần ghi của bạn đã thay nó.`,
  };
}

/** Báo và hỏi: "Lấy của máy kia" chạy `takeTheirs` (hoàn tác lần ghi này, hay ghi lại điều máy kia đã đặt); "Giữ của tôi" để nguyên.
 *  Không có đường lấy lại (gộp tên đã ghi cả ở cấp tên) thì chỉ báo. */
export function warnElsewhere(count: number, was: string, takeTheirs?: () => void): void {
  const note = elsewhereNote(count, was);
  toast.warning(note.title, {
    id: "edited-elsewhere",
    duration: 20_000,
    description: note.description,
    ...(takeTheirs
      ? { action: { label: "Lấy của máy kia", onClick: takeTheirs }, cancel: { label: "Giữ của tôi", onClick: () => undefined } }
      : {}),
  });
}

/** `seen` gửi kèm lần ghi cho những câu của lần bấm: điều thẻ/màn này đang thấy cho từng câu (`known`; câu không có thì ""). */
export function seenFor(lines: readonly { stableId: string }[], known: Readonly<Record<string, string>> | undefined): Record<string, string> {
  return Object.fromEntries(lines.map((line) => [line.stableId, known?.[line.stableId] ?? ""]));
}
