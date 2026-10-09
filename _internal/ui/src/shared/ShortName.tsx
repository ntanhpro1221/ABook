import { cn } from "./cn";
import { middleEllipsis } from "./format";

/** Tên máy trong chỗ hẹp: ở khổ điện thoại rút giữ cả đầu lẫn đuôi ("NGDtu…Lecoo" - tên máy hay chung đầu, chỗ phân biệt nằm ở đuôi), từ `sm` trở lên cắt bằng
 *  CSS như thường. Tên đầy đủ luôn nằm ở tooltip. */
export function ShortName({ name, short = 12, className }: { name: string; short?: number; className?: string }) {
  return (
    <span className={cn("min-w-0", className)} title={name}>
      <span className="sm:hidden">{middleEllipsis(name, short)}</span>
      <span className="hidden truncate sm:inline">{name}</span>
    </span>
  );
}
