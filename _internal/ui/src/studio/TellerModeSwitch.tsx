import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mic2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Switch } from "@/desktop/PhoneSync";
import { cn } from "@/shared/cn";
import { Button, Dialog } from "@/shared/ui";
import { api, type BookSummary } from "./api";
import { pollDelay, retryUnlessGone } from "./polling";
import { costText, needsConfirm, TELLER_TITLE, tellerHint, type TellerModeView } from "./tellerMode";

/** Công tắc "Người kể xưng “tôi” tự kể chuyện" của một cuốn (webui/teller_mode.py), dưới hàng "Người kể chuyện" của tab Nhân vật.
 *  Mặc định tắt. Sách đã có bản thu thì bật / tắt hiện trước số câu phải thu lại và chờ bạn xác nhận; sách đang chạy thì chờ tạm dừng hẳn. */
export function TellerModeSwitch({ book, className }: { book: BookSummary; className?: string }) {
  const client = useQueryClient();
  const [asking, setAsking] = useState<"teller" | "narrator" | null>(null);
  const { data } = useQuery({
    queryKey: ["narrator-mode", book.id],
    queryFn: () => api<TellerModeView>(`/api/books/${book.id}/narrator-mode`),
    refetchInterval: (query) => pollDelay(book.running ? 15_000 : false, query.state),
    retry: retryUnlessGone,
  });
  const save = useMutation({
    mutationFn: (mode: "teller" | "narrator") => api<TellerModeView>(`/api/books/${book.id}/narrator-mode`, { method: "PUT", body: { mode } }),
    onSuccess: (view) => {
      client.setQueryData(["narrator-mode", book.id], view);
      for (const key of ["book", "work", "cast", "script"]) void client.invalidateQueries({ queryKey: [key, book.id] });
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: ["listen", "cast", book.id] });  // số câu của người kể và nhân vật trong tab Nhân vật
      setAsking(null);
      if (view.castLocked && view.mode === "teller" && view.applied) toast.success("Đã đổi", { description: "Bấm “Tiếp tục” để thu lại những câu đổi giọng." });
    },
    onError: (error: Error) => {
      setAsking(null);
      toast.error("Chưa đổi được", { description: error.message });
    },
  });
  if (!data?.available) return null;
  const on = data.mode === "teller";
  const busy = Boolean(data.castLocked && (book.running || book.starting));
  const id = `teller-mode-${book.id}`;
  const change = (value: boolean) => {
    const mode = value ? "teller" : "narrator";
    if (needsConfirm(data)) setAsking(mode);
    else save.mutate(mode);
  };
  return (
    <>
      <label htmlFor={id} className={cn("mt-3 flex items-start gap-3 rounded-xl border border-line bg-panel p-4 text-left", className)}>
        <Switch id={id} labelledBy={`${id}-name`} describedBy={`${id}-hint`} checked={on} disabled={save.isPending || busy} onCheckedChange={change} />
        <span>
          <span id={`${id}-name`} className="block text-sm font-medium text-fg">{TELLER_TITLE}</span>
          <span id={`${id}-hint`} className="mt-0.5 block text-[0.8125rem] leading-relaxed text-fg-2">
            {busy ? "Sách đang chạy - tạm dừng hẳn rồi hãy đổi." : tellerHint(on)}
            {!busy && data.castLocked && !needsConfirm(data) && !on && " Chưa câu nào bị ảnh hưởng đã được thu nên đổi không tốn gì."}
          </span>
        </span>
      </label>
      <Dialog
        open={asking !== null}
        onOpenChange={(open) => !open && setAsking(null)}
        title={asking === "teller" ? "Cho người kể “tôi” tự kể chuyện?" : "Trả câu kể về giọng dẫn?"}
        description={costText(data.plan, asking === "teller")}
      >
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setAsking(null)}>
            Thôi
          </Button>
          <Button variant="primary" icon={Mic2} loading={save.isPending} onClick={() => asking && save.mutate(asking)}>
            {asking === "teller" ? "Bật và thu lại" : "Tắt và thu lại"}
          </Button>
        </div>
      </Dialog>
    </>
  );
}
