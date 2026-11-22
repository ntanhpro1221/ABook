import { useLayoutEffect, useRef, type HTMLAttributes } from "react";
import { cn } from "./cn";
import { ONE_LINE_MIN_SCALE } from "./widthClass.generated";

/** "one": vừa một dòng ở cỡ gốc · "shrunk": thu cỡ cho vừa một dòng · "wrap": thu tới đáy vẫn không vừa, xuống dòng ở cỡ gốc · "unmeasured": chưa có bề ngang (ẩn). */
export type OneLineFitState = "one" | "shrunk" | "wrap" | "unmeasured";

const STEP = 0.5;

interface Measure { el: HTMLElement; base: number; line: string; room: number; need: number; size: number; min: number; state?: OneLineFitState }

/** Ghi trạng thái cuối. Xuống dòng (và chưa đo) đặt `white-space: normal` THẲNG trên chữ: khung cha (nút dùng chung `whitespace-nowrap`) không được
 *  làm chữ đã "xuống dòng" nằm một dòng tràn ra ngoài (soát leftfix C1). */
function settle(m: Measure, state: OneLineFitState) {
  if (state === "wrap" || state === "unmeasured") {
    m.el.style.fontSize = "";
    m.el.style.lineHeight = "";
    m.el.style.whiteSpace = "normal";
  }
  m.el.dataset.fit = state;
  m.state = state;
}

/** Đo cả lô theo pha: ghi hết - đọc hết - ghi hết, nên N chữ chỉ ép dàn trang vài lần chứ không N lần (soát leftfix T6: danh sách hàng trăm câu / file). */
export function fitOneLines(els: readonly HTMLElement[]): OneLineFitState[] {
  // Pha 1 (ghi): về cỡ gốc, một dòng.
  for (const el of els) {
    el.style.fontSize = "";
    el.style.lineHeight = "";
    el.style.whiteSpace = "nowrap";
  }
  // Pha 2 (đọc): một lần dàn trang cho cả lô.
  const all: Measure[] = els.map((el) => {
    const style = getComputedStyle(el);
    return { el, base: parseFloat(style.fontSize) || 0, line: style.lineHeight, room: el.clientWidth, need: el.scrollWidth, size: 0, min: 0 };
  });
  let open: Measure[] = [];
  for (const m of all) {
    if (m.room <= 0 || m.base <= 0) settle(m, "unmeasured");
    else if (m.need <= m.room) settle(m, "one");
    else {
      m.min = m.base * ONE_LINE_MIN_SCALE;
      m.size = Math.floor(((m.base * m.room) / m.need) / STEP) * STEP;
      if (m.size < m.min) settle(m, "wrap");
      else open.push(m);
    }
  }
  // Pha 3: thu theo tỉ lệ rồi chỉnh từng bước 0,5 px - mỗi vòng ghi cả lô rồi đọc cả lô.
  for (const m of open) {
    // Chữ thu nhỏ giữ chiều cao dòng gốc: hàng không co giật, icon đầu hàng vẫn đứng giữa dòng.
    if (m.line.endsWith("px")) m.el.style.lineHeight = m.line;
    m.el.style.fontSize = `${m.size}px`;
  }
  while (open.length) {
    const next: Measure[] = [];
    for (const m of open) {
      if (m.el.scrollWidth <= m.el.clientWidth) settle(m, "shrunk");
      else if (m.size - STEP >= m.min) next.push(m);
      else settle(m, "wrap");
    }
    for (const m of next) {
      m.size -= STEP;
      m.el.style.fontSize = `${m.size}px`;
    }
    open = next;
  }
  return all.map((m) => m.state!);
}

/** Đo `el` và đặt cỡ chữ ngay tại chỗ (trước khi vẽ, không giật khung): một dòng ở cỡ gốc; không vừa thì thu dần tới `ONE_LINE_MIN_SCALE` cỡ gốc;
 *  thu tới đáy vẫn không vừa thì trả cỡ gốc và để chữ xuống dòng. Không bao giờ "…". Cùng luật với điện thoại `OneLineFit` và Qt `OneLineFit.qml`. */
export function fitOneLine(el: HTMLElement): OneLineFitState {
  return fitOneLines([el])[0];
}

/** Cỡ chữ nhỏ nhất của chữ vừa khung (tên sách trên bìa vẽ): cùng sàn với Android `BookCover` FitText (2 sp) - thà nhỏ còn hơn cắt. */
export const BOX_FIT_MIN_PX = 2;

