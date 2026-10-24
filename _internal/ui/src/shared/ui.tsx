import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { AlertTriangle, ChevronLeft, ChevronRight, Loader2, RotateCw, WifiOff, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ButtonHTMLAttributes, ComponentType, CSSProperties, FocusEvent, ReactNode, Ref } from "react";
import { cn } from "@/shared/cn";
import { scrollMotion } from "@/shared/motion";
import { revealedScroll, wheelScroll } from "@/shared/tabScroll";
import { MotionRegion } from "./MotionRegion";
import { MotionPresence } from "./MotionPresence";
import { useBackLayer } from "./backStack";

type IconType = ComponentType<{ className?: string; strokeWidth?: number }>;

// ---- Nút --------------------------------------------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:bg-accent-hover shadow-[0_1px_0_rgb(255_255_255/0.25)_inset]",
  secondary: "bg-panel-2 text-fg border border-control hover:bg-hover hover:border-control-strong",
  outline: "text-fg border border-control-strong hover:bg-hover",
  ghost: "text-fg-2 hover:bg-hover hover:text-fg",
  danger: "bg-danger-soft text-danger hover:bg-danger hover:text-white",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[0.8125rem] gap-1.5 rounded-lg",
  md: "h-9 px-3.5 text-sm gap-2 rounded-lg",
  lg: "h-11 px-5 text-[0.9375rem] gap-2 rounded-xl",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: IconType;
  loading?: boolean;
  /** React 19: `ref` đi như một prop thường - đủ để chỗ gọi đặt tiêu điểm về nút (vd TemplateBar sau khi lưu mẫu). */
  ref?: Ref<HTMLButtonElement>;
}

/** Nút đang chạy việc (`loading`): KHÔNG `disabled` - nút disabled mất tiêu điểm, người đi bằng bàn phím / trình đọc màn hình rơi về đầu trang
 *  (soát a67: Thử giọng, Tải / Huỷ giọng). Nút vẫn nhận tiêu điểm, báo `aria-disabled` + `aria-busy`, cú bấm (chuột, Enter, Space, gửi form) bị
 *  chặn ở đây. `disabled` của chỗ gọi chỉ có hiệu lực khi không chạy việc (chỗ gọi hay truyền cả hai cùng lúc). */
export function busyClick<E extends { preventDefault: () => void }>(loading: boolean | undefined, onClick: ((event: E) => void) | undefined) {
  if (!loading) return onClick;
  return (event: E) => event.preventDefault();
}

/** Nút có chữ dài (đường dẫn, tên mục): chữ xuống dòng, bẻ cả chuỗi liền, nút cao thêm thay vì rộng hơn khung - chữ hệ thống to ở 320 px không đẩy trang tràn ngang (soát a102). */
export const WRAP_LABEL = "h-auto min-h-8 max-w-full whitespace-normal py-1.5 text-center [overflow-wrap:anywhere]";

export function Button({
  variant = "secondary",
  size = "md",
  icon: Icon,
  loading,
  className,
  children,
  disabled,
  onClick,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={loading ? undefined : disabled}
      aria-disabled={loading || undefined}
      aria-busy={loading || undefined}
      onClick={busyClick(loading, onClick)}
      className={cn(
        "inline-flex select-none items-center justify-center whitespace-nowrap font-medium pointer-coarse:min-w-[48px] transition-[background-color,color,border-color,outline-color,box-shadow,transform,opacity] duration-motion-fast active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45 aria-disabled:cursor-default aria-disabled:opacity-45 aria-disabled:active:scale-100",
        VARIANTS[variant],
        SIZES[size],
        // Màn hẹp / cảm ứng: nút 28-38 px nới vùng chạm theo chiều dọc lên 40 px (touch-reach trong styles.css; soát UX 29-09 và a14: "Sửa",
        // "Nam", "Nữ", "Thử giọng" chỉ 28-32 px trên điện thoại).
        "touch-reach",
        className,
      )}
      {...rest}
    >
      <MotionRegion as="span" aria-hidden className={cn("inline-grid shrink-0 place-items-center", (Icon || loading !== undefined) && (size === "lg" ? "glyph" : "size-4"))}>{loading ? (
        <Loader2 className="size-4 animate-spin" />
      ) : Icon ? (
        <Icon className={size === "lg" ? "glyph" : "size-4"} strokeWidth={2} />
      ) : loading !== undefined ? <span /> : null}</MotionRegion>
      <MotionRegion as="span" className="inline-flex min-w-0 items-center justify-center gap-2" motionKey={typeof children === "string" || typeof children === "number" ? children : undefined}>{children}</MotionRegion>
    </button>
  );
}

/** Nút thay chỗ nhau trong một khối khi việc đổi pha (Tải -> Huỷ khi bắt đầu tải, Huỷ -> Tải / Thử lại khi xong hay huỷ): nút đang giữ tiêu điểm biến
 *  mất thì tiêu điểm rơi về đầu trang (soát a67). Khối mang `useFocusFollows(pha)`: tiêu điểm đang ở trong khối mà rơi mất thì chuyển tới nút mang
 *  `data-focus-next` (nút vừa hiện), không có thì tới phần tử mang `data-focus-fallback` (tiêu đề khối, tabIndex -1). */
export function focusFollowTarget(box: Element | null, active: Element | null, body: Element | null): HTMLElement | null {
  // Tiêu điểm còn trên một phần tử thật (nút cũ vẫn còn, hay người dùng đã sang chỗ khác): để nguyên.
  if (!box || (active && active !== body && active.isConnected)) return null;
  return box.querySelector<HTMLElement>("[data-focus-next]") ?? box.querySelector<HTMLElement>("[data-focus-fallback]");
}

