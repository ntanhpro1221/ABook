import { widthAtLeast } from "./widthClass.generated";

/** Media query of the compact-height class (content window lower than 480 px). */
export const SHORT_WINDOW = "(max-height: 479px)";

export function shortWindow(height: number): boolean {
  return height < 480;
}

/** One rule for phone landscape, split windows and tablets, measured after the sidebar. */
export function twoPaneWindow(width: number, short: boolean): boolean {
  return widthAtLeast(width, "expanded") || (short && widthAtLeast(width, "medium"));
}
