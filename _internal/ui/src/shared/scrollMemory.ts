import { useLayoutEffect, useRef, type RefObject } from "react";

// Chỗ cuộn của trang theo phiên: quay lại trang sách / danh sách chương Studio từ trình phát, màn đọc hay Thư viện thì về đúng chỗ
// đang xem (soát a30 L3: trang sách 3000 chương cuộn ở 108.280 px, Back thì về đầu). Nhớ trong sessionStorage - mở lại app là phiên mới.

/** Khung cuộn gần nhất chứa `node` (khung có overflow-y auto/scroll - vùng nội dung `<main>` của vỏ app); không có thì cả trang. */
export function scrollParent(node: Element): HTMLElement {
  for (let at = node.parentElement; at; at = at.parentElement) {
    const { overflowY } = getComputedStyle(at);
    if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") return at;
  }
  return (document.scrollingElement ?? document.documentElement) as HTMLElement;
}

/** Khung cuộn là cả trang (cuộn bằng cửa sổ): sự kiện cuộn đến ở `window`, mép trên khung nhìn là 0. */
export function isPage(scroller: Element): boolean {
  return scroller === document.scrollingElement || scroller === document.documentElement || scroller === document.body;
}

/** Đọc một giá trị JSON của phiên; bộ nhớ phiên bị chặn (chế độ riêng tư, trang xem trước) hay hỏng thì như chưa có. */
export function sessionRead(key: string): unknown {
  try {
    const raw = sessionStorage.getItem(key);
    return raw === null ? null : (JSON.parse(raw) as unknown);
  } catch {
    return null;
  }
}

export function sessionWrite(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Bộ nhớ phiên bị chặn hay đầy: chỉ mất chỗ cuộn, trang vẫn chạy.
  }
}

/** Vị trí cuộn để `top..bottom` (so với mép trên khung) hiện ở giữa khung cao `view`; đã nằm trọn trong khung thì null (không cuộn). */
export function revealShift(top: number, bottom: number, view: number): number | null {
  if (top >= 0 && bottom <= view) return null;
  return Math.round(top - (view - (bottom - top)) / 2);
}

/** Đưa phần tử vào giữa khung cuộn nếu nó chưa nằm trọn trong khung. */
export function reveal(scroller: HTMLElement, element: Element): void {
  const view = isPage(scroller) ? { top: 0, height: window.innerHeight } : scroller.getBoundingClientRect();
  const box = element.getBoundingClientRect();
  const shift = revealShift(box.top - view.top, box.bottom - view.top, view.height);
  if (shift !== null) scroller.scrollTop += shift;
}

/** Chờ layout và các hoạt ảnh đang đổi vị trí hàng trước khi đo chỗ cuộn. */
export function afterScrollLayout(node: HTMLElement, callback: () => void): () => void {
  let alive = true;
  const frame = requestAnimationFrame(() => {
    const animations = (node.getAnimations?.({ subtree: true }) ?? [])
      .filter(animation => animation.effect?.getComputedTiming().endTime !== Infinity);
    void Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
      if (alive && node.isConnected) callback();
    });
  });
  return () => { alive = false; cancelAnimationFrame(frame); };
}

const KEY = "abook.scroll.";

/** Ghi chỗ cuộn hiện tại của trang `key`. */
export function saveScroll(key: string, scroller: { scrollTop: number }): void {
  sessionWrite(KEY + key, Math.round(scroller.scrollTop));
}

/** Về chỗ đã nhớ của trang `key`; chưa nhớ (mở lần đầu trong phiên) thì `first`. */
export function restoreScroll<S extends { scrollTop: number }>(key: string, scroller: S, first?: (scroller: S) => void): void {
  const saved = sessionRead(KEY + key);
  if (typeof saved === "number" && Number.isFinite(saved)) scroller.scrollTop = saved;
  else first?.(scroller);
}

/** Trang nhớ chỗ cuộn theo `key` (vd từng cuốn sách) trong phiên. Mở lại trang thì về chỗ ấy; chưa nhớ chỗ nào thì `first`
 *  (vd đưa chương đang nghe vào khung). `key` null = trang chưa sẵn (đang nạp) - chờ. `ref` là một phần tử trong trang. */
export function useScrollMemory(key: string | null, ref: RefObject<HTMLElement | null>, first?: (scroller: HTMLElement) => void) {
  const firstNow = useRef(first);
  firstNow.current = first;
  useLayoutEffect(() => {
    const node = ref.current;
    if (!key || !node) return;
    const scroller = scrollParent(node);
    const target: EventTarget = isPage(scroller) ? window : scroller;
    let alive = true;
    let restored = false;
    let cancelLayout: (() => void) | undefined;
    // Sau mọi layout effect của lần dựng này: vỏ app (usePageEnter) đưa trang mới về đầu trong effect của chính nó, chạy SAU effect
    // của trang con. Microtask vẫn chạy trước khi trình duyệt vẽ - không thấy trang nháy ở đầu. Hàng đích có thể còn trong nhóm
    // đang mở ra (Fold): đo lại sau layout và chuyển động, trừ khi bạn đã tự cuộn trong lúc chờ.
    queueMicrotask(() => {
      if (!alive) return;
      restoreScroll(key, scroller, firstNow.current);
      const settled = scroller.scrollTop;
      cancelLayout = afterScrollLayout(scroller, () => {
        if (scroller.scrollTop === settled) restoreScroll(key, scroller, firstNow.current);
        restored = true;
      });
    });
    const save = () => { if (restored) saveScroll(key, scroller); };
    target.addEventListener("scroll", save, { passive: true });
    return () => {
      alive = false;
      cancelLayout?.();
      target.removeEventListener("scroll", save);
    };
  }, [key, ref]);
}
