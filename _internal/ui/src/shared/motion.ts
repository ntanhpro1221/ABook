import { useCallback, useEffect, useLayoutEffect, useRef, useState, type AnimationEvent, type RefObject, type SetStateAction } from "react";
import { flushSync } from "react-dom";

/** Thời lượng (ms) - cùng số với token --motion-* trong styles.css (chỗ phải đặt bằng JS: Web Animations, hẹn giờ gỡ phần tử). */
export const MOTION = {
  fast: 120,
  fastOut: 90,
  medium: 220,
  mediumOut: 150,
  slow: 300,
  slowOut: 200,
} as const;

/** Đường cong - cùng giá trị với --ease-* (Material 3). */
export const EASE = {
  standard: "cubic-bezier(0.2, 0, 0, 1)",
  decelerate: "cubic-bezier(0.05, 0.7, 0.1, 1)",
  accelerate: "cubic-bezier(0.3, 0, 0.8, 0.15)",
} as const;

/** Người dùng xin giảm chuyển động (Cài đặt hệ điều hành)? Môi trường không có matchMedia (dựng thử) thì coi là không. */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
}

/** Kiểu cuộn cho scrollTo / scrollIntoView / scrollBy: trượt êm, trừ khi người dùng xin giảm chuyển động (soát a31 M2) - mọi chỗ
 *  cuộn "smooth" đi qua đây để không chỗ nào quên kiểm. */
export function scrollMotion(animate = true): ScrollBehavior {
  return animate && !prefersReducedMotion() ? "smooth" : "auto";
}

// Đổi trang (MotionHashRouter): KHÔNG qua View Transition - trên WebView điện thoại một chuyển cảnh rỗng đã chiếm khung 70-140 ms
// để chụp cả tài liệu, cộng thời gian dựng trang mới là màn đứng ~170 ms rồi mới mờ (video chủ sách 25-10 "mở tab thư viện bị giật").
// Thay vào đó: khung nội dung `.page-motion` mờ đi ngay khi bấm (chỉ opacity/transform - chạy trên GPU), trang mới dựng trong lúc khung
// đã khuất, rồi hiện vào theo hướng (sâu vào / lùi ra / ngang hàng). Thanh tab, thanh phát đứng yên. Xin giảm chuyển động: chỉ mờ / hiện.
let leaving: Promise<void> | null = null;
let entering: NavMotion | null = null;

function pageSurface(doc: TransitionDocument | undefined): HTMLElement | null {
  return doc?.querySelector?.<HTMLElement>(".page-motion") ?? null;
}

/** Trang mới đang vào (từ lúc bấm tới khi hiện xong khung đầu): nội dung có sẵn của nó không tự mọc / trượt riêng - khung trang đã lo. */
export function pageEntering(): boolean {
  return entering !== null;
}

let settleUntil = 0;
const clock = () => (typeof performance === "undefined" ? Date.now() : performance.now());

/** Mở cửa sổ "đang ổn định": trang vừa hiện vào, mở app, hay lượt dữ liệu đầu vừa về (ArrivalScope). */
export function markArrival(ms: number = MOTION.slow): void {
  settleUntil = Math.max(settleUntil, clock() + ms);
}

/** Trang đang vào hay vừa vào / dữ liệu đầu vừa về: thứ tới lúc này (thẻ, dòng danh sách, khối cài đặt) hiện tại chỗ cùng trang, không mọc
 *  cao dần đẩy phần dưới xuống (máy dò dịch bố cục 25-10: lưới Thư viện trôi 110 px lúc mở app, thẻ buổi sáng đẩy lưới 261 px). Thứ tới SAU
 *  cửa sổ này (người dùng thêm sách, mở mục) vẫn mở ra có chuyển động. */
export function pageSettling(): boolean {
  return entering !== null || clock() < settleUntil;
}

/** Mờ trang hiện tại đi rồi mới đổi. Đang mờ dở (bấm liên tiếp) thì dùng lại lần mờ ấy - lần đổi cuối cùng thắng. */
export function leavePage(nav: NavMotion, doc: TransitionDocument | undefined = browserDocument()): Promise<void> {
  const page = pageSurface(doc);
  if (nav === "none" || !page || typeof page.animate !== "function" || doc?.visibilityState === "hidden") return Promise.resolve();
  entering = nav;
  if (leaving) return leaving;
  const shift = prefersReducedMotion() || nav === "through" ? 0 : nav === "back" ? 12 : -12;
  const animation = page.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: shift ? `translateX(${shift}px)` : "none" }], {
    duration: MOTION.fastOut,
    easing: EASE.accelerate,
    fill: "forwards",
  });
  leaving = animation.finished.then(() => undefined, () => undefined).then(() => {
    leaving = null;
  });
  return leaving;
}

/** Sau commit của trang mới (layout effect của router, trước khi vẽ): bỏ lớp mờ của lần rời và cho trang hiện vào. */
export function enterPage(doc: TransitionDocument | undefined = browserDocument()): void {
  const nav = entering;
  entering = null;
  const page = pageSurface(doc);
  if (!nav || !page || typeof page.animate !== "function") return;
  for (const animation of page.getAnimations?.() ?? []) animation.cancel();
  // Thứ dựng cùng trang mới (nội dung hiện dần, dòng nhô lên, khung chờ) đi theo chuyển cảnh của trang, không chồng thêm một lượt hiện của riêng nó.
  for (const animation of page.getAnimations?.({ subtree: true }) ?? []) if (justEntering(animation)) animation.finish();
  const reduced = prefersReducedMotion();
  const from = reduced ? "none" : nav === "through" ? "scale(0.97)" : `translateX(${nav === "back" ? -32 : 32}px)`;
  const duration = reduced ? MOTION.fast : nav === "through" ? MOTION.medium : MOTION.slow;
  markArrival(duration);
  page.animate([{ opacity: 0, transform: from }, { opacity: 1, transform: "none" }], { duration, easing: EASE.decelerate });
}

