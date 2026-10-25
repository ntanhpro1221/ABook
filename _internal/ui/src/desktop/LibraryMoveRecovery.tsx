import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "@/shared/toast";
import { api } from "@/studio/api";
import { pickFolder } from "@/studio/data";
import { Button } from "@/shared/ui";

export interface LibraryMoveRecoveryState { message: string; currentRoot: string }

/** Kept visible until the server has committed the user's explicit recovery choice. */
export function LibraryMoveRecovery({ recovery }: { recovery: LibraryMoveRecoveryState }) {
  const client = useQueryClient();
  const [oldRoot, setOldRoot] = useState(recovery.currentRoot);
  const [newRoot, setNewRoot] = useState(recovery.currentRoot);
  const [busy, setBusy] = useState(false);
  const choose = async (which: "old" | "new") => {
    try {
      const path = await pickFolder(which === "old" ? "Chọn thư viện trước khi chuyển" : "Chọn thư viện sau khi chuyển", which === "old" ? oldRoot : newRoot);
      if (path) (which === "old" ? setOldRoot : setNewRoot)(path);
    } catch (error) { toast.error((error as Error).message); }
  };
  const resolve = async (action: "finish" | "rollback" | "ignore") => {
    setBusy(true);
    try {
      await api("/api/library-move/recovery", { method: "POST", body: { action, oldRoot, newRoot } });
      await client.invalidateQueries();
      toast.success("Đã xử lý lần chuyển thư viện");
    } catch (error) { toast.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <div role="alert" className="m-4 space-y-3 py-4 text-sm">
    <p>{recovery.message}</p>
    <p>Kiểm tra đường dẫn: hoàn tất dùng thư viện sau, quay lui dùng thư viện trước, bỏ qua giữ hiện tại; nhật ký được giữ.</p>
    <div className="flex flex-wrap items-center gap-2">
      <label className="min-w-0 flex-1">Trước khi chuyển<input aria-label="Thư viện trước khi chuyển" className="w-full rounded border border-line bg-sunken p-2" value={oldRoot} onChange={(e) => setOldRoot(e.target.value)} disabled={busy} /></label>
      <Button disabled={busy} onClick={() => void choose("old")}>Chọn thư mục trước</Button>
      <label className="min-w-0 flex-1">Sau khi chuyển<input aria-label="Thư viện sau khi chuyển" className="w-full rounded border border-line bg-sunken p-2" value={newRoot} onChange={(e) => setNewRoot(e.target.value)} disabled={busy} /></label>
      <Button disabled={busy} onClick={() => void choose("new")}>Chọn thư mục sau</Button>
    </div>
    <div className="flex flex-wrap gap-2">
      <Button disabled={busy} onClick={() => void resolve("finish")}>Hoàn tất chuyển</Button>
      <Button disabled={busy} variant="ghost" onClick={() => void resolve("rollback")}>Quay lui</Button>
      <Button disabled={busy} variant="ghost" onClick={() => void resolve("ignore")}>Bỏ qua</Button>
    </div>
  </div>;
}
