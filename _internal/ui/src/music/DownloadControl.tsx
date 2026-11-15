import { ArrowDown, Download, Square } from "lucide-react";
import { StateIcon } from "../shared/StateIcon";
import { PendingIndicator } from "../shared/PendingIndicator";
import { S } from "../shared/strings.generated";
import type { TrackLoad } from "./library";

export function DownloadControl({ load, online, busy, onSave, onStop, onDelete }: {
  load: TrackLoad; online: boolean; busy: boolean; onSave: () => void; onStop: () => void; onDelete: () => void;
}) {
  const label = busy ? load.kind === "done" ? S.s_dang_xoa_71482e81 : S.s_dang_tai_465b1987 : load.kind === "loading" ? S.s_stop_download : load.kind === "done" ? S.s_downloaded_delete : load.kind === "failed" ? S.s_thu_lai_c58d068c : S.s_tai_ve_9b5bdb44;
  return <button type="button" aria-label={label} title={label} aria-busy={busy || undefined}
    disabled={busy || (!online && load.kind !== "loading" && load.kind !== "done")}
    onClick={load.kind === "loading" ? onStop : load.kind === "done" ? onDelete : onSave}
    className="press relative grid size-9 shrink-0 place-items-center rounded-control text-accent-text hover:bg-hover touch-reach disabled:opacity-40">
    <StateIcon state={load.kind} className="relative inline-grid size-9 place-items-center">
      <PendingIndicator pending={busy && load.kind !== "loading"}>
      {load.kind === "loading" ? <DownloadProgress percent={load.percent} /> : load.kind === "done" ?
        <span className="grid size-5 place-items-center rounded-full bg-accent text-accent-ink"><ArrowDown className="size-3.5" /></span> : <Download className="size-5" />}
      </PendingIndicator>
    </StateIcon>
  </button>;
}

export function DownloadProgress({ percent }: { percent: number | null }) {
  const circumference = 2 * Math.PI * 16;
  return <span className="relative grid size-9 place-items-center">
    <svg aria-hidden viewBox="0 0 36 36" className={percent === null ? "absolute size-9 animate-spin motion-reduce:animate-none" : "absolute size-9"} data-motion-live>
      <circle cx="18" cy="18" r="16" fill="none" stroke="currentColor" strokeOpacity={0.2} strokeWidth={2} />
      <circle cx="18" cy="18" r="16" transform="rotate(-90 18 18)" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={circumference * (1 - (percent ?? 25) / 100)} />
    </svg>
    <Square aria-hidden className="size-2 fill-current" />
  </span>;
}
