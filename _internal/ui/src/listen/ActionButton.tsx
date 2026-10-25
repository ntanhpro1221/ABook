import type { ButtonHTMLAttributes, ComponentType, ReactNode, Ref } from "react";
import { cn } from "@/shared/cn";
import { MotionRegion } from "@/shared/MotionRegion";

// Nút phụ có nhãn (docs/DESIGN.md mục 6b): biểu tượng trơn ở trên, nhãn nhỏ ở dưới - MỘT kiểu cho hàng phụ của trang sách (Đọc · Tìm · Từ đầu ·
// Thêm) và của trình phát (Tốc độ · Hẹn giờ · Chương). Không viền, không nền: chỉ nền nhạt khi rê / chạm, thu 0,97 khi nhấn.

type IconType = ComponentType<{ className?: string; strokeWidth?: number }>;

export const ACTION_BUTTON =
  "inline-flex min-h-[3.5rem] min-w-16 shrink-0 select-none flex-col items-center justify-center gap-1 rounded-lg px-2 py-1.5 transition-[transform,color,background-color,opacity] duration-motion-fast hover:bg-hover hover:text-fg active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40";
/** Ô biểu tượng: cao cố định để chữ thay biểu tượng ("1,15×") không làm nhãn dưới nhảy. */
export const ACTION_GLYPH = "inline-grid h-6 min-w-6 place-items-center text-[0.9375rem] font-semibold leading-none";
export const ACTION_LABEL = "tabular text-xs font-medium leading-none";

export function actionTone(active?: boolean): string {
  return active ? "text-accent-text" : "text-fg-2";
}

export function ActionButton({
  icon: Icon,
  label,
  glyph,
  glyphKey,
  active,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  ref?: Ref<HTMLButtonElement>;
  icon?: IconType;
  /** Nhãn thấy dưới biểu tượng (1-2 chữ). Tên đọc màn hình đặt bằng aria-label nếu cần nói thêm (phải chứa nhãn này). */
  label: ReactNode;
  /** Thay biểu tượng (vd "1,15×"). */
  glyph?: ReactNode;
  /** Chữ thay biểu tượng chỉ có số ("1,15×"): số không vào dấu đổi nội dung của MotionRegion - đưa giá trị làm khoá mờ chéo. */
  glyphKey?: unknown;
  active?: boolean;
}) {
  return (
    <button type="button" className={cn(ACTION_BUTTON, actionTone(active), className)} {...rest}>
      <MotionRegion as="span" aria-hidden className={ACTION_GLYPH} motionKey={glyphKey}>{glyph ?? (Icon ? <Icon className="size-5" strokeWidth={2} /> : null)}</MotionRegion>
      <MotionRegion as="span" className={ACTION_LABEL} motionKey={typeof label === "string" ? label : undefined}>{label}</MotionRegion>
    </button>
  );
}
