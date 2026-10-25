/** Mọi menu con cách mép ngoài menu cha 8 px, đỉnh/đáy trùng nhau; bù lề của dòng neo thay vì lấy dòng làm mép bảng. */
export function submenuOffsets(trigger: Element | null, side: "left" | "right", align: "start" | "end") {
  const parent = trigger?.closest<HTMLElement>('[role="dialog"][data-side],[role="menu"][data-side]');
  if (!trigger || !parent) return null;
  const row = trigger.getBoundingClientRect(), box = parent.getBoundingClientRect();
  // Bấm nhanh khi bảng cha còn đang phóng nhẹ: rect đã mang scale, offset của popper thì tính theo CSS chưa biến đổi.
  const transform = getComputedStyle(parent).transform;
  const matrix = transform && transform !== "none" ? new DOMMatrixReadOnly(transform) : null;
  const sx = matrix?.a || 1, sy = matrix?.d || 1;
  return {
    sideOffset: (side === "left" ? row.left - box.left : box.right - row.right) / sx + 8,
    // floating-ui đảo dấu ở căn end: dương đẩy lên.
    alignOffset: (align === "end" ? row.bottom - box.bottom : box.top - row.top) / sy,
  };
}