/** Hoạt ảnh hiện vào vừa bắt đầu ở nhịp này: hữu hạn, ngắn, chưa chạy. Vòng lặp (khung chờ nhấp nháy) và hoạt ảnh dài (đếm ngược) giữ nguyên. */
function justEntering(animation: globalThis.Animation): boolean {
  const timing = animation.effect?.getComputedTiming?.();
  if (!timing || timing.iterations === Infinity || typeof timing.endTime !== "number" || timing.endTime > MOTION.slow * 2) return false;
  return Number(animation.currentTime ?? 0) < MOTION.fast / 2;
}

// Lần đầu dựng khung (mở app) không đi qua router: khung nội dung hiện dần và nhích lên. Dùng Web Animations trên chính khung nên KHÔNG
// dựng lại trang (key theo đường dẫn sẽ làm mất trạng thái, cuộn, ô đang gõ). Đổi trang thì router (leavePage / enterPage) lo.
export function usePageEnter(ref: RefObject<HTMLElement | null>, key: string, { resetScroll = true } = {}) {
  useLayoutEffect(() => {
    const element = ref.current;
    // Trang mới mở từ đầu: vùng cuộn dùng chung giữa các trang từng giữ vị trí trang trước (soát UX 29-09 - "Tạo sách nói"
    // mở ở 67px, chế độ Đọc ở 115px dưới header).
    if (resetScroll) element?.scrollTo?.({ top: 0 });
    if (!element || typeof element.animate !== "function") return;
    if (pageEntering() || viewTransitionRunning()) return;
    markArrival();
    const shift = prefersReducedMotion() ? 0 : 8;
    element.animate(
      [
        { opacity: 0, transform: `translateY(${shift}px)` },
        { opacity: 1, transform: "none" },
      ],
      { duration: prefersReducedMotion() ? MOTION.fast : MOTION.slow, easing: EASE.decelerate },
    );
  }, [ref, key, resetScroll]);
}

/** Bố cục đổi theo cỡ cửa sổ (`key` đổi khi vượt mốc): khung hiện dần từ 55 % thay vì nhảy. Lần đầu không chạy. */
export function useLayoutChangeFade(ref: RefObject<HTMLElement | null>, key: string) {
  const first = useRef(true);
  useLayoutEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    ref.current?.animate?.([{ opacity: 0.55 }, { opacity: 1 }], { duration: prefersReducedMotion() ? MOTION.fast : MOTION.medium, easing: EASE.standard });
  }, [ref, key]);
}

/** Khoá trang cho usePageFocus: đổi chương trong chế độ Đọc (/book/x/read/ch) là cùng một trang - chương tự sang khi đang nghe
 *  không được giật tiêu điểm của người dùng. */
export function pageFocusKey(pathname: string): string {
  return pathname.replace(/\/read(\/.*)?$/, "/read");
}

// Chuyển trang (soát a31 K2): tiêu điểm sang tiêu đề h1 của trang mới - trình đọc màn hình đọc tên trang, Tab đi tiếp từ đầu nội dung
// thay vì từ chỗ của trang cũ (hay từ đầu tài liệu khi nút vừa bấm đã biến mất). Lần tải đầu không đụng. Người dùng đã tự đặt tiêu điểm
// vào chỗ khác trong lúc trang dựng (ô tìm tự focus, bấm nút) thì thôi. Trang chưa có h1 (đang tải dữ liệu) thì chờ vài khung hình
// rồi đặt vào chính khung nội dung.
export function usePageFocus(ref: RefObject<HTMLElement | null>, key: string) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const before = document.activeElement;
    let frame = 0;
    let tries = 0;
    const attempt = () => {
      const element = ref.current;
      const now = document.activeElement;
      if (!element || (now && now !== before && now !== document.body)) return;
      const heading = element.querySelector<HTMLElement>("h1");
      if (heading) {
        if (!heading.hasAttribute("tabindex")) heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
      } else if (++tries < 30) frame = requestAnimationFrame(attempt);
      else if (element.tabIndex === -1) element.focus({ preventScroll: true });
    };
    frame = requestAnimationFrame(attempt);
    return () => cancelAnimationFrame(frame);
  }, [ref, key]);
}

// ---- View Transitions ------------------------------------------------------------------------------------------------------------

type TransitionLike = { ready?: Promise<unknown>; finished?: Promise<unknown> };
type TransitionDocument = {
  startViewTransition?: (update: () => void) => TransitionLike;
  visibilityState?: string;
  documentElement: { dataset: DOMStringMap };
  querySelector?: Document["querySelector"];
  querySelectorAll?: Document["querySelectorAll"];
  body?: HTMLElement;
};

/** Hướng của lần chuyển: sâu vào / lùi ra (trượt ngang "shared axis"), ngang hàng (mờ qua "fade through"), hay không chuyển vùng trang
 *  (mở Đang nghe, đổi giao diện). Ghi lên <html data-nav> cho styles.css. */
export type NavMotion = "forward" | "back" | "through" | "none";

const browserDocument = (): TransitionDocument | undefined => (typeof document === "undefined" ? undefined : (document as unknown as TransitionDocument));
let latest = 0;

/** WebView cũ: ảnh DOM tĩnh chỉ sống trong một lần fade, không giữ component/effect hay chặn chạm.
 * Thay đổi chạy ngay; ảnh cũ tự gỡ cả khi animationend không tới. Chỉ chụp vùng đang đổi, không chụp portal. */
export function fallbackSnapshot(doc: TransitionDocument, nav: NavMotion): void {
  if (!doc.body || !doc.querySelector || doc.visibilityState === "hidden") return;
  const dialogs = nav === "none" ? Array.from(doc.querySelectorAll?.<HTMLElement>('[role="dialog"][data-state="open"]') ?? []) : [];
  const target = dialogs[dialogs.length - 1] ?? doc.querySelector<HTMLElement>(nav === "none" ? ".now-playing [data-motion-content], .now-playing, .page-motion" : ".page-motion");
  if (!target) return;
  captureMotionSnapshot(target, doc, dialogs.length ? 51 : 39);
  // React commit xong thì surface mới hiện vào dưới ảnh cũ; không trì hoãn thao tác.
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => {
    target.animate?.([{ opacity: 0.35 }, { opacity: 1 }], { duration: MOTION.fast, easing: EASE.standard });
  });
}

