import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { isPage, scrollParent, sessionRead, sessionWrite } from "./scrollMemory";

// Danh sách rất dài (sách 3000 chương, thư viện vài trăm cuốn): chỉ dựng các KHỐI hàng gần màn hình; khối ở xa là một ô trống cao
// bằng chính nó (đo lúc nó còn hiện; chưa hiện lần nào thì theo chiều cao một hàng đo ở khối đầu). Trang sách 3000 chương từng dựng
// ~39.000 nút DOM và mọi hàng vẽ lại theo nhịp trình phát (soát uxfix30). Không thư viện ngoài: hàng cao thấp khác nhau, trang cuộn
// bằng cửa sổ hay bằng khung nào cũng được.

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

/** Chiều cao ô trống của khối `index` chưa dựng (danh sách `total` hàng): đã đo thì đúng số đo, chưa thì số hàng x `row` (một hàng). */
export function blockHeight(index: number, total: number, block: number, row: number, measured: ReadonlyMap<number, number>): number {
  return measured.get(index) ?? Math.min(block, total - index * block) * row;
}

/** Chiều cao trung bình một hàng của các khối đã đo; chưa đo khối nào thì null. */
export function rowHeightOf(measured: ReadonlyMap<number, number>, total: number, block: number): number | null {
  let height = 0;
  let rows = 0;
  for (const [index, value] of measured) {
    height += value;
    rows += Math.max(0, Math.min(block, total - index * block));
  }
  return rows > 0 ? height / rows : null;
}

/** Một số đo của ResizeObserver: khối `index`, bề rộng, chiều cao, và khối ấy đang dựng thật (không phải ô trống). */
export type BlockSize = { index: number; width: number; height: number; filled: boolean };

/** Số đo các khối của một danh sách. Khối chưa vẽ lần nào lấy chiều cao một hàng đo ĐƯỢC ở lần đo đầu (khối đầu đã vẽ), không theo
 *  số ước cứng: thư viện ước 90 px/cuốn mà thật ~50, cuộn lên qua khối chưa đo thì khung nhìn nhảy 2.400 px (soát a30 L5, L4, L2, L7).
 *  Bề rộng đổi (cửa sổ, xoay máy) thì số đo cũ sai hết - hàng xuống dòng khác, lưới đổi số cột: xoá rồi đo lại (L6). */
export class BlockSizes {
  measured = new Map<number, number>();
  /** Chiều cao một hàng từ lần đo đầu; null = chưa đo, ô trống dùng số ước. */
  row: number | null = null;
  width: number | null = null;

  constructor(
    public total: number,
    readonly block: number,
  ) {}

  /** Ghi một loạt số đo. Trả true khi ô trống phải vẽ lại (vừa có chiều cao một hàng, hay bề rộng đổi). */
  record(sizes: readonly BlockSize[]): boolean {
    let changed = false;
    for (const size of sizes) {
      // Khung bị ẩn (bề rộng 0): số đo vô nghĩa.
      if (size.width <= 0) continue;
      if (this.width !== null && Math.abs(size.width - this.width) > 0.5) {
        this.measured.clear();
        this.row = null;
        changed = true;
      }
      this.width = size.width;
      if (size.filled) this.measured.set(size.index, size.height);
    }
    if (this.row === null) {
      this.row = rowHeightOf(this.measured, this.total, this.block);
      if (this.row !== null) changed = true;
    }
    return changed;
  }

  /** Số hàng đổi (thư viện thêm sách): khối từ chỗ đổi trở đi có số hàng khác - bỏ số đo của chúng, giữ chiều cao một hàng. */
  resize(total: number): void {
    const from = Math.floor(Math.min(total, this.total) / this.block);
    for (const index of [...this.measured.keys()]) if (index >= from) this.measured.delete(index);
    this.total = total;
  }

  height(index: number, estimate: number): number {
    return blockHeight(index, this.total, this.block, this.row ?? estimate, this.measured);
  }

  toJSON() {
    return { total: this.total, block: this.block, width: this.width, row: this.row, measured: [...this.measured] };
  }

  /** Số đo đã lưu trong phiên (quay lại trang): đúng danh sách ấy thì dựng lại y như lúc rời, chỗ cuộn nhớ được mới khớp. */
  static from(saved: unknown, total: number, block: number): BlockSizes {
    const sizes = new BlockSizes(total, block);
    const value = saved as Partial<ReturnType<BlockSizes["toJSON"]>> | null;
    if (!value || value.total !== total || value.block !== block || !Array.isArray(value.measured)) return sizes;
    sizes.width = typeof value.width === "number" ? value.width : null;
    sizes.row = typeof value.row === "number" ? value.row : null;
    for (const entry of value.measured) {
      if (Array.isArray(entry) && typeof entry[0] === "number" && typeof entry[1] === "number") sizes.measured.set(entry[0], entry[1]);
    }
    return sizes;
  }
}

