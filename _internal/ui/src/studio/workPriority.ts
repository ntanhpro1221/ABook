import { S } from "../shared/strings.generated";

export interface WorkPriority {
  reason: "upcoming" | "impact" | "tentative" | "redo" | "refused";
  lines: number;
  recordedLines: number | null;
  recordedChapters: number | null;
  estimatedActions: number;
  overlapLines: number;
  upcoming: boolean;
  tentative: boolean;
}

/** Default scope only. Live book state owns the application time. */
export function priorityText(item: { priority?: WorkPriority; affected: number; redoOnly?: boolean }, note: string): string {
  const p = item.priority;
  const reasons = {
    upcoming: S.s_work_reason_upcoming, impact: S.s_work_reason_impact,
    tentative: S.s_work_reason_tentative, redo: S.s_work_reason_redo, refused: S.s_work_reason_refused,
  };
  return [reasons[p?.reason ?? "impact"],
    p && p.recordedLines !== null && p.recordedChapters !== null
      ? S.s_work_recorded(p.lines, p.recordedLines, p.recordedChapters) : S.s_work_unknown(p?.lines ?? item.affected),
    S.s_work_effort(p?.estimatedActions ?? 1),
    p?.overlapLines ? S.s_work_overlap(p.overlapLines) : "",
    item.redoOnly ? S.s_work_reason_redo : S.s_work_apply(note),
  ].filter(Boolean).join(" ");
}