export function useFocusFollows(phase: unknown) {
  const ref = useRef<HTMLDivElement | null>(null);
  const inside = useRef(false);
  useEffect(() => {
    if (!inside.current) return;
    focusFollowTarget(ref.current, document.activeElement, document.body)?.focus();
  }, [phase]);
  return {
    ref,
    onFocusCapture: () => void (inside.current = true),
    // Nút đang giữ tiêu điểm bị gỡ: blur không có nơi tới (relatedTarget null) - vẫn tính là "trong khối" để chuyển tiếp.
    onBlurCapture: (event: FocusEvent<HTMLElement>) => {
      if (event.relatedTarget) inside.current = Boolean(ref.current?.contains(event.relatedTarget as Node));
    },
  };
}

export function IconButton({
  label,
  icon: Icon,
  className,
  size = "md",
  tone = "ghost",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  ref?: Ref<HTMLButtonElement>;
  label: string;
  icon: IconType;
  size?: "sm" | "md" | "lg";
  tone?: "ghost" | "solid";
}) {
  const box = size === "sm" ? "size-8" : size === "lg" ? "size-11" : "size-9";
  const glyph = size === "lg" ? "glyph-20" : "glyph";
  // Màn hẹp / cảm ứng: nút nới vùng chạm theo CHIỀU DỌC lên 40 px (touch-reach, soát UX 29-09 và a14) - không nới ngang, vì các nút trên
  // thanh công cụ đứng sát nhau, vùng nới ngang sẽ giành chạm của nút bên cạnh. Màn cảm ứng: rộng thật 48 dp (soát a67: 39 dp).
  const reach = "touch-reach pointer-coarse:min-w-[48px]";
  return (
    <Tooltip label={label}>
      <button
        type="button"
        aria-label={label}
        className={cn(
          "inline-flex shrink-0 items-center justify-center rounded-lg transition-[color,background-color,outline-color,opacity] duration-motion-fast disabled:pointer-events-none disabled:opacity-40",
          tone === "ghost" ? "text-fg-2 hover:bg-hover hover:text-fg" : "bg-panel-2 text-fg hover:bg-hover",
          box,
          reach,
          className,
        )}
        {...rest}
      >
        <MotionRegion as="span" className="inline-grid shrink-0 place-items-center"><Icon className={glyph} strokeWidth={2} /></MotionRegion>
      </button>
    </Tooltip>
  );
}

// ---- Tooltip ----------------------------------------------------------------------------------------------

export const TooltipProvider = TooltipPrimitive.Provider;

/** Tiêu điểm vào nút mà KHÔNG phải do đi bằng bàn phím (app trả tiêu điểm về nút mở sau khi chọn bằng chuột trong bảng Tốc độ...): không bật
 *  chú thích - chỉ Tab / phím mới bật. Trình duyệt không hiểu :focus-visible thì bật như cũ. */
function quietFocus(event: FocusEvent<HTMLElement>) {
  try {
    if (!event.currentTarget.matches(":focus-visible")) event.preventDefault();
  } catch {
    // :focus-visible không được hỗ trợ
  }
}

export function Tooltip({ label, children, side = "top" }: { label: ReactNode; children: ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  const [open, setOpen] = useState(false);
  const content = useRef<HTMLDivElement>(null);
  // Tooltip có state instant-open/delayed-open riêng: Back đóng trực tiếp, không gửi Esc xuống hộp phía dưới.
  useBackLayer(open && Boolean(label), () => setOpen(false), content);
  if (!label) return <>{children}</>;
  return (
    <TooltipPrimitive.Root open={open} onOpenChange={setOpen}>
      <TooltipPrimitive.Trigger asChild onFocus={quietFocus}>
        {children}
      </TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          ref={content}
          inert={!open}
          style={open ? undefined : CLOSING}
          side={side}
          sideOffset={6}
          className="motion-tooltip z-50 max-w-72 rounded-md bg-fg px-2.5 py-1.5 text-xs font-medium text-bg shadow-float"
        >
          {label}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

// ---- Tiến độ ----------------------------------------------------------------------------------------------

export type Tone = "accent" | "success" | "danger" | "warning" | "muted";
const BAR: Record<Tone, string> = {
  accent: "bg-accent",
  success: "bg-success",
  danger: "bg-danger",
  warning: "bg-warning",
  muted: "bg-fg-3",
};

export function Progress({
  value,
  tone = "accent",
  running = false,
  size = "md",
  className,
  label,
  valueText,
  indeterminate = false,
}: {
  value: number;
  tone?: Tone;
  running?: boolean;
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
  /** Tên thanh cho trình đọc màn hình ("Đã nghe", "Tiến độ: <tên sách>") - không có thì chỉ nghe "thanh tiến độ 47" (soát a31 A1). */
  label: string;
  /** Lời đọc của giá trị ("đã nghe 42%"); không có thì trình đọc màn hình đọc phần trăm. Tên thanh không được mang số - số trong tên đứng yên trong
   *  khi giá trị chạy, đọc ra hai số mâu thuẫn (soát a67: "Đang xuất 6 chương · 0%" mà giá trị 14). */
  valueText?: string;
  /** Việc chạy mà không báo được tiến độ (đóng gói file): vạch chạy qua lại thay vì phần trăm. */
  indeterminate?: boolean;
}) {
  const height = { xs: "h-1", sm: "h-1.5", md: "h-2", lg: "h-2.5" }[size];
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(clamped * 100)}
      aria-valuetext={indeterminate ? undefined : valueText}
      className={cn("relative w-full overflow-hidden rounded-full bg-line", height, className)}
    >
      {indeterminate ? (
        <div className={cn("indeterminate-bar h-full w-2/5 rounded-full", BAR[tone])} />
      ) : (
        <div
          className={cn("motion-progress relative h-full overflow-hidden rounded-full", BAR[tone], running && "sheen")}
          style={{ transform: `scaleX(${clamped})` }}
        />
      )}
    </div>
  );
}

/** Thuộc tính trợ năng của các vạch "đã nghe" nhỏ (thẻ sách ở Thư viện, dòng chương ở trang sách, thanh phát gọn): trước đây là div trơn, trình đọc
 *  màn hình không biết có vạch ấy (soát a67). */
type Box = { top: number; bottom: number; left: number; right: number };

/** Khoảng phải cuộn (dương = cuộn xuống) để phần tử `target` không nằm dưới thông báo nào; 0 = không bị che. Thông báo ở nửa trên màn thì đẩy phần tử
 *  xuống dưới nó, ở nửa dưới thì kéo lên trên nó. */
export function toastClearance(target: Box, toasts: readonly Box[], viewportHeight: number, gap = 8): number {
  for (const toast of toasts) {
    if (target.left >= toast.right || target.right <= toast.left || target.top >= toast.bottom || target.bottom <= toast.top) continue;
    return toast.top + toast.bottom < viewportHeight ? target.top - toast.bottom - gap : target.bottom - toast.top + gap;
  }
  return 0;
}

function scrollParent(element: HTMLElement): Element {
  for (let node = element.parentElement; node; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node);
    if ((overflowY === "auto" || overflowY === "scroll") && node.scrollHeight > node.clientHeight) return node;
  }
  return document.scrollingElement ?? document.documentElement;
}

