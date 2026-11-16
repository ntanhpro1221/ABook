import { cn } from "./cn";
import { middleEllipsis } from "./format";

/** Chỉ dùng cho thanh mini có chiều cao cố định, ghi lý do ngay tại chỗ gọi. Khổ điện thoại giữ đầu lẫn đuôi; từ `sm` dùng CSS.
 *  Tên đầy đủ luôn nằm ở tooltip. Các hàng khác dùng OneLineFit để thu cỡ rồi xuống dòng. */
export function ShortName({ name, short = 12, className }: { name: string; short?: number; className?: string }) {
  return (
    <span className={cn("min-w-0", className)} title={name}>
      <span className="sm:hidden">{middleEllipsis(name, short)}</span>
      <span className="hidden truncate sm:inline">{name}</span>
    </span>
  );
}