/** Ảnh tĩnh của một vùng trước React commit. Dùng chung cho VT fallback và nội dung cập nhật bất đồng bộ. */
const snapshotCleanups = new WeakMap<HTMLElement, () => void>();
const snapshotPlacements = new WeakMap<HTMLElement, () => void>();
const snapshotLife = new WeakMap<HTMLElement, (ms: number) => void>();
const snapshotTargets = new Map<HTMLElement, HTMLElement>();
// Chỉ ảnh trong surface theo layout/clip. Một rAF chung, sống tối đa tới timer gỡ ảnh cuối.
const surfacePlacements = new Set<() => void>();
let surfaceFrame: number | undefined;
function scheduleSurfaceFrame(): void {
  if (surfaceFrame !== undefined || !surfacePlacements.size) return;
  surfaceFrame = requestAnimationFrame(() => {
    surfaceFrame = undefined;
    for (const place of surfacePlacements) place();
    scheduleSurfaceFrame();
  });
}
/** Chỉ nhận quyền vẽ sau khi vùng đã xác nhận đổi nội dung. Ảnh cha dự phòng có thể bị bỏ sau commit. */
export function settleMotionSnapshot(target: HTMLElement, clone: HTMLElement | undefined): HTMLElement | undefined {
  if (!clone || !snapshotCleanups.has(clone)) return clone;
  snapshotPlacements.get(clone)?.(); // React commit có thể vừa đổi kích thước khung cuộn/hộp.
  for (const [source, image] of snapshotTargets) {
    if (image === clone) continue;
    if (source !== target && source.contains?.(target)) { removeMotionSnapshot(clone); return; }
    if (source === target || target.contains?.(source)) removeMotionSnapshot(image);
  }
  snapshotTargets.set(target, clone);
  return clone;
}
/** Ảnh cũ do người gọi tự chuyển động (trượt ngang của tab): bỏ fade CSS mặc định, giữ ảnh đủ lâu cho hoạt ảnh ấy. */
export function holdMotionSnapshot(clone: HTMLElement, ms: number): void {
  clone.setAttribute("data-motion-slide", "");
  snapshotLife.get(clone)?.(ms);
}
export function removeMotionSnapshot(clone: HTMLElement | undefined): void {
  if (!clone) return;
  const cleanup = snapshotCleanups.get(clone);
  if (cleanup) cleanup();
  else clone.remove();
}

export function captureMotionSnapshot(target: HTMLElement, doc: TransitionDocument = document, floorZ = 51, host?: HTMLElement, deferOverlap = false, followScroll = false): HTMLElement | undefined {
  if (!doc.body || doc.visibilityState === "hidden") return;
  const bounds = target.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const clone = target.cloneNode(true) as HTMLElement;
  clone.querySelectorAll(".motion-snapshot").forEach(node => node.remove());
  clone.querySelectorAll("[id], [autofocus]").forEach((node) => { node.removeAttribute("id"); node.removeAttribute("autofocus"); });
  clone.removeAttribute("id");
  clone.removeAttribute("role");
  clone.querySelectorAll("[role]").forEach((node) => node.removeAttribute("role"));
  clone.querySelectorAll("[name]").forEach((node) => node.removeAttribute("name"));
  clone.setAttribute("aria-hidden", "true");
  clone.setAttribute("inert", "");
  clone.classList.add("motion-snapshot");
  Object.assign(clone.style, {
    position: host ? "absolute" : "fixed", top: `${bounds.top}px`, left: `${bounds.left}px`, right: "auto", bottom: "auto", width: `${bounds.width}px`, height: `${bounds.height}px`,
    boxSizing: "border-box", minWidth: "0", minHeight: "0", maxWidth: "none", maxHeight: "none",
    margin: "0", zIndex: String(floorZ), pointerEvents: "none", overflow: "hidden", transform: "none", translate: "none",
  });
  // Các biến màu được giữ trước khi đổi theme, ảnh cũ không đổi màu theo ảnh mới.
  const computed = getComputedStyle(target);
  // Header thường kế thừa font từ h2/h3; ảnh được đưa ra surface nên phải giữ kiểu chữ ấy.
  // Edge có thể trả shorthand `font` rỗng khi CSS dùng font-feature-settings.
  for (const name of ["font-size", "font-family", "font-weight", "font-style", "font-stretch", "font-variant", "font-feature-settings", "font-variation-settings",
    "line-height", "letter-spacing", "word-spacing", "color", "text-align", "text-transform", "white-space", "direction"]) {
    const value = computed.getPropertyValue(name);
    if (value) clone.style.setProperty(name, value);
  }
  clone.style.zIndex = String(Math.max(floorZ, (parseInt(computed.zIndex) || 0) + 1));
  for (const name of computed) if (name.startsWith("--")) clone.style.setProperty(name, computed.getPropertyValue(name));
  clone.style.backgroundColor = computed.backgroundColor === "rgba(0, 0, 0, 0)" ? computed.getPropertyValue("--bg") : computed.backgroundColor;
  const hasSnapshots = Boolean(target.querySelector?.(".motion-snapshot"));
  const originalNodes = [target, ...target.querySelectorAll<HTMLElement>("*")].filter(node => !hasSnapshots || !node.closest(".motion-snapshot"));
  const clonedNodes = [clone, ...clone.querySelectorAll<HTMLElement>("*")];
  // Absolute snapshots form a new formatting context: a child's collapsed margin
  // would otherwise reappear INSIDE the image (e.g. AddBook's first QueueList).
  if (computed.display === "block" && computed.overflow === "visible") {
    for (const [first, image, edge, margin] of [
      [target.firstElementChild, clone.firstElementChild, "top", "marginTop"],
      [target.lastElementChild, clone.lastElementChild, "bottom", "marginBottom"],
    ] as const) {
      let child = first, copy = image;
      while (child && copy) {
        const style = getComputedStyle(child);
        if (style.position === "absolute" || style.position === "fixed" || style.float !== "none" ||
          Math.abs(child.getBoundingClientRect()[edge] - bounds[edge]) >= 1) break;
        if (parseFloat(style[margin]) > 0) (copy as HTMLElement).style[margin] = "0px";
        if (style.display !== "block" || style.overflow !== "visible") break;
        child = edge === "top" ? child.firstElementChild : child.lastElementChild;
        copy = edge === "top" ? copy.firstElementChild : copy.lastElementChild;
      }
    }
  }
  // Phần tử sticky con (khung cuộn nằm NGOÀI vùng chụp): ảnh không tự ghim được, nên đặt relative
  // và mỗi frame bù theo rect thật của phần tử gốc (xem trackSurfaceSnapshot).
  const pins: StickyPin[] = [];
  // cloneNode không sao chép lựa chọn sống của select (cả multiple / selectedIndex=-1).
  originalNodes.forEach((node, index) => {
    const copy = clonedNodes[index];
    if (index > 0 && getComputedStyle(node).position === "sticky" && !scrollsInside(node, target)) {
      copy.style.position = "relative";
      copy.style.top = "0px"; copy.style.left = "0px"; copy.style.right = "auto"; copy.style.bottom = "auto";
      pins.push({ node, copy, x: 0, y: 0, natural: undefined });
    }
    if (node.tagName === "SELECT") {
      const select = node as HTMLSelectElement, image = copy as HTMLSelectElement;
      Array.from(select.options).forEach((option, at) => { image.options[at].selected = option.selected; });
      if (!select.multiple) image.selectedIndex = select.selectedIndex;
    }
    // Hàng content-visibility:auto ngoài màn đo lại bằng intrinsic size khi clone.
    // Đóng băng chiều cao cũ để giữ đúng chương đang nhìn trong khung cuộn con.
    if (node.classList?.contains("[content-visibility:auto]") || node.style?.contentVisibility === "auto") {
      const style = getComputedStyle(node);
      copy.style.contentVisibility = "visible";
      copy.style.containIntrinsicSize = "none";
      const chrome = style.boxSizing === "border-box" ? 0 : ["paddingTop", "paddingBottom", "borderTopWidth", "borderBottomWidth"]
        .reduce((sum, key) => sum + (parseFloat(style[key as "paddingTop"]) || 0), 0);
      copy.style.height = `${parseFloat(style.height) + chrome || node.getBoundingClientRect().height}px`;
      copy.style.boxSizing = "border-box";
    }
  });
  (host ?? doc.body).append(clone);
  const stopTracking = trackSurfaceSnapshot(target, clone, bounds, host, followScroll, pins);
  originalNodes.forEach((node, index) => {
    if (node.scrollTop) clonedNodes[index].scrollTop = node.scrollTop;
    if (node.scrollLeft) clonedNodes[index].scrollLeft = node.scrollLeft;
  });
  let timer = window.setTimeout(() => removeMotionSnapshot(clone), MOTION.fastOut + 80);
  snapshotLife.set(clone, (ms) => { window.clearTimeout(timer); timer = window.setTimeout(() => removeMotionSnapshot(clone), ms); });
  const onEnd = (event: Event) => {
    if (event.target !== clone) return;
    removeMotionSnapshot(clone);
  };
  snapshotCleanups.set(clone, () => {
    window.clearTimeout(timer);
    clone.removeEventListener?.("animationend", onEnd);
    snapshotCleanups.delete(clone);
    snapshotPlacements.delete(clone);
    if (snapshotTargets.get(target) === clone) snapshotTargets.delete(target);
    stopTracking?.();
    clone.remove();
  });
  clone.addEventListener("animationend", onEnd);
  if (deferOverlap) { snapshotPlacements.get(clone)?.(); return clone; }
  return settleMotionSnapshot(target, clone);
}

