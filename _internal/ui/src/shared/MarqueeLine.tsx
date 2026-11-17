import { useLayoutEffect, useRef, useState, type HTMLAttributes } from "react";
import { cn } from "./cn";
import { prefersReducedMotion } from "./motion";
import { ONE_LINE_MIN_SCALE, TIMING } from "./widthClass.generated";

/** "one": vừa ở cỡ gốc · "shrunk": thu cỡ cho vừa · "scroll": ở cỡ đáy và chạy chữ · "unmeasured": chưa có bề ngang. */
export type MarqueeFit = "one" | "shrunk" | "scroll" | "unmeasured";

const STEP = 0.5;

/** Cỡ chữ và cách nằm của chữ trong ô rộng `room`: cùng luật với điện thoại `marqueeFit` và Qt `MarqueeLine.qml`. `measure(size)` trả bề ngang một dòng ở cỡ ấy. */
export function marqueeFit(room: number, base: number, measure: (size: number) => number): { fit: MarqueeFit; size: number } {
  if (room <= 0 || base <= 0) return { fit: "unmeasured", size: base };
  const need = measure(base);
  if (need <= room) return { fit: "one", size: base };
  const min = base * ONE_LINE_MIN_SCALE;
  for (let size = Math.floor((base * room) / need / STEP) * STEP; size >= min; size -= STEP) {
    if (measure(size) <= room) return { fit: "shrunk", size };
  }
  if (measure(min) <= room) return { fit: "shrunk", size: min };
  return { fit: "scroll", size: min };
}

/** Một vòng chạy chữ dài `cycle` px (bề ngang tên + khe): đứng `TIMING.marqueeDelayMs` ở đầu rồi trượt đều `TIMING.marqueeSpeed` px/giây tới `-cycle`
 *  (bản chép thứ hai về đúng chỗ bản đầu) - khung hình cho Web Animations, lặp vô hạn. */
export function marqueeLoop(cycle: number): { keyframes: Keyframe[]; duration: number } {
  const travel = (cycle / TIMING.marqueeSpeed) * 1000;
  const duration = TIMING.marqueeDelayMs + travel;
  const pause = TIMING.marqueeDelayMs / duration;
  return {
    keyframes: [{ transform: "translateX(0)", offset: 0 }, { transform: "translateX(0)", offset: pause }, { transform: `translateX(${-cycle}px)`, offset: 1 }],
    duration,
  };
}

/**
 * Tên trong ô MỘT DÒNG CỐ ĐỊNH (thanh phát thu nhỏ, trình phát - DESIGN.md §5.5 "Tên một dòng"; điện thoại `MarqueeLine`, Qt `MarqueeLine.qml`): ô luôn cao đúng một
 * dòng ở cỡ gốc nên bìa và nút phát không bao giờ dời vì tên dài ngắn. Vừa ở cỡ gốc thì giữ nguyên; không vừa thì thu cỡ tới `ONE_LINE_MIN_SCALE` cỡ gốc; thu tới đó
 * vẫn không vừa thì CHẠY CHỮ: đứng `TIMING.marqueeDelayMs` ở đầu, trượt `TIMING.marqueeSpeed` px/giây tới khi bản chép thứ hai (cách `TIMING.marqueeGap`) về đúng
 * chỗ bản đầu, rồi lại đứng. Giảm chuyển động: không trượt - nhảy từng đoạn, mỗi đoạn đứng một nhịp, tới cuối tên thì về đầu. Không bao giờ "…"; trình đọc màn hình
 * đọc tên một lần (bản chép aria-hidden, chỉ dựng khi trượt). Đo lại khi chữ đổi, khi khung đổi bề ngang và khi phông nạp xong.
 */
export function MarqueeLine({ children, className, ...rest }: Omit<HTMLAttributes<HTMLSpanElement>, "children"> & { children: string }) {
  const box = useRef<HTMLSpanElement>(null);
  const strip = useRef<HTMLSpanElement>(null);
  const first = useRef<HTMLSpanElement>(null);
  // Bản chép thứ hai chỉ có khi đang trượt (không có trong DOM lúc khác: tìm chữ trong test ra đúng một chỗ)
  const [twin, setTwin] = useState(false);
  useLayoutEffect(() => {
    const el = box.current;
    const row = strip.current;
    const text = first.current;
    if (!el || !row || !text) return;
    let stop = () => {};
    let width = -1;
    let fontSize = -1;
    const run = () => {
      const base = parseFloat(getComputedStyle(el).fontSize) || 0;
      if (el.clientWidth === width && base === fontSize) return;
      width = el.clientWidth;
      fontSize = base;
      stop();
      row.style.fontSize = "";
      row.style.transform = "";
      const { fit, size } = marqueeFit(el.clientWidth, base, (px) => {
        row.style.fontSize = `${px}px`;
        return text.scrollWidth;
      });
      row.style.fontSize = fit === "one" || fit === "unmeasured" ? "" : `${size}px`;
      el.dataset.fit = fit;
      setTwin(fit === "scroll" && !prefersReducedMotion());
      if (fit !== "scroll") return;
      const gap = TIMING.marqueeGap;
      const cycle = text.scrollWidth + gap;
      const room = el.clientWidth;
      if (prefersReducedMotion()) {
        // Nhảy từng đoạn: bề ngang ô trừ khe; đoạn cuối canh cuối tên vào mép phải
        const end = text.scrollWidth - room;
        let offset = 0;
        const timer = window.setInterval(() => {
          offset = offset >= end - 0.5 ? 0 : Math.min(end, offset + Math.max(1, room - gap));
          row.style.transform = `translateX(${-offset}px)`;
        }, TIMING.marqueeDelayMs);
        stop = () => window.clearInterval(timer);
        return;
      }
      if (typeof row.animate !== "function") return;
      const { keyframes, duration } = marqueeLoop(cycle);
      const animation = row.animate(keyframes, { duration, iterations: Infinity, easing: "linear" });
      stop = () => animation.cancel();
    };
    run();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(run);
    observer?.observe(el);
    let live = true;
    document.fonts?.ready.then(() => { if (live) { width = -1; run(); } }, () => {});
    return () => {
      live = false;
      observer?.disconnect();
      stop();
    };
  }, [children, className]);
  return (
    <span ref={box} data-marquee-line="" className={cn("relative block min-w-0 overflow-hidden whitespace-nowrap", className)} {...rest}>
      <span ref={strip} className="inline-flex will-change-transform" style={{ gap: TIMING.marqueeGap }}>
        <span ref={first}>{children}</span>
        {twin && <span aria-hidden>{children}</span>}
      </span>
    </span>
  );
}
