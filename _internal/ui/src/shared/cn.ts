import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

const merge = extendTailwindMerge({
  extend: { classGroups: { "font-size": [{ text: ["body", "body-small", "caption", "section", "page"] }] } },
});

export function cn(...inputs: ClassValue[]): string {
  return merge(clsx(inputs));
}
