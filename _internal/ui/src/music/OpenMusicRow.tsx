import { DisclosureRow } from "../shared/DisclosureRow";
import { S } from "../shared/strings.generated";

/** Lối sang màn "Nhạc" ở những chỗ từng chứa "Nhạc của tôi" (Cài đặt › Nghe, Sửa sách, Studio › Nhạc nền): nhạc là nội dung, quản lý ở
 *  một chỗ (docs/DESIGN.md mục Nhạc), các chỗ cũ chỉ còn đường dẫn tới đó. */
export function OpenMusicRow({ className }: { className?: string }) {
  return <DisclosureRow to="/music" title={S.s_mo_nhac_c2f1b86b} summary={S.s_nhac_cua_toi_f65b7ac6} className={className} />;
}
