import type { ReactNode } from "react";
import { cn } from "./cn";

/** Cùng cấp mục dù đứng riêng hay gập mở: giữ nhịp 56 px, chữ thường 18/500 (DESIGN 5.5). */
export function SectionHeading({ as: Heading = "h2", children, className, id }: {
  as?: "h2" | "h3" | "h4"; children: ReactNode; className?: string; id?: string;
}) {
  return <Heading id={id} data-section-heading data-section-title className={cn("section-title flex min-h-[3.5rem] items-center", className)}>{children}</Heading>;
}
