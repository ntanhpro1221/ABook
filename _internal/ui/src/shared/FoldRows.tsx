import type { ReactNode } from "react";
import { AnimatedRows } from "./MotionPresence";
import { Windowed } from "./Windowed";

/** A disclosure's children share the page's scroll container. Small blocks bound first-open work. */
export function FoldRows<T>({ items, keyOf, children, className, estimate = 140 }: {
  items: readonly T[];
  keyOf: (item: T) => string;
  children: (item: T, index: number) => ReactNode;
  className?: string;
  estimate?: number;
}) {
  return <Windowed items={items} block={6} margin="300px 0px" alwaysBlocks estimate={estimate}
    row={(item, index) => <div key={keyOf(item)}>{children(item, index)}</div>}
    renderBlock={(block, start) => <AnimatedRows items={block} keyOf={keyOf} className={className}>{(item, index) => children(item, start + index)}</AnimatedRows>} />;
}
