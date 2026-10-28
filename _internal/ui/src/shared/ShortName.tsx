import { cn } from "./cn";
/** Tên máy luôn đầy đủ; tên liền dài cũng xuống dòng trong cột hiện tại. */
export function ShortName({ name, className }: { name: string; className?: string }) {
  return (
    <span className={cn("min-w-0 [overflow-wrap:anywhere] whitespace-normal", className)}>
      {name}
    </span>
  );
}
