// Mặt đọc theo (DESIGN.md 5.1): nền riêng của vùng chữ đọc theo, chọn ở Cài đặt > Giao diện > "Nền đọc", cả hai nền tảng.
// Đặt data-surface lên <html>; styles.css (.reading-surface) đổi nền / mực của vùng ấy. "auto" = Giấy ở giao diện sáng, Đêm ở giao diện tối.

export type ReadingSurface = "auto" | "paper" | "ivory" | "night";

export const READING_SURFACES: { value: ReadingSurface; label: string }[] = [
  { value: "auto", label: "Tự động" },
  { value: "paper", label: "Giấy" },
  { value: "ivory", label: "Ngà" },
  { value: "night", label: "Đêm" },
];

export function readingSurfaceOr(value: unknown, fallback: ReadingSurface = "auto"): ReadingSurface {
  return READING_SURFACES.some((surface) => surface.value === value) ? (value as ReadingSurface) : fallback;
}

export function applyReadingSurface(surface: ReadingSurface): void {
  const root = document.documentElement;
  if (surface === "auto") delete root.dataset.surface;
  else root.dataset.surface = surface;
}
