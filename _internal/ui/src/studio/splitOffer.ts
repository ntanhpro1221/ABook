// Đề xuất chia TXT: tên sách là metadata; phần mở đầu luôn còn trong số chương và chữ của sách.

/** Hai tên sách là một: không phân biệt hoa thường, khoảng trắng thừa, dạng dấu (txt_split.same_title). */
export function sameTitle(a: string, b: string): boolean {
  const norm = (text: string) => text.normalize("NFC").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
  return norm(a) !== "" && norm(a) === norm(b);
}

export interface SplitPlan {
  chapters: number;
  preamble: boolean;
  titleLine?: string;
}

/** Số chương sẽ ra và số phận dòng tên truyện đầu file, với Tên sách `title` đang điền. */
export function splitOutcome(plan: SplitPlan, title: string): { chapters: number; titleAsName: boolean; titleStays: boolean } {
  const line = plan.titleLine ?? "";
  const titleAsName = Boolean(line) && sameTitle(line, title);
  return { chapters: plan.chapters, titleAsName, titleStays: Boolean(line) };
}