/** Tiêu điểm không bao giờ nằm dưới thông báo (soát a67, cửa sổ 640×400: thẻ tiến độ xuất che tab "Lịch sử" và nút "…" của chương): phần tử vừa
 *  nhận tiêu điểm mà bị một thông báo che thì cuộn khung chứa nó cho lộ ra. Gắn một lần ở gốc app (máy tính và điện thoại). */
export function useFocusClearOfToasts() {
  useEffect(() => {
    const onFocus = (event: Event) => {
      const target = event.target as HTMLElement | null;
      if (!target?.getBoundingClientRect || target.closest("[data-sonner-toaster]")) return;
      // Đợi trình duyệt tự cuộn tới phần tử (Tab tới chỗ khuất) rồi mới đo.
      requestAnimationFrame(() => {
        const toasts = Array.from(document.querySelectorAll('[data-sonner-toast]:not([data-visible="false"])'), (toast) => toast.getBoundingClientRect());
        const delta = toastClearance(target.getBoundingClientRect(), toasts, window.innerHeight);
        if (delta) scrollParent(target).scrollBy({ top: delta });
      });
    };
    document.addEventListener("focusin", onFocus);
    return () => document.removeEventListener("focusin", onFocus);
  }, []);
}

export function heardBarProps(fraction: number) {
  const percent = Math.round(Math.max(0, Math.min(1, fraction)) * 100);
  return {
    role: "progressbar",
    "aria-label": "Đã nghe",
    "aria-valuemin": 0,
    "aria-valuemax": 100,
    "aria-valuenow": percent,
    "aria-valuetext": `đã nghe ${percent}%`,
  } as const;
}

/** Chữ tiến độ đổi liên tục (đồng hồ, MB, %) trong vùng aria-live / role=status: mắt thấy `shown` (trình đọc màn hình bỏ qua), trình đọc
 *  màn hình đọc `spoken` - chữ chỉ đổi khi đổi pha hay qua mốc 25 % (spokenProgress, shared/progressSpeech.ts), không phải mỗi giây (soát a31 A6). */
let politeRegion: HTMLElement | null = null;

/** Nói một lời xác nhận ngắn qua vùng aria-live polite chung của trang ("Tốc độ đọc 1,2×" sau khi chọn trong bảng Tốc độ - soát a67): vùng có sẵn,
 *  rỗng, rồi mới điền chữ (vùng vừa chèn kèm chữ thường không được đọc); cùng một câu nói hai lần liền vẫn được đọc lại. */
export function announce(text: string) {
  if (typeof document === "undefined" || !document.body) return;
  if (!politeRegion?.isConnected) {
    politeRegion = document.createElement("div");
    politeRegion.className = "sr-only";
    politeRegion.setAttribute("aria-live", "polite");
    politeRegion.setAttribute("data-announcer", "");
    document.body.append(politeRegion);
  }
  const region = politeRegion;
  region.textContent = "";
  window.setTimeout(() => (region.textContent = text), 120);
}

export function LiveText({ shown, spoken }: { shown: ReactNode; spoken: string }) {
  return (
    <>
      <span aria-hidden>{shown}</span>
      <span className="sr-only">{spoken}</span>
    </>
  );
}

// ---- Trạng thái -------------------------------------------------------------------------------------------

export function Vu({ className }: { className?: string }) {
  return (
    <span className={cn("vu inline-flex h-3 items-end gap-[2px]", className)} aria-hidden>
      <span className="h-full w-[3px] rounded-sm bg-current" />
      <span className="h-full w-[3px] rounded-sm bg-current" />
      <span className="h-full w-[3px] rounded-sm bg-current" />
      <span className="h-full w-[3px] rounded-sm bg-current" />
    </span>
  );
}

const PILL: Record<Tone, string> = {
  accent: "bg-accent-soft text-accent-text",
  success: "bg-success-soft text-success",
  danger: "bg-danger-soft text-danger",
  warning: "bg-warning-soft text-warning",
  muted: "bg-hover text-fg-2",
};