/** Phần tử sticky trong vùng chụp: `copy` trong ảnh (relative), `x`/`y` là độ bù đang áp (px trong ảnh),
 *  `natural` là toạ độ tự nhiên của copy so với góc ảnh (px màn hình), đo một lần ở lần đặt đầu. */
type StickyPin = { node: HTMLElement; copy: HTMLElement; x: number; y: number; natural?: { x: number; y: number } };

/** Khung cuộn gần nhất của sticky nằm trong vùng chụp thì ảnh tự giữ đúng (scrollTop được chép), không cần bù. */
function scrollsInside(node: HTMLElement, target: HTMLElement): boolean {
  for (let parent = node.parentElement; parent; parent = parent.parentElement) {
    const style = getComputedStyle(parent);
    if (/auto|scroll|hidden|clip|overlay/.test(`${style.overflowX || style.overflow} ${style.overflowY || style.overflow}`)) return target.contains(parent);
  }
  return false;
}

function trackSurfaceSnapshot(target: HTMLElement, clone: HTMLElement, bounds: DOMRect, host?: HTMLElement, followScroll = false, pins: StickyPin[] = []): (() => void) | undefined {
  // Host có thể là menu tĩnh trong popper transform: offsetParent sau append mới là containing block.
  const containingBlock = host ? (clone.offsetParent as HTMLElement | null) ?? host : undefined;
  const hostBounds = containingBlock?.getBoundingClientRect();
  const scaleX = containingBlock?.offsetWidth ? hostBounds!.width / containingBlock.offsetWidth : 1;
  const scaleY = containingBlock?.offsetHeight ? hostBounds!.height / containingBlock.offsetHeight : 1;
  const left = hostBounds ? (bounds.left - hostBounds.left) / scaleX - containingBlock!.clientLeft + containingBlock!.scrollLeft : bounds.left;
  const top = hostBounds ? (bounds.top - hostBounds.top) / scaleY - containingBlock!.clientTop + containingBlock!.scrollTop : bounds.top;
  clone.style.width = `${bounds.width / scaleX}px`;
  clone.style.height = `${bounds.height / scaleY}px`;
  // Ảnh nằm trên surface nhưng vẫn phải cắt ở các khung cuộn của nội dung gốc.
  const ancestors: { node: HTMLElement; x: number; y: number; maxX: number; maxY: number; dx: number; dy: number; ignoredX: number; ignoredY: number; sx: number; sy: number; clipX: boolean; clipY: boolean }[] = [];
  for (let node = target.parentElement; node; node = node.parentElement) {
    const style = getComputedStyle(node), rect = node.getBoundingClientRect();
    ancestors.push({ node, x: node.scrollLeft, y: node.scrollTop,
      maxX: Math.max(0, node.scrollWidth - node.clientWidth), maxY: Math.max(0, node.scrollHeight - node.clientHeight),
      dx: 0, dy: 0, ignoredX: 0, ignoredY: 0,
      sx: node.offsetWidth ? rect.width / node.offsetWidth : 1, sy: node.offsetHeight ? rect.height / node.offsetHeight : 1,
      clipX: /auto|scroll|hidden|clip/.test(style.overflowX || style.overflow),
      clipY: /auto|scroll|hidden|clip/.test(style.overflowY || style.overflow) });
    if (node === host) break;
  }
  if (!host && !ancestors.some(item => item.clipX || item.clipY) && !pins.length) return;
  // Chỉ phần đã nhìn thấy lúc chụp được vẽ; hộp lớn lên không lộ chương cũ khác.
  const initialClip = { left: 0, top: 0, right: 0, bottom: 0 };
  if (host) for (const item of ancestors) {
    // Hidden/clip often belongs to an opening Fold: its clip must grow with it.
    const style = getComputedStyle(item.node);
    if (!/auto|scroll|overlay/.test(style.overflowY || style.overflow) && !/auto|scroll|overlay/.test(style.overflowX || style.overflow)) continue;
    const rect = item.node.getBoundingClientRect();
    if (item.clipX) {
      initialClip.left = Math.max(initialClip.left, rect.left + item.node.clientLeft * item.sx - bounds.left);
      initialClip.right = Math.max(initialClip.right, bounds.right - rect.left - (item.node.clientLeft + item.node.clientWidth) * item.sx);
    }
    if (item.clipY) {
      initialClip.top = Math.max(initialClip.top, rect.top + item.node.clientTop * item.sy - bounds.top);
      initialClip.bottom = Math.max(initialClip.bottom, bounds.bottom - rect.top - (item.node.clientTop + item.node.clientHeight) * item.sy);
    }
  }
  const place = () => {
    let dx = 0, dy = 0;
    // Containing block và tổ tiên của nó tự cuộn ảnh. Menu static trong popper thì không:
    // containing block nằm ngoài menu, nên vẫn phải trừ delta cuộn của chính menu.
    for (const item of ancestors) {
      const x = item.node.scrollLeft, y = item.node.scrollTop;
      const maxX = Math.max(0, item.node.scrollWidth - item.node.clientWidth), maxY = Math.max(0, item.node.scrollHeight - item.node.clientHeight);
      // Clamp do nội dung co không phải người dùng cuộn. Trang opt-in theo cả restore.
      const clampX = Boolean(host) && maxX < item.maxX && item.x > maxX && Math.abs(x - maxX) < 1;
      const clampY = Boolean(host) && maxY < item.maxY && item.y > maxY && Math.abs(y - maxY) < 1;
      item.dx += clampX ? 0 : x - item.x; item.dy += clampY ? 0 : y - item.y;
      item.ignoredX += clampX ? x - item.x : 0; item.ignoredY += clampY ? y - item.y : 0;
      if (host || followScroll) {
        if (!containingBlock || (item.node !== containingBlock && !item.node.contains(containingBlock))) {
          dx += item.dx * item.sx; dy += item.dy * item.sy;
        } else {
          // Khung chứa tự trừ scroll thật; bù riêng phần clamp đã bỏ qua.
          dx -= item.ignoredX * item.sx; dy -= item.ignoredY * item.sy;
        }
      }
      item.x = x; item.y = y; item.maxX = maxX; item.maxY = maxY;
    }
    clone.style.left = `${left - dx / scaleX}px`; clone.style.top = `${top - dy / scaleY}px`;
    if (pins.length) {
      // Cuộn tuyến tính chỉ đúng với phần chưa ghim: phần sticky đứng theo vị trí thật của bản gốc.
      const frame = clone.getBoundingClientRect();
      const px = frame.width ? frame.width / (bounds.width / scaleX) : scaleX;
      const py = frame.height ? frame.height / (bounds.height / scaleY) : scaleY;
      for (const pin of pins) {
        if (!pin.node.isConnected) continue; // Bản gốc đã gỡ sau commit: giữ chỗ ghim cuối.
        const live = pin.node.getBoundingClientRect();
        if (!pin.natural) { const copy = pin.copy.getBoundingClientRect(); pin.natural = { x: copy.left - frame.left, y: copy.top - frame.top }; }
        let outerX = 0, outerY = 0; // sticky lồng nhau: copy con đi theo độ bù của copy cha.
        for (const other of pins) if (other !== pin && other.copy.contains(pin.copy)) { outerX += other.x * px; outerY += other.y * py; }
        pin.x = (live.left - frame.left - pin.natural.x - outerX) / px;
        pin.y = (live.top - frame.top - pin.natural.y - outerY) / py;
        pin.copy.style.left = `${pin.x}px`; pin.copy.style.top = `${pin.y}px`;
      }
    }
    if (!ancestors.some(item => item.clipX || item.clipY)) return;
    // Đo ảnh sau đặt vị trí: host có thể vừa cuộn/di chuyển bằng CSS, ảnh tự đi theo host.
    const image = clone.getBoundingClientRect();
    const sx = image.width ? image.width / (bounds.width / scaleX) : scaleX;
    const sy = image.height ? image.height / (bounds.height / scaleY) : scaleY;
    let l = image.left + initialClip.left * sx / scaleX, t = image.top + initialClip.top * sy / scaleY,
      r = image.right - initialClip.right * sx / scaleX, b = image.bottom - initialClip.bottom * sy / scaleY;
    for (const item of ancestors) {
      if (!item.clipX && !item.clipY) continue;
      const rect = item.node.getBoundingClientRect();
      const sx = item.node.offsetWidth ? rect.width / item.node.offsetWidth : 1;
      const sy = item.node.offsetHeight ? rect.height / item.node.offsetHeight : 1;
      const x = rect.left + item.node.clientLeft * sx, y = rect.top + item.node.clientTop * sy;
      if (item.clipX) { l = Math.max(l, x); r = Math.min(r, x + item.node.clientWidth * sx); }
      if (item.clipY) { t = Math.max(t, y); b = Math.min(b, y + item.node.clientHeight * sy); }
    }
    clone.style.clipPath = `inset(${Math.max(0, t - image.top) / sy}px ${Math.max(0, image.right - r) / sx}px ${Math.max(0, image.bottom - b) / sy}px ${Math.max(0, l - image.left) / sx}px)`;
  };
  // Scroll không bubble; capture theo cả khung đang cuộn trong lúc ảnh mờ đi.
  target.ownerDocument?.addEventListener?.("scroll", place, true);
  window.addEventListener?.("scroll", place);
  snapshotPlacements.set(clone, place);
  surfacePlacements.add(place);
  scheduleSurfaceFrame(); // Sau commit và layout effect của Collapse, rồi theo resize trong suốt fade.
  return () => {
    surfacePlacements.delete(place);
    if (!surfacePlacements.size && surfaceFrame !== undefined) {
      cancelAnimationFrame(surfaceFrame);
      surfaceFrame = undefined;
    }
    target.ownerDocument?.removeEventListener?.("scroll", place, true);
    window.removeEventListener?.("scroll", place);
  };
}

