import { useRef, type ReactNode } from "react";
import { cn } from "./cn";
import { MOTION, usePresence, useListPresence } from "./motion";

/** Khớp animation-delay của .motion-loading-placeholder trong styles.css. */
export const LOADING_PATIENCE = 200;
const now = () => (typeof performance === "undefined" ? Date.now() : performance.now());
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

/** Khung chờ cũ mờ ra đè trên nội dung đang hiện vào; không dựng nội dung thật hai lần, không trì hoãn tương tác.
 *  Chiều ngược lại (khoá truy vấn đổi: lọc, đổi tab): nội dung cũ không bị gỡ cứng - nó đứng yên (inert) tới khi khung chờ hiện ra
 *  (sau LOADING_PATIENCE) rồi mờ đi dưới khung chờ; dữ liệu mới về trước đó thì thay thẳng tại chỗ, không có nhịp trống. */
export function LoadingCrossfade({ loading, placeholder, children, className }: { loading: boolean; placeholder: ReactNode; children: ReactNode; className?: string }) {
  const presence = usePresence(loading);
  const content = usePresence(!loading, LOADING_PATIENCE + MOTION.mediumOut);
  const last = useRef(children);
  if (!loading) last.current = children;
  // Chỉ hiện dần sau khi khung chờ thật sự đã hiện. Dữ liệu có sẵn từ lần trước thì nội dung đứng yên cùng trang, không hiện dần lần nữa.
  const waited = useRef(loading);
  if (loading) waited.current = true;
  // Khung chờ chỉ hiện khi chờ lâu hơn LOADING_PATIENCE (CSS .motion-loading-placeholder trễ đúng chừng ấy): dữ liệu về sớm thì nó chưa
  // từng hiện, nên gỡ luôn không mờ ra - không có nhịp xám chớp rồi mờ sang nội dung (máy ảo 25-10: tab Studio lần đầu).
  // Chốt ngay lúc hết chờ (không tính lại mỗi lần vẽ: khung đang khép mà hiện lại sẽ chớp đúng nhịp phải tránh).
  const since = useRef(loading ? now() : 0);
  const skip = useRef(false);
  // Lượt chờ này bắt đầu khi nội dung cũ còn trên màn (giữ lại, inert): về sớm thì nội dung mới thay tại chỗ, không hiện dần từ 0.
  const held = useRef(false);
  if (loading) {
    if (!since.current) {
      since.current = now();
      held.current = content.mounted;
    }
    skip.current = false;
  } else if (since.current) {
    skip.current = now() - since.current < LOADING_PATIENCE;
    since.current = 0;
  }
  const unseen = !loading && skip.current;
  return <ArrivalScope loading={loading}><div className={cn("motion-loading", className)}>
    {presence.mounted && !unseen && <div className="motion-loading-placeholder motion-panel" data-state={presence.state} inert={!loading} aria-hidden={!loading || undefined} onAnimationEnd={presence.onAnimationEnd}>{placeholder}</div>}
    {content.mounted && <div className={cn("motion-loading-content", !loading && waited.current && !(held.current && unseen) && "motion-reveal")} data-state={loading ? "closed" : undefined} inert={loading} aria-hidden={loading || undefined} onAnimationEnd={content.onAnimationEnd}>{loading ? last.current : children}</div>}
  </div></ArrivalScope>;
}
