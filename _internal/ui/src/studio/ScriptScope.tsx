import { useState } from "react";
import { S } from "@/shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence, Reveal } from "@/shared/MotionPresence";
import { Button, Dialog, SelectionMark } from "@/shared/ui";
import type { ChapterScript, Line, Person } from "./ScriptTab";
import { scopeConflict, scopeLines, scopeSelected, type ScopeMode } from "./scopeLines";
import { useFadeScroller } from "@/shared/scrollFade";

export const scopeOptions: [ScopeMode, string][] = [
  ["line", S.s_cau_nay_ee66e104], ["scene", S.s_scope_scene], ["chapter", S.s_scope_chapter], ["manual", S.s_scope_manual],
];

export function ScriptScope({ script: incoming, line, onClose, onApply }: {
  script: ChapterScript; line: Line; onClose: () => void; onApply: (lines: Line[], person: Person, revision: string) => Promise<void>;
}) {
  const [script] = useState(incoming);
  const fade = useFadeScroller();
  const [mode, setMode] = useState<ScopeMode>(line.scene == null ? "line" : "scene");
  const initialRange = line.scene == null ? [line] : script.lines.filter((item) => item.scene === line.scene);
  const [start, setStart] = useState((initialRange[0]?.seq ?? line.seq) + 1);
  const [end, setEnd] = useState((initialRange.at(-1)?.seq ?? line.seq) + 1);
  const [toggled, setToggled] = useState<string[]>([]);
  const [person, setPerson] = useState<Person | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const candidates = scopeLines(script.lines, line.stableId, mode, start - 1, end - 1);
  const selected = scopeSelected(candidates, toggled);
  const conflicts = candidates.filter(scopeConflict).length;
  const fold = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
  const everyone = [...script.cast, ...script.others, { value: "UNNAMED", label: S.s_vai_phu_khong_ten_6395f0d2, lines: 0 }]
    .filter((item, index, all) => item.value !== "NARRATOR" && all.findIndex((other) => other.value === item.value) === index);
  const found = everyone.filter((item) => fold(item.label).includes(fold(query.trim()))).slice(0, 8);
  const apply = async () => {
    if (!person) return;
    setBusy(true); setError("");
    try { await onApply(selected, person, script.scopeRevision ?? ""); onClose(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : S.s_scope_changed); }
    finally { setBusy(false); }
  };
  return <Dialog open onOpenChange={(open) => { if (!open && !busy) onClose(); }} title={S.s_scope_title}
    footer={<Button className="w-full sm:w-auto" variant="primary" disabled={busy || !person || !selected.length} onClick={apply}>{S.s_scope_apply}</Button>}>
    <div className="space-y-3">
      <p className="text-body-small text-fg-2">{line.scene == null ? S.s_scope_no_markers : S.s_scope_marker_note}</p>
      <div className="flex flex-wrap gap-2">
        {scopeOptions.map(([value, label]) => <Button key={value} size="sm" variant="ghost" aria-pressed={value === mode} className={value === mode ? "font-bold underline underline-offset-4" : undefined}
          disabled={busy || (value === "scene" && line.scene == null)} onClick={() => { setMode(value); setToggled([]); }}>{label}</Button>)}
      </div>
      <MotionRegion motionKey={mode}>
        {mode === "manual" && <div className="flex gap-3">
          <label className="text-body-small">{S.s_scope_start}<input aria-label={S.s_scope_start} className="w-24 rounded-control border border-line p-2" type="number" min={1} max={(script.lines.at(-1)?.seq ?? 0) + 1} value={start} onChange={(event) => setStart(Number(event.target.value))} /></label>
          <label className="text-body-small">{S.s_scope_end}<input aria-label={S.s_scope_end} className="w-24 rounded-control border border-line p-2" type="number" min={1} max={(script.lines.at(-1)?.seq ?? 0) + 1} value={end} onChange={(event) => setEnd(Number(event.target.value))} /></label>
        </div>}
      </MotionRegion>
      <MotionRegion motionKey={person?.value ?? "pick"}>
        {person ? <Button variant="ghost" onClick={() => setPerson(null)}>{S.s_scope_target(person.label)}</Button>
          : <div>
            <input className="w-full rounded-control border border-control-line bg-bg p-3 text-body-small" aria-label={S.s_tim_nguoi_noi_70e3871e} placeholder={S.s_tim_nguoi_noi_70e3871e} value={query} onChange={(event) => setQuery(event.target.value)} />
            <AnimatedRows items={found} keyOf={(item) => item.value}>{(item) => <button type="button" onClick={() => setPerson(item)} className="flex min-h-10 w-full items-center gap-3 rounded-control px-2 text-left text-body-small hover:bg-hover"><SelectionMark selected={item.value === line.current} />{item.label}</button>}</AnimatedRows>
            <MotionPresence open={query.trim() !== "" && found.length === 0}>
              <div className="flex gap-2">{([["male", S.s_nam_22dd59c8], ["female", S.s_nu_e15bc11c], ["unknown", S.s_khong_ro_8af7da78]] as const).map(([gender, label]) => <Button key={gender} variant="ghost" onClick={() => setPerson({ value: query.trim(), label: query.trim(), lines: 0, newGender: gender })}>{label}</Button>)}</div>
            </MotionPresence>
          </div>}
      </MotionRegion>
      <MotionRegion motionKey={[selected.length, conflicts, person?.value]}>
        <p role="status" className="text-body-small">{S.s_scope_count(selected.length, conflicts)}</p>
        <p className="text-body-small text-fg-2">{S.s_scope_before_after(line.label, person?.label ?? S.s_scope_pick)}</p>
      </MotionRegion>
      <div ref={fade.ref} style={fade.style} className="max-h-72 overflow-y-auto" data-motion-live>
        <AnimatedRows items={candidates} keyOf={(item) => item.stableId}>{(item) => <button type="button" role="checkbox" aria-checked={selected.includes(item)} className="flex w-full items-start gap-2 rounded-control p-2 text-left hover:bg-hover"
          onClick={() => setToggled((old) => old.includes(item.stableId) ? old.filter((id) => id !== item.stableId) : [...old, item.stableId])}>
          <SelectionMark selected={selected.includes(item)} /><span className="text-body-small">{item.seq + 1}. {item.text}<Reveal when={scopeConflict(item)}><span className="block text-fg-2">{S.s_scope_conflict}</span></Reveal><span className="block text-fg-2">{S.s_scope_before_after(item.wish?.state === "pending" ? item.wish.label : item.label, person?.label ?? S.s_scope_pick)}</span></span>
        </button>}</AnimatedRows>
      </div>
      <MotionRegion motionKey={error}><p role="alert" className="text-body-small text-danger">{error}</p></MotionRegion>
    </div>
  </Dialog>;
}
