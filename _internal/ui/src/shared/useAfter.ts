import { useEffect, useState } from "react";

/** `true` chỉ khi `active` đã đứng yên đủ `ms` mili giây liên tục; `active` tắt là tắt ngay. Dùng cho lời nói trạng thái chờ ("Đang chuẩn bị giọng đọc…"):
 *  chờ ngắn (đệm một nhịp giữa câu) không được làm dòng chữ nháy ra rồi mất. */
export function useAfter(active: boolean, ms: number): boolean {
  const [late, setLate] = useState(false);
  useEffect(() => {
    if (!active) {
      setLate(false);
      return;
    }
    const timer = window.setTimeout(() => setLate(true), ms);
    return () => window.clearTimeout(timer);
  }, [active, ms]);
  return active && late;
}
