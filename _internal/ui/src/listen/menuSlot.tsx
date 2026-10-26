import { Cast } from "lucide-react";
import { submenuOffsets } from "@/shared/menuPosition";
import { createContext, useContext, useMemo, type ButtonHTMLAttributes, type ReactNode, type Ref } from "react";

/** Nút điều khiển không giữ focus sau cú bấm chuột: Space sau đó vẫn là phát/tạm dừng, không lặp lại nút vừa bấm. */
export const keepFocus = { onMouseDown: (event: { preventDefault: () => void }) => event.preventDefault() };

export const MENU_ROW = "flex min-h-10 w-full items-center gap-3 rounded-control px-2 text-left text-sm text-fg hover:bg-hover disabled:opacity-40 disabled:hover:bg-transparent max-sm:min-h-[48px]";

/** Chỗ mở của hộp con bật từ MỘT DÒNG của menu "…" trên máy tính: sát cạnh trái menu cha, mép đáy (menu cha mở lên) hay mép đỉnh (menu cha mở xuống)
 *  thẳng mép menu cha - trước đây hộp con mở lên trên nút, chồng lên menu cha với mép trái lệch 1175 / 1153 / 1126 / 1181 (soát 25-10 C8). Nút mở là CẢ DÒNG
 *  nên số đo đúng cả khi hộp bị lật sang phải. Không có menu cha (nút đứng ngoài "…") thì null: hộp con mở như cũ. */
export type BesideParent = { side: "left"; align: "start" | "end"; sideOffset: number; alignOffset: number };
export function besideParentMenu(trigger: Element | null): BesideParent | null {
  const parent = trigger?.closest<HTMLElement>('[role="dialog"][data-side]');
  if (!trigger || !parent) return null;
  const up = parent.dataset.side === "top";
  const align = up ? "end" : "start";
  return { side: "left", align, ...submenuOffsets(trigger, "left", align)! };
}

/** Một dòng có tên cho nút riêng của nền / tính năng (gợi ý đọc, phát trên thiết bị khác): MenuSlot giữ chỗ và nói tên + biểu tượng của dòng, nút con
 *  tự vẽ CẢ DÒNG bằng <SlotFace> - đúng một biểu tượng ở đầu dòng, bên phải là chữ trạng thái (không biểu tượng thứ hai, soát 25-10 C8). Nút không có thì cả
 *  dòng không chiếm chỗ. Nút con tự lấy dữ liệu và có thể tới muộn lúc menu đang mở: dòng mở / khép bằng chiều cao + độ mờ (.menu-slot trong styles.css), không bật tắt. */
const MenuSlotContext = createContext<{ label: string; icon: typeof Cast } | null>(null);
/** Nút nằm trong MenuSlot thì trả tên + biểu tượng dòng (vẽ bằng SlotFace); đứng ngoài thì null (vẽ nút biểu tượng như thường). */
export function useMenuSlot() {
  return useContext(MenuSlotContext);
}
export function MenuSlot({ label, children, icon = Cast }: { label: string; children: ReactNode; icon?: typeof Cast }) {
  const slot = useMemo(() => ({ label, icon }), [label, icon]);
  return (
    <div className="menu-slot">
      <div>
        <MenuSlotContext.Provider value={slot}>{children}</MenuSlotContext.Provider>
      </div>
    </div>
  );
}
/** Mặt của một dòng MenuSlot: biểu tượng · tên · `value` (chữ trạng thái, bên phải). Là nút trọn dòng - Radix Trigger dùng được qua asChild. */
export function SlotFace({ value, ref, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { ref?: Ref<HTMLButtonElement>; value?: ReactNode }) {
  const slot = useContext(MenuSlotContext);
  if (!slot) return null;
  const Icon = slot.icon;
  return (
    <button ref={ref} type="button" data-player-menu-row className={MENU_ROW} {...keepFocus} {...rest}>
      <Icon className="size-4 shrink-0 text-fg-2" />
      <span className="min-w-0 flex-1 truncate">{slot.label}</span>
      {value && <span className="tabular min-w-0 max-w-[45%] truncate text-xs font-medium text-fg-2">{value}</span>}
    </button>
  );
}
