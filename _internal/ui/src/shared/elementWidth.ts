import { useLayoutEffect, useState, type RefObject } from "react";

/** Bề rộng bố cục (px, làm tròn) của một phần tử, theo dõi khi nó đổi cỡ; null cho tới lần đo đầu (trước khung vẽ đầu tiên).
 *  Dùng cho luật theo bề rộng NỘI DUNG chứ không theo cửa sổ (thanh bên chiếm chỗ): trang sách tách hai cột từ 840 (BOOK_SPLIT_WIDTH),
 *  cùng ngưỡng với Qt (BookPage.qml: Theme.widthExpanded). clientWidth không chịu ảnh hưởng của phép biến đổi (trang đang trượt vào). */
export function useElementWidth(ref: RefObject<HTMLElement | null>): number | null {
  const [width, setWidth] = useState<number | null>(null);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const read = (value: number) => setWidth((old) => (old === Math.round(value) ? old : Math.round(value)));
    read(node.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const last = entries[entries.length - 1];
      read(last ? last.contentRect.width : node.clientWidth);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}