export function StatusPill({
  label,
  tone,
  live = false,
  className,
}: {
  label: string;
  tone: Tone;
  live?: boolean;
  className?: string;
}) {
  return (
    <MotionRegion as="span" motionKey={[label, tone, live]}
      className={cn(
        "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-xs font-medium transition-colors duration-motion-fast",
        PILL[tone],
        className,
      )}
    >
      {live ? <Vu className="h-2.5" /> : <span className="size-1.5 rounded-full bg-current" />}
      {label}
    </MotionRegion>
  );
}

// ---- Tab --------------------------------------------------------------------------------------------------

export const Tabs = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

/** Bao các TabsContent của một hàng tab: Radix gỡ bảng cũ ngay khi đổi tab - không có vỏ chung thì bảng mới thay tức thì và chiều cao trang
 *  nhảy. Một MotionRegion khoá theo tab: bảng cũ mờ ra, bảng mới hiện vào, chiều cao chuyển dần. */
export function TabsPanels({ value, children, className }: { value: string; children: ReactNode; className?: string }) {
  return <MotionRegion motionKey={value} fadeThrough className={className}>{children}</MotionRegion>;
}

const FADE = 36;

/** `label`: tên của hàng tab cho trình đọc màn hình ("Mục của sách") - không có thì chỉ nghe "danh sách tab" (soát a31 K7/A2). */
export function TabsList({ children, className, label }: { children: ReactNode; className?: string; label: string }) {
  // Hàng tab không vừa (điện thoại, hay cửa sổ hẹp có thanh bên) thì cuộn ngang thay vì tràn ra ngoài trang, và mép nào
  // còn tab bị che thì mờ dần - không thì "Nhân v" bị cắt trông như lỗi, không ai biết là còn tab (soát UX 29-09).
  const list = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });
  useEffect(() => {
    const element = list.current;
    if (!element) return;
    const update = () => {
      const left = element.scrollLeft > 2;
      const right = element.scrollLeft + element.clientWidth < element.scrollWidth - 2;
      setEdges((old) => (old.left === left && old.right === right ? old : { left, right }));
    };
    update();
    element.addEventListener("scroll", update, { passive: true });
    // Lăn chuột thường chạy hàng tab sang ngang (chuột không có lăn ngang, thanh cuộn thì ẩn); tới đầu/cuối hàng thì nhả cho trang cuộn dọc.
    const onWheel = (event: WheelEvent) => {
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientWidth : 1;
      const next = wheelScroll(event.deltaX * unit, event.deltaY * unit, element.scrollLeft, element.clientWidth, element.scrollWidth, event.ctrlKey);
      if (next === null) return;
      event.preventDefault();
      element.scrollLeft = next;
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(element);
    return () => {
      element.removeEventListener("scroll", update);
      element.removeEventListener("wheel", onWheel);
      observer?.disconnect();
    };
  }, []);
  // Tab đang chọn (mở bằng địa chỉ ?tab=cast, hay bấm nhảy từ nơi khác) nằm ngoài vùng thấy thì cuộn ngang tới nó.
  const lastActive = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const element = list.current;
    const active = element?.querySelector<HTMLElement>("[data-state=active]");
    // Chỉ khi tab đang chọn ĐỔI - người dùng tự cuộn hàng tab đi chỗ khác thì không kéo lại.
    if (!element || !active || active === lastActive.current) return;
    lastActive.current = active;
    const next = revealedScroll(active.offsetLeft, active.offsetWidth, element.scrollLeft, element.clientWidth, FADE);
    if (next !== null) element.scrollLeft = next;
  });
  const mask = edges.left || edges.right
    ? `linear-gradient(to right, ${edges.left ? `transparent, black ${FADE}px` : "black"}, ${
        edges.right ? `black calc(100% - ${FADE}px), transparent` : "black"
      })`
    : undefined;
  const style: CSSProperties | undefined = mask ? { maskImage: mask, WebkitMaskImage: mask } : undefined;
  const nudge = (direction: -1 | 1) => list.current?.scrollBy({ left: direction * list.current.clientWidth * 0.7, behavior: scrollMotion() });
  return (
    <div className="relative">
      <TabsPrimitive.List
        ref={list}
        aria-label={label}
        style={style}
        className={cn("flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line [scrollbar-width:none]", className)}
      >
        {children}
      </TabsPrimitive.List>
      {/* Mũi tên báo còn tab ngoài mép (mọi cỡ màn: chuột bấm được; bàn phím đã có phím mũi tên của hàng tab). */}
      {edges.left && (
        <button type="button" tabIndex={-1} aria-label="Xem các tab trước" onClick={() => nudge(-1)} className="absolute left-0 top-0 grid h-11 w-9 place-items-center text-fg-2 hover:text-fg">
          <span className="grid size-6 place-items-center rounded-full border border-line bg-panel-2 shadow-sm">
            <ChevronLeft className="size-3.5" />
          </span>
        </button>
      )}
      {edges.right && (
        <button type="button" tabIndex={-1} aria-label="Xem các tab sau" onClick={() => nudge(1)} className="absolute right-0 top-0 grid h-11 w-9 place-items-center text-fg-2 hover:text-fg">
          <span className="grid size-6 place-items-center rounded-full border border-line bg-panel-2 shadow-sm">
            <ChevronRight className="size-3.5" />
          </span>
        </button>
      )}
    </div>
  );
}