/** Chữ vừa trọn một khung có bề ngang VÀ chiều cao cố định (tên sách trên bìa vẽ): giữ cỡ gốc khi vừa, không thì thu cỡ (tìm nhị phân, cả lô cùng
 *  bước) tới khi không tràn ngang hay dọc - không bao giờ "…", như Android FitText và Qt `fontSizeMode: Text.Fit` (soát leftfix T3). */
export function fitBoxes(els: readonly HTMLElement[]): number[] {
  for (const el of els) el.style.fontSize = "";
  const over = (el: HTMLElement) => el.scrollHeight > el.clientHeight + 0.5 || el.scrollWidth > el.clientWidth + 0.5;
  const base = els.map((el) => parseFloat(getComputedStyle(el).fontSize) || 0);
  const fits = els.map((el) => !over(el));
  const lo = base.map(() => BOX_FIT_MIN_PX);
  const hi = base.slice();
  const open = els.map((_, i) => !fits[i] && base[i] > BOX_FIT_MIN_PX && els[i].clientHeight > 0);
  for (let round = 0; round < 8 && open.some(Boolean); round++) {
    const mid = hi.map((h, i) => Math.round(((lo[i] + h) / 2) * 4) / 4);
    els.forEach((el, i) => { if (open[i]) el.style.fontSize = `${mid[i]}px`; });
    els.forEach((el, i) => {
      if (!open[i]) return;
      if (over(el)) hi[i] = mid[i];
      else lo[i] = mid[i];
      if (hi[i] - lo[i] <= 0.25) open[i] = false;
    });
  }
  return els.map((el, i) => {
    if (fits[i] || base[i] <= 0) {
      el.dataset.fit = base[i] > 0 ? "one" : "unmeasured";
      return base[i];
    }
    el.style.fontSize = `${lo[i]}px`;
    el.dataset.fit = "shrunk";
    return lo[i];
  });
}

/** Mọi chữ tự đo đang gắn: kiểu đo, khung theo dõi (chính nó, cha, ông) và bề ngang lần đo trước. */
interface Live { frames: HTMLElement[]; widths: number[]; heights?: number; box: boolean }
const live = new Map<HTMLElement, Live>();
const watchers = new Map<HTMLElement, Set<HTMLElement>>();
const queued = new Set<HTMLElement>();
let flushing = false;
let observer: ResizeObserver | null | undefined;
let fontsHooked = false;

/** Chữ nằm trong hàng `content-visibility: auto` ngoài màn: trình duyệt bỏ qua dàn trang của hàng ấy - đo nó là ép dàn trang lại cả hàng (2.000 hàng
 *  file = 2.000 lần), mất hết lợi ích của content-visibility. Để "chưa đo" (xuống dòng, không cắt) và đo khi hàng hiện ra (soát leftfix T6). */
function skipped(el: HTMLElement) {
  return typeof el.checkVisibility === "function" && !el.checkVisibility({ contentVisibilityAuto: true });
}

function flush() {
  flushing = false;
  const all = [...queued].filter((el) => el.isConnected && live.has(el));
  queued.clear();
  const els: HTMLElement[] = [];
  for (const el of all) {
    if (!skipped(el)) els.push(el);
    else {
      el.style.fontSize = "";
      el.style.lineHeight = "";
      if (!live.get(el)!.box) el.style.whiteSpace = "normal";
      el.dataset.fit = "unmeasured";
    }
  }
  if (!els.length) return;
  fitOneLines(els.filter((el) => !live.get(el)!.box));
  fitBoxes(els.filter((el) => live.get(el)!.box));
  for (const el of els) {
    const item = live.get(el)!;
    item.widths = item.frames.map((frame) => frame.clientWidth);
    item.heights = el.clientHeight;
  }
}

/** Gom mọi yêu cầu đo trong cùng một lượt: vi tác vụ chạy sau mọi useLayoutEffect của lần commit, trước khi trình duyệt vẽ - không giật khung. */
function schedule(el: HTMLElement) {
  queued.add(el);
  if (flushing) return;
  flushing = true;
  queueMicrotask(flush);
}

function sharedObserver() {
  if (observer !== undefined) return observer;
  observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver((entries) => {
    for (const entry of entries ?? []) {
      for (const el of watchers.get(entry.target as HTMLElement) ?? []) {
        const item = live.get(el);
        // Chưa đo được (bề ngang 0 - hàng content-visibility ngoài màn, khung ẩn): hiện ra là đo lại, kể cả khi khung cha giữ nguyên bề ngang.
        if (item && (el.dataset.fit === "unmeasured" || item.frames.some((frame, i) => frame.clientWidth !== item.widths[i]))) schedule(el);
        // Chữ vừa khung: khung đổi chiều cao (bìa co theo màn) cũng phải đo lại.
        else if (item?.box && item.frames[0].clientHeight !== item.heights) schedule(el);
      }
    }
  });
  return observer;
}

