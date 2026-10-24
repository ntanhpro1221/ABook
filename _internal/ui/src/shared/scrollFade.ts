import { useEffect, useState, type CSSProperties, type RefObject } from "react";

/** Mép mờ báo "còn nữa, cuộn được" cho danh sách cuộn dọc (DESIGN 4.5: không gì cụt cứng): mép trên mờ khi đã cuộn xuống, mép dưới mờ khi
 *  còn hàng dưới. Cùng cách hàng tab cuộn ngang (ui.tsx TabsList) - mặt nạ trên chính khung cuộn, nên đặt khung viền ở lớp ngoài (viền trong
 *  khung bị mặt nạ làm mờ theo). Trả `style` cho khung cuộn; `undefined` khi không có gì để cuộn. */
export function scrollFadeMask(edges: { top: boolean; bottom: boolean }, size = 36): string | undefined {
  if (!edges.top && !edges.bottom) return undefined;
  return `linear-gradient(to bottom, ${edges.top ? `transparent, black ${size}px` : "black"}, ${edges.bottom ? `black calc(100% - ${size}px), transparent` : "black"})`;
}

export function useScrollFade(ref: RefObject<HTMLElement | null>, size = 36): CSSProperties | undefined {
  const [edges, setEdges] = useState({ top: false, bottom: false });
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
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
  }, [ref]);
  const mask = scrollFadeMask(edges, size);
  return mask ? { maskImage: mask, WebkitMaskImage: mask } : undefined;
}
