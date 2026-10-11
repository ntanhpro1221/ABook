import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

/** Người dùng xin giảm chuyển động (Cài đặt hệ điều hành)? Môi trường không có matchMedia (dựng thử) thì coi là không. */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
}

/** Kiểu cuộn cho scrollTo / scrollIntoView / scrollBy: trượt êm, trừ khi người dùng xin giảm chuyển động (soát a31 M2) - mọi chỗ
 *  cuộn "smooth" đi qua đây để không chỗ nào quên kiểm. */
export function scrollMotion(animate = true): ScrollBehavior {
  return animate && !prefersReducedMotion() ? "smooth" : "auto";
}

// Chuyển trang: khi đường dẫn đổi, nội dung mới hiện dần và nhích lên 6px. Dùng Web Animations trên chính khung nội
// dung nên KHÔNG dựng lại trang (key theo đường dẫn sẽ làm mất trạng thái, cuộn, ô đang gõ). Người dùng xin giảm
// chuyển động thì thôi.
export function usePageEnter(ref: RefObject<HTMLElement | null>, key: string, { resetScroll = true } = {}) {
  useLayoutEffect(() => {
    const element = ref.current;
    // Trang mới mở từ đầu: vùng cuộn dùng chung giữa các trang từng giữ vị trí trang trước (soát UX 29-09 - "Tạo sách nói"
    // mở ở 67px, chế độ Đọc ở 115px dưới header).
    if (resetScroll) element?.scrollTo?.({ top: 0 });
    if (!element || typeof element.animate !== "function") return;
    if (prefersReducedMotion()) return;
    element.animate(
      [
        { opacity: 0, transform: "translateY(6px)" },
        { opacity: 1, transform: "none" },
      ],
      { duration: 220, easing: "cubic-bezier(0.2, 0, 0, 1)" },
    );
  }, [ref, key, resetScroll]);
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
