import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { AlertTriangle, Check, ChevronLeft, ChevronRight, Loader2, RotateCw, WifiOff, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ButtonHTMLAttributes, ComponentType, CSSProperties, FocusEvent, HTMLAttributes, ReactNode, Ref, SelectHTMLAttributes } from "react";
import { cn } from "@/shared/cn";
import { markArrival, scrollMotion } from "@/shared/motion";
import { revealedScroll, wheelScroll } from "@/shared/tabScroll";
import { keepDots } from "./DotJoin";
import { MotionRegion } from "./MotionRegion";
import { MotionPresence } from "./MotionPresence";
import { SlidingIndicator } from "./SlidingIndicator";
import { useBackLayer } from "./backStack";
import { useMediaQuery } from "./media";
import { useRowFade, useScrollFadeOn } from "./scrollFade";

type IconType = ComponentType<{ className?: string; strokeWidth?: number }>;

/** Ô chọn trải hết cột như ô nhập; chỉ hàng giờ/phút đặt `inline` để các mảnh của một giá trị đứng cạnh nhau. */
export function Select({ className, inline, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { ref?: Ref<HTMLSelectElement>; inline?: boolean }) {
  return <select {...props} data-select-layout={inline ? "inline" : "column"} className={cn("shared-select max-w-full min-w-0 rounded-lg border border-line bg-panel px-2.5 text-sm font-normal text-fg outline-none focus-visible:border-focus disabled:opacity-50 aria-disabled:opacity-50", inline ? "w-auto" : "w-full", className)} />;
}

/** Dấu chọn giữ nguyên chỗ khi đổi mục; chỉ độ mờ đổi, không làm hàng nhảy ngang. Luôn đứng ĐẦU dòng của danh sách chọn (DESIGN 6; luật
 *  check-mark-trailing đọc `data-selection-mark`). */
export function SelectionMark({ selected, className }: { selected: boolean; className?: string }) {
  return <Check aria-hidden data-selection-mark className={cn("size-4 shrink-0 text-accent-text transition-opacity duration-motion-fast", selected ? "opacity-100" : "opacity-0", className)} />;
}

// ---- Nút --------------------------------------------------------------------------------------------------

type Variant = "primary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:bg-accent-hover [box-shadow:inset_0_1px_0_var(--button-shine)]",
  ghost: "text-accent-text hover:bg-hover",
  danger: "bg-danger-soft text-danger hover:bg-danger hover:text-danger-ink",
};

