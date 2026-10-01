// Soát số chương ở bước 1 của trình tạo sách (soát UX a6 01-10, B4): tải truyện về hay gặp chương trùng (hai file cùng
// "Chương 12"), thiếu chương (14 rồi 18), xếp lùi (chương 9 sau chương 10), và phần nối tiếp không bắt đầu đúng chương kế
// của phần trước. Máy chỉ NÓI ra - người dùng tự quyết bỏ / thêm file (không bao giờ tự sửa nguồn).

const NUMBER = /(?:chương|chuong|hồi|hoi|chapter|tiết|第)\s*0*(\d{1,5})/i;
const BARE = /^0*(\d{1,5})(?!\d)/;

/** Số chương đọc từ dòng đầu, rồi tên file ("0012 Chương 12.txt", "012.txt"); không có thì null. */
export function chapterNumber(firstLine: string, name: string): number | null {
  const found = NUMBER.exec(firstLine) ?? NUMBER.exec(name) ?? BARE.exec(name);
  return found ? Number(found[1]) : null;
}

export interface NumberedFile {
  name: string;
  firstLine: string;
}

export function chapterNumberIssues(files: NumberedFile[], previousLast?: string): string[] {
  const numbered = files.map((file) => ({ name: file.name, number: chapterNumber(file.firstLine, file.name) }));
  const known = numbered.filter((file): file is { name: string; number: number } => file.number !== null);
  // Ít hơn một nửa số file có số chương: truyện không đánh số (EPUB theo tên chương) - không đoán.
  if (known.length < 2 || known.length * 2 < files.length) return [];
  const issues: string[] = [];
  const seen = new Map<number, string[]>();
  for (const file of known) seen.set(file.number, [...(seen.get(file.number) ?? []), file.name]);
  const duplicates = [...seen.entries()].filter(([, names]) => names.length > 1);
  for (const [number, names] of duplicates.slice(0, 3)) {
    issues.push(`Chương ${number} có ${names.length} file (${names.slice(0, 3).join(", ")}) - giữ một, bỏ các file kia.`);
  }
  if (duplicates.length > 3) issues.push(`và ${duplicates.length - 3} số chương trùng khác.`);
  const backwards: string[] = [];
  const gaps: string[] = [];
  for (let index = 1; index < known.length; index += 1) {
    const before = known[index - 1].number;
    const here = known[index].number;
    if (here < before) backwards.push(`chương ${here} đứng sau chương ${before}`);
    else if (here > before + 1) gaps.push(here === before + 2 ? `chương ${before + 1}` : `chương ${before + 1}–${here - 1}`);
  }
  if (backwards.length) {
    issues.push(`Thứ tự lệch: ${backwards.slice(0, 3).join("; ")}${backwards.length > 3 ? `; và ${backwards.length - 3} chỗ khác` : ""} - tên file xếp khác số chương.`);
  }
  if (gaps.length) {
    issues.push(`Có vẻ thiếu ${gaps.slice(0, 4).join(", ")}${gaps.length > 4 ? ` và ${gaps.length - 4} khoảng khác` : ""}.`);
  }
  const last = previousLast ? chapterNumber(previousLast, previousLast) : null;
  const first = known[0].number;
  if (last !== null && first !== last + 1) {
    issues.push(
      first <= last
        ? `Phần trước đã làm tới chương ${last}, phần này lại bắt đầu từ chương ${first} - làm lại các chương đã có?`
        : `Phần trước dừng ở chương ${last}, phần này bắt đầu từ chương ${first} - thiếu chương ${last + 1}${first > last + 2 ? `–${first - 1}` : ""}.`,
    );
  }
  return issues;
}
