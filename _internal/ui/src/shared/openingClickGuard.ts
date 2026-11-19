import { useRef, type MouseEvent, type PointerEvent } from "react";

/** Một lớp nổi (menu, Sheet) mở ngay lúc ngón tay NHẤN (Radix DropdownMenu mở ở pointerdown) nằm dưới ngón tay trước khi nhấc.
 *  Click của chính cú chạm ấy được trình duyệt gửi cho thứ nằm dưới ngón lúc nhấc - một mục / nút của lớp vừa mở - và chọn nó
 *  (gateflake 19-11: máy bận, chạm "Thêm tuỳ chọn" mở Sheet rồi chọn luôn "Hồ sơ mới"). Click do con trỏ sinh ra (detail > 0) mà không có
 *  lần nhấn nào BẮT ĐẦU trong lớp là cú chạm mở, không phải lựa chọn; click bàn phím / lập trình (detail 0) vẫn qua. */
export function useOpeningClickGuard<T extends Element>(handlers: {
  onPointerDownCapture?: (event: PointerEvent<T>) => void;
  onPointerCancelCapture?: (event: PointerEvent<T>) => void;
  onClickCapture?: (event: MouseEvent<T>) => void;
} = {}) {
  const armed = useRef(false);
  return {
    onPointerDownCapture: (event: PointerEvent<T>) => { armed.current = true; handlers.onPointerDownCapture?.(event); },
    onPointerCancelCapture: (event: PointerEvent<T>) => { armed.current = false; handlers.onPointerCancelCapture?.(event); },
    onClickCapture: (event: MouseEvent<T>) => {
      const opening = event.detail > 0 && !armed.current;
      armed.current = false;
      if (opening) { event.preventDefault(); event.stopPropagation(); return; }
      handlers.onClickCapture?.(event);
    },
  };
}
