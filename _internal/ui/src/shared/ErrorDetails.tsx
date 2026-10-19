import { cn } from "./cn";

/** "Chi tiết" thu gọn dưới một lời báo lỗi: nguyên văn lỗi kỹ thuật để gửi cho người hỗ trợ, người dùng không phải đọc (soát a64: hộp Thêm sách,
 *  a66: lỗi tải giọng / mô-đun). Không có gì thì không hiện. */
export function ErrorDetails({ technical, className }: { technical?: string; className?: string }) {
  if (!technical) return null;
  return (
    <details className={cn("mt-1 text-xs", className)}>
      <summary className="cursor-pointer select-none">Chi tiết</summary>
      <p className="mt-1 select-text break-words font-mono">{technical}</p>
    </details>
  );
}
