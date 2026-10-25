import { useRef, type ReactNode } from "react";
import { cn } from "./cn";
import { usePresence, useListPresence } from "./motion";
import { ArrivalScope, Collapse } from "./Collapse";
import type { RowState } from "./motion";

/** Dùng cho danh sách hữu hạn đã phân trang; không đưa cả kho sách vào DOM thay cho Windowed. */
export function AnimatedRows<T>({ items, keyOf, children, className, as: List = "ul" }: { items: readonly T[]; keyOf: (item: T) => string; children: (item: T, index: number, state: RowState) => ReactNode; className?: string; as?: "ul" | "ol" }) {
  const rows = useListPresence(items, keyOf);
  const indices = new Map(items.map((item, index) => [keyOf(item), index]));
  return <List className={className}>{rows.map(({ key, item, state, ref }) => <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}><div>{children(item, indices.get(key) ?? -1, state)}</div></li>)}</List>;
}

/** Lớp tự dựng: đóng là inert ngay, giữ hình tới animationend; thời hạn dự phòng lo trường hợp WebView bỏ sự kiện. */
export function MotionPresence({ open, children, className, bodyClassName }: { open: boolean; children: ReactNode; className?: string; bodyClassName?: string }) {
  const presence = usePresence(open);
  const last = useRef(children);
  if (open) last.current = children;
  if (!presence.mounted) return null;
  return <div className={cn("motion-flow", className)}><Collapse open={open} appear className={bodyClassName}><div className="motion-panel" data-state={presence.state} inert={!open} aria-hidden={!open || undefined} onAnimationEnd={presence.onAnimationEnd}>{open ? children : last.current}</div></Collapse></div>;
}

/** Khung chờ cũ mờ ra đè trên nội dung đang hiện vào; không dựng nội dung thật hai lần, không trì hoãn tương tác. */
export function LoadingCrossfade({ loading, placeholder, children, className }: { loading: boolean; placeholder: ReactNode; children: ReactNode; className?: string }) {
  const presence = usePresence(loading);
  // Chỉ hiện dần sau khi khung chờ thật sự đã hiện. Dữ liệu có sẵn từ lần trước thì nội dung đứng yên cùng trang, không hiện dần lần nữa.
  const waited = useRef(loading);
  if (loading) waited.current = true;
  return <ArrivalScope loading={loading}><div className={cn("motion-loading", className)}>
    {presence.mounted && <div className="motion-loading-placeholder motion-panel" data-state={presence.state} inert={!loading} aria-hidden={!loading || undefined} onAnimationEnd={presence.onAnimationEnd}>{placeholder}</div>}
    {!loading && <div className={cn("motion-loading-content", waited.current && "motion-reveal")}>{children}</div>}
  </div></ArrivalScope>;
}
