import { Reveal } from "./MotionPresence";
import { useRef, useState, type ReactNode } from "react";
import { Button, Dialog, DialogActions } from "./ui";
import { S } from "./strings.generated";

export type DestructiveAction = { title: string; description: ReactNode; label?: string; failureMessage?: string; run: () => void | Promise<unknown> };
/** One confirmation contract: cancel has initial focus, destructive action is last. */
export function useDestructiveConfirm() {
  const [action, setAction] = useState<DestructiveAction | null>(null);
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const [error, setError] = useState("");
  const close = () => { if (!locked.current) { setAction(null); setError(""); } };
  const confirm = (next: DestructiveAction) => { if (!locked.current) { setError(""); setAction(next); } };
  const accept = async () => {
    if (!action || locked.current) return;
    locked.current = true;
    setBusy(true); setError("");
    try { await action.run(); setAction(null); }
    catch { setError(action.failureMessage ?? S.s_action_failed_retry); }
    finally { locked.current = false; setBusy(false); }
  };
  const dialog = <Dialog open={action !== null} onOpenChange={(open) => { if (!open) close(); }} title={action?.title} description={action?.description}
    footer={<DialogActions><Button data-autofocus variant="ghost" disabled={busy} onClick={close}>{S.s_huy_96732485}</Button>
      <Button variant="danger" loading={busy} onClick={() => accept()}>{error ? S.s_thu_lai_c58d068c : action?.label ?? S.s_xoa_777195ab}</Button></DialogActions>}>
    <Reveal when={Boolean(error)}><p role="alert" className="text-sm text-danger">{error}</p></Reveal>
  </Dialog>;
  return { confirm, dialog };
}