/** Đang có một View Transition do app mở (đổi trang, Đang nghe, đổi giao diện). */
export function viewTransitionRunning(doc: TransitionDocument | undefined = browserDocument()): boolean {
  return Boolean(doc?.documentElement.dataset.vt);
}

/** Đổi giao diện trong một View Transition (ảnh cũ -> ảnh mới, styles.css lo hoạt ảnh). Không có API (trình duyệt cũ, trình dựng thử) hay
 *  cửa sổ đang ẩn thì đổi thẳng - chỗ gọi có đường dự phòng riêng (usePageEnter, .now-playing). Xin giảm chuyển động VẪN đi qua đây: CSS đặt
 *  --motion-amount = 0 nên chỉ còn hiện/mờ chéo, không bật tắt cứng. `update` luôn chạy đúng một lần, kể cả khi chuyển cảnh bị huỷ hay bị
 *  lần chuyển sau thay: Back bấm liên tiếp không bao giờ bị nuốt (lần sau bỏ hoạt ảnh của lần trước, không bỏ thay đổi). `sync`: cách
 *  chạy `update` trong chuyển cảnh - mặc định flushSync để React vẽ xong trước khi trình duyệt chụp ảnh mới. */
export function withViewTransition(
  update: () => void,
  nav: NavMotion = "none",
  doc: TransitionDocument | undefined = browserDocument(),
  sync: (run: () => void) => void = flushSync,
): boolean {
  const start = doc?.startViewTransition;
  if (!doc || typeof start !== "function" || doc.visibilityState === "hidden") {
    if (doc) fallbackSnapshot(doc, nav);
    update();
    return false;
  }
  const root = doc.documentElement;
  const id = ++latest;
  root.dataset.nav = nav;
  root.dataset.vt = "1";
  let done = false;
  const run = () => {
    if (done) return;
    done = true;
    sync(update);
  };
  const clear = () => {
    if (id !== latest) return;
    delete root.dataset.vt;
    delete root.dataset.nav;
  };
  let transition: TransitionLike | undefined;
  try {
    transition = start.call(doc, run);
  } catch {
    fallbackSnapshot(doc, nav);
    run();
  }
  // Chuyển cảnh bị huỷ (TimeoutError, lần chuyển mới thay) thì trạng thái vẫn đã đổi trong `run` - chỉ là không có hoạt ảnh.
  transition?.ready?.catch(() => run());
  if (transition?.finished) void transition.finished.catch(() => undefined).then(() => { run(); clear(); });
  else {
    run();
    clear();
  }
  return Boolean(transition);
}

