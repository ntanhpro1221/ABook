import { cloneElement, createContext, Fragment, isValidElement, useContext, useLayoutEffect, useRef, type AnimationEvent, type ReactElement, type ReactNode } from "react";
import { cn } from "./cn";
import { EASE, MOTION, prefersReducedMotion, usePresence, useListPresence } from "./motion";

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

type Revealable = ReactElement<{ className?: string; onAnimationEnd?: (event: AnimationEvent<HTMLElement>) => void }>;

const PresentContext = createContext(true);
export const usePresent = () => useContext(PresentContext);

/** Optional slots must test their current content, not the truthiness of a
 * Presence element that intentionally survives after its child disappears. */
export function hasPresentContent(value: ReactNode): boolean {
  if (Array.isArray(value)) return value.some(hasPresentContent);
  if (isValidElement<{ children?: ReactNode }>(value) && (value.type === Presence || value.type === Fragment)) return hasPresentContent(value.props.children);
  return Boolean(value);
}

/** Retain the last rendered value through exit, including values narrowed by a conditional.
 * The contents host keeps flex/grid layout and animates the actual DOM roots of custom
 * components, so they need not forward animation props. Portals own their surface motion. */
export function Presence({ children }: { children: ReactNode }) {
  const parentOpen = usePresent();
  const open = parentOpen && Boolean(children);
  const presence = usePresence(open);
  const last = useRef(children);
  const host = useRef<HTMLSpanElement>(null);
  const previous = useRef(open);
  const initial = useRef(open);
  if (open) last.current = children;
  useLayoutEffect(() => {
    if (previous.current === open) return;
    previous.current = open;
    const reduced = prefersReducedMotion();
    const duration = reduced ? MOTION.fast : open ? MOTION.medium : MOTION.mediumOut;
    const animations = Array.from(host.current?.children ?? []).map(element => {
      const alpha = Number.parseFloat(getComputedStyle(element).opacity);
      const opacity = Number.isFinite(alpha) ? alpha : 1;
      return element.animate?.(
        open
          ? [{ opacity: 0, transform: reduced ? "none" : "translateY(8px)" }, { opacity, transform: "none" }]
          : [{ opacity, transform: "none" }, { opacity: 0, transform: reduced ? "none" : "translateY(-8px)" }],
        { duration, easing: open ? EASE.decelerate : EASE.accelerate, fill: open ? "backwards" : "forwards" },
      );
    });
    return () => animations.forEach(animation => animation?.cancel());
  }, [open]);
  if (!presence.mounted) return null;
  const child = open ? children : last.current;
  // Native roots keep their HTML parent/child contract (ul/li, dl/dt, table rows).
  if (isValidElement(child) && typeof child.type === "string") return <PresentContext.Provider value={open}><Reveal when={open} appear={!initial.current}>{child as Revealable}</Reveal></PresentContext.Provider>;
  return <PresentContext.Provider value={open}><span ref={host} style={{ display: "contents" }} inert={!open} aria-hidden={!open || undefined}>{child}</span></PresentContext.Provider>;
}

/** Hiện/ẩn MỘT phần tử mà không thêm lớp bọc (chữ trong dòng, biểu tượng, phần tử trong hàng flex): gắn `motion-panel` + data-state
 *  vào chính phần tử ấy - phần tử DOM, biểu tượng lucide hay thành phần chuyển className/props xuống DOM (Button). Đóng là inert ngay,
 *  giữ nội dung cuối tới hết hiệu ứng (giảm chuyển động: chỉ mờ ngắn). Có sẵn từ lúc dựng thì đứng yên, không hiện dần lần nữa. */
export function Reveal({ when, children, appear = false }: { when: unknown; children: Revealable; appear?: boolean }) {
  const open = Boolean(when);
  const presence = usePresence(open);
  const last = useRef(children);
  const moved = useRef(appear || !open);
  if (open) last.current = children;
  else moved.current = true;
  if (!presence.mounted) return null;
  const child = open ? children : last.current;
  if (!moved.current) return child;
  return cloneElement(child, {
    className: cn(child.props.className, "motion-panel"),
    "data-state": presence.state,
    // Chỉ thêm khi đóng: phần tử tự có aria-hidden (số đếm chỉ để nhìn) giữ nguyên lúc đang hiện.
    ...(open ? {} : { inert: true, "aria-hidden": true }),
    onAnimationEnd: (event: AnimationEvent<HTMLElement>) => {
      child.props.onAnimationEnd?.(event);
      presence.onAnimationEnd(event);
    },
  } as Record<string, unknown>);
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
