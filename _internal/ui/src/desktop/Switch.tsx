import * as SwitchPrimitive from "@radix-ui/react-switch";
import { feedback } from "@/shared/feedback";

// Công tắc của app máy tính. Mô-đun riêng (từng nằm trong PhoneSync.tsx): trình phát, trang sách, Studio dùng nó mà không kéo cả mục
// Thiết bị của Cài đặt vào gói đầu (docs/PERF_WEB.md).

export function Switch({
  id,
  checked,
  onCheckedChange,
  disabled,
  ariaDisabled,
  label,
  labelledBy,
  describedBy,
}: {
  id?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  ariaDisabled?: boolean;
  /** Tên cho trình đọc màn hình khi không có <label htmlFor> trỏ tới công tắc (soát UX 29-09: "Lịch đêm" chỉ đọc "switch"). */
  label?: string;
  /** <label> bọc cả tên lẫn đoạn mô tả dài: tên là phần tử mang mã này, đoạn mô tả đọc riêng (`describedBy`) - không thì tên đọc lên dài
   *  300+ chữ (soát a31). */
  labelledBy?: string;
  describedBy?: string;
}) {
  return (
    <SwitchPrimitive.Root
      id={id}
      aria-label={label}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      checked={checked}
      onCheckedChange={(value) => {
        if (ariaDisabled) return;
        feedback("toggle");
        onCheckedChange(value);
      }}
      disabled={disabled}
      aria-disabled={ariaDisabled || undefined}
      className="ui-switch touch-hit focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:opacity-50 aria-disabled:opacity-50"
    >
      <SwitchPrimitive.Thumb className="motion-switch-thumb" />
    </SwitchPrimitive.Root>
  );
}
