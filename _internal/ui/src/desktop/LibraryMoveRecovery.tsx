import { S } from "../shared/strings.generated";
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
      const path = await pickFolder(which === "old" ? S.s_chon_thu_vien_truoc_khi_chuyen_7d85fde4 : S.s_chon_thu_vien_sau_khi_chuyen_ee4895cf, which === "old" ? oldRoot : newRoot);
      if (path) (which === "old" ? setOldRoot : setNewRoot)(path);
    } catch (error) { toast.error((error as Error).message); }
  };
  const resolve = async (action: "finish" | "rollback" | "ignore") => {
    setBusy(true);
    try {
      await api("/api/library-move/recovery", { method: "POST", body: { action, oldRoot, newRoot } });
      await client.invalidateQueries();
      toast.success(S.s_da_xu_ly_lan_chuyen_thu_vien_c143564b);
    } catch (error) { toast.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <div role="alert" className="m-4 space-y-3 py-4 text-sm">
    <p>{recovery.message}</p>
    <p>{S.s_kiem_tra_duong_dan_hoan_tat_dung_thu_vien_12eb02fe}</p>
    <div className="flex flex-wrap items-center gap-2">
      <label className="min-w-0 flex-1">{S.s_truoc_khi_chuyen_3ca9e502}<input aria-label={S.s_thu_vien_truoc_khi_chuyen_c012f0f0} className="w-full rounded-control border border-line bg-sunken p-2" value={oldRoot} onChange={(e) => setOldRoot(e.target.value)} disabled={busy} /></label>
      <Button disabled={busy} onClick={() => void choose("old")}>{S.s_chon_thu_muc_truoc_c2cda7f4}</Button>
      <label className="min-w-0 flex-1">{S.s_sau_khi_chuyen_2ba52e4f}<input aria-label={S.s_thu_vien_sau_khi_chuyen_11438b42} className="w-full rounded-control border border-line bg-sunken p-2" value={newRoot} onChange={(e) => setNewRoot(e.target.value)} disabled={busy} /></label>
      <Button disabled={busy} onClick={() => void choose("new")}>{S.s_chon_thu_muc_sau_217a3a2f}</Button>
    </div>
    <div className="flex flex-wrap gap-2">
      <Button disabled={busy} onClick={() => void resolve("finish")}>{S.s_hoan_tat_chuyen_37f331ca}</Button>
      <Button disabled={busy} variant="ghost" onClick={() => void resolve("rollback")}>{S.s_quay_lui_1fdecb6f}</Button>
      <Button disabled={busy} variant="ghost" onClick={() => void resolve("ignore")}>{S.s_bo_qua_c67ba288}</Button>
    </div>
  </div>;
}
