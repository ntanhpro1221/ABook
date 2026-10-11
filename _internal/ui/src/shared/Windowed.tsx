import { useEffect, useRef, useState, type ReactNode } from "react";

// Danh sách rất dài (sách 3000 chương, thư viện vài trăm cuốn): chỉ dựng các KHỐI hàng gần màn hình; khối ở xa là một ô trống cao
// bằng chính nó (đo lúc nó còn hiện; chưa hiện lần nào thì ước theo số hàng). Trang sách 3000 chương từng dựng ~39.000 nút DOM và
// mọi hàng vẽ lại theo nhịp trình phát (soát uxfix30). Không thư viện ngoài: hàng cao thấp khác nhau, trang cuộn bằng cửa sổ hay
// bằng khung nào cũng được (IntersectionObserver lấy khung nhìn làm gốc).

/** Số hàng mỗi khối; danh sách không quá hai khối thì dựng hết như cũ. */
export const WINDOW_BLOCK = 40;
/** Dựng trước khối trong khoảng này quanh màn hình: cuộn nhanh không thấy ô trống. */
const MARGIN = "1500px 0px";

/** Các khối cần dựng lúc đầu (danh sách `total` hàng): khối đầu và khối chứa `keep` (hàng phải có sẵn để cuộn tới - chương đang nghe). */
export function firstBlocks(total: number, block: number, keep?: number): Set<number> {
  const shown = new Set([0]);
  if (keep !== undefined && keep >= 0 && keep < total) shown.add(Math.floor(keep / block));
  return shown;
}

/** Chiều cao ô trống của khối `index` chưa dựng (danh sách `total` hàng): đã đo thì đúng số đo, chưa thì số hàng x `estimate`. */
export function blockHeight(index: number, total: number, block: number, estimate: number, measured: ReadonlyMap<number, number>): number {
  return measured.get(index) ?? Math.min(block, total - index * block) * estimate;
}

export function Windowed<T>({
  items,
  row,
  estimate,
  keep,
  block = WINDOW_BLOCK,
  className,
}: {
  items: readonly T[];
  /** Một hàng; `index` là vị trí trong cả danh sách (cho aria-rowindex / aria-posinset). */
  row: (item: T, index: number) => ReactNode;
  /** Chiều cao ước của một hàng (px) cho khối chưa dựng lần nào. */
  estimate: number;
  /** Vị trí luôn dựng (vd chương đang nghe). */
  keep?: number;
  block?: number;
  /** Lớp của mỗi khối (vd lưới: mỗi khối tự là một lưới cùng cột). */
  className?: string;
}) {
  const count = Math.ceil(items.length / block);
  const windowed = items.length > block * 2 && typeof IntersectionObserver !== "undefined";
  const [shown, setShown] = useState<ReadonlySet<number>>(() => firstBlocks(items.length, block, keep));
  const measured = useRef(new Map<number, number>());
  const nodes = useRef<(HTMLDivElement | null)[]>([]);
  useEffect(() => {
    if (!windowed) return;
    const observer = new IntersectionObserver(
      (entries) => {
        setShown((previous) => {
          let next: Set<number> | null = null;
          for (const entry of entries) {
            const index = Number((entry.target as HTMLElement).dataset.block);
            if (entry.isIntersecting === previous.has(index)) continue;
            next ??= new Set(previous);
            if (entry.isIntersecting) next.add(index);
            else {
              // Rời màn hình khi còn đang dựng: nhớ chiều cao thật để ô trống thay nó không làm trang nhảy.
              measured.current.set(index, entry.boundingClientRect.height);
              next.delete(index);
            }
          }
          return next ?? previous;
        });
      },
      { rootMargin: MARGIN },
    );
    for (const node of nodes.current.slice(0, count)) if (node) observer.observe(node);
    return () => observer.disconnect();
  }, [windowed, count]);
  // Chương đang nghe đổi sang khối khác: dựng sẵn khối ấy.
  const kept = keep !== undefined && keep >= 0 ? Math.floor(keep / block) : -1;
  useEffect(() => {
    if (kept >= 0) setShown((previous) => (previous.has(kept) ? previous : new Set([...previous, kept])));
  }, [kept]);
  if (!windowed) return <>{items.map(row)}</>;
  return (
    <>
      {Array.from({ length: count }, (_, index) => {
        const start = index * block;
        const visible = shown.has(index) || index === kept;
        return (
          <div
            key={index}
            role="none"
            data-block={index}
            ref={(node) => {
              nodes.current[index] = node;
            }}
            className={className}
            style={visible ? undefined : { height: blockHeight(index, items.length, block, estimate, measured.current) }}
          >
            {visible && items.slice(start, start + block).map((item, offset) => row(item, start + offset))}
          </div>
        );
      })}
    </>
  );
}
