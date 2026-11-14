.pragma library

function lines(all, anchor, mode, start, end) {
    const base = all.find(line => line.stableId === anchor)
    if (!base || (mode === "scene" && (base.scene === null || base.scene === undefined))) return []
    if (mode === "manual" && (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end < start)) return []
    return all.filter(line => line.editable && (line.kind === "dialogue" || line.kind === "thought") && (line.speaker || line.current) === (base.speaker || base.current)
        && (mode !== "line" || line.stableId === anchor)
        && (mode !== "scene" || line.scene === base.scene)
        && (mode !== "manual" || (start <= line.seq && line.seq <= end)))
}
function conflict(line) { return !!(line.wish || line.lineWish) }
function selected(candidates, toggled) { return candidates.filter(line => conflict(line) === (toggled.indexOf(line.stableId) >= 0)) }