export function TabsTrigger({ value, children, count }: { value: string; children: ReactNode; count?: number }) {
  return (
    <TabsPrimitive.Trigger
      value={value}
      className="touch-row relative -mb-px inline-flex h-11 shrink-0 items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-2 text-sm sm:px-3 font-medium text-fg-2 transition-colors hover:text-fg data-[state=active]:border-accent data-[state=active]:text-fg"
    >
      {children}
      {/* Số đếm dính vào tên khi đọc ("Chương6") - trình đọc màn hình nghe "Chương, 6 mục" (soát a67). */}
      <MotionRegion as="span" className="inline-flex" motionKey={count ?? null}>{count !== undefined && (
        <span className="tabular rounded-full bg-hover px-1.5 py-px text-[0.6875rem] font-semibold text-fg-2">
          <span className="sr-only">, </span>
          {count}
          <span className="sr-only"> mục</span>
        </span>
      )}</MotionRegion>
    </TabsPrimitive.Trigger>
  );
}

/** Bấm vào thông báo (Toaster của sonner) trong lúc hộp thoại đang mở không được tính là bấm ra ngoài hộp - hộp đóng mất chữ đang
 *  gõ. Dùng cho `onInteractOutside` của Dialog / Sheet; Toaster đặt `pointer-events-auto` để nút trong thông báo bấm được. */
function keepOpenForToasts(event: { target: EventTarget | null; preventDefault: () => void }) {
  if (event.target instanceof Element && event.target.closest("[data-sonner-toaster]")) event.preventDefault();
}

/** Lớp đang đóng (Radix giữ lại tới khi chuyển động xong) không nhận chạm. Lúc mở KHÔNG truyền `style`: Radix đặt `pointer-events: auto`
 *  cho hộp và nền (body bị đặt `none` khi hộp mở) rồi trải `style` của ta đè lên - một khoá `pointerEvents: undefined` xoá mất `auto`,
 *  hộp thừa hưởng `none` từ body: chạm xuyên qua hộp thành bấm ra ngoài, hộp đóng (soát máy ảo 0.4.134). */
const CLOSING = { pointerEvents: "none" } as const;

// ---- Hộp thoại --------------------------------------------------------------------------------------------

/** Nút ✕ của hộp thoại / tấm trượt: biểu tượng 20 px nhưng vùng bấm 44 x 44 px (máy tính), 48 x 48 (cảm ứng); lề âm giữ chỗ chiếm trong bố cục như
 *  cũ (soát a67: chỉ 24 x 24 px). */
const CLOSE_BUTTON =
  "-m-[0.75rem] inline-flex size-[2.75rem] shrink-0 items-center justify-center rounded-lg text-fg-3 hover:bg-hover hover:text-fg pointer-coarse:-m-[0.875rem] pointer-coarse:size-[3rem]";

/** Phần tử "đã mở hộp" từ chỗ con trỏ đang đứng: mục của một menu (Radix DropdownMenu) mất ngay khi menu đóng, nên đó là nút mở menu (menu mang
 *  `aria-labelledby` = mã nút ấy; menu con thì lần lên tiếp). Phần tử thường thì chính nó. */
export function dialogOpener(element: Element | null): Element | null {
  for (let depth = 0; depth < 4 && element; depth++) {
    const menu = element.closest?.('[role="menu"]');
    if (!menu) return element;
    const trigger = menu.getAttribute("aria-labelledby");
    element = trigger ? element.ownerDocument.getElementById(trigger) : null;
  }
  return element;
}

/** Chỗ con trỏ đứng lần gần nhất, đã quy về "phần tử mở hộp" (`dialogOpener`). Hộp mở từ mục menu: lúc hộp dựng, menu đã đóng và con trỏ về body -
 *  chỉ có cách nhớ từ trước. */
let lastFocus: Element | null = null;
if (typeof document !== "undefined") {
  document.addEventListener("focusin", (event) => (lastFocus = dialogOpener(event.target instanceof Element ? event.target : null)), true);
  // Cách người dùng vừa thao tác (chạm / chuột hay phím), ghi lên <html data-input>: app tự đặt tiêu điểm (tiêu đề trang mới - usePageFocus,
  // nút X khi hộp mở) sau một lần CHẠM thì không vẽ khung tiêu điểm - WebView vẫn vẽ cho tiêu điểm do mã đặt (soát a66: khung quanh "Tải sách",
  // quanh X). Đi bằng phím thì khung vẫn hiện như cũ (styles.css).
  const mark = (input: "pointer" | "keyboard") => () => {
    if (document.documentElement.dataset.input !== input) document.documentElement.dataset.input = input;
  };
  document.addEventListener("pointerdown", mark("pointer"), true);
  document.addEventListener("keydown", mark("keyboard"), true);
}

/** Phần tử nhận lại con trỏ khi hộp đóng: chính phần tử đã mở hộp, nếu nó còn trong trang (hộp mở bằng hash hay thẻ đã gỡ thì
 *  không có - để trình duyệt tự lo). `Dialog` điều khiển từ ngoài nên Radix không có nút mở để trả con trỏ về (soát UX a17). */
export function focusReturnTarget(opener: Element | null, body: Element | null): HTMLElement | null {
  if (!opener || opener === body || !(opener as HTMLElement).isConnected || typeof (opener as HTMLElement).focus !== "function") return null;
  return opener as HTMLElement;
}