/** Hướng đổi trang theo hành động của Router và vị trí trong lịch sử: PUSH = sâu vào; POP về chỗ thấp hơn = lùi ra; REPLACE (tab, nhóm cài
 *  đặt ở hai cột, ?tab=) = ngang hàng. Cùng trang chỉ đổi ?/# bằng PUSH / POP (tìm, chọn mục) thì không chuyển vùng trang. */
export function navMotion(action: "PUSH" | "POP" | "REPLACE", from: { pathname: string; idx: number; search?: string }, to: { pathname: string; idx: number; search?: string }): NavMotion {
  if (from.pathname === to.pathname && new URLSearchParams(from.search).get("step") !== new URLSearchParams(to.search).get("step")) return to.idx < from.idx ? "back" : "forward";
  // Cùng trang, chỉ đổi ?tab= / tham số: trang đứng yên, vùng nội dung tự trượt (TabsPanels) - không mờ cả màn hình.
  if (from.pathname === to.pathname) return "none";
  if (action === "REPLACE") return "through";
  // Giữa hai mục gốc (tab dưới / thanh bên: Thư viện, Tải sách, Studio, Cài đặt) là ngang hàng, không phải sâu vào.
  if (depth(from.pathname) <= 1 && depth(to.pathname) <= 1) return "through";
  if (action === "PUSH") return "forward";
  return to.idx < from.idx ? "back" : "forward";
}

function depth(pathname: string): number {
  return pathname.split("/").filter(Boolean).length;
}

// ---- Lớp tự dựng hiện / ẩn bằng state ---------------------------------------------------------------------------------------------

/** Lớp còn trong trang không: đang mở, hoặc đã đóng mà hiệu ứng đóng chưa xong. */
export function presenceMounted(open: boolean, mounted: boolean, exitDone: boolean): boolean {
  return open || (mounted && !exitDone);
}

/** State thay cả bước/nội dung: bỏ cập nhật bằng nhau. Setter thứ ba không mở VT (dọn khi đóng, hoặc MotionRegion cục bộ).
 * Giữ giá trị mới ngay khi gọi để các updater liên tiếp thấy đúng thứ tự; callback VT đến muộn không ghi đè lần dọn mới hơn.
 * Không chạy side effect trong React updater: StrictMode có thể gọi updater nhiều lần. */
