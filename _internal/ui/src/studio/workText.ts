import { S } from "../shared/strings.generated";
// Chữ của hộp "Việc cần duyệt" tách khỏi giao diện để kiểm bằng test (soát UX a8 07-10): tiêu đề thẻ đã quyết, lời mở đầu theo
// trạng thái sách, và các câu nói về tên trùng / nghe thử. Không đụng chữ truyện - chỉ chữ của chính Studio.

/** Chữ đầu viết hoa - "câu này" đứng đầu câu báo. */
export function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Nhãn nút ("Vai phụ không tên", "Người kể") đứng GIỮA câu thì viết thường chữ đầu - "…của vai phụ không tên" (soát UX
 *  29-09). Tên người giữ nguyên. */
export function midSentence(label: string | null | undefined): string {
  const text = label ?? "";
  return text === S.s_vai_phu_khong_ten_6395f0d2 || text === S.s_nguoi_ke_fd36cd15 ? text.charAt(0).toLowerCase() + text.slice(1) : text;
}

/** Tiêu đề thẻ người kể của đoạn sau khi đã quyết - nói KẾT QUẢ, không lặp tiền tố của nhãn ("Người kể: Mai" -> "Đoạn này do
 *  Mai kể", soát UX a8: từng ra "Đoạn này: Người kể: Mai kể"). */
export function narratorDecidedTitle(current: string, answer: string): string {
  if (answer === S.s_giu_nguyen_1b550a12) return current ? S.s_doan_nay_van_do_0_ke_1aa31bd2(current) : S.s_doan_nay_van_ke_o_ngoi_thu_ba_ad31af6d;
  if (answer === S.s_doi_nguoi_ke_ddc42796) return S.s_doan_nay_khong_phai_0_ke_691681b8(current);
  const name = answer.replace(/^Người kể:\s*/, "").trim();
  return S.s_doan_nay_do_0_ke_9870e5f7(name || answer);
}

/** Hai nút đầu của thẻ người kể của đoạn, và lựa chọn đã ghi (`requested`) ứng với nút nhận. `current`: người kể máy đang dùng
 *  ("" = chương kể ngôi thứ ba); `heading`: đoạn mở bằng dòng tiêu đề góc nhìn ("Góc nhìn của Mai") - nút nhận nói đúng tên ấy. */
export function narratorButtons(current: string, heading?: { label: string } | null): { accept: string; keep: string; accepted: string } {
  const keep = current ? S.s_giu_0_b8c06ffa(current) : S.s_giu_ngoi_thu_ba_271d46cb;
  if (!heading) return { accept: S.s_ke_ngoi_thu_ba_3ba8b1e4, keep, accepted: S.s_doi_nguoi_ke_ddc42796 };
  return heading.label
    ? { accept: S.s_0_ke_d684eff0(heading.label), keep, accepted: S.s_nguoi_ke_0_78e70db0(heading.label) }
    : { accept: S.s_ke_ngoi_thu_ba_3ba8b1e4, keep, accepted: S.s_doi_nguoi_ke_ddc42796 };
}

/** Phần của thẻ việc mà tiêu đề đã quyết cần. */
export interface DecidedLike {
  kind: string;
  requested?: string | null;
  current: string;
  surface?: string;
  subject?: string;
  lines?: unknown[];
  voiceChoices?: { label: string; done?: string }[];
}

/** Thẻ đã quyết nói KẾT QUẢ thay vì lặp câu hỏi ("Đọc “Arcanist” là…?" khi đã giữ - soát UX 29-09); null = giữ tiêu đề. */
export function decidedTitle(item: DecidedLike): string | null {
  const answer = item.requested;
  if (!answer) return null;
  if (item.kind === "pronunciation" && item.surface) {
    return answer === item.current ? S.s_giu_0_doc_la_1_f568ced8(item.surface, answer) : S.s_0_se_doc_la_1_e0b21c39(item.surface, answer);
  }
  if (item.voiceChoices?.length) return item.voiceChoices.find((choice) => choice.label === answer || choice.done === answer)?.done ?? null;
  if (item.kind === "alias") return S.s_0_la_1_9ee6c344(item.subject ?? item.current, midSentence(answer));
  if (item.kind === "narrator") return narratorDecidedTitle(item.current, answer);
  if (item.lines?.length) return S.s_0_cua_1_c0e3e388(item.lines.length > 1 ? S.s_0_cau_nay_eeb40df6(item.lines.length) : S.s_cau_nay_ee66e104, midSentence(answer));
  return null;
}

/** Lời mở đầu của hộp việc theo trạng thái sách. Câu cuối KHÔNG nói "không phải dừng sách": sách đang dừng thì câu ấy tự mâu thuẫn
 *  với câu đầu (soát UX a8). */
export function inboxLead(book: { running: boolean; paused?: unknown; phase: string }): string {
  const first =
    book.running && book.paused
      ? S.s_sach_dang_tam_dung_sua_ap_khi_lam_tiep_12a374a4
      : book.running
        ? S.s_may_dang_chay_tiep_sua_ap_o_chuong_sau_5482c856
        : book.phase === "done"
          ? S.s_sua_xong_bam_ap_dung_thay_doi_43042cc6
          : S.s_sach_dang_dung_sua_ap_khi_lam_tiep_9778f9fd;
  return S.s_uu_tien_viec_tren_0_c06ed70f(first);
}

/** Câu lời kể chia thành mảnh thường / mảnh tô (`mark`) ở mỗi chỗ có một trong `names` (dạng tên đã hạ chữ, work_items gửi kèm
 *  câu): nguyên chữ, không phân biệt hoa thường, tên dài trước - thẻ "Người này có phải X?" tô tên ứng viên quanh câu được hỏi. */
export function markNames(text: string, names?: string[]): { text: string; mark: boolean }[] {
  const forms = [...new Set((names ?? []).map((name) => name.trim()).filter(Boolean))].sort((a, b) => b.length - a.length);
  if (!forms.length) return [{ text, mark: false }];
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}])(?:${forms.map((form) => form.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})(?![\\p{L}\\p{N}])`, "giu");
  const parts: { text: string; mark: boolean }[] = [];
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), mark: false });
    parts.push({ text: match[0], mark: true });
    last = match.index + match[0].length;
  }
  if (last < text.length || !parts.length) parts.push({ text: text.slice(last), mark: false });
  return parts;
}

/** Tên hiển thị trùng nhau (ba “Lính gác”): khoá so sánh - bỏ gạch dưới, dấu cách thừa, hoa thường. */
export function nameKey(name: string): string {
  return name.replace(/_/g, " ").replace(/\s+/g, " ").trim().toLocaleLowerCase("vi");
}

/** Những tên xuất hiện ở từ hai dòng trở lên trong danh sách nhân vật - dòng mang tên ấy hỏi "cùng tên - một người?". */
export function sameNames(people: { displayName: string }[]): Set<string> {
  const seen = new Map<string, number>();
  for (const person of people) {
    const key = nameKey(person.displayName);
    if (key) seen.set(key, (seen.get(key) ?? 0) + 1);
  }
  return new Set([...seen].filter(([, count]) => count > 1).map(([key]) => key));
}