/** Khối nằm ở mép trên khung nhìn (`viewTop`) và mép trên của nó so với mép khung. Các khối xếp dọc theo thứ tự - tìm nhị phân. */
export function anchorAt(count: number, boxOf: (index: number) => { top: number; bottom: number }, viewTop: number): { index: number; top: number } | null {
  let low = 0;
  let high = count - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (boxOf(middle).bottom > viewTop) {
      found = middle;
      high = middle - 1;
    } else low = middle + 1;
  }
  return found < 0 ? null : { index: found, top: boxOf(found).top - viewTop };
}

/** Phần cộng vào scrollTop để khối neo đứng yên trên màn hình sau khi các khối PHÍA TRÊN nó đổi chiều cao (ô trống thành hàng thật, đo
 *  lại). `top` là mép trên khối so với mép khung, trước và sau; người dùng cuộn giữa chừng thì scrollTop đổi theo, không tính là lệch. */
export function anchorShift(before: { top: number; scrollTop: number }, after: { top: number; scrollTop: number }): number {
  const shift = after.top + after.scrollTop - (before.top + before.scrollTop);
  return Math.abs(shift) < 0.5 ? 0 : shift;
}

/** Khối có dựng không: gần màn hình, chứa hàng phải giữ (chương đang nghe), hay đang giữ tiêu điểm bàn phím - kể cả hai khối kề nó,
 *  để Tab / Shift+Tab từ hàng đầu/cuối khối đi tiếp sang hàng kế thay vì nhảy tới khối dựng sẵn ở xa (soát a30 L1). */
export function blockVisible(index: number, shown: ReadonlySet<number>, kept: number, focused: number | null): boolean {
  return shown.has(index) || index === kept || (focused !== null && Math.abs(index - focused) <= 1);
}

function viewTopOf(scroller: HTMLElement): number {
  return isPage(scroller) ? 0 : scroller.getBoundingClientRect().top;
}

