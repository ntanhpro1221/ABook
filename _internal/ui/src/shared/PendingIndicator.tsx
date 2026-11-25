import { Loader2 } from "lucide-react";
import { useAfter } from "./useAfter";
import { StateIcon } from "./StateIcon";

export const PENDING_DELAY_MS = 180;
/** The caller locks immediately; only the visual spinner waits to avoid flashing.  sizes the spinner like the icon it
 *  replaces (a 12 px glyph in a text-sized button spins at 12 px, so the label does not move). */
export function PendingIndicator({ pending, children, className = "size-5" }: { pending: boolean; children?: React.ReactNode; className?: string }) {
  const visible = useAfter(pending, PENDING_DELAY_MS);
  return <StateIcon state={visible}>{visible ? <Loader2 aria-hidden className={className + " animate-spin motion-reduce:animate-none"} /> : children}</StateIcon>;
}
