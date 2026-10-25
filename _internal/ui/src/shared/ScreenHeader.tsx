// Đầu màn dùng chung mọi màn gốc và màn con, cả điện thoại lẫn máy tính (soát 25-10: chân chữ tiêu đề Thư viện / Studio / Cài đặt
// điện thoại 54 / 46 / 40, máy tính 28-32 px tuỳ màn, ba kiểu nút quay lại). Một chỗ quyết đệm trên, cỡ tiêu đề, hàng tiêu đề, dòng phụ,
// nút ← và khe nút phải - đổi tab đáy thì tiêu đề đứng yên, màn con có tiêu đề cùng chân chữ với màn gốc.
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { MotionRegion } from "./MotionRegion";
import { cn } from "./cn";

/** Cỡ tiêu đề màn (DESIGN 5.5: 24 điện thoại / 32 máy tính). Tiêu đề nằm trong nội dung (tên sách cạnh bìa, tên dự án) dùng chung cỡ này. */
export const SCREEN_TITLE = "text-2xl font-bold tracking-tight sm:text-[2rem]";

/** Nút ← của màn con: một kiểu cho mọi màn (Cài đặt con, trang sách, dự án, đọc theo). Nét mũi tên thẳng mép nội dung, vùng chạm 48 / 40. */
export function BackButton({ label, onClick, className }: { label: string; onClick: () => void; className?: string }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} title={label} className={cn("back-button rounded-lg text-fg-2 transition-colors hover:text-fg", className)}>
      <ArrowLeft className="size-[20px]" aria-hidden />
    </button>
  );
}

/** Đầu màn. `back`: màn con - nút ← đứng trước tiêu đề (không có tiêu đề thì đứng riêng một hàng, như trang sách: tên nằm cạnh bìa).
 *  `subtitle`: một dòng phụ ngay dưới hàng tiêu đề (số cuốn, số dự án); `subtitleKey` đổi thì dòng ấy mờ chéo. `actions`: khe nút bên phải,
 *  căn giữa theo hàng tiêu đề; chỗ gọi tự bù đệm của nút cho chữ thẳng mép phải. */
export function ScreenHeader({ title, back, subtitle, subtitleKey, actions, className }: {
  title?: ReactNode;
  back?: { label: string; onClick: () => void };
  subtitle?: ReactNode;
  subtitleKey?: unknown;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header data-screen-header="" className={cn("pt-[12px] sm:pt-[32px]", className)}>
      {/* Hàng cao cố định 48 / 40 (bằng nút chạm / nút chuột): có nút phải hay nút ← hay không, chân chữ tiêu đề vẫn ở một chỗ. Nút phải
          không bóp tiêu đề thành hai dòng ở màn hẹp: tiêu đề giữ một dòng, nút xuống dưới (soát UX 05-10). */}
      <div className="flex min-h-[48px] flex-wrap items-center justify-between gap-x-4 gap-y-3 sm:min-h-[40px]">
        {(back || title !== undefined) && (
          <div className={cn("flex items-center", back ? "min-w-0 flex-1" : "shrink-0")}>
            {back && <BackButton label={back.label} onClick={back.onClick} />}
            {title !== undefined && (
              <h1 data-screen-title={back ? "child" : "root"} className={cn(SCREEN_TITLE, "leading-[32px] sm:leading-[40px]", back ? "min-w-0 [overflow-wrap:anywhere]" : "whitespace-nowrap")}>
                {title}
              </h1>
            )}
          </div>
        )}
        {actions}
      </div>
      {subtitle !== undefined && (
        <MotionRegion as="p" motionKey={subtitleKey} className="mt-[4px] text-sm text-fg-2">
          {subtitle}
        </MotionRegion>
      )}
    </header>
  );
}
