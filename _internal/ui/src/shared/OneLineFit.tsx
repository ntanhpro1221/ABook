import { useLayoutEffect, useRef, type HTMLAttributes } from "react";
import { cn } from "./cn";
import { ONE_LINE_MIN_SCALE } from "./widthClass.generated";

/** "one": vừa một dòng ở cỡ gốc · "shrunk": thu cỡ cho vừa một dòng · "wrap": thu tới đáy vẫn không vừa, xuống dòng ở cỡ gốc · "unmeasured": chưa có bề ngang (ẩn). */
export type OneLineFitState = "one" | "shrunk" | "wrap" | "unmeasured";

const STEP = 0.5;

/** Đo `el` và đặt cỡ chữ ngay tại chỗ (trước khi vẽ, không giật khung): một dòng ở cỡ gốc; không vừa thì thu dần tới `ONE_LINE_MIN_SCALE` cỡ gốc;
 *  thu tới đáy vẫn không vừa thì trả cỡ gốc và để chữ xuống dòng. Không bao giờ "…". Cùng luật với điện thoại `OneLineFit` và Qt `OneLineFit.qml`. */
export function fitOneLine(el: HTMLElement): OneLineFitState {
  el.style.fontSize = "";
  el.style.lineHeight = "";
  el.style.whiteSpace = "nowrap";
  const style = getComputedStyle(el);
  const base = parseFloat(style.fontSize) || 0;
  const line = style.lineHeight;
  const room = el.clientWidth;
  const need = el.scrollWidth;
  let state: OneLineFitState;
  if (room <= 0 || base <= 0) state = "unmeasured";
  else if (need <= room) state = "one";
  else {
    const min = base * ONE_LINE_MIN_SCALE;
    let size = Math.floor(((base * room) / need) / STEP) * STEP;
    if (size < min) state = "wrap";
    else {
      // Chữ thu nhỏ giữ chiều cao dòng gốc: hàng không co giật, icon đầu hàng vẫn đứng giữa dòng.
      if (line.endsWith("px")) el.style.lineHeight = line;
      el.style.fontSize = `${size}px`;
      while (el.scrollWidth > el.clientWidth && size - STEP >= min) {
        size -= STEP;
        el.style.fontSize = `${size}px`;
      }
      state = el.scrollWidth > el.clientWidth ? "wrap" : "shrunk";
    }
  }
  if (state === "wrap" || state === "unmeasured") {
    el.style.fontSize = "";
    el.style.lineHeight = "";
    el.style.whiteSpace = "";
  }
  el.dataset.fit = state;
  return state;
}

/** Hàng flex chứa OneLineFit: tên xuống dòng thì mọi thứ canh DÒNG ĐẦU (máy dò icon-off-first-line), còn lại canh giữa như cũ. */
export const FIRST_LINE_ROW = "has-[>[data-fit=wrap]]:items-start";
/** Icon đứng trước OneLineFit trong FIRST_LINE_ROW, nhỏ hơn dòng chữ (cỡ --icon-w, mặc định 1rem): đứng giữa dòng đầu khi tên xuống dòng. */
export const FIRST_LINE_ICON = "[:has(>[data-fit=wrap])>&]:mt-line-icon";
/** Chữ phụ đứng sau OneLineFit trong FIRST_LINE_ROW (giới tính, số câu): tên xuống dòng thì cùng đường chân chữ với dòng đầu của tên (máy dò BASELINE). */
export const FIRST_LINE_TEXT = "[:has(>[data-fit=wrap])>&]:self-baseline";

/** Tên một dòng (tên giọng, tên nhân vật trong danh sách chọn) mà không cắt chữ - DESIGN.md §5.5 "Tên một dòng". Mặc định (chưa đo, không có JS) chữ xuống
 *  dòng; đo lại khi chữ đổi, khi khung cha / ông đổi bề ngang và khi phông nạp xong. */
export function OneLineFit({ children, className, ...rest }: Omit<HTMLAttributes<HTMLSpanElement>, "children"> & { children: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Khung cha có thể co theo chữ (chip): theo dõi cả ông để biết khi chỗ rộng ra.
    const frames = [el.parentElement, el.parentElement?.parentElement].filter((frame): frame is HTMLElement => Boolean(frame));
    let widths: number[] = [];
    const run = () => {
      fitOneLine(el);
      widths = frames.map((frame) => frame.clientWidth);
    };
    run();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => {
      if (frames.some((frame, i) => frame.clientWidth !== widths[i])) run();
    });
    for (const frame of frames) observer?.observe(frame);
    let live = true;
    document.fonts?.ready.then(() => { if (live) run(); }, () => {});
    return () => {
      live = false;
      observer?.disconnect();
    };
  }, [children]);
  return <span ref={ref} data-one-line-fit="" className={cn("block min-w-0 break-words data-[fit=wrap]:self-baseline", className)} {...rest}>{children}</span>;
}
