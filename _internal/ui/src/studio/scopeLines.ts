import type { Line } from "./ScriptTab";

export type ScopeMode = "line" | "scene" | "chapter" | "manual";

/** All rows, including off-screen rows. Identity is the original opaque role. */
export function scopeLines(lines: Line[], anchor: string, mode: ScopeMode, start: number, end: number): Line[] {
  const base = lines.find((line) => line.stableId === anchor);
  if (!base || (mode === "scene" && base.scene == null)) return [];
  if (mode === "manual" && (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end < start)) return [];
  return lines.filter((line) => line.editable && ["dialogue", "thought"].includes(line.kind) && (line.speaker || line.current) === (base.speaker || base.current) &&
    (mode !== "line" || line.stableId === anchor) &&
    (mode !== "scene" || line.scene === base.scene) &&
    (mode !== "manual" || (start <= line.seq && line.seq <= end)));
}

export function scopeConflict(line: Line): boolean { return !!(line.wish || line.lineWish); }

export function scopeSelected(lines: Line[], toggled: string[]): Line[] {
  return lines.filter((line) => scopeConflict(line) === toggled.includes(line.stableId));
}
