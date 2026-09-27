import { useLayoutEffect, type RefObject } from "react";

// Chuyển trang: khi đường dẫn đổi, nội dung mới hiện dần và nhích lên 6px. Dùng Web Animations trên chính khung nội
// dung nên KHÔNG dựng lại trang (key theo đường dẫn sẽ làm mất trạng thái, cuộn, ô đang gõ). Người dùng xin giảm
// chuyển động thì thôi.
export function usePageEnter(ref: RefObject<HTMLElement | null>, key: string) {
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element || typeof element.animate !== "function") return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    element.animate(
      [
        { opacity: 0, transform: "translateY(6px)" },
        { opacity: 1, transform: "none" },
      ],
      { duration: 220, easing: "cubic-bezier(0.2, 0, 0, 1)" },
    );
  }, [ref, key]);
}