export function Windowed<T>({
  items,
  row,
  estimate,
  keep,
  block = WINDOW_BLOCK,
  className,
  memory,
}: {
  items: readonly T[];
  /** Một hàng; `index` là vị trí trong cả danh sách (cho aria-rowindex / aria-posinset). */
  row: (item: T, index: number) => ReactNode;
  /** Chiều cao ước của một hàng (px) - chỉ dùng tới khi đo được khối đầu. */
  estimate: number;
  /** Vị trí luôn dựng (vd chương đang nghe). */
  keep?: number;
  block?: number;
  /** Lớp của mỗi khối (vd lưới: mỗi khối tự là một lưới cùng cột). */
  className?: string;
  /** Khoá nhớ số đo trong phiên (vd theo sách): quay lại trang thì danh sách cao y như lúc rời - chỗ cuộn nhớ được (useScrollMemory) mới đúng. */
  memory?: string;
}) {
  const total = items.length;
  const count = Math.ceil(total / block);
  const windowed = total > block * 2 && typeof IntersectionObserver !== "undefined";
  const memoryKey = memory ? `abook.blocks.${memory}` : null;
  const sizes = useRef<BlockSizes | null>(null);
  if (sizes.current === null || sizes.current.block !== block) sizes.current = BlockSizes.from(memoryKey ? sessionRead(memoryKey) : null, total, block);
  else if (sizes.current.total !== total) sizes.current.resize(total);
  const [shown, setShown] = useState<ReadonlySet<number>>(() => firstBlocks(total, block, keep));
  const shownNow = useRef(shown);
  shownNow.current = shown;
  const [focused, setFocused] = useState<number | null>(null);
  const focusedNow = useRef(focused);
  focusedNow.current = focused;
  const [, setVersion] = useState(0);
  const nodes = useRef<(HTMLDivElement | null)[]>([]);
  const view = useRef<{ scroller: HTMLElement; count: number } | null>(null);
  /** Khối neo trước một thay đổi chiều cao do chính danh sách gây ra (khối dựng/bỏ, đo lại); effect dưới bù cuộn theo nó. */
  const pending = useRef<{ index: number; top: number; scrollTop: number } | null>(null);
  const hold = () => {
    const at = view.current;
    if (!at || pending.current) return;
    const found = anchorAt(at.count, (index) => nodes.current[index]?.getBoundingClientRect() ?? { top: Infinity, bottom: Infinity }, viewTopOf(at.scroller));
    pending.current = found && { ...found, scrollTop: at.scroller.scrollTop };
  };
  // Chương đang nghe đổi sang khối khác: dựng sẵn khối ấy (giữ chỗ neo trước khi nó đổi cỡ).
  const kept = keep !== undefined && keep >= 0 ? Math.floor(keep / block) : -1;
  const keptBefore = useRef(kept);
  if (keptBefore.current !== kept) {
    keptBefore.current = kept;
    hold();
  }
  useEffect(() => {
    if (kept >= 0) setShown((previous) => (previous.has(kept) ? previous : new Set([...previous, kept])));
  }, [kept]);

  useLayoutEffect(() => {
    if (!windowed) return;
    const first = nodes.current[0];
    if (!first) return;
    const scroller = scrollParent(first);
    view.current = { scroller, count };
    // Tự giữ chỗ (hold + effect bù dưới), không nhờ scroll anchoring của trình duyệt: Safari (WKWebView của bản máy Mac) không có,
    // và khi có thì hai bên cùng bù thành bù hai lần.
    const anchoring = scroller.style.overflowAnchor;
    scroller.style.overflowAnchor = "none";
    const intersections = new IntersectionObserver(
      (entries) => {
        const previous = shownNow.current;
        let next: Set<number> | null = null;
        for (const entry of entries) {
          const index = Number((entry.target as HTMLElement).dataset.block);
          if (entry.isIntersecting === previous.has(index)) continue;
          next ??= new Set(previous);
          if (entry.isIntersecting) next.add(index);
          else next.delete(index);
        }
        if (!next) return;
        hold();
        shownNow.current = next;
        setShown(next);
      },
      // Gốc là chính khung cuộn: gốc mặc định (cửa sổ) bị `<main>` cắt nên lề 1500 px vô tác dụng - khối chỉ dựng khi đã lộ vào
      // khung, ngay mép màn hình, và đổi cỡ trước mắt người xem.
      { root: isPage(scroller) ? null : scroller, rootMargin: MARGIN },
    );
    const resizes =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver((entries) => {
            const current = sizes.current!;
            const changed = current.record(
              entries.map((entry) => {
                const target = entry.target as HTMLElement;
                return {
                  index: Number(target.dataset.block),
                  width: entry.contentRect.width,
                  height: entry.borderBoxSize?.[0]?.blockSize ?? target.getBoundingClientRect().height,
                  filled: target.dataset.filled !== undefined,
                };
              }),
            );
            if (memoryKey) sessionWrite(memoryKey, current);
            if (changed) {
              hold();
              setVersion((version) => version + 1);
            }
          });
    for (const node of nodes.current.slice(0, count)) {
      if (!node) continue;
      intersections.observe(node);
      resizes?.observe(node);
    }
    return () => {
      intersections.disconnect();
      resizes?.disconnect();
      scroller.style.overflowAnchor = anchoring;
      view.current = null;
      pending.current = null;
    };
  }, [windowed, count, memoryKey]);

  // Sau mỗi lần dựng: khối phía trên khung nhìn đổi chiều cao thì bù scrollTop đúng phần chênh - nội dung đang thấy đứng yên.
  useLayoutEffect(() => {
    const before = pending.current;
    const at = view.current;
    pending.current = null;
    const node = before && nodes.current[before.index];
    if (!before || !at || !node) return;
    const shift = anchorShift(before, { top: node.getBoundingClientRect().top - viewTopOf(at.scroller), scrollTop: at.scroller.scrollTop });
    if (shift) at.scroller.scrollTop += shift;
  });

  if (!windowed) return <>{items.map(row)}</>;
  return (
    <>
      {Array.from({ length: count }, (_, index) => {
        const start = index * block;
        const visible = blockVisible(index, shown, kept, focused);
        return (
          <div
            key={index}
            role="none"
            data-block={index}
            data-filled={visible ? "" : undefined}
            ref={(node) => {
              nodes.current[index] = node;
            }}
            className={className}
            style={visible ? undefined : { height: sizes.current!.height(index, estimate) }}
            // Tiêu điểm bàn phím ở trong khối: giữ khối dù đã cuộn xa (gỡ đi thì tiêu điểm rơi về BODY, Tab kế nhảy lung tung - soát a30 L1).
            onFocus={() => {
              if (focusedNow.current === index) return;
              hold();
              focusedNow.current = index;
              setFocused(index);
            }}
            onBlur={(event) => {
              const node = event.currentTarget;
              // Chờ tiêu điểm tới chỗ mới; cửa sổ mất tiêu điểm thì phần tử vẫn là activeElement - vẫn giữ.
              setTimeout(() => {
                if (focusedNow.current !== index || node.contains(document.activeElement)) return;
                hold();
                focusedNow.current = null;
                setFocused(null);
              });
            }}
          >
            {visible && items.slice(start, start + block).map((item, offset) => row(item, start + offset))}
          </div>
        );
      })}
    </>
  );
}
