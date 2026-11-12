import { Minus, Plus } from "lucide-react";
import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { S } from "./strings.generated";
import { cn } from "./cn";
import { feedback } from "./feedback";
import { MotionPresence } from "./MotionPresence";
import { announce } from "./ui";
import { PAGE_STEPS, tickLabels, chipRows, chipIndex, formatNumber, fromFraction, isDetent, parseValue, quantize, stepValue, toFraction, type ValueSpec } from "./valuePickerLogic";

/** Giữ nút -/+: chờ chừng này rồi lặp. */
const REPEAT_DELAY_MS = 400;
const REPEAT_EVERY_MS = 80;

/**
 * Bộ chọn giá trị số - MỘT kiểu cho cả app (DESIGN mục 6 "Chọn giá trị"; Android ValuePicker.kt, Qt ValuePicker.qml cùng cấu trúc), từ trên xuống:
 *  1. giá trị hiện tại chữ lớn - chạm vào là gõ số (Enter xác nhận, Esc bỏ, kẹp trong biên và báo nhẹ "Trong khoảng a–b");
 *  2. thước kéo tự do giữa nút - / + (giữ để lặp); nấc hút + tiếng/rung ở các giá trị tiêu biểu; phím mũi tên một bước, PageUp/PageDown mười bước;
 *  3. hàng chip giá trị tiêu biểu, chip trùng giá trị đang chọn chữ --text đậm;
 *  4. `children`: lựa chọn đặc biệt không phải số ("Hết chương này"), hàng riêng dưới cùng.
 * `onChange` là lúc áp (thả tay, chạm chip, -/+, Enter, phím); khi kéo, chữ lớn và thước chạy theo tay, `onPreview` nếu cần nghe ngay.
 * `dense`: two rows: label + editable value, then ruler with numeric labels centred below its detents.
 */
