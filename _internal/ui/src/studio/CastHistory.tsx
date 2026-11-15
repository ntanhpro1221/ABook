import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Fold } from "@/shared/Collapse";
import { AnimatedRows, Reveal } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import { Button } from "@/shared/ui";
import { S } from "@/shared/strings.generated";
import type { CastHistoryView } from "@/listen/model";
import { api } from "./api";
import { refreshAfterDecision } from "./decisions";

export function CastHistory({ bookId, history, editable }: { bookId: string; history?: CastHistoryView; editable: boolean }) {
  const client = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState("");
  const [queued, setQueued] = useState<Set<string>>(new Set());
  async function undo(operationId: string) {
    if (busy) return;
    setBusy(operationId);
    setProblem("");
    try {
      await api(`/api/books/${bookId}/cast-history/undo`, { method: "POST", body: { operationId } });
      setQueued(previous => new Set([...previous, operationId]));
      refreshAfterDecision(client, bookId);
    } catch (error) {
      setProblem((error as Error).message);
    } finally {
      setBusy(null);
    }
  }
  return <Fold storageKey={`book.${bookId}.cast-history`} title={S.s_lich_su_0a235708} className="mt-4">
    <Reveal when={problem}><MotionRegion as="p" role="alert" className="text-sm text-danger">{problem}</MotionRegion></Reveal>
    <Reveal when={!history?.items.length}><p className="py-2 text-sm text-fg-2">{S.s_cast_history_manual}</p></Reveal>
    <AnimatedRows items={history?.items ?? []} keyOf={item => item.operationId}>
      {item => {
        const state = item.state === "applied" && queued.has(item.operationId) ? "pending" : item.state;
        return <div className="flex items-center gap-3 py-3">
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">{S.s_cast_history_row(item.source || S.s_cast_history_group, item.target, item.lines)}</div>
            <MotionRegion as="div" className="text-xs text-fg-2">
              {state === "undone" ? S.s_da_hoan_tac_2ef55fca : state === "pending" ? S.s_cho_ap_dung_77a52853 : ""}
            </MotionRegion>
            <Reveal when={item.conflicts > 0}><p className="text-xs text-fg-2">{S.s_cast_history_conflicts(item.conflicts)}</p></Reveal>
            <Reveal when={(item.aliasConflicts ?? 0) > 0}><p className="text-xs text-fg-2">{S.s_cast_history_alias_conflicts(item.aliasConflicts ?? 0)}</p></Reveal>
            <Reveal when={state === "pending"}><p className="text-xs text-fg-2">{S.s_cast_history_audio}</p></Reveal>
          </div>
          <Reveal when={editable && state === "applied"}>
            <Button variant="ghost" disabled={busy !== null} loading={busy === item.operationId} onClick={() => undo(item.operationId)}>{S.s_hoan_tac_e72ff675}</Button>
          </Reveal>
        </div>;
      }}
    </AnimatedRows>
  </Fold>;
}
