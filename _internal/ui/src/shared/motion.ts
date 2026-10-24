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

// Chuyển trang khi KHÔNG có View Transitions (MotionHashRouter lo phần có): nội dung mới hiện dần và nhích lên. Dùng Web Animations trên
// chính khung nội dung nên KHÔNG dựng lại trang (key theo đường dẫn sẽ làm mất trạng thái, cuộn, ô đang gõ). Xin giảm chuyển động: chỉ hiện dần.
export function usePageEnter(ref: RefObject<HTMLElement | null>, key: string, { resetScroll = true } = {}) {
  useLayoutEffect(() => {
    const element = ref.current;
    // Trang mới mở từ đầu: vùng cuộn dùng chung giữa các trang từng giữ vị trí trang trước (soát UX 29-09 - "Tạo sách nói"
    // mở ở 67px, chế độ Đọc ở 115px dưới header).
    if (resetScroll) element?.scrollTo?.({ top: 0 });
    if (!element || typeof element.animate !== "function") return;
    // Đổi trang này đi qua View Transition: ảnh chụp đã chuyển cả vùng - thêm hoạt ảnh ở đây là hiện dần hai lần.
    if (viewTransitionRunning()) return;
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
export function removeMotionSnapshot(clone: HTMLElement | undefined): void {
  if (!clone) return;
  const cleanup = snapshotCleanups.get(clone);
  if (cleanup) cleanup();
  else clone.remove();
}

export function captureMotionSnapshot(target: HTMLElement, doc: TransitionDocument = document, floorZ = 51): HTMLElement | undefined {
  if (!doc.body || doc.visibilityState === "hidden") return;
  const bounds = target.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const clone = target.cloneNode(true) as HTMLElement;
  clone.querySelectorAll("[id], [autofocus]").forEach((node) => { node.removeAttribute("id"); node.removeAttribute("autofocus"); });
  clone.removeAttribute("id");
  clone.removeAttribute("role");
  clone.querySelectorAll("[role]").forEach((node) => node.removeAttribute("role"));
  clone.querySelectorAll("[name]").forEach((node) => node.removeAttribute("name"));
  clone.setAttribute("aria-hidden", "true");
  clone.setAttribute("inert", "");
  clone.classList.add("motion-snapshot");
  Object.assign(clone.style, {
    position: "fixed", top: `${bounds.top}px`, left: `${bounds.left}px`, width: `${bounds.width}px`, height: `${bounds.height}px`,
    margin: "0", zIndex: String(floorZ), pointerEvents: "none", overflow: "hidden", transform: "none", translate: "none",
  });
  // Các biến màu được giữ trước khi đổi theme, ảnh cũ không đổi màu theo ảnh mới.
  const computed = getComputedStyle(target);
  clone.style.zIndex = String(Math.max(floorZ, (parseInt(computed.zIndex) || 0) + 1));
  for (const name of computed) if (name.startsWith("--")) clone.style.setProperty(name, computed.getPropertyValue(name));
  clone.style.backgroundColor = computed.backgroundColor === "rgba(0, 0, 0, 0)" ? computed.getPropertyValue("--bg") : computed.backgroundColor;
  const originalNodes = [target, ...target.querySelectorAll<HTMLElement>("*")];
  const clonedNodes = [clone, ...clone.querySelectorAll<HTMLElement>("*")];
  doc.body.append(clone);
  originalNodes.forEach((node, index) => {
    if (node.scrollTop) clonedNodes[index].scrollTop = node.scrollTop;
    if (node.scrollLeft) clonedNodes[index].scrollLeft = node.scrollLeft;
  });
  const timer = window.setTimeout(() => removeMotionSnapshot(clone), MOTION.fastOut + 80);
  const onEnd = (event: Event) => {
    if (event.target !== clone) return;
    removeMotionSnapshot(clone);
  };
  snapshotCleanups.set(clone, () => {
    window.clearTimeout(timer);
    clone.removeEventListener?.("animationend", onEnd);
    snapshotCleanups.delete(clone);
    clone.remove();
  });
  clone.addEventListener("animationend", onEnd);
  return clone;
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
  if (action === "REPLACE") return "through";
  if (from.pathname === to.pathname && new URLSearchParams(from.search).get("step") !== new URLSearchParams(to.search).get("step")) return to.idx < from.idx ? "back" : "forward";
  if (from.pathname === to.pathname) return "none";
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
  const generation = useRef(0);
  const update = useCallback((next: SetStateAction<T>, animate: boolean) => {
    const resolved = typeof next === "function" ? (next as (previous: T) => T)(current.current) : next;
    if (Object.is(current.current, resolved)) return;
    current.current = resolved;
    const version = ++generation.current;
    const apply = () => { if (version === generation.current) set(typeof resolved === "function" ? () => resolved : resolved); };
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
    setRows((shown) => mergeRows(shown, items, keyOf));
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