function keepNewLayerFocus(event: Event): boolean {
  if (!document.activeElement?.closest('[data-state="open"]:is([role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"])')) return false;
  event.preventDefault();
  return true;
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  width = "max-w-lg",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  width?: string;
}) {
  // Nhớ phần tử đang giữ con trỏ lúc hộp mở (trước khi Radix chuyển con trỏ vào hộp) để trả về khi đóng.
  const opener = useRef<Element | null>(null);
  const lastContent = useRef({ title, description, children });
  if (open) lastContent.current = { title, description, children };
  const shown = open ? { title, description, children } : lastContent.current;
  useLayoutEffect(() => {
    if (open) opener.current = lastFocus;
  }, [open]);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        {/* Mở / đóng đều có chuyển động (styles.css .motion-scrim / .motion-dialog): Radix giữ hộp lại tới khi hiệu ứng đóng xong. Làm mờ nền chỉ
            khi có chuột - trên điện thoại tầm trung, mờ nền mỗi khung hình làm hiệu ứng mở giật. */}
        <DialogPrimitive.Overlay inert={!open} style={open ? undefined : CLOSING} className="motion-scrim fixed inset-0 z-40 bg-scrim pointer-fine:backdrop-blur-[2px]" />
        <DialogPrimitive.Content
          inert={!open}
          style={open ? undefined : CLOSING}
          className={cn(
            "motion-dialog fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 flex max-h-[90dvh] flex-col rounded-2xl border border-line bg-panel p-6 shadow-float focus:outline-none",
            width,
          )}
          onInteractOutside={keepOpenForToasts}
          onCloseAutoFocus={(event) => {
            if (keepNewLayerFocus(event)) return;
            const target = focusReturnTarget(opener.current, document.body);
            opener.current = null;
            if (!target) return;
            event.preventDefault();
            target.focus();
          }}
          // Ô mang `data-escape-local` (vd ô đổi tên chương) tự xử lý phím Esc để huỷ việc đang gõ; Esc ở đó không đóng cả hộp.
          onEscapeKeyDown={(event) => {
            if ((event.target as HTMLElement | null)?.closest?.("[data-escape-local]")) event.preventDefault();
          }}
          onOpenAutoFocus={(event) => {
            // Radix đặt con trỏ vào thứ bấm được đầu tiên - nút X ở đầu hộp - đè lên `autoFocus` của ô nhập (soát UX 30-09:
            // hộp Đổi tên). Ô nào mang `data-autofocus` thì nhận con trỏ, chữ có sẵn được chọn để gõ đè.
            const target = (event.currentTarget as HTMLElement | null)?.querySelector<HTMLElement>("[data-autofocus]");
            if (!target) return;
            event.preventDefault();
            target.focus();
            if (target instanceof HTMLInputElement) target.select();
          }}
        >
          <div className="mb-4 flex shrink-0 items-start justify-between gap-4">
            <div>
              <DialogPrimitive.Title className="text-lg font-semibold">
                <MotionRegion as="span" className="block" motionKey={typeof shown.title === "string" || typeof shown.title === "number" ? shown.title : undefined}>{shown.title}</MotionRegion>
              </DialogPrimitive.Title>
              <DialogPrimitive.Description className="text-sm text-fg-2">
                <MotionRegion as="span" className={shown.description ? "mt-1 block" : "block"} motionKey={typeof shown.description === "string" || typeof shown.description === "number" ? shown.description : undefined}>{shown.description}</MotionRegion>
              </DialogPrimitive.Description>
            </div>
            <DialogPrimitive.Close asChild>
              <button aria-label="Đóng" className={CLOSE_BUTTON}>
                <X className="size-5" />
              </button>
            </DialogPrimitive.Close>
          </div>
          {/* Hộp cao hơn màn (điện thoại, cửa sổ thấp) thì nội dung cuộn trong hộp, nút Đóng ở đầu luôn thấy được (soát UX a15). */}
          <div className="-mx-1 min-h-0 flex-1 overflow-y-auto overscroll-contain px-1">{shown.children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** Tấm trượt từ đáy màn điện thoại, thay cho bảng nổi neo vào một nút nhỏ: trên màn hẹp bảng nổi bị ép sát mép và phải
 *  cuộn trong khung thấp (soát UX 29-09, bảng cách đọc câu ở tab Kịch bản). `trigger` là nút mở (asChild). */
export function Sheet({
  open,
  onOpenChange,
  title,
  trigger,
  children,
  onEscapeKeyDown,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  trigger: ReactNode;
  children: ReactNode;
  onEscapeKeyDown?: (event: KeyboardEvent) => void;
}) {
  const lastContent = useRef({ title, children });
  if (open) lastContent.current = { title, children };
  const shown = open ? { title, children } : lastContent.current;
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay inert={!open} style={open ? undefined : CLOSING} className="motion-scrim fixed inset-0 z-40 bg-scrim" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          inert={!open}
          style={open ? undefined : CLOSING}
          onCloseAutoFocus={keepNewLayerFocus}
          // Đóng (Esc, nút Đóng, chạm nền): Radix tự trả tiêu điểm về nút mở (Trigger) - trước đây chặn việc ấy nên tiêu điểm rơi về BODY (soát a31 K1).
          onEscapeKeyDown={onEscapeKeyDown}
          onInteractOutside={keepOpenForToasts}
          className="motion-sheet fixed inset-x-0 bottom-0 z-50 max-h-[85dvh] overflow-y-auto overscroll-contain rounded-t-2xl border-t border-line bg-panel px-3 pb-[max(env(safe-area-inset-bottom),0.75rem)] pt-2 shadow-float focus:outline-none"
        >
          <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-line-strong" aria-hidden />
          <div className="flex items-center justify-between gap-3 px-1.5">
            <DialogPrimitive.Title className="text-sm font-semibold">
              <MotionRegion as="span" className="block" motionKey={typeof shown.title === "string" || typeof shown.title === "number" ? shown.title : undefined}>{shown.title}</MotionRegion>
            </DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <button aria-label="Đóng" className={CLOSE_BUTTON}>
                <X className="size-5" />
              </button>
            </DialogPrimitive.Close>
          </div>
          {shown.children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

// ---- Khác -------------------------------------------------------------------------------------------------

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("motion-skeleton rounded-md bg-line", className)} />;
}

/** Khung chờ theo hình nội dung: dòng danh sách, thẻ duyệt, hay lưới bìa. */
export function ContentSkeleton({ shape = "rows", count = 3, label = "Đang tải", className }: {
  shape?: "rows" | "cards" | "covers";
  count?: number;
  label?: string;
  className?: string;
}) {
  return <MotionRegion role="status" aria-label={label} className={cn("motion-reveal", shape === "covers" ? "grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-4" : "space-y-4", className)}>
    <span className="sr-only">{label}</span>
    {Array.from({ length: count }, (_, index) => <div key={index} aria-hidden="true" className={cn(shape === "rows" && "flex items-center gap-3", shape === "cards" && "space-y-3 py-3")}>
      {shape === "covers" ? <Skeleton className="aspect-[2/3] rounded-xl" /> : shape === "rows" ? <Skeleton className="size-10 shrink-0" /> : <Skeleton className="h-4 w-1/3" />}
      <div className={cn("min-w-0 flex-1 space-y-2", shape === "covers" && "mt-3")}>
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className={cn("h-3 w-1/2", shape === "cards" && "w-full")} />
      </div>
    </div>)}
  </MotionRegion>;
}

/** Lỗi ở ngay vùng bị ảnh hưởng; nội dung đã có vẫn dùng được. */
export function InlineError({ message, onRetry, className }: { message: string; onRetry: () => void; className?: string }) {
  // Nút đứng ngay sau câu (màn rộng không đẩy nó ra mép phải); màn hẹp xuống dòng thì thẳng mép với chữ - -ml bù phần đệm của nút ghost.
  return <MotionRegion role="alert" motionKey={message} className={cn("motion-reveal flex items-start gap-3 py-3 text-sm", className)}>
    <AlertTriangle aria-hidden className="mt-[3px] size-4 shrink-0 text-danger" />
    <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
      <p className="min-w-0 max-w-[60ch] text-pretty text-fg-2">{message}</p>
      <Button variant="ghost" size="sm" icon={RotateCw} className="-ml-3" onClick={onRetry}>Thử lại</Button>
    </div>
  </MotionRegion>;
}

/** Chỉ thông báo mất mạng; không gỡ nội dung hay chặn thao tác trên máy. */
export function OfflineStrip({ offline: forced, message = "Mất mạng · Bạn vẫn dùng được sách đã tải." }: { offline?: boolean; message?: string }) {
  const [offline, setOffline] = useState(() => typeof navigator !== "undefined" && navigator.onLine === false);
  useEffect(() => {
    const lost = () => setOffline(true);
    const back = () => setOffline(false);
    window.addEventListener("offline", lost);
    window.addEventListener("online", back);
    return () => { window.removeEventListener("offline", lost); window.removeEventListener("online", back); };
  }, []);
  return <MotionPresence open={forced ?? offline} className="shrink-0">
    <div role="status" className="flex items-center gap-2 border-b border-line bg-warning-soft px-5 py-2 text-xs text-fg-2">
      <WifiOff aria-hidden className="size-3.5 shrink-0" /><span>{message}</span>
    </div>
  </MotionPresence>;
}

export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
  className,
}: {
  icon: IconType;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("motion-reveal flex flex-col items-center px-6 py-14 text-center", className)}>
      <div className="mb-4 grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent-text">
        <Icon className="size-7" strokeWidth={1.75} />
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <p className="mt-1.5 max-w-md text-sm leading-relaxed text-fg-2">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** Danh sách tải lỗi mà chưa có gì để hiện: phải nói là LỖI, không phải "chưa có gì" (soát a28 lỗi 4 - thư viện báo "Chưa có sách" khi máy
 *  chủ trả 500). Đã có dữ liệu từ lần trước thì cứ hiện dữ liệu ấy. */
export function failedEmpty(query: { isError: boolean; data?: readonly unknown[] | null }): boolean {
  return query.isError && !query.data?.length;
}

export function LoadError({ what, onRetry, className }: { what: string; error?: unknown; onRetry: () => void; className?: string }) {
  return <InlineError message={`Chưa tải được ${what}; bạn hãy kiểm tra kết nối rồi thử lại.`} onRetry={onRetry} className={className} />;
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-line-strong bg-panel-2 px-1 font-sans text-[0.6875rem] font-medium text-fg-2">
      {children}
    </kbd>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs font-medium text-fg-3">{label}</div>
      <div className="tabular mt-1 truncate text-xl font-semibold tracking-tight">{value}</div>
      {hint && <div className="mt-0.5 truncate text-xs text-fg-2">{hint}</div>}
    </div>
  );
}

