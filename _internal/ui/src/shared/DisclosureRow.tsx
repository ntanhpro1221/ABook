import { ChevronRight } from "lucide-react";
import { Link, type LinkProps } from "react-router";
import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";
import { cn } from "./cn";
import { MotionRegion } from "./MotionRegion";

/** Một hàng cho cả đi tới và gập mở: mũi tên luôn neo mép phải của cột. */
export function DisclosureRow({ title, summary, icon, expanded, controls, onClick, to, replace, state, current, section, className, ref, ...rest }: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "title"> & {
  title: ReactNode; summary?: ReactNode; icon?: ReactNode; expanded?: boolean; controls?: string;
  onClick?: () => void; to?: LinkProps["to"]; replace?: boolean; state?: LinkProps["state"]; current?: boolean; section?: boolean; className?: string; ref?: Ref<HTMLButtonElement>;
}) {
  const body = <>
    {icon && <span className={cn("shrink-0", current ? "text-fg" : "text-fg-2")} aria-hidden>{icon}</span>}
    <span className="min-w-0 flex-1">
      <span data-section-title={section ? "" : undefined} className={cn(section ? "block section-title [overflow-wrap:anywhere]" : "block text-base [overflow-wrap:anywhere]", !section && (current ? "font-semibold" : "font-medium"))}>{title}</span>
      <MotionRegion as="span" className="block text-sm font-normal text-fg-2" motionKey={typeof summary === "string" || typeof summary === "number" ? summary : undefined}>{summary}</MotionRegion>
    </span>
    <ChevronRight className={cn("disclosure-chevron ink-end [--icon-w:14px] size-4 shrink-0 text-fg-3", expanded && "rotate-90")} aria-hidden />
  </>;
  // Mục đang mở của danh sách nhóm là điều hướng (DESIGN 6 "Điều hướng"): nền trung tính nhạt + chữ đậm màu thường, như thanh bên.
  // Nền (rê chuột, đang mở) vẽ ở lớp ::before tràn 12 px ra hai bên: chữ và icon không dính mép nền mà bố cục hàng không đổi - lùi lề
  // âm trên chính hàng kéo chữ theo ở hàng có className riêng (máy dò FILL INSET, Studio 25-10).
  const rowClass = cn("disclosure-row relative isolate flex min-h-[3.5rem] w-full items-center gap-3.5 text-left before:absolute before:inset-y-0 before:-inset-x-3 before:-z-10 before:rounded-lg before:transition-colors hover:before:bg-hover", section ? "py-0" : "py-1.5", current && "text-fg before:bg-hover", className);
  return to !== undefined ? <Link to={to} replace={replace} state={state} aria-current={current ? "page" : undefined} className={rowClass}>{body}</Link>
    : <button {...rest} ref={ref} data-section-heading={section ? "" : undefined} type="button" aria-expanded={expanded} aria-controls={controls} onClick={onClick} className={rowClass}>{body}</button>;
}
