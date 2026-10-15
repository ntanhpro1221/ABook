import { Monitor } from "lucide-react";
import { cn } from "@/shared/cn";
import { listenOnlyOwner, onComputerLine } from "@/shared/peerStudio";
import { useAppInfo } from "@/studio/data";

/** Tên máy tính đang phục vụ trang Studio từ xa (hay "máy tính" khi chưa biết) - cùng cách Cài đặt > Điều khiển từ xa gọi nó. */
export function useComputerName(): string {
  const { data: info } = useAppInfo();
  return info ? listenOnlyOwner(info) : "máy tính";
}

/** Thay cho một việc mà Studio từ xa không làm được và chỉ làm được ngay trên máy tính: nói thẳng "Làm ở máy tính <tên máy>" thay vì ẩn nút
 *  im lặng (người dùng đang tìm nó) hay để nút bấm ra lỗi 403. `verb`: "Làm", "Đổi", "Tải giọng"... Dùng chỗ nào thì chỗ đó đã kiểm
 *  `info.remote`. */
export function OnComputerOnly({ verb = "Làm", className }: { verb?: string; className?: string }) {
  const name = useComputerName();
  return (
    <span className={cn("inline-flex max-w-full items-center gap-1.5 rounded-full bg-sunken px-2.5 py-1 text-xs text-fg-2", className)}>
      <Monitor className="size-3.5 shrink-0" aria-hidden />
      <span className="min-w-0 text-pretty">{onComputerLine(verb, name)}</span>
    </span>
  );
}