/** Nhóm radio theo mẫu WAI-ARIA: Tab vào đúng MỘT nút (nút đang chọn), mũi tên / Home / End chọn luôn mục kế và
 * đưa tiêu điểm tới đó. Gắn vào phần tử `role="radiogroup"`; các nút `role="radio"` phải theo đúng thứ tự `values`.
 * Chỉ nhận phím đến từ một nút radio CỦA CHÍNH nhóm, chưa bị ai xử lý: phím của nhóm con (tốc độ nằm trong nhóm giọng) nổi lên không đổi lựa chọn nhóm ngoài. */
export function radioGroupKeys<T>(values: readonly T[], value: T, onChange: (value: T) => void) {
  return (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.defaultPrevented || !values.length) return;
    const radio = (event.target as HTMLElement | null)?.closest?.('[role="radio"]');
    if (!radio || radio.closest('[role="radiogroup"]') !== event.currentTarget) return;
    const step = ({ ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 } as Record<string, number>)[event.key];
    const index = values.indexOf(value);
    // Chưa chọn mục nào của nhóm (giá trị nằm ở nhóm khác): mũi tên tới mục đầu / cuối thay vì bỏ qua mục đầu.
    const next = step && index < 0 ? (step > 0 ? 0 : values.length - 1) : step ? (index + step + values.length) % values.length : event.key === "Home" ? 0 : event.key === "End" ? values.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    onChange(values[next]);
    event.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]')[next]?.focus();
  };
}

