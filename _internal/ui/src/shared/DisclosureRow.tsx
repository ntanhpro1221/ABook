import { ChevronRight } from "lucide-react";
import { Link, type LinkProps } from "react-router";
import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";
import { cn } from "./cn";
import { MotionRegion } from "./MotionRegion";

/** Một hàng cho cả đi tới và gập mở: mũi tên luôn neo mép phải của cột. */
export function DisclosureRow({ title, summary, icon, expanded, controls, onClick, to, replace, state, current, className, ref, ...rest }: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "title"> & {
  title: ReactNode; summary?: ReactNode; icon?: ReactNode; expanded?: boolean; controls?: string;
  onClick?: () => void; to?: LinkProps["to"]; replace?: boolean; state?: LinkProps["state"]; current?: boolean; className?: string; ref?: Ref<HTMLButtonElement>;
}) {
  const body = <>
    {icon && <span className="shrink-0 text-fg-2" aria-hidden>{icon}</span>}
    <span className="min-w-0 flex-1">
      <span className="block text-base font-medium [overflow-wrap:anywhere]">{title}</span>
      <MotionRegion as="span" className="block text-sm font-normal text-fg-2" motionKey={typeof summary === "string" || typeof summary === "number" ? summary : undefined}>{summary}</MotionRegion>
    </span>
    <ChevronRight className={cn("disclosure-chevron ink-end [--icon-w:14px] size-4 shrink-0 text-fg-3", expanded && "rotate-90")} aria-hidden />
  </>;
  const rowClass = cn("disclosure-row relative flex min-h-[3.5rem] w-full items-center gap-3.5 py-1.5 text-left transition-colors hover:bg-hover", current && "text-accent-text", className);
  return to !== undefined ? <Link to={to} replace={replace} state={state} aria-current={current ? "page" : undefined} className={rowClass}>{body}</Link>
    : <button {...rest} ref={ref} type="button" aria-expanded={expanded} aria-controls={controls} onClick={onClick} className={rowClass}>{body}</button>;
}
