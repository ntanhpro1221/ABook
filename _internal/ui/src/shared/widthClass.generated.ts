// SINH TỰ ĐỘNG bởi scripts/gen_native_tokens.py từ docs/DESIGN.md §5.5 (Khổ cửa sổ). KHÔNG sửa tay: sửa DESIGN.md rồi chạy lại script
// (tests/test_native_tokens.py bắt lệch). Cùng một nguồn với WidthClass của Tokens.kt (điện thoại) và Theme.widthClass (Qt).

export const WIDTH_CLASSES = ["compact", "medium", "expanded", "large", "extraLarge"] as const;
export type WidthClass = (typeof WIDTH_CLASSES)[number];

/** Bề ngang nội dung (px) mà mỗi khổ bắt đầu. */
export const WIDTH_FROM: Record<WidthClass, number> = {
  compact: 0,
  medium: 600,
  expanded: 840,
  large: 1200,
  extraLarge: 1600,
};

/** Khổ của một bề ngang nội dung (px): khổ lớn nhất có mốc không vượt quá nó. */
export function widthClass(px: number): WidthClass {
  let found: WidthClass = WIDTH_CLASSES[0];
  for (const name of WIDTH_CLASSES) if (px >= WIDTH_FROM[name]) found = name;
  return found;
}

/** `px` đạt ít nhất khổ `name`. */
export function widthAtLeast(px: number, name: WidthClass): boolean {
  return px >= WIDTH_FROM[name];
}