/** tabIndex của nút thứ `index` trong nhóm radio: chỉ nút đang chọn (hay nút đầu, khi chưa chọn gì) nằm trong vòng Tab. */
export function radioTabIndex<T>(values: readonly T[], value: T, index: number) {
  return values[index] === value || (!values.includes(value) && index === 0) ? 0 : -1;
}

/** Bảng nổi có nhiều nút (Tốc độ, Giọng đọc, Hẹn giờ của trình phát): mũi tên đi từ nút này sang nút kia như menu "Tuỳ chọn khác" (Radix) - xuống /
 *  phải là nút sau, lên / trái là nút trước, Home / End về đầu / cuối, không vòng lại. Lên / xuống bỏ qua nút phụ đứng cạnh một lựa chọn (`side`: nút
 *  "Thử" cạnh tên giọng) để đi thẳng theo danh sách; trái / phải đi qua cả nút phụ. Trả phần tử cần tới, hay null nếu phím không phải việc của nó. */
export function arrowTarget<T>(items: readonly T[], current: T | null, key: string, side: (item: T) => boolean = () => false): T | null {
  const step = ({ ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 } as Record<string, number>)[key];
  if (!step && key !== "Home" && key !== "End") return null;
  const pool = key === "ArrowLeft" || key === "ArrowRight" ? items : items.filter((item) => !side(item) || item === current);
  if (!pool.length) return null;
  if (key === "Home") return pool[0];
  if (key === "End") return pool[pool.length - 1];
  const index = current === null ? -1 : pool.indexOf(current);
  if (index < 0) return step > 0 ? pool[0] : pool[pool.length - 1];
  return pool[Math.max(0, Math.min(pool.length - 1, index + step))];
}

const ARROW_ITEMS = 'button:not([disabled]), a[href], input[type="checkbox"]:not([disabled])';

/** `onKeyDown` cho khung của bảng nổi: mũi tên / Home / End theo `arrowTarget`. Đang ở ô nhập, thanh trượt thì để phím cho ô ấy. */
export function menuArrowKeys(event: React.KeyboardEvent<HTMLElement>) {
  const target = event.target as HTMLElement;
  if (event.altKey || event.ctrlKey || event.metaKey || target.closest?.('input:not([type="checkbox"]), textarea, select, [role="slider"], [contenteditable="true"]')) return;
  const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(ARROW_ITEMS)).filter((item) => item.getClientRects().length > 0);
  const current = items.find((item) => item === target || item.contains(target)) ?? null;
  const next = arrowTarget(items, current, event.key, (item) => item.hasAttribute("data-arrow-side"));
  if (!next) return;
  event.preventDefault();
  event.stopPropagation();
  next.focus();
}

const QUARTERS = Array.from({ length: 96 }, (_, index) =>
  `${String(Math.floor(index / 4)).padStart(2, "0")}:${String((index % 4) * 15).padStart(2, "0")}`,
);

/** Giờ 24h ("22:00"), mỗi 15 phút. Ô `type="time"` gốc hiện theo locale hệ thống ("10:00 Chiều" cho 22:00 - soát UX
 *  29-09). Giờ đã lưu lệch 15 phút ("22:10") vẫn có trong danh sách. */
export function TimeSelect({
  value,
  onChange,
  label,
  className,
  disabled,
  ariaDisabled,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  className?: string;
  disabled?: boolean;
  ariaDisabled?: boolean;
}) {
  const options = QUARTERS.includes(value) ? QUARTERS : [...QUARTERS, value].sort();
  return (
    <select aria-label={label} value={value} disabled={disabled} aria-disabled={ariaDisabled || undefined}
      onPointerDown={(event) => { if (ariaDisabled) event.preventDefault(); }}
      onKeyDown={(event) => { if (ariaDisabled && event.key !== "Tab") event.preventDefault(); }}
      onChange={(event) => { if (!ariaDisabled) onChange(event.target.value); }} className={cn("tabular aria-disabled:opacity-50", className)}>
      {options.map((time) => (
        <option key={time} value={time}>
          {time}
        </option>
      ))}
    </select>
  );
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  wrap = false,
  className,
  itemClassName,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
  label: string;
  /** Trải hết bề ngang của khung (nhiều lựa chọn - 8 loại việc, thanh lọc cần ~1089px). Nhóm nào cũng xuống hàng khi khung hẹp hay chữ lớn, không tràn ngang (soát a100 V5). */
  wrap?: boolean;
  /** Thêm cho khung ngoài (vd. trải hết bề ngang trên điện thoại). */
  className?: string;
  /** Thêm cho từng nút (vd. cỡ chạm trên điện thoại). */
  itemClassName?: string;
}) {
  const values = options.map((option) => option.value);
  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={radioGroupKeys(values, value, onChange)}
      className={cn("flex-wrap gap-0.5 rounded-lg border border-line bg-panel-2 p-0.5", wrap ? "flex" : "inline-flex max-w-full", className)}
    >
      {options.map((option, index) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          tabIndex={radioTabIndex(values, value, index)}
          onClick={() => onChange(option.value)}
          className={cn(
            "touch-row h-7 whitespace-nowrap rounded-md px-3 text-[0.8125rem] font-medium transition-colors pointer-coarse:min-w-[48px]",
            value === option.value ? "bg-panel text-fg shadow-card" : "text-fg-2 hover:text-fg",
            itemClassName,
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