const SIZES: Record<Size, string> = {
  sm: "h-10 min-h-10 px-3 text-[0.8125rem] gap-1.5 rounded-lg",
  md: "h-10 min-h-10 px-3.5 text-sm gap-2 rounded-lg",
  lg: "h-10 min-h-10 px-5 text-[0.9375rem] gap-2 rounded-xl",
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

/** Nút có chữ dài (đường dẫn, tên mục): chữ xuống dòng, bẻ cả chuỗi liền, nút cao thêm thay vì rộng hơn khung - chữ hệ thống to ở 320 px không đẩy trang tràn ngang (soát a102).
 *  Một dòng thì cao đúng như nút cùng cỡ (min-h của cỡ nút giữ lại): trước đây `min-h-8 py-1.5` làm nút sm cao 32, md 32,5 cạnh nút thường 28 / 31,5. */
export const WRAP_LABEL = "h-auto max-w-full whitespace-normal py-1 leading-snug text-center [overflow-wrap:anywhere]";

export function Button({
  variant = "ghost",
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
      data-variant={variant}
      data-size={size}
      disabled={loading ? undefined : disabled}
      aria-disabled={loading || undefined}
      aria-busy={loading || undefined}
      onClick={busyClick(loading, onClick)}
      className={cn(
        "shared-button inline-flex select-none items-center justify-center whitespace-nowrap font-medium pointer-coarse:min-w-[48px] press transition-[background-color,color,border-color,outline-color,box-shadow,transform,scale,opacity] duration-motion-fast disabled:pointer-events-none disabled:opacity-45 aria-disabled:cursor-default aria-disabled:opacity-45",
        VARIANTS[variant],
        SIZES[size],
        // Màn hẹp / cảm ứng: nút 28-38 px nới vùng chạm theo chiều dọc lên 40 px (touch-reach trong styles.css; soát UX 29-09 và a14: "Sửa",
        // "Nam", "Nữ", "Thử giọng" chỉ 28-32 px trên điện thoại).
        "touch-reach",
        className,
      )}
      {...rest}
    >
      <MotionRegion as="span" aria-hidden className={cn("inline-grid shrink-0 place-items-center", !Icon && loading === undefined && "hidden", (Icon || loading !== undefined) && (size === "lg" ? "glyph" : "size-4"))}>{loading ? (
        <Loader2 className="size-4 animate-spin" />
      ) : Icon ? (
        <Icon className={size === "lg" ? "glyph" : "size-4"} strokeWidth={2} />
      ) : loading !== undefined ? <span /> : null}</MotionRegion>
      <MotionRegion as="span" className="inline-flex min-w-0 items-center gap-2" motionKey={typeof children === "string" || typeof children === "number" ? children : undefined}>{children}</MotionRegion>
    </button>
  );
}

/** Phán quyết của một hàng cần cỡ điều khiển và biểu tượng; liên kết mở ngữ cảnh dùng mực phụ. */
export function DecisionButton({ icon = Check, ...props }: ButtonProps) {
  return <Button {...props} data-decision icon={icon} />;
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
          "press inline-flex shrink-0 items-center justify-center rounded-lg transition-[color,background-color,outline-color,scale,opacity] duration-motion-fast disabled:pointer-events-none disabled:opacity-40",
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
          {/* Nhãn đổi lúc chú giải đang mở ("Nghe" -> "Dừng"): chữ mờ qua, không thay cứng. */}
          <MotionRegion as="span" className="block">{label}</MotionRegion>
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
      {/* Đổi kiểu thanh (chạy qua lại <-> phần trăm) mờ qua; đổi màu (tone) chuyển dần (.motion-progress / .indeterminate-bar) - không nhảy. */}
      <MotionRegion motionKey={indeterminate} className="h-full w-full">
      {indeterminate ? (
        <div className={cn("indeterminate-bar h-full w-2/5 rounded-full", BAR[tone])} />
      ) : (
        <div
          className={cn("motion-progress relative h-full overflow-hidden rounded-full", BAR[tone], running && "sheen")}
          style={{ transform: `scaleX(${clamped})` }}
        />
      )}
      </MotionRegion>
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

const STATUS_INK: Record<Tone, string> = {
  accent: "text-accent-text",
  success: "text-success",
  danger: "text-danger",
  warning: "text-warning",
  muted: "text-fg-2",
};

/** Trạng thái dạng CHỮ (không viên thuốc): đứng trong một dòng thông tin ("Đang thu âm · 24 chương · 2 giờ 33 phút") - viên thuốc nằm trên tiêu đề
 *  làm tiêu đề lệch dòng theo trạng thái. Cùng tên màu với StatusPill (tone), `live` thêm vạch nhạc đang chạy. */
export function StatusText({ label, tone, live = false, className }: { label: string; tone: Tone; live?: boolean; className?: string }) {
  return (
    <MotionRegion as="span" motionKey={[label, tone, live]} className={cn("inline-flex items-center gap-1.5 whitespace-nowrap font-medium transition-colors duration-motion-fast", STATUS_INK[tone], className)}>
      {live && <Vu className="h-2.5" />}
      {label}
    </MotionRegion>
  );
}

// ---- Tab --------------------------------------------------------------------------------------------------

export const Tabs = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

/** Bao các TabsContent của một hàng tab: Radix gỡ bảng cũ ngay khi đổi tab - không có vỏ chung thì bảng mới thay tức thì và chiều cao trang
 *  nhảy. Một MotionRegion khoá theo tab: bảng cũ trượt ra, bảng mới trượt vào từ phía tab vừa chọn (thứ tự đọc từ hàng tab của cùng Tabs), chiều cao chuyển dần. */
export function TabsPanels({ value, children, className }: { value: string; children: ReactNode; className?: string }) {
  const box = useRef<HTMLElement | null>(null);
  return <MotionRegion elementRef={box} motionKey={value} slideIndex={tabIndex(box.current, value)} fadeThrough className={className}>{children}</MotionRegion>;
}

/** Vị trí của tab `value` trong hàng tab của Tabs gần nhất (Radix đặt id nút tab là `<gốc>-trigger-<value>`). */
function tabIndex(panels: HTMLElement | null, value: string): number | undefined {
  const tabs = panels?.closest("[data-orientation]")?.querySelectorAll<HTMLElement>('[role="tab"]');
  const index = tabs ? Array.from(tabs).findIndex((tab) => tab.id.endsWith(`-trigger-${value}`)) : -1;
  return index < 0 ? undefined : index;
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
  // Mép mờ đổi bề rộng 0 <-> FADE bằng biến CSS có kiểu (@property --tab-fade-* trong styles.css) nên trượt dần, không bật cứng.
  const style = { "--tab-fade-l": `${edges.left ? FADE : 0}px`, "--tab-fade-r": `${edges.right ? FADE : 0}px` } as CSSProperties;
  const nudge = (direction: -1 | 1) => list.current?.scrollBy({ left: direction * list.current.clientWidth * 0.7, behavior: scrollMotion() });
  return (
    <div className="relative">
      <TabsPrimitive.List
        ref={list}
        aria-label={label}
        style={style}
        data-tab-row=""
        className={cn("tab-row-fade relative flex gap-5 overflow-x-auto overflow-y-hidden border-b border-line [scrollbar-width:none] sm:gap-6", className)}
      >
        <SlidingIndicator variant="line" />
        {children}
      </TabsPrimitive.List>
      {/* Mũi tên báo còn tab ngoài mép (mọi cỡ màn: chuột bấm được; bàn phím đã có phím mũi tên của hàng tab). */}
      {/* Luôn dựng, chỉ mờ vào / ra tại chỗ (.motion-hold): cuộn vài px không làm mũi tên bật ra cứng. */}
      <button type="button" tabIndex={-1} aria-label="Xem các tab trước" aria-hidden={!edges.left || undefined} data-state={edges.left ? "open" : "closed"} onClick={() => nudge(-1)} className="motion-hold absolute left-0 top-0 grid h-11 w-9 place-items-center text-fg-2 hover:text-fg">
        <span className="grid size-6 place-items-center rounded-full border border-line bg-panel-2 shadow-sm">
          <ChevronLeft className="size-3.5" />
        </span>
      </button>
      <button type="button" tabIndex={-1} aria-label="Xem các tab sau" aria-hidden={!edges.right || undefined} data-state={edges.right ? "open" : "closed"} onClick={() => nudge(1)} className="motion-hold absolute right-0 top-0 grid h-11 w-9 place-items-center text-fg-2 hover:text-fg">
        <span className="grid size-6 place-items-center rounded-full border border-line bg-panel-2 shadow-sm">
          <ChevronRight className="size-3.5" />
        </span>
      </button>
    </div>
  );
}

// Không đệm ngang: chữ tab đầu thẳng mép nội dung (bìa, nút chính) và gạch chân dài đúng bằng chữ, như hàng lọc Thư viện (soát 24-10).
// Điện thoại, hàng 2-4 tab: tab chia đều bề ngang, chữ căn giữa (Material "fixed tabs" - chủ sách 25-10) - xem [data-tab-row] trong styles.css.
export function TabsTrigger({ value, children, count }: { value: string; children: ReactNode; count?: number }) {
  return (
    <TabsPrimitive.Trigger
      value={value}
      className="touch-row relative -mb-px inline-flex h-11 shrink-0 items-center whitespace-nowrap border-b-2 border-transparent text-sm font-medium text-fg-2 transition-colors duration-motion-medium hover:text-fg data-[state=active]:text-fg"
    >
      <TabLabel count={count}>{children}</TabLabel>
    </TabsPrimitive.Trigger>
  );
}

/** Tên tab + số đếm trên CÙNG một đường chân chữ (DESIGN 6 "Tab trong trang": số nhỏ cạnh chữ). Dùng cho mọi tab - kể cả nút "Thêm" -
 *  để số không lệch dòng với tên ở chỗ nào. Số là chữ trơn `--text-2`, không viên thuốc. */
export function TabLabel({ count, children }: { count?: number; children: ReactNode }) {
  return (
    <span data-indicator-target="" className="inline-flex items-baseline gap-1.5">
      {children}
      {/* Số đếm dính vào tên khi đọc ("Chương6") - trình đọc màn hình nghe "Chương, 6 mục" (soát a67). */}
      <MotionRegion as="span" className="inline-flex" motionKey={count ?? null}>{count !== undefined && (
        <span className="tabular text-xs font-normal text-fg-2">
          <span className="sr-only">, </span>
          {count}
          <span className="sr-only"> mục</span>
        </span>
      )}</MotionRegion>
    </span>
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

/** Hộp / bảng vừa mở: thứ dựng cùng nó (MotionPresence đang mở, hàng danh sách) đứng tại chỗ cùng hộp đang hiện vào, không mọc từ 0 bên trong
 *  (motion.ts pageSettling, như trang mới vào). Thứ tới SAU lúc ấy (lỗi, hàng mới) vẫn mở ra có chuyển động. Đánh dấu lúc dựng, trước khi con dựng. */
function useArrivalOnOpen(open: boolean) {
  const was = useRef(false);
  if (open && !was.current) markArrival();
  useLayoutEffect(() => {
    was.current = open;
  });
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  width = "max-w-lg",
  footer,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  width?: string;
  footer?: ReactNode;
}) {
  useArrivalOnOpen(open);
  // Nhớ phần tử đang giữ con trỏ lúc hộp mở (trước khi Radix chuyển con trỏ vào hộp) để trả về khi đóng.
  const opener = useRef<Element | null>(null);
  const lastContent = useRef({ title, description, children, footer });
  if (open) lastContent.current = { title, description, children, footer };
  const shown = open ? { title, description, children, footer } : lastContent.current;
  useLayoutEffect(() => {
    if (open) opener.current = lastFocus;
  }, [open]);
  const phone = useMediaQuery("(max-width: 640px)");
  // Thân cuộn mờ ở mép còn nội dung (DESIGN 4.5: không gì cụt cứng) - hộp dài như bộ sách nhiều tập không giấu hàng cuối không dấu hiệu.
  const [body, setBody] = useState<HTMLDivElement | null>(null);
  const fade = useScrollFadeOn(body);
  // Ô mang `data-escape-local` (vd ô đổi tên chương) tự xử lý phím Esc để huỷ việc đang gõ; Esc ở đó không đóng cả hộp.
  const escapeLocal = (event: KeyboardEvent) => {
    if ((event.target as HTMLElement | null)?.closest?.("[data-escape-local]")) event.preventDefault();
  };
  if (phone) return <Sheet open={open} onOpenChange={onOpenChange} title={title} description={description} footer={footer} onEscapeKeyDown={escapeLocal}>{children}</Sheet>;
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
            "motion-dialog fixed left-[calc(50%+(env(safe-area-inset-left)-env(safe-area-inset-right))/2)] top-[calc(50%+(env(safe-area-inset-top)-env(safe-area-inset-bottom))/2)] z-50 w-[calc(100%-2rem-env(safe-area-inset-left)-env(safe-area-inset-right))] -translate-x-1/2 -translate-y-1/2 flex max-h-[min(90dvh,calc(100dvh-2rem-env(safe-area-inset-top)-env(safe-area-inset-bottom)))] flex-col rounded-[20px] border border-line bg-panel p-[24px] shadow-float focus:outline-none",
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
          onEscapeKeyDown={escapeLocal}
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
              <DialogPrimitive.Title data-surface-title className="text-lg font-bold">
                <MotionRegion as="span" className="block" motionKey={typeof shown.title === "string" || typeof shown.title === "number" ? shown.title : undefined}>{keepDots(shown.title)}</MotionRegion>
              </DialogPrimitive.Title>
              <DialogPrimitive.Description className="text-sm text-fg-2">
                <MotionRegion as="span" className={shown.description ? "mt-1 block" : "block"} motionKey={typeof shown.description === "string" || typeof shown.description === "number" ? shown.description : undefined}>{keepDots(shown.description)}</MotionRegion>
              </DialogPrimitive.Description>
            </div>
            {/* Mực của ✕ dừng 5/24 ô biểu tượng trước mép ô (3,65 px ở 17,5 px): lề phải bù thêm chừng ấy cho mực thẳng mép nội dung. */}
            <DialogPrimitive.Close asChild>
              <button aria-label="Đóng" className={cn(CLOSE_BUTTON, "-mr-[16.9px] pointer-coarse:-mr-[18.9px]")}>
                <X className="size-5" />
              </button>
            </DialogPrimitive.Close>
          </div>
          {/* Hộp cao hơn màn (điện thoại, cửa sổ thấp) thì nội dung cuộn trong hộp, nút Đóng ở đầu luôn thấy được (soát UX a15). */}
          <div ref={setBody} style={fade} className="dialog-body -mx-1 min-h-0 flex-1 overflow-y-auto overscroll-contain px-1">{shown.children}</div>
          <SurfaceFooter>{shown.footer}</SurfaceFooter>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** Chân hộp tách khỏi thân cuộn: nút luôn thấy; một bố cục cho mỗi nền tảng. */
function SurfaceFooter({ children }: { children?: ReactNode }) {
  return <MotionPresence open={Boolean(children)} className="surface-footer shrink-0" bodyClassName="border-t border-line pt-4 mt-4">{children}</MotionPresence>;
}

export function DialogActions({ children, className, ...props }: HTMLAttributes<HTMLElement>) {
  return <MotionRegion {...props} data-dialog-actions className={cn("dialog-actions", className)}>{children}</MotionRegion>;
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
  description,
  footer,
  focusSelector,
  onKeyDown,
  className,
  onHeightChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  trigger?: ReactNode;
  children: ReactNode;
  onEscapeKeyDown?: (event: KeyboardEvent) => void;
  description?: ReactNode;
  footer?: ReactNode;
  focusSelector?: string;
  onKeyDown?: React.KeyboardEventHandler<HTMLDivElement>;
  className?: string;
  onHeightChange?: (height: number) => void;
}) {
  useArrivalOnOpen(open);
  const lastContent = useRef({ title, children, description, footer });
  if (open) lastContent.current = { title, children, description, footer };
  const shown = open ? { title, children, description, footer } : lastContent.current;
  const opener = useRef<Element | null>(null);
  const start = useRef<number | null>(null);
  const dragged = useRef(false);
  const [drag, setDrag] = useState(0);
  const [surface, setSurface] = useState<HTMLDivElement | null>(null);
  const [body, setBody] = useState<HTMLDivElement | null>(null);
  const fade = useScrollFadeOn(body);
  const closeSheet = useRef(onOpenChange);
  closeSheet.current = onOpenChange;
  useEffect(() => {
    if (!surface || !open) return;
    let origin: { x: number; y: number } | null = null;
    let distance = 0;
    const begin = (event: TouchEvent) => {
      const target = event.target as Element;
      if (target.closest('button, input, textarea, select, [role="slider"], [data-sheet-grip]')) return;
      for (let node = target; node && node !== surface; node = node.parentElement!) {
        if (node.scrollTop > 0) return;
      }
      const touch = event.touches[0];
      if (touch) origin = { x: touch.clientX, y: touch.clientY };
    };
    const move = (event: TouchEvent) => {
      if (!origin || !event.touches[0]) return;
      const touch = event.touches[0];
      distance = Math.max(0, touch.clientY - origin.y);
      // Ngón về lại trên điểm đầu (hay vuốt ngang): bảng về chỗ, không đứng lệch tới khi nhấc tay.
      if (distance <= Math.abs(touch.clientX - origin.x)) { distance = 0; setDrag(0); return; }
      event.preventDefault(); setDrag(distance);
    };
    const end = () => { if (distance >= 64) closeSheet.current(false); origin = null; distance = 0; setDrag(0); };
    const cancel = () => { origin = null; distance = 0; setDrag(0); };
    surface.addEventListener("touchstart", begin, { passive: true });
    surface.addEventListener("touchmove", move, { passive: false });
    surface.addEventListener("touchend", end);
    surface.addEventListener("touchcancel", cancel);
    return () => {
      surface.removeEventListener("touchstart", begin); surface.removeEventListener("touchmove", move);
      surface.removeEventListener("touchend", end); surface.removeEventListener("touchcancel", cancel);
    };
  }, [surface, open]);
  useEffect(() => {
    if (!open || !onHeightChange) return;
    const element = surface;
    if (!element) return;
    const update = () => onHeightChange(element.getBoundingClientRect().height);
    update();
    const observer = new ResizeObserver(update); observer.observe(element);
    return () => { observer.disconnect(); onHeightChange(0); };
  }, [open, onHeightChange, surface]);
  useLayoutEffect(() => { if (open) opener.current = lastFocus; }, [open]);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      {trigger && <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>}
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay inert={!open} style={open ? undefined : CLOSING} className="motion-scrim fixed inset-0 z-40 bg-scrim" />
        <DialogPrimitive.Content
          {...(!shown.description ? { "aria-describedby": undefined } : {})}
          ref={setSurface}
          inert={!open}
          style={!open ? CLOSING : drag ? { transform: `translateY(${drag}px)`, animation: "none", transition: "none" } : undefined}
          onCloseAutoFocus={(event) => {
            if (keepNewLayerFocus(event)) return;
            if (!trigger) {
              const target = focusReturnTarget(opener.current, document.body);
              if (target) { event.preventDefault(); target.focus(); }
            }
          }}
          onOpenAutoFocus={(event) => {
            const target = (event.currentTarget as HTMLElement).querySelector<HTMLElement>(focusSelector ?? "[data-autofocus]");
            if (!target) return;
            event.preventDefault(); target.focus();
            if (target instanceof HTMLInputElement) target.select();
          }}
          onKeyDown={onKeyDown}
          // Đóng (Esc, nút Đóng, chạm nền): Radix tự trả tiêu điểm về nút mở (Trigger) - trước đây chặn việc ấy nên tiêu điểm rơi về BODY (soát a31 K1).
          onEscapeKeyDown={onEscapeKeyDown}
          onInteractOutside={keepOpenForToasts}
          className={cn("motion-sheet sheet-surface fixed inset-x-0 bottom-0 z-50 flex max-h-[min(85dvh,calc(100dvh-env(safe-area-inset-top)-0.5rem))] min-w-0 flex-col rounded-t-[20px] bg-panel pl-[max(env(safe-area-inset-left),20px)] pr-[max(env(safe-area-inset-right),20px)] pb-[max(env(safe-area-inset-bottom),20px)] shadow-float focus:outline-none", className)}
        >
          <div data-sheet-grip className="shrink-0 touch-none pb-3 pt-3"
            onPointerDown={(event) => {
              if (event.target instanceof Element && event.target.closest("button:not([data-sheet-handle])")) return;
              dragged.current = false;
              start.current = event.clientY; event.currentTarget.setPointerCapture?.(event.pointerId);
            }}
            onPointerMove={(event) => { if (start.current !== null) { dragged.current ||= Math.abs(event.clientY - start.current) > 4; setDrag(Math.max(0, event.clientY - start.current)); } }}
            onPointerUp={(event) => {
              const distance = start.current === null ? 0 : event.clientY - start.current;
              start.current = null; setDrag(0);
              if (distance >= 64) onOpenChange(false);
            }}
            onPointerCancel={() => { start.current = null; setDrag(0); }}>
          <DialogPrimitive.Close asChild>
            <button type="button" aria-label="Đóng" data-sheet-handle onClick={(event) => { if (dragged.current) { event.preventDefault(); dragged.current = false; } }} className="mx-auto mb-2 flex size-[48px] items-center justify-center rounded-lg">
              <span className="h-[4px] w-[40px] rounded-full bg-line-strong" aria-hidden />
            </button>
          </DialogPrimitive.Close>
          <div className="flex items-center justify-between gap-3">
            <DialogPrimitive.Title data-surface-title className="text-lg font-bold">
              <MotionRegion as="span" className="block" motionKey={typeof shown.title === "string" || typeof shown.title === "number" ? shown.title : undefined}>{keepDots(shown.title)}</MotionRegion>
            </DialogPrimitive.Title>
          </div>
          </div>
          <div ref={setBody} style={fade} className="sheet-body -mx-[20px] min-h-0 min-w-0 overflow-y-auto overscroll-contain px-[20px]">
            {/* Mô tả / chân bảng hiện / ẩn lúc bảng đang mở: mở / khép tại chỗ (lúc mở bảng thì đứng yên cùng bảng - useArrivalOnOpen). */}
            <MotionPresence open={Boolean(shown.description)}><DialogPrimitive.Description className="mb-3 text-pretty text-sm text-fg-2"><MotionRegion as="span" className="block" motionKey={typeof shown.description === "string" ? shown.description : undefined}>{keepDots(shown.description)}</MotionRegion></DialogPrimitive.Description></MotionPresence>
            {shown.children}
          </div>
          <SurfaceFooter>{shown.footer}</SurfaceFooter>
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

/** Lỗi ở ngay vùng bị ảnh hưởng; nội dung đã có vẫn dùng được. `open`: chỗ gọi hiện / ẩn lỗi theo điều kiện - truyền điều kiện vào đây
 *  thay vì dựng / gỡ cả phần tử theo điều kiện ấy, để lỗi mở / khép tại chỗ (MotionPresence) chứ không bật tắt (soát chuyển động 139; motionLint.test.ts
 *  chặn kiểu viết cũ). */
export function InlineError({ message, onRetry, className, open }: { message: string; onRetry: () => void; className?: string; open?: boolean }) {
  if (open !== undefined) return <MotionPresence open={open}><InlineError message={message} onRetry={onRetry} className={className} /></MotionPresence>;
  // Nút đứng ngay sau câu (màn rộng không đẩy nó ra mép phải); màn hẹp xuống dòng thì thẳng mép với chữ - -ml bù phần đệm của nút ghost.
  // Câu đệm trên dưới cho dòng đầu đứng giữa chiều cao nút (--button-h), icon đứng giữa dòng ấy - cả khi câu gãy dòng hay nút xuống dòng
  // (từng là mt-[3px] theo chữ trần: hàng cao bằng nút đẩy chữ xuống, icon treo trên dòng - soát 25-10, máy dò icon-off-first-line).
  return <MotionRegion role="alert" motionKey={message} className={cn("motion-reveal flex items-start gap-3 py-3 text-sm", className)}>
    <AlertTriangle aria-hidden className="ink-start mt-[calc((var(--button-h)-1rem)/2)] size-4 shrink-0 text-danger" />
    <div className="flex min-w-0 flex-wrap items-start gap-x-3 gap-y-1">
      <p className="measure min-w-0 py-[calc((var(--button-h)-1lh)/2)] text-balance text-fg-2">{message}</p>
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
    {/* Nền tràn cả bề ngang, chữ thẳng lề nội dung của trang bên dưới (page-x, khung 1180 như Thư viện / Studio) - từng bắt đầu ở 17,5 px
        (máy tính x=254 trong khi lề nội dung 288, soát 25-10). */}
    <div role="status" className="border-b border-line bg-warning-soft py-2 text-xs text-fg-2">
      <div className="page-x mx-auto flex max-w-[1180px] items-center gap-2">
        <WifiOff aria-hidden className="ink-start size-3.5 shrink-0 [--icon-w:calc(var(--spacing)*3.5)]" /><span>{message}</span>
      </div>
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
  // Tự là một vùng: đổi tiêu đề / lời / nút lúc đang hiện (tìm chữ khác, lọc khác) mờ qua tại chỗ, không đổi cứng; hiện / ẩn cả khối thì chỗ
  // gọi bọc MotionPresence (motionLint.test.ts).
  return (
    <MotionRegion className={cn("motion-reveal flex flex-col items-center px-6 py-14 text-center", className)}>
      <div className="mb-4 grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent-text">
        <Icon className="size-7" strokeWidth={1.75} />
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <p className="mt-1.5 max-w-md text-sm leading-relaxed text-fg-2">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </MotionRegion>
  );
}

/** Danh sách tải lỗi mà chưa có gì để hiện: phải nói là LỖI, không phải "chưa có gì" (soát a28 lỗi 4 - thư viện báo "Chưa có sách" khi máy
 *  chủ trả 500). Đã có dữ liệu từ lần trước thì cứ hiện dữ liệu ấy. */
export function failedEmpty(query: { isError: boolean; data?: readonly unknown[] | null }): boolean {
  return query.isError && !query.data?.length;
}

export function LoadError({ what, onRetry, className, open }: { what: string; error?: unknown; onRetry: () => void; className?: string; open?: boolean }) {
  return <InlineError message={`Chưa tải được ${what}; bạn hãy kiểm tra kết nối rồi thử lại.`} onRetry={onRetry} className={className} open={open} />;
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-line-strong bg-panel-2 px-[6px] font-sans text-[0.6875rem] font-medium text-fg-2">
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
    <Select inline aria-label={label} value={value} disabled={disabled} aria-disabled={ariaDisabled || undefined}
      onPointerDown={(event) => { if (ariaDisabled) event.preventDefault(); }}
      onKeyDown={(event) => { if (ariaDisabled && event.key !== "Tab") event.preventDefault(); }}
      onChange={(event) => { if (!ariaDisabled) onChange(event.target.value); }} className={cn("tabular aria-disabled:opacity-50", className)}>
      {options.map((time) => (
        <option key={time} value={time}>
          {time}
        </option>
      ))}
    </Select>
  );
}

export function ChoiceRow<T extends string>({
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
      className={cn("choice-row relative max-w-full flex-wrap gap-x-[24px] gap-y-1", wrap ? "flex" : "inline-flex max-w-full", className)}
    >
      <SlidingIndicator variant="line" />
      {options.map((option, index) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          tabIndex={radioTabIndex(values, value, index)}
          onClick={() => onChange(option.value)}
          className={cn(
            "touch-hit touch-row relative min-h-10 whitespace-nowrap border-b-2 border-transparent text-sm font-medium transition-colors duration-motion-medium",
            value === option.value ? "font-bold text-fg" : "text-fg-2 hover:text-fg",
            itemClassName,
          )}
        >
          <ChoiceLabel text={option.label} />
        </button>
      ))}
    </div>
  );
}

/** Mép nét chữ, kể cả dấu nhô của “ữ”, quyết định khoảng nhìn thấy giữa hai lựa chọn. */
function ChoiceLabel({ text }: { text: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const context = document.createElement("canvas").getContext("2d");
      if (!context) return;
      const s = getComputedStyle(el);
      context.font = `${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
      const m = context.measureText(text);
      el.style.marginInlineStart = `${m.actualBoundingBoxLeft}px`;
      el.style.marginInlineEnd = `${m.actualBoundingBoxRight - m.width}px`;
    };
    measure();
    document.fonts?.addEventListener("loadingdone", measure);
    return () => document.fonts?.removeEventListener("loadingdone", measure);
  }, [text]);
  return <span ref={ref} className="block">{text}</span>;
}

/** Hàng lọc: chữ trơn, mục đang chọn có gạch chân hổ phách (DESIGN 6 "Bộ lọc") - không hộp segmented. Cùng nghĩa radiogroup như `ChoiceRow`
 *  (mũi tên đổi mục, tiêu điểm vào đúng mục đang chọn). Khoảng cách như hàng lọc Thư viện: 20 px, 24 px từ `sm`. */
export function FilterRow<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
  label: string;
  className?: string;
}) {
  const values = options.map((option) => option.value);
  const [row, setRow] = useState<HTMLDivElement | null>(null);
  const fade = useRowFade(row);
  return (
    <div ref={setRow} style={fade} role="radiogroup" aria-label={label} onKeyDown={radioGroupKeys(values, value, onChange)} className={cn("relative flex max-w-full overflow-x-auto [scrollbar-width:none]", className)}>
      <SlidingIndicator variant="line" />
      {options.map((option, index) => [
        index > 0 && <RowGap key={`gap-${option.value}`} />,
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          tabIndex={radioTabIndex(values, value, index)}
          onClick={() => onChange(option.value)}
          className={cn(
            "touch-row h-9 shrink-0 whitespace-nowrap border-b-2 border-transparent text-sm font-medium transition-colors duration-motion-medium",
            value === option.value ? "text-fg" : "text-fg-2 hover:text-fg",
          )}
        >
          <ChoiceLabel text={option.label} />
        </button>,
      ])}
    </div>
  );
}

/** Khoảng giữa các mục của hàng lọc / hàng tab: 20 px (24 px từ `sm`) nhưng CO được tới 8 px khi hàng gần đủ chỗ - thiếu vài px không biến cả
 *  hàng thành thanh cuộn (chủ sách 25-10: "chỉ có một chút xíu content thôi cũng thành scroll"). Thật sự không vừa thì mới cuộn + mờ mép. */
export function RowGap({ className }: { className?: string }) {
  return <span aria-hidden className={cn("w-5 min-w-2 shrink sm:w-6", className)} />;
}
