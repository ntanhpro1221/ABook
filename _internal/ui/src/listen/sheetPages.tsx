import { createContext, useCallback, useContext, useId, useLayoutEffect, useMemo, useRef, useState } from "react";

/** Trang con của tấm trượt (điện thoại): mở một dòng của tấm (Âm thanh, Giọng, ...) hay một trang trong đó (Âm sắc) thì tiêu đề trang
 *  THAY tiêu đề tấm thành "← Âm sắc", như tấm con của Android - không xếp chồng dưới tên tấm. `portal`: trang có thân riêng (dòng MenuShell),
 *  thân ấy thay cả danh sách của tấm; trang không portal (Âm sắc) tự thay nội dung tại chỗ trong trang cha, chỉ mượn đầu tấm. */
export type SheetPage = { title: string; back: () => void; depth: number; portal: boolean };
type Pages = { set: (id: string, page: SheetPage | null) => void; slot: HTMLElement | null; contentDepth: number };

export const SheetPages = createContext<Pages | null>(null);
/** Độ sâu của trang đang chứa phần tử: 0 = danh sách gốc của tấm. */
export const SheetPageDepth = createContext(0);

/** Đăng ký trang `title` với tấm đang chứa khi `open`. Trả về tấm (null khi không ở trong tấm: hộp nổi máy tính - chỗ gọi tự vẽ đầu trang). */
export function useSheetPage(open: boolean, title: string, back: () => void, portal = false): (Pages & { depth: number }) | null {
  const pages = useContext(SheetPages);
  const depth = useContext(SheetPageDepth) + 1;
  const id = useId();
  const latest = useRef(back);
  latest.current = back;
  const set = pages?.set;
  useLayoutEffect(() => {
    if (!set || !open) return;
    set(id, { title, back: () => latest.current(), depth, portal });
    return () => set(id, null);
  }, [set, open, title, depth, portal, id]);
  return pages ? { ...pages, depth } : null;
}

/** Ngăn xếp trang của một tấm: trang trên cùng (sâu nhất) cho đầu tấm; `contentDepth` = trang có thân riêng sâu nhất đang mở. */
export function useSheetPageStack() {
  const [pages, setPages] = useState<Record<string, SheetPage>>({});
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const set = useCallback((id: string, page: SheetPage | null) => setPages((previous) => {
    if (!page && !(id in previous)) return previous;
    const next = { ...previous };
    if (page) next[id] = page; else delete next[id];
    return next;
  }), []);
  const stack = Object.values(pages).sort((a, b) => a.depth - b.depth);
  const contentDepth = stack.reduce((deepest, page) => page.portal ? Math.max(deepest, page.depth) : deepest, 0);
  const api = useMemo(() => ({ set, slot, contentDepth }), [set, slot, contentDepth]);
  return { api, top: stack.at(-1) ?? null, setSlot };
}