function hookFonts() {
  if (fontsHooked) return;
  fontsHooked = true;
  document.fonts?.ready.then(() => { for (const el of live.keys()) schedule(el); }, () => {});
  // Hàng content-visibility vừa hiện ra: đo chữ chưa đo trong hàng ấy (sự kiện không nổi bọt - nghe ở pha bắt của document).
  document.addEventListener("contentvisibilityautostatechange", (event) => {
    if ((event as Event & { skipped?: boolean }).skipped) return;
    const row = event.target as HTMLElement;
    for (const el of row.querySelectorAll<HTMLElement>("[data-fit=unmeasured]")) if (live.has(el)) schedule(el);
  }, true);
}

function attach(el: HTMLElement, box = false) {
  // Khung cha có thể co theo chữ (chip): theo dõi cả ông để biết khi chỗ rộng ra; chính chữ để biết khi nó thôi bị bỏ qua dàn trang.
  const frames = [el, el.parentElement, el.parentElement?.parentElement].filter((frame): frame is HTMLElement => Boolean(frame));
  live.set(el, { frames, widths: [], box });
  const ro = sharedObserver();
  for (const frame of frames) {
    let set = watchers.get(frame);
    if (!set) {
      set = new Set();
      watchers.set(frame, set);
      ro?.observe(frame);
    }
    set.add(el);
  }
  hookFonts();
}

function detach(el: HTMLElement) {
  const item = live.get(el);
  live.delete(el);
  queued.delete(el);
  for (const frame of item?.frames ?? []) {
    const set = watchers.get(frame);
    set?.delete(el);
    if (set && !set.size) {
      watchers.delete(frame);
      observer?.unobserve?.(frame);
    }
  }
  // Không còn chữ nào: trả bộ theo dõi (lần gắn sau tạo lại, theo ResizeObserver của lúc ấy).
  if (!live.size) {
    observer?.disconnect();
    observer = undefined;
  }
}

/** Tên một dòng (giọng, nhân vật, máy / điện thoại, thiết bị phát, hồ sơ) mà không cắt chữ - DESIGN.md §5.5 "Tên một dòng". Mặc định (chưa đo, không có JS) chữ xuống
 *  dòng; đo lại khi chữ đổi, khi khung cha / ông đổi bề ngang và khi phông nạp xong. Mọi OneLineFit dùng chung một ResizeObserver và đo theo lô. */
export function OneLineFit({ children, className, ...rest }: Omit<HTMLAttributes<HTMLSpanElement>, "children"> & { children: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    attach(el);
    return () => detach(el);
  }, []);
  useLayoutEffect(() => {
    if (ref.current) schedule(ref.current);
  }, [children]);
  return <span ref={ref} data-one-line-fit="" className={cn("block min-w-0 whitespace-normal break-words data-[fit=wrap]:self-baseline", className)} {...rest}>{children}</span>;
}

/** Chữ vừa trọn khung (tên sách trên bìa vẽ): khung cho chữ bề ngang và chiều cao (flex-1 / size-full); chữ dài thì nhỏ lại, không cắt. Cỡ gốc lấy
 *  từ CSS thừa kế (đặt cỡ ở khung cha). */
export function FitBox({ children, className, ...rest }: Omit<HTMLAttributes<HTMLSpanElement>, "children"> & { children: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    attach(el, true);
    return () => detach(el);
  }, []);
  useLayoutEffect(() => {
    if (ref.current) schedule(ref.current);
  }, [children]);
  return <span ref={ref} data-fit-box="" className={cn("block min-h-0 overflow-hidden [overflow-wrap:normal]", className)} {...rest}>{children}</span>;
}

/** Hàng flex chứa OneLineFit: tên xuống dòng thì mọi thứ canh DÒNG ĐẦU (máy dò icon-off-first-line), còn lại canh giữa như cũ. */
export const FIRST_LINE_ROW = "has-[>[data-fit=wrap]]:items-start";
/** Icon đứng trước OneLineFit trong FIRST_LINE_ROW, nhỏ hơn dòng chữ (cỡ --icon-w, mặc định 1rem): đứng giữa dòng đầu khi tên xuống dòng. */
export const FIRST_LINE_ICON = "[:has(>[data-fit=wrap])>&]:mt-line-icon";
/** Chữ phụ đứng sau OneLineFit trong FIRST_LINE_ROW (giới tính, số câu): tên xuống dòng thì cùng đường chân chữ với dòng đầu của tên (máy dò BASELINE). */
export const FIRST_LINE_TEXT = "[:has(>[data-fit=wrap])>&]:self-baseline";