export function ValuePicker({
  spec,
  value,
  onChange,
  onPreview,
  format,
  chipLabel,
  label,
  hint,
  dense = false,
  stepperOnly = false,
  stepButtons = true,
  disabled = false,
  busy = false,
  current = true,
  className,
  children,
}: {
  spec: ValueSpec;
  value: number;
  onChange: (value: number) => void;
  onPreview?: (value: number) => void;
  /** Chữ của một giá trị kèm đơn vị: "23 phút", "1,35×". */
  format: (value: number) => string;
  /** Chữ trên chip; mặc định như `format`. */
  chipLabel?: (value: number) => string;
  /** Tên của giá trị (trình đọc màn hình, ô gõ; hàng `dense` hiện ra). */
  label: string;
  /** Dòng giải thích dưới tên (hàng `dense` của Cài đặt). */
  hint?: ReactNode;
  dense?: boolean;
  /** A labelled count with the shared editable value between the step buttons. */
  stepperOnly?: boolean;
  stepButtons?: boolean;
  disabled?: boolean;
  /** Đang lưu lần đổi trước: vẫn focus được (aria-disabled), nhưng không đổi gì. */
  busy?: boolean;
  /** false: giá trị này chưa phải lựa chọn đang áp (hẹn giờ đang "Hết chương") - không tô chip nào. */
  current?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  const [moving, setMoving] = useState<number | null>(null);
  const [typing, setTyping] = useState(false);
  const [clampNote, setClampNote] = useState(false);
  const shown = quantize(spec, moving ?? value);
  const last = useRef(shown);
  last.current = shown;
  const track = useRef<HTMLDivElement>(null);
  const rulerId = useId();
  const repeat = useRef<{ timer: ReturnType<typeof setTimeout> | null; pressed: boolean }>({ timer: null, pressed: false });
  const input = useRef<HTMLInputElement>(null);
  const tickGesture = useRef({x: 0, dragged: false});
  const rulerHost = useRef<HTMLDivElement>(null);
  const [plan, setPlan] = useState({inset: 8, aligned: false});
  const labels = spec.typical.map(chipLabel ?? (v => formatNumber(spec, v)));
  const labelKey = JSON.stringify(labels);
  useLayoutEffect(() => {
    const host = rulerHost.current;
    if (!host) return;
    const measure = () => {
      const width = host.getBoundingClientRect().width;
      if (width <= 0) return;
      const widths = [...host.querySelectorAll<HTMLElement>("[data-value-label-measure]")].map(node => Math.ceil(node.getBoundingClientRect().width) + 1); // + 1px: centred text snaps to device pixels
      const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
      const next = tickLabels(spec.typical.map(v => toFraction(spec, v)), widths, width, rem / 2, rem / 4);
      setPlan(old => old.inset === next.inset && old.aligned === next.aligned ? old : next);
    };
    measure();
    void document.fonts?.ready.then(measure);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(host);
    host.querySelectorAll("[data-value-label-measure]").forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [spec, labelKey, dense]);

  useEffect(() => () => {
    if (repeat.current.timer) clearTimeout(repeat.current.timer);
  }, []);
  useEffect(() => {
    if (typing) input.current?.select();
  }, [typing]);

  const commit = (next: number) => {
    setMoving(null);
    if (busy) return;
    // Chưa phải lựa chọn đang áp (`current` false): chọn đúng giá trị đang đứng vẫn là đặt.
    if (next !== value || !current) onChange(next);
  };
  const nudge = (steps: number) => {
    const next = stepValue(spec, last.current, steps);
    if (next === last.current) return;
    if (isDetent(spec, last.current, next)) feedback("tick");
    last.current = next;
    commit(next);
  };

  const fractionAt = (clientX: number) => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0) return toFraction(spec, shown);
    const inset = plan.inset;
    return (clientX - rect.left - inset) / (rect.width - 2 * inset);
  };
  const drag = (clientX: number) => {
    const next = fromFraction(spec, fractionAt(clientX));
    if (next === last.current) return;
    if (isDetent(spec, last.current, next)) feedback("tick");
    last.current = next;
    setMoving(next);
    onPreview?.(next);
  };
  const onPointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    if (disabled || event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.focus({ preventScroll: true });
    drag(event.clientX);
  };
  const onPointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    if (moving === null || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
    drag(event.clientX);
  };
  const onPointerUp = (event: ReactPointerEvent<HTMLElement>) => {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    if (moving !== null) commit(moving);
  };
  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const steps = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: PAGE_STEPS, PageDown: -PAGE_STEPS }[event.key];
    let next: number | null = null;
    if (steps !== undefined) next = stepValue(spec, shown, steps);
    else if (event.key === "Home") next = spec.min;
    else if (event.key === "End") next = spec.max;
    if (next === null) return;
    // Phím mũi tên đổi giá trị này, không tua sách (phím tắt của trình phát nằm ở cửa sổ).
    event.preventDefault();
    event.stopPropagation();
    if (isDetent(spec, shown, next)) feedback("tick");
    commit(next);
  };

  const startRepeat = (steps: number) => {
    nudge(steps);
    const again = (delay: number) => {
      repeat.current.timer = setTimeout(() => {
        nudge(steps);
        again(REPEAT_EVERY_MS);
      }, delay);
    };
    again(REPEAT_DELAY_MS);
  };
  const stopRepeat = () => {
    if (repeat.current.timer) clearTimeout(repeat.current.timer);
    repeat.current.timer = null;
  };
  // Nút trơn (không Tooltip): bộ chọn nằm cả ở chỗ không có TooltipProvider (Cài đặt, hộp sửa sách); tên nằm ở aria-label + title.
  const stepButton = (steps: number) => {
    if (!stepButtons) return null;
    const Icon = steps < 0 ? Minus : Plus;
    const name = steps < 0 ? S.s_giam_a6c2901a : S.s_tang_a2363bce;
    return (
      <button
        type="button"
        aria-label={name}
        title={name}
        disabled={disabled || (steps < 0 ? shown <= spec.min : shown >= spec.max)}
        aria-disabled={busy || undefined}
        data-value-step={steps < 0 ? "down" : "up"}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          repeat.current.pressed = true;
          startRepeat(steps);
        }}
        onPointerUp={stopRepeat}
        onPointerLeave={stopRepeat}
        onPointerCancel={stopRepeat}
        // Bàn phím / trình đọc màn hình: Enter, Space là một bước; chạm / chuột đã bước ở onPointerDown.
        onClick={() => {
          if (repeat.current.pressed) repeat.current.pressed = false;
          else nudge(steps);
        }}
        className={cn(
          "press touch-reach inline-flex shrink-0 items-center justify-center rounded-control text-fg-2 transition-[color,background-color,scale,opacity] duration-motion-fast hover:bg-hover hover:text-fg disabled:pointer-events-none disabled:opacity-40 pointer-coarse:min-w-[48px]",
          // Kiểu gọn: mực của "−" / "+" thẳng mép cột chữ (nút 32, icon 12: đệm 10 px - máy dò INK EDGE).
          "size-12",
        )}
      >
        <Icon className="glyph" strokeWidth={2} />
      </button>
    );
  };

  const finishTyping = (text: string | null) => {
    setTyping(false);
    if (text === null) return;
    const parsed = parseValue(spec, text);
    if (!parsed) return;
    setClampNote(parsed.clamped);
    if (parsed.clamped) announce(S.s_trong_khoang_0_1_5313ae3f(format(spec.min), format(spec.max)));
    commit(parsed.value);
  };

  const fraction = toFraction(spec, shown);
  const selected = current ? chipIndex(spec, shown) : -1;
  const big = (
    <span className={cn(dense ? "text-sm text-fg-2" : "text-3xl font-semibold leading-tight text-fg")}>{format(shown)}</span>
  );
  const valueField = typing ? (
    <input
      ref={input}
      data-value-input
      aria-label={label}
      inputMode="decimal"
      enterKeyHint="done"
      defaultValue={formatNumber(spec, shown)}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.key === "Enter") finishTyping(event.currentTarget.value);
        else if (event.key === "Escape") {
          event.preventDefault();
          finishTyping(null);
        }
      }}
      onBlur={(event) => finishTyping(event.currentTarget.value)}
      className={cn(
        "rounded-control border border-line-strong bg-panel px-2 text-center outline-none focus-visible:ring-2 focus-visible:ring-focus",
        dense ? "h-8 w-20 text-sm" : "h-12 w-32 text-2xl font-semibold",
      )}
    />
  ) : (
    <button
      type="button"
      data-value-display
      aria-pressed={stepperOnly ? current : undefined}
      disabled={disabled}
      aria-disabled={busy || undefined}
      title={S.s_cham_de_go_so_adc1d0d1}
      aria-label={`${label}: ${format(shown)}. ${S.s_cham_de_go_so_adc1d0d1}`}
      onClick={() => {
        if (stepperOnly && !current) { commit(shown); return; }
        setClampNote(false);
        setTyping(true);
      }}
      className={cn("press touch-reach min-w-12 rounded-control px-2 hover:bg-hover disabled:opacity-40", dense ? "-mr-2 h-5" : "min-h-12")}
    >
      {big}
    </button>
  );

  if (stepperOnly) return <div data-value-picker data-value-stepper className={cn("flex flex-col gap-2", className)}>
    <div data-value-section-label className="text-sm text-fg-2">{label}</div>
    <div className="flex items-center">{stepButton(-1)}<div className="flex min-w-0 flex-1 justify-center">{valueField}</div>{stepButton(1)}</div>
    <MotionPresence open={clampNote}><p data-value-clamped className="text-center text-xs text-fg-2">{S.s_trong_khoang_0_1_5313ae3f(format(spec.min), format(spec.max))}</p></MotionPresence>
  </div>;

  return (
    <div data-value-picker data-value-dense={dense || undefined} aria-disabled={disabled || undefined} className={cn("flex min-w-0 flex-col", dense ? "gap-0" : "gap-2", disabled && "opacity-50", className)}>
      {dense ? (
        <div className="flex min-h-5 items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-medium text-pretty">{label}</div>
            {hint && <div className="mt-0.5 text-xs leading-snug text-fg-2 [overflow-wrap:anywhere]">{hint}</div>}
          </div>
          {valueField}
        </div>
      ) : (
        <div className="flex min-h-12 items-center justify-center">{valueField}</div>
      )}
      <MotionPresence open={clampNote}>
        <p data-value-clamped className={cn("text-xs text-fg-2", !dense && "text-center")}>
          {S.s_trong_khoang_0_1_5313ae3f(format(spec.min), format(spec.max))}
        </p>
      </MotionPresence>
      <div className="flex items-start">
        {stepButton(-1)}
        <div ref={rulerHost} className={cn("relative min-w-0 flex-1", !plan.aligned ? "h-12" : dense ? "h-14" : "h-16")}>
          {labels.map((text, i) => <span key={i} aria-hidden data-value-label-measure className={cn("pointer-events-none invisible absolute whitespace-nowrap font-semibold ", dense ? "text-xs" : "text-sm")}>{text}</span>)}
          <div
          ref={track}
          id={rulerId}
          role="slider"
          tabIndex={disabled ? -1 : 0}
          aria-label={label}
          aria-valuemin={spec.min}
          aria-valuemax={spec.max}
          aria-valuenow={shown}
          aria-valuetext={format(shown)}
          aria-disabled={disabled || busy || undefined}
          data-value-ruler
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onKeyDown={onKeyDown}
          className="group relative h-12 w-full cursor-pointer touch-none select-none rounded-control outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <span aria-hidden className="absolute top-1/2 h-1 -translate-y-1/2 overflow-hidden rounded-full bg-line-strong" style={{left: plan.inset, right: plan.inset}}>
            {/* Chỉ transform (không transition bề rộng / vị trí - luật gallery_jank_policy). */}
            <span
              className={cn("absolute inset-0 origin-left rounded-full bg-accent", moving === null && "transition-transform duration-motion-fast")}
              style={{ transform: `scaleX(${fraction})` }}
            />
          </span>
          {plan.aligned && spec.typical.map((typical) => (
            <span
              key={typical}
              aria-hidden
              data-value-detent
              className="pointer-events-none absolute top-1/2 h-3 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-fg-2 opacity-60"
              style={{ left: `calc(${plan.inset}px + (100% - ${2 * plan.inset}px) * ${toFraction(spec, typical)})` }}
            />
          ))}
          {/* Lớp rộng đúng bằng thanh, dịch theo phần trăm của chính nó = phần trăm của thanh; núm đứng ở mép trái lớp ấy. */}
          <span
            aria-hidden
            className={cn("pointer-events-none absolute inset-y-0", moving === null && "transition-transform duration-motion-fast")}
            style={{ left: plan.inset, right: plan.inset, transform: `translateX(${fraction * 100}%)` }}
          >
            <span className="absolute left-0 top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent shadow transition-[scale] duration-motion-fast group-active:scale-125" />
          </span>
        </div>
        {plan.aligned && spec.typical.map((typical, index) => <button
          key={typical} type="button" data-value-chip={typical} data-value-tick-label data-tap-proxy-for={rulerId}
          aria-label={format(typical)} aria-pressed={index === selected} disabled={disabled} aria-disabled={busy || undefined}
          onPointerDown={event => {
            if (event.button !== 0) return;
            event.currentTarget.setPointerCapture(event.pointerId);
            tickGesture.current = {x: event.clientX, dragged: false};
            const fraction = fractionAt(event.clientX);
            const nearest = spec.typical.reduce((best, v) => Math.abs(toFraction(spec, v) - fraction) < Math.abs(toFraction(spec, best) - fraction) ? v : best);
            last.current = nearest;
            setMoving(nearest);
          }}
          onPointerMove={event => {
            if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
            if (Math.abs(event.clientX - tickGesture.current.x) > 4) tickGesture.current.dragged = true;
            if (tickGesture.current.dragged) drag(event.clientX);
          }}
          onPointerUp={event => {
            if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
            event.currentTarget.releasePointerCapture(event.pointerId);
            if (!tickGesture.current.dragged) feedback("toggle");
            setClampNote(false);
            const fraction = fractionAt(event.clientX);
            const nearest = spec.typical.reduce((best, v) => Math.abs(toFraction(spec, v) - fraction) < Math.abs(toFraction(spec, best) - fraction) ? v : best);
            commit(tickGesture.current.dragged ? last.current : nearest);
          }}
          onPointerCancel={() => setMoving(null)}
          onClick={event => { if (event.detail === 0) { feedback("toggle"); setClampNote(false); commit(typical); } }}
          className={cn("absolute flex h-12 min-w-12 -translate-x-1/2 items-center justify-center rounded-control pt-4 hover:bg-hover", dense ? "top-2 text-xs" : "top-4 text-sm", index === selected ? "font-semibold text-fg" : "text-fg-2")}
          style={{left: `calc(${plan.inset}px + (100% - ${2 * plan.inset}px) * ${toFraction(spec, typical)})`}}
        ><span data-value-label>{labels[index]}</span></button>)}
        </div>
        {stepButton(1)}
      </div>
      {!plan.aligned && spec.typical.length > 0 && (
        <div className="mx-12"><BalancedChips label={label}>
          {spec.typical.map((typical, index) => (
            <button
              key={typical}
              type="button"
              disabled={disabled}
              aria-disabled={busy || undefined}
              aria-pressed={index === selected}
              data-current-choice={index === selected ? "" : undefined}
              data-value-chip={typical}
              aria-label={format(typical)}
              onClick={() => {
                feedback("toggle");
                setClampNote(false);
                commit(typical);
              }}
              className={cn(
                "touch-row inline-flex items-center justify-center whitespace-nowrap rounded-control px-2.5 transition-colors duration-motion-medium hover:bg-hover disabled:opacity-40",
                dense ? "h-7 text-xs" : "h-9 min-w-12 text-sm",
                index === selected ? "font-semibold text-fg" : "text-fg",
              )}
            >
              <span data-value-chip-measure data-value-label className="inline-block">{(chipLabel ?? ((v: number) => formatNumber(spec, v)))(typical)}</span>
            </button>
          ))}
        </BalancedChips></div>
      )}
      {children}
    </div>
  );
}

