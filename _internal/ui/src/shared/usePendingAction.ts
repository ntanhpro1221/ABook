import { useEffect, useRef, useState } from "react";
import { S } from "./strings.generated";

/** A returned promise owns the button until settlement, including the first frame. */
export function usePendingAction<E>(action: ((event: E) => unknown) | undefined) {
  const [pending, setPending] = useState(false);
  const locked = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const invoke = (event: E) => {
    if (!action || locked.current) return;
    const execute = () => {
      if (locked.current) return;
      try {
        const result = action(event);
        if (result && typeof (result as PromiseLike<unknown>).then === "function") {
          locked.current = true; setPending(true);
          void Promise.resolve(result).catch(report).finally(() => {
            locked.current = false;
            if (mounted.current) setPending(false);
          });
        }
      } catch { report(); }
    };
    const report = () => { void import("./toast").then(({toast}) => toast.error(S.s_action_failed_retry,
      {action: {label: S.s_thu_lai_c58d068c, onClick: execute}})); };
    execute();
  };
  return { pending, invoke };
}

/** A react-query mutation as a shared Button action: `onClick={() => settled(save.mutateAsync(x))}`. The returned promise keeps the
 *  clicked button pending until the request settles (only that button, not every button of the same mutation); the mutation's own
 *  `onError` already reports a failure, so the rejection is absorbed here instead of raising a second toast. */
export function settled(promise: Promise<unknown>): Promise<void> {
  return promise.then(() => undefined, () => undefined);
}
