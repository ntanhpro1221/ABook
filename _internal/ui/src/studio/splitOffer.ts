// Đề xuất "Tách thành N chương" ở bước 1 của trình tạo sách (abook/webui/txt_split.py): chữ trước chương đầu chỉ là MỘT dòng tên truyện
// thì nó là tên sách chứ không phải một chương "Mở đầu" 4 chữ - nhưng chỉ khi nó trùng Tên sách đang điền; khác tên thì chữ ấy vẫn ở lại
// làm chương (app không bao giờ tự bỏ chữ của truyện).

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
  return { chapters: plan.chapters - (titleAsName ? 1 : 0), titleAsName, titleStays: Boolean(line) && !titleAsName };
}
