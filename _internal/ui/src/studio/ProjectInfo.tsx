import { Dialog } from "@/shared/ui";
import { formatClock, formatDate, formatRelative } from "@/shared/format";
import type { BookSummary } from "./api";
import { analyzerLabel, narratorLabel } from "./analyzerLabel";

/** Những điều về một dự án mà đầu trang không cần nói mỗi lần mở: giọng kể, chất lượng, model phân tích, ngày tạo, lần nghe cuối. Đầu trang chỉ giữ một dòng
 *  (trạng thái · số chương · độ dài); phần kỹ thuật như tên model nằm ở đây, không ở nơi người nghe lướt qua (soát 25-10). */
export function projectDetails(book: BookSummary): string[] {
  return [
    narratorLabel(book.settings),
    book.settings.profileLabel,
    // Model đã phân tích cuốn này - đổi model mặc định thì biết cuốn nào làm bằng model cũ.
    book.settings.analyzer ? analyzerLabel(book.settings.analyzer) : "",
    book.createdAt ? `Tạo ${formatDate(book.createdAt)}` : "",
    book.position ? `Nghe lần cuối ${formatRelative(book.position.at)} ở ${formatClock(book.position.seconds)}` : "",
  ].filter(Boolean);
}

export function ProjectInfoDialog({ book, open, onOpenChange }: { book: BookSummary; open: boolean; onOpenChange: (open: boolean) => void }) {
  const details = projectDetails(book);
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Chi tiết dự án" description={book.title}>
      <ul className="space-y-1.5 text-sm text-fg-2">
        {details.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </Dialog>
  );
}
