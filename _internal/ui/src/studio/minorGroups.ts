// Thẻ "vai phụ không tên cả cuốn" (webui/work_items.py mục 5): mọi câu của một nhãn vai ở nhiều chương, người nghe bỏ chọn
// câu nào không phải rồi chọn người một lần. Phần tính ở đây, không đụng giao diện - để thử được bằng vitest.

export interface LineRef {
  stableId: string;
  textSha256: string;
}

/** Một yêu cầu POST /speaker: các câu và người nói của chúng. */
export interface SpeakerRequest {
  lines: LineRef[];
  speaker: string;
}

export interface KeepableItem {
  lines?: LineRef[];
  currentValue?: string;
  /** Thẻ nhóm: mỗi vai giữ người của nó - một yêu cầu cho mỗi vai. */
  keepGroups?: SpeakerRequest[];
}

/** Câu còn được chọn (giữ thứ tự của thẻ). */
export function pickedLines(lines: LineRef[], left: ReadonlySet<string>): LineRef[] {
  return lines.filter((line) => !left.has(line.stableId));
}

/** Bật / tắt một câu: trả tập mới (state React không sửa tại chỗ). */
export function toggleLine(left: ReadonlySet<string>, stableId: string): Set<string> {
  const next = new Set(left);
  if (next.has(stableId)) next.delete(stableId);
  else next.add(stableId);
  return next;
}

/** "Giữ nguyên" một thẻ là những yêu cầu nào: thẻ thường giữ người đang nói cho mọi câu; thẻ nhóm giữ người của từng vai.
 *  Thẻ không giữ được (không có người đang nói) thì rỗng. */
export function keepRequests(item: KeepableItem): SpeakerRequest[] {
  if (item.keepGroups?.length) return item.keepGroups.filter((group) => group.lines.length > 0);
  if (item.lines?.length && item.currentValue) return [{ lines: item.lines, speaker: item.currentValue }];
  return [];
}

/** Dòng nói đang chọn bao nhiêu câu, cho thẻ nhóm. */
export function pickNote(picked: number, total: number): string {
  if (picked === total) return `Đang chọn cả ${total} câu`;
  if (picked === 0) return `Chưa chọn câu nào trong ${total} câu`;
  return `Đang chọn ${picked}/${total} câu`;
}
