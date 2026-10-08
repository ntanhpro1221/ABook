// Nút Back của Android khi menu / hộp thoại / tấm trượt đang mở: đóng lớp trên cùng trước, không rời trang (soát UX a9).
// Radix đã giữ sẵn ngăn xếp lớp (DismissableLayer: chỉ lớp trên cùng nhận phím Esc), nên không đăng ký lại từng chỗ dùng - hàng chục
// Dialog/Sheet/DropdownMenu/Popover khai bằng Root không điều khiển, thêm một chỗ nữa là quên một chỗ. Back chỉ cần biết "có lớp nào
// đang mở không" và nếu có thì gửi Esc, đúng đường bàn phím máy tính đang đi.

/** Vai trò ARIA của nội dung các lớp Radix chặn thao tác phía dưới; tooltip cố ý không có trong đây. */
const LAYER_ROLES = new Set(["dialog", "alertdialog", "menu", "listbox"]);

type LayerElement = { getAttribute(name: string): string | null };
type LayerDocument = {
  querySelectorAll(selector: string): ArrayLike<LayerElement>;
  dispatchEvent(event: Event): boolean;
};

/** Phần tử có phải nội dung một lớp đang mở (không phải lớp đang đóng dở trong hiệu ứng). */
export function isOpenLayer(element: LayerElement): boolean {
  return element.getAttribute("data-state") === "open" && LAYER_ROLES.has(element.getAttribute("role") ?? "");
}

export function hasOpenLayer(doc: LayerDocument = document): boolean {
  return Array.from(doc.querySelectorAll('[data-state="open"]')).some(isOpenLayer);
}

/** Đóng lớp trên cùng nếu có; trả về true khi đã có lớp để đóng (Back không làm gì thêm). */
export function dismissTopLayer(doc: LayerDocument = document): boolean {
  if (!hasOpenLayer(doc)) return false;
  doc.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
  return true;
}
