import { useEffect, useState } from "react";

/** Khớp một media query, theo dõi khi cửa sổ đổi cỡ. Trình duyệt thiếu matchMedia (trình dựng thử) thì coi là không khớp.
 *  Nghe cả `resize`: vài môi trường (giả lập khung nhìn, WebView cũ) đổi cỡ mà không phát sự kiện `change` của query. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => typeof window !== "undefined" && Boolean(window.matchMedia?.(query).matches));
  useEffect(() => {
    const media = window.matchMedia?.(query);
    if (!media) return;
    const update = () => setMatches(window.matchMedia(query).matches);
    update();
    media.addEventListener("change", update);
    window.addEventListener("resize", update);
    return () => {
      media.removeEventListener("change", update);
      window.removeEventListener("resize", update);
    };
  }, [query]);
  return matches;
}
