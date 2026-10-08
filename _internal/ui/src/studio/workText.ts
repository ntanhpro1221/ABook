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
  return text === "Vai phụ không tên" || text === "Người kể" ? text.charAt(0).toLowerCase() + text.slice(1) : text;
}

/** Tiêu đề thẻ người kể của đoạn sau khi đã quyết - nói KẾT QUẢ, không lặp tiền tố của nhãn ("Người kể: Mai" -> "Đoạn này do
 *  Mai kể", soát UX a8: từng ra "Đoạn này: Người kể: Mai kể"). */
export function narratorDecidedTitle(current: string, answer: string): string {
  if (answer === "Giữ nguyên") return `Đoạn này vẫn do ${current} kể`;
  if (answer === "Đổi người kể") return `Đoạn này không phải ${current} kể`;
  const name = answer.replace(/^Người kể:\s*/, "").trim();
  return `Đoạn này do ${name || answer} kể`;
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
    return answer === item.current ? `Giữ: “${item.surface}” đọc là “${answer}”` : `“${item.surface}” sẽ đọc là “${answer}”`;
  }
  if (item.voiceChoices?.length) return item.voiceChoices.find((choice) => choice.label === answer || choice.done === answer)?.done ?? null;
  if (item.kind === "alias") return `“${item.subject ?? item.current}” là ${midSentence(answer)}`;
  if (item.kind === "narrator") return narratorDecidedTitle(item.current, answer);
  if (item.lines?.length) return `${item.lines.length > 1 ? `${item.lines.length} câu này` : "Câu này"} của ${midSentence(answer)}`;
  return null;
}

/** Lời mở đầu của hộp việc theo trạng thái sách. Câu cuối KHÔNG nói "không phải dừng sách": sách đang dừng thì câu ấy tự mâu thuẫn
 *  với câu đầu (soát UX a8). */
export function inboxLead(book: { running: boolean; paused?: unknown; phase: string }): string {
  const first =
    book.running && book.paused
      ? "Sách đang tạm dừng - sửa bây giờ, máy áp khi làm tiếp."
      : book.running
        ? "Máy đã tự quyết và đang chạy tiếp - không có gì phải chờ."
        : book.phase === "done"
          ? "Sách đã xong - sửa xong thì bấm “Áp dụng thay đổi” ở trên để thu lại đúng các câu bị ảnh hưởng."
          : "Sách đang dừng - sửa bây giờ, máy áp khi làm tiếp.";
  return `${first} Đây là những chỗ máy không chắc, xếp theo lợi: việc ở trên sửa một lần được nhiều câu nhất. Cách đọc tên, người nói, giới và giọng nhân vật đều sửa ngay tại đây.`;
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
