import type { ReactNode } from "react";
import { cn } from "@/shared/cn";

/** Các mẩu nối bằng dấu "·", chỉ xuống dòng giữa hai mẩu, và dấu của mẩu đứng đầu một dòng không hiện: không "Giọng Ngọc Lan ·" treo cuối
 * dòng, không "· 4 giờ 40 phút" đứng đầu dòng (audit140 C7). Dấu là lớp giả trước mỗi mẩu; hàng lùi trái đúng bề rộng một dấu và khung cắt phần
 * lùi ấy, nên dấu của mẩu mở đầu dòng nằm ngoài khung (styles.css `.dot-join`). Mẩu dài vẫn tự xuống dòng bên trong. */
export function DotJoin({ parts, className }: { parts: ReactNode[]; className?: string }) {
  const shown = parts.filter((part) => part !== false && part !== null && part !== undefined && part !== "");
  return (
    <span className={cn("dot-join", className)}>
      <span>{shown.map((part, index) => <span key={index}>{part}</span>)}</span>
    </span>
  );
}

/** Chữ liền có sẵn dấu " · " (tên sách "Sương Mù · Tập 2" trong tiêu đề hộp thoại, thông báo): khoảng trắng hai bên dấu thành khoảng không
 * ngắt để dấu không đứng đầu hay cuối dòng. Chỉ đổi cách hiện, không đổi chữ của sách. */
export function keepDots<T extends ReactNode>(text: T): T | string {
  return typeof text === "string" ? text.replace(/ · /g, " · ") : text;
}
