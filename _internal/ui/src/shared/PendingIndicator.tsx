import { Loader2 } from "lucide-react";
import { useAfter } from "./useAfter";
import { StateIcon } from "./StateIcon";

export const PENDING_DELAY_MS = 180;
/** The caller locks immediately; only the visual spinner waits to avoid flashing. */
export function PendingIndicator({ pending, children }: { pending: boolean; children?: React.ReactNode }) {
  const visible = useAfter(pending, PENDING_DELAY_MS);
  return <StateIcon state={visible}>{visible ? <Loader2 aria-hidden className="size-5 animate-spin motion-reduce:animate-none" /> : children}</StateIcon>;
}
