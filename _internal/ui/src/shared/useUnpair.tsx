import { useState, type ReactNode } from "react";
import { toast } from "sonner";
import { UnpairDialog } from "./UnpairDialog";
import { unpairCopy, type UnpairChoice, type UnsentEdits } from "./unpair";

interface Asking<T> {
  target: T;
  unsent: UnsentEdits;
}

/** Gỡ ghép một máy mà không lặng lẽ mất sửa chưa gửi: `start(máy)` hỏi `unsent`; không còn sửa thì gỡ luôn (`run(máy, null)`), còn thì
 *  hiện `dialog` với các lựa chọn. `run(máy, "send" | "discard")` gửi trước / bỏ rồi gỡ và ném lỗi (nói lý do) nếu không làm được -
 *  lỗi hiện trong hộp, máy vẫn ghép. Dùng chung điện thoại và máy tính. */
export function useUnpair<T>(options: {
  self: "điện thoại" | "máy tính";
  name: (target: T) => string;
  reachable: (target: T) => boolean;
  unsent: (target: T) => Promise<UnsentEdits>;
  run: (target: T, choice: UnpairChoice | null) => Promise<void>;
}): { start: (target: T) => Promise<void>; dialog: ReactNode } {
  const [asking, setAsking] = useState<Asking<T> | null>(null);
  const [busy, setBusy] = useState<UnpairChoice | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = async (target: T) => {
    try {
      const unsent = await options.unsent(target);
      if (unpairCopy(options.name(target), options.self, unsent, true) === null) {
        await options.run(target, null);
        return;
      }
      setError(null);
      setAsking({ target, unsent });
    } catch (problem) {
      toast.error("Chưa gỡ ghép được", { description: (problem as Error).message });
    }
  };

  const choose = async (choice: UnpairChoice) => {
    if (!asking) return;
    setBusy(choice);
    setError(null);
    try {
      await options.run(asking.target, choice);
      setAsking(null);
    } catch (problem) {
      setError((problem as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const copy = asking ? unpairCopy(options.name(asking.target), options.self, asking.unsent, options.reachable(asking.target)) : null;
  return {
    start,
    dialog: <UnpairDialog copy={copy} busy={busy} error={error} onChoose={(choice) => void choose(choice)} onCancel={() => setAsking(null)} />,
  };
}
