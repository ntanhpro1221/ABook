// Ngăn xếp "lớp đóng được bằng Back" ngoài Radix: màn con dựng bằng state (panel trong màn Đang nghe, bước con trong hộp, khung ghép
// thiết bị…) tự đăng ký khi mở và tự gỡ khi đóng / rời trang. Nút Back của Android (android/backLayers.ts) đóng lớp trên cùng trước khi
// lùi trang - trước đây những lớp này không ai biết tới, Back đi thẳng ra trang trước hay thu nhỏ app (chủ app 23-10).
// Hộp / menu / tấm trượt Radix KHÔNG cần đăng ký: chúng tự mang role + data-state, backLayers đọc thẳng từ trang.
import { useEffect, useRef, type RefObject } from "react";
import { nextBackOrder } from "./backOrder";

export interface BackLayer {
  id: number;
  close: () => void;
  /** Phần tử của lớp: lớp nằm TRONG một hộp Radix đang mở (bước con của hộp) thì đứng trên hộp ấy. */
  element: () => Element | null;
}

const stack: BackLayer[] = [];

/** Đẩy một lớp lên ngăn xếp; trả về hàm gỡ (gọi nhiều lần cũng được). */
export function pushBackLayer(close: () => void, element: () => Element | null = () => null): () => void {
  const layer: BackLayer = { id: nextBackOrder(), close, element };
  stack.push(layer);
  return () => {
    const index = stack.indexOf(layer);
    if (index >= 0) stack.splice(index, 1);
  };
}

/** Lớp mở sau cùng, chưa đóng. */
export function topBackLayer(): BackLayer | undefined {
  return stack.findLast((layer) => {
    const element = layer.element();
    return !element?.closest?.('[inert], [hidden], [data-state="closed"]');
  });
}

export function backLayerCount(): number {
  return stack.length;
}

/** Lớp nào đang mở thì nằm trong ngăn xếp Back: `open` bật là đăng ký, tắt / gỡ component là gỡ. `close` lấy bản mới nhất lúc bấm Back.
 *  `ref`: phần tử của lớp, cần khi lớp nằm trong một hộp Radix (để Back đóng bước con trước, hộp sau). */
export function useBackLayer(open: boolean, close: () => void, ref?: RefObject<Element | null>, returnFocus?: RefObject<HTMLElement | null>): void {
  const latest = useRef(close);
  const wasOpen = useRef(open);
  latest.current = close;
  useEffect(() => {
    const previous = wasOpen.current;
    wasOpen.current = open;
    if (!open) {
      if (previous && !returnFocus?.current?.closest?.('[inert], [hidden]')) returnFocus?.current?.focus({ preventScroll: true });
      return;
    }
    return pushBackLayer(
      () => latest.current(),
      () => ref?.current ?? null,
    );
  }, [open, ref, returnFocus]);
}