export function useMotionState<T>(initial: T | (() => T)) {
  const [value, set] = useState(initial);
  const current = useRef(value);
  const applied = useRef(value);
  const pending = useRef(false);
  const generation = useRef(0);
  const update = useCallback((next: SetStateAction<T>, animate: boolean) => {
    const resolved = typeof next === "function" ? (next as (previous: T) => T)(current.current) : next;
    if (animate ? Object.is(current.current, resolved) : Object.is(applied.current, resolved) && !pending.current) return;
    current.current = resolved;
    const version = ++generation.current;
    pending.current = animate;
    const apply = () => {
      if (version !== generation.current) return;
      pending.current = false;
      applied.current = resolved;
      set(typeof resolved === "function" ? () => resolved : resolved);
    };
    if (animate) withViewTransition(apply);
    else apply();
  }, []);
  const change = useCallback((next: SetStateAction<T>) => update(next, true), [update]);
  const withoutTransition = useCallback((next: SetStateAction<T>) => update(next, false), [update]);
  return [value, change, withoutTransition] as const;
}

/** Một lần đóng: sự kiện của con không được gỡ cha; huỷ khi mở lại/unmount; luôn có hạn chờ nếu animationend bị bỏ. */
export function exitCompletion(done: () => void, duration: number, schedule: (run: () => void, ms: number) => () => void = (run, ms) => {
  const timer = setTimeout(run, ms);
  return () => clearTimeout(timer);
}) {
  let active = true;
  let cancelTimer = () => {};
  const finish = () => {
    if (!active) return;
    active = false;
    cancelTimer();
    done();
  };
  cancelTimer = schedule(finish, duration + 80);
  return {
    end: (event: { target: unknown; currentTarget: unknown }) => { if (event.target === event.currentTarget) finish(); },
    cancel: () => { active = false; cancelTimer(); },
  };
}

/** Giữ một lớp tự dựng (panel, bước con, khung ghép, thông báo trong trang) trong trang tới khi hiệu ứng đóng chạy xong, như Presence của
 *  Radix: `mounted` để dựng, `state` ("open" / "closed") cho data-state + lớp .motion-panel, `onAnimationEnd` gắn vào chính phần tử ấy.
 *  Hẹn giờ dự phòng (thời lượng đóng + 80 ms) gỡ lớp cả khi animationend không tới (phần tử ẩn, trình duyệt bỏ hoạt ảnh) - không bao giờ
 *  kẹt một lớp vô hình chắn chạm. Lớp đóng thì ngăn Back (useBackLayer theo `open`) gỡ NGAY: Back kế tiếp đi tiếp được. */
export function usePresence(open: boolean, exitMs: number = MOTION.mediumOut) {
  const [mounted, setMounted] = useState(open);
  const exit = useRef<ReturnType<typeof exitCompletion> | null>(null);
  if (open && !mounted) setMounted(true);
  useEffect(() => {
    if (open || !mounted) return;
    exit.current = exitCompletion(() => setMounted(false), exitMs);
    return () => { exit.current?.cancel(); exit.current = null; };
  }, [open, mounted, exitMs]);
  const onAnimationEnd = useCallback(
    (event: AnimationEvent<HTMLElement>) => {
      if (!open) exit.current?.end(event);
    },
    [open],
  );
  return { mounted: open || mounted, state: (open ? "open" : "closed") as "open" | "closed", onAnimationEnd };
}

// ---- Danh sách thêm / xoá --------------------------------------------------------------------------------------------------------

export type RowState = "enter" | "idle" | "exit";
export interface PresentRow<T> {
  key: string;
  item: T;
  state: RowState;
}

/** Ghép danh sách mới vào danh sách đang hiện: hàng mới "enter", hàng còn ở lại giữ trạng thái (bản dữ liệu mới nhất), hàng vừa mất "exit" -
 *  giữ đúng chỗ cũ để mắt thấy nó khép lại tại chỗ. `first`: lần dựng đầu, không hàng nào "enter" (cả trang đã có hiệu ứng mở). */
export function mergeRows<T>(shown: readonly PresentRow<T>[], next: readonly T[], keyOf: (item: T) => string, first = false): PresentRow<T>[] {
  const previous = new Map(shown.map((row) => [row.key, row]));
  const keys = new Set(next.map(keyOf));
  const result: PresentRow<T>[] = next.map((item) => {
    const key = keyOf(item);
    const old = previous.get(key);
    return { key, item, state: first ? "idle" : !old || old.state === "exit" ? "enter" : old.state };
  });
  // Hàng đang xoá bám vào hàng sống kế tiếp ở vị trí cũ; thứ tự hàng sống luôn theo `next` (kể cả sắp xếp lại).
  let anchor: string | undefined;
  for (let index = shown.length - 1; index >= 0; index--) {
    const row = shown[index];
    if (keys.has(row.key)) anchor = row.key;
    else {
      const at = anchor === undefined ? result.length : result.findIndex((item) => item.key === anchor);
      result.splice(at < 0 ? result.length : at, 0, { ...row, state: "exit" });
      anchor = row.key;
    }
  }
  return result;
}

/** Bỏ hàng đã khép xong, hàng mới mở xong thành đứng yên. */
export function settleRows<T>(rows: readonly PresentRow<T>[]): PresentRow<T>[] {
  return rows.filter((row) => row.state !== "exit").map((row) => (row.state === "enter" ? { ...row, state: "idle" } : row));
}

/** Đo đúng một lần khi hàng bắt đầu vào/ra. Height px chạy trên cả WebView chưa tween được grid track. */
export function measureMotionRow(element: HTMLElement | null): void {
  if (!element) return;
  const body = element.firstElementChild as HTMLElement | null;
  if (body) element.style.setProperty("--row-height", `${body.scrollHeight}px`);
}

/** Danh sách có hàng thêm / xoá mượt (lớp .motion-row + data-state): hàng mới mở chiều cao + hiện dần, hàng bị xoá khép lại rồi mới gỡ.
 *  So theo DÃY KHOÁ, không theo mảng: mảng dựng lại mỗi lần vẽ (lọc, sắp xếp) không làm danh sách "đổi". Hàng còn ở lại luôn mang dữ liệu
 *  mới nhất; hàng đang khép giữ dữ liệu cuối cùng của nó. */