/** Measure the rendered numerals, including the current font scale, before balancing rows. */
function BalancedChips({label, children}: {label: string; children: ReactNode}) {
  const ref = useRef<HTMLDivElement>(null);
  const [rows, setRows] = useState<number[][]>([]);
  const items = Array.isArray(children) ? children : [children];
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const measure = () => {
      if (element.clientWidth <= 0) return;
      const widths = [...element.querySelectorAll<HTMLElement>("[data-value-chip-measure]")].map(node => {
        const style = getComputedStyle(node.parentElement!);
        return Math.max(Number.parseFloat(style.minWidth) || 48, node.getBoundingClientRect().width + Number.parseFloat(style.paddingLeft) + Number.parseFloat(style.paddingRight));
      });
      const gap = Number.parseFloat(getComputedStyle(element.firstElementChild!).columnGap) || 4;
      const next = chipRows(widths, element.clientWidth, gap);
      setRows(old => JSON.stringify(old) === JSON.stringify(next) ? old : next);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    element.querySelectorAll("[data-value-chip-measure]").forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [label, items.length]);
  const groups = rows.length ? rows : [items.map((_, i) => i)];
  return <div ref={ref} role="group" aria-label={label} data-value-chips className="flex flex-col">
    {groups.map((group, i) => <div key={i} data-value-chip-row className={cn("flex gap-1", group.length === 1 ? "justify-center" : "justify-between")}>{group.map(index => items[index])}</div>)}
  </div>;
}
