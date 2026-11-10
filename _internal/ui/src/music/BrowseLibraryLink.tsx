import { ChevronRight } from "lucide-react";
import { Link } from "react-router";
import { cn } from "../shared/cn";
import { S } from "../shared/strings.generated";

/** "Xem cả kho ›" ở cuối "Đổi bài" (Sửa sách, Studio › Nhạc nền): mở màn Nhạc ở chế độ chọn cho đúng đoạn này - "Dùng" ghim bài như
 *  "Chọn" trong danh sách gợi ý. Đi sang trang khác nên mũi tên phải là đúng (test_toggle_chevron). */
export function BrowseLibraryLink({ bookId, scene, className }: { bookId: string; scene: string; className?: string }) {
  return (
    <Link to={`/music?pick=${encodeURIComponent(bookId)}&scene=${encodeURIComponent(scene)}`} className={cn("inline-flex min-h-10 items-center gap-1 text-sm font-medium text-accent-text", className)}>
      {S.s_xem_ca_kho_fa30b353}<ChevronRight aria-hidden className="size-4" />
    </Link>
  );
}
