import { S } from "../shared/strings.generated";
import { toast } from "@/shared/toast";

// Hai máy (hay hai cửa sổ) cùng sửa một chỗ: người nói của câu, cách đọc một tên, phán quyết "Nghe lại". Mỗi lần ghi gửi kèm `seen` - điều
// giao diện này đang thấy - và máy chủ trả `elsewhere` khi điều đang ghi đã khác (server `_edited_elsewhere`, `_reading_elsewhere`, post_review).
// Lần ghi vẫn vào, không bao giờ chặn; nhưng không được thay im lặng một lựa chọn mới hơn: hỏi giữ của mình hay lấy của máy kia (soát a23 B19,
// a27 lỗi 4).

/** Câu báo: `count` chỗ vừa được sửa ở nơi khác, `was` là điều nơi ấy đã đặt (nói bằng lời; "" = chưa ai quyết). */
export function elsewhereNote(count: number, was: string): { title: string; description: string } {
  return {
    title: count > 1 ? S.s_0_cau_vua_duoc_sua_o_may_hay_cua_so_khac_1f803269(count) : S.s_cho_nay_vua_duoc_sua_o_may_hay_cua_so_khac_66af9a6c,
    description: S.s_0_lan_ghi_cua_ban_da_thay_no_420a088b(was ? S.s_truoc_do_dang_la_0_4ed72a4f(was) : S.s_truoc_do_chua_ai_quyet_khac_1f656a59),
  };
}

/** Báo và hỏi: "Lấy của máy kia" chạy `takeTheirs` (hoàn tác lần ghi này, hay ghi lại điều máy kia đã đặt); bỏ qua thông báo thì giữ bản của bạn.
 *  Không có đường lấy lại (gộp tên đã ghi cả ở cấp tên) thì chỉ báo. */
export function warnElsewhere(count: number, was: string, takeTheirs?: () => void): void {
  const note = elsewhereNote(count, was);
  toast.warning(note.title, {
    id: "edited-elsewhere",
    duration: 20_000,
    description: note.description,
    // Giữ bản của bạn = để thông báo trôi đi (một nút duy nhất, không "Giữ bản của bạn").
    ...(takeTheirs ? { action: { label: S.s_lay_cua_may_kia_37d97780, onClick: takeTheirs } } : {}),
  });
}

/** `seen` gửi kèm lần ghi cho những câu của lần bấm: điều thẻ/màn này đang thấy cho từng câu (`known`; câu không có thì ""). */
export function seenFor(lines: readonly { stableId: string }[], known: Readonly<Record<string, string>> | undefined): Record<string, string> {
  return Object.fromEntries(lines.map((line) => [line.stableId, known?.[line.stableId] ?? ""]));
}

/** Cách đọc một câu như máy chủ so (`_line_elsewhere`): loại đoạn, cảm xúc, cường độ, chữ đem đọc. */
export interface SeenDelivery {
  kind: string;
  emotion: string;
  intensity: number | null;
  spoken?: string | null;
}

/** `seen` của lần sửa cách đọc một câu: cách đọc màn này đang thấy (bỏ trạng thái chờ/đã áp), null = chưa ai sửa câu này. */
export function seenDelivery(wish: SeenDelivery | null | undefined): SeenDelivery | null {
  if (!wish) return null;
  return { kind: wish.kind, emotion: wish.emotion, intensity: wish.intensity, ...(wish.spoken != null ? { spoken: wish.spoken } : {}) };
}

/** "Lấy của máy kia" cho cách đọc một câu: ghi lại đúng những gì máy kia đã đặt. null = máy kia không đặt gì - không có gì để lấy lại. */
export function theirDelivery(theirs: SeenDelivery | null): { kind?: string; emotion?: string; intensity?: number; spoken?: string } | null {
  if (!theirs) return null;
  const change = {
    ...(theirs.kind ? { kind: theirs.kind } : {}),
    ...(theirs.emotion ? { emotion: theirs.emotion } : {}),
    ...(theirs.intensity != null ? { intensity: theirs.intensity } : {}),
    ...(theirs.spoken != null ? { spoken: theirs.spoken } : {}),
  };
  return Object.keys(change).length ? change : null;
}

/** Phán quyết "Nghe lại" nói bằng lời ("" = chưa ai quyết). */
export function verdictWord(verdict: string | null | undefined): string {
  return verdict === "ok" ? S.s_on_742e24ad : verdict === "redo" ? S.s_can_thu_lai_9d482626 : "";
}

/** Lựa chọn giọng máy kia đã đặt cho nhân vật (`elsewhere` của POST /voice), nói bằng lời ("" = không có gì chờ). */
export function voiceWas(theirs: { voice: string; gender: string }): string {
  if (theirs.voice) return S.s_giong_0_e048b478(theirs.voice);
  return theirs.gender === "female" ? S.s_nhan_vat_nu_36236b63 : theirs.gender === "male" ? S.s_nhan_vat_nam_8de64942 : "";
}
