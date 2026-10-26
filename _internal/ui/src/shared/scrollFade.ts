import { useCallback, useEffect, useState, type CSSProperties, type RefObject } from "react";

/** Bề cao mép mờ của mọi vùng cuộn - cùng số với điện thoại native (`ScrollFadeEdge` ở mobile/android/.../ui/components/ScrollFade.kt). */
export const SCROLL_FADE = 24;

/** Mép mờ báo "còn nữa, cuộn được" cho danh sách cuộn dọc (DESIGN 4.5: không gì cụt cứng): mép trên mờ khi đã cuộn xuống, mép dưới mờ khi
 *  còn hàng dưới. Cùng cách hàng tab cuộn ngang (ui.tsx TabsList) - mặt nạ trên chính khung cuộn, nên đặt khung viền ở lớp ngoài (viền trong
 *  khung bị mặt nạ làm mờ theo). Trả `style` cho khung cuộn; `undefined` khi không có gì để cuộn. */
export function scrollFadeMask(edges: { top: boolean; bottom: boolean }, size = SCROLL_FADE): string | undefined {
  if (!edges.top && !edges.bottom) return undefined;
  return `linear-gradient(to bottom, ${edges.top ? `transparent, black ${size}px` : "black"}, ${edges.bottom ? `black calc(100% - ${size}px), transparent` : "black"})`;
}

export function useScrollFade(ref: RefObject<HTMLElement | null>, size = SCROLL_FADE): CSSProperties | undefined {
  const [element, setElement] = useState<HTMLElement | null>(null);
  useEffect(() => setElement(ref.current), [ref]);
  return useScrollFadeOn(element, size);
}

/** Như `useScrollFade` cho khung chỉ có sau khi mở (thân hộp thoại / bảng đáy trong Portal): nhận chính phần tử qua ref gọi lại (`ref={setBody}`). */
export function useScrollFadeOn(element: HTMLElement | null, size = SCROLL_FADE): CSSProperties | undefined {
  const [edges, setEdges] = useState({ top: false, bottom: false });
  useEffect(() => {
    if (!element) {
      setEdges((old) => (old.top || old.bottom ? { top: false, bottom: false } : old));
      return;
    }
    const update = () => {
      const top = element.scrollTop > 2;
      const bottom = element.scrollTop + element.clientHeight < element.scrollHeight - 2;
      setEdges((old) => (old.top === top && old.bottom === bottom ? old : { top, bottom }));
    };
    update();
    element.addEventListener("scroll", update, { passive: true });
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(element);
    // Hàng thêm / bớt không đổi cỡ khung (khung đã chạm trần cao) - nhưng đổi chiều cao nội dung: nghe cả khung con.
    const mutations = typeof MutationObserver === "undefined" ? null : new MutationObserver(update);
    mutations?.observe(element, { childList: true, subtree: true });
    return () => {
      element.removeEventListener("scroll", update);
      observer?.disconnect();
      mutations?.disconnect();
    };
  }, [element]);
  const mask = scrollFadeMask(edges, size);
  return mask ? { maskImage: mask, WebkitMaskImage: mask } : undefined;
}

/** Khung cuộn lồng trong bảng / hộp / trang (máy dò scrollFadeRules.test.ts): `const fade = useFadeScroller(); <ul ref={fade.ref} style={fade.style}>`.
 *  Phần tử đã có ref riêng thì đưa ref ấy vào `also`: một ref gọi lại giữ cả hai. */
export function useFadeScroller<T extends HTMLElement = HTMLElement>(also?: RefObject<T | null>) {
  const [element, setElement] = useState<T | null>(null);
  const ref = useCallback((node: T | null) => {
    if (also) also.current = node;
    setElement(node);
  }, [also]);
  return { ref, style: useScrollFadeOn(element) };
}

/** Như `useScrollFade` cho hàng cuộn NGANG (hàng lọc Thư viện, `FilterRow`): mục cuối không bao giờ bị cắt cứng ở mép khi chữ hệ thống to
 *  (soát 25-10: "Xong" cụt ở cỡ chữ 115 %) - mép nào còn mục bị che thì mờ dần, như hàng tab. Nghe cả cỡ từng mục: chữ to ra không đổi cỡ khung.
 *  Nhận chính phần tử qua ref gọi lại (`ref={setRow}`): hàng có thể chỉ hiện sau khi tải xong. */
export function useRowFade(element: HTMLElement | null, size = SCROLL_FADE): CSSProperties | undefined {
  const [edges, setEdges] = useState({ left: false, right: false });
  useEffect(() => {
    if (!element) return;
    const update = () => {
      const left = element.scrollLeft > 2;
      const right = element.scrollLeft + element.clientWidth < element.scrollWidth - 2;
      setEdges((old) => (old.left === left && old.right === right ? old : { left, right }));
    };
    update();
    element.addEventListener("scroll", update, { passive: true });
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(element);
    for (const child of Array.from(element.children)) observer?.observe(child);
    return () => {
      element.removeEventListener("scroll", update);
      observer?.disconnect();
    };
  }, [element]);
  if (!element || (!edges.left && !edges.right)) return undefined;
  const mask = `linear-gradient(to right, ${edges.left ? `transparent, black ${size}px` : "black"}, ${edges.right ? `black calc(100% - ${size}px), transparent` : "black"})`;
  return { maskImage: mask, WebkitMaskImage: mask };
}