export function useListPresence<T>(items: readonly T[], keyOf: (item: T) => string): (PresentRow<T> & { ref?: typeof measureMotionRow })[] {
  const keys = JSON.stringify(items.map(keyOf));
  const [rows, setRows] = useState<PresentRow<T>[]>(() => mergeRows([], items, keyOf, true));
  const [seen, setSeen] = useState(keys);
  if (seen !== keys) {
    setSeen(keys);
    // Hàng tới cùng trang / lượt dữ liệu đầu đứng yên tại chỗ; hàng thêm sau đó mới mở ra.
    const settling = pageSettling();
    setRows((shown) => mergeRows(shown, items, keyOf, settling));
  }
  const moving = rows.some((row) => row.state !== "idle");
  useEffect(() => {
    if (!moving) return;
    const timer = window.setTimeout(() => setRows(settleRows), MOTION.medium + 60);
    return () => window.clearTimeout(timer);
  }, [keys, moving]);
  const fresh = new Map(items.map((item) => [keyOf(item), item]));
  return rows.map((row) => ({ ...row, item: fresh.get(row.key) ?? row.item, ref: row.state === "idle" ? undefined : measureMotionRow }));
}

// ---- <details> -------------------------------------------------------------------------------------------------------------------

type Animation = { onfinish: (() => void) | null; oncancel: (() => void) | null; cancel(): void };
export type DetailsLike = {
  open: boolean;
  style: { height: string; overflow: string };
  dataset: DOMStringMap;
  children?: ArrayLike<Element>;
  ownerDocument?: Pick<Document, "activeElement">;
  getBoundingClientRect(): { height: number };
  querySelector(selector: string): { getBoundingClientRect(): { height: number }; focus?(): void } | null;
  animate?: (frames: Keyframe[], options: KeyframeAnimationOptions) => Animation;
};

const detailsAnimations = new WeakMap<object, Animation>();

/** Mở / gập một <details> có chuyển động chiều cao: mở thì đặt `open` trước rồi kéo cao dần; gập thì khép tới cao của dòng tóm tắt rồi mới
 *  bỏ `open`. Bấm lại giữa chừng thì đảo chiều từ chỗ đang đứng. Thiếu Web Animations thì fade CSS và hẹn giờ đóng.
 *  `chrome`: phần cao ngoài dòng tóm tắt khi đã gập (đệm, viền của chính <details>). */
export function toggleDetails(details: DetailsLike, chrome = 0, reduced = prefersReducedMotion()): boolean {
  const fallback = typeof details.animate !== "function";
  const summary = details.querySelector("summary");
  if (!summary) return false;
  const phase = details.dataset.motion;
  const shrinking = phase === "opening" ? true : phase === "closing" ? false : details.open;
  const from = details.getBoundingClientRect().height;
  detailsAnimations.get(details)?.cancel();
  for (const child of Array.from(details.children ?? [])) {
    if (child === summary) continue;
    if (shrinking && child.contains(details.ownerDocument?.activeElement ?? null)) summary.focus?.();
    (child as HTMLElement).inert = shrinking;
  }
  details.style.overflow = "clip";
  details.style.height = "";
  details.open = true;
  const to = shrinking ? summary.getBoundingClientRect().height + chrome : details.getBoundingClientRect().height;
  details.dataset.motion = shrinking ? "closing" : "opening";
  if (fallback) details.dataset.motionFallback = "1";
  // Reduced: CSS fade từng thân con, giữ summary đứng yên; animation này chỉ giữ thời hạn đóng.
  let timer: ReturnType<typeof setTimeout> | undefined;
  const animation: Animation = details.animate?.(reduced ? [{ opacity: 1 }, { opacity: 1 }] : [{ height: `${from}px` }, { height: `${to}px` }], {
    duration: reduced ? MOTION.fast : shrinking ? MOTION.mediumOut : MOTION.medium,
    easing: shrinking ? EASE.accelerate : EASE.standard,
  }) ?? { onfinish: null, oncancel: null, cancel() { clearTimeout(timer); this.oncancel?.(); } };
  detailsAnimations.set(details, animation);
  const finish = (completed: boolean) => {
    if (detailsAnimations.get(details) !== animation) return;
    detailsAnimations.delete(details);
    if (completed && shrinking) details.open = false;
    delete details.dataset.motion;
    delete details.dataset.motionFallback;
    details.style.height = "";
    details.style.overflow = "";
  };
  animation.onfinish = () => finish(true);
  animation.oncancel = () => finish(false);
  if (fallback) timer = setTimeout(() => animation.onfinish?.(), MOTION.fast);
  return true;
}

/** Một lần cho cả app (main.tsx hai nền): mọi <details> (Chi tiết kỹ thuật, Xem lỗi…) mở / gập có chuyển động thay vì bật tắt. Bắt ở mức
 *  tài liệu nên chỗ mới thêm cũng tự có. Bấm kèm phím bổ trợ, bấm vào nút / liên kết nằm trong dòng tóm tắt, hay <details data-instant>
 *  thì để trình duyệt tự lo. Phím Enter / Space trên <summary> cũng sinh sự kiện click nên đi cùng đường. */
export function installDetailsMotion(doc: Document = document): () => void {
  const onClick = (event: MouseEvent) => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const target = event.target as Element | null;
    const summary = target?.closest?.("summary");
    const details = summary?.parentElement;
    if (!summary || !details || details.tagName !== "DETAILS" || "instant" in details.dataset) return;
    const control = target?.closest("a, button, input, select, textarea, label");
    if (control && summary.contains(control)) return;
    const style = doc.defaultView?.getComputedStyle(details);
    const chrome = style
      ? ["paddingTop", "paddingBottom", "borderTopWidth", "borderBottomWidth"].reduce((sum, key) => sum + (parseFloat(style[key as "paddingTop"]) || 0), 0)
      : 0;
    if (toggleDetails(details as unknown as DetailsLike, chrome)) event.preventDefault();
  };
  doc.addEventListener("click", onClick);
  return () => doc.removeEventListener("click", onClick);
}
