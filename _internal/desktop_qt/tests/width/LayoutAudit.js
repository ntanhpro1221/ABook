.pragma library

// Actual rendered geometry, in page coordinates. Do not use bounding-box width
// as a proxy for text: a centred label can hide inside a very wide button.
function type(item, name) { return String(item).indexOf(name + "_") === 0 || String(item).indexOf(name + "(") === 0 }
function shown(item) { return item.visible && item.opacity > 0.01 && item.width > 0 && item.height > 0 }
function box(item, page) {
    const p = item.mapToItem(page, 0, 0)
    return {x: p.x, y: p.y, w: item.width, h: item.height}
}
function ink(item, page) {
    const b = box(item, page)
    if (item.paintedWidth !== undefined && String(item.text || "") !== "") {
        const dx = item.horizontalAlignment === 2 ? b.w - item.paintedWidth
                 : item.horizontalAlignment === 4 ? (b.w - item.paintedWidth) / 2 : 0
        b.x += dx; b.w = item.paintedWidth; b.h = item.paintedHeight
        return b
    }
    return null
}
function name(item) { return item.objectName || item.text || String(item).split("(")[0] }
function aligned(items, page, hits, label) {
    const active = items.filter(i => i && shown(i))
    if (active.length < 2) return
    const x = box(active[0], page).x
    for (const item of active.slice(1)) {
        const delta = box(item, page).x - x
        if (Math.abs(delta) > 2) hits.push({rule: "section-left", group: label, item: name(item), delta: Math.round(delta * 100) / 100})
    }
}
function scan(page, groups) {
    const hits = [], items = [], text = []
    function walk(item) {
        if (!shown(item)) return
        items.push(item)
        if (ink(item, page)) text.push(item)
        for (const child of item.children || []) walk(child)
    }
    walk(page)
    for (const group of groups || []) aligned(group.items, page, hits, group.label)
    for (const item of items) {
        // Vertical section stacks share a column. Short text labels, centred
        // icons/buttons and inset content inside a section are not sections.
        if (String(item).indexOf("QQuickColumn") === 0) {
            const sections = (item.children || []).filter(c => shown(c) && c.width >= item.width * 0.6
                && c.paintedWidth === undefined && c.clicked === undefined && c.children.length > 0)
            aligned(sections, page, hits, name(item))
        }
        if ((type(item, "ChoiceChip") || type(item, "ControlChip")) && !item.fullWidthReason && item.width > item.implicitWidth + 2) {
            hits.push({rule: "stretched-chip", item: name(item), width: Math.round(item.width), natural: Math.round(item.implicitWidth)})
        }
        if (type(item, "ChoiceRow") || type(item, "PageSwitch")) {
            if (type(item, "PageSwitch") && item.width > item.implicitWidth + 2)
                hits.push({rule: "stretched-segment", item: name(item), width: Math.round(item.width), natural: Math.round(item.implicitWidth)})
            function choices(node) {
                for (const child of node.children || []) {
                    if (!shown(child)) continue
                    if (child.clicked !== undefined && child.implicitWidth > 0 && child.width > child.implicitWidth + 2)
                        hits.push({rule: "stretched-segment", item: name(child), width: Math.round(child.width), natural: Math.round(child.implicitWidth)})
                    else choices(child)
                }
            }
            choices(item)
        }
    }
    for (const item of text) {
        const b = ink(item, page)
        // Find the closest horizontal composition containing the label. Tall
        // pages/empty states are not rows; the check also sees nested buttons.
        let row = item.parent
        // Stop at a compact row too: ascending past its content measure would
        // count the page margins as empty space inside the row (e.g. PeerBar).
        while (row && row !== page && !(row.width > 400 && row.height <= 240)) row = row.parent
        if (!row || row.width <= 800 || row.height > 240) continue
        const r = box(row, page)
        let left = r.x, right = r.x + r.w
        for (const peer of items) {
            if (peer === item) continue
            let p = ink(peer, page)
            if (!p && type(peer, "CoverView")) p = box(peer, page)
            if (!p || p.y + p.h <= b.y || p.y >= b.y + b.h) continue
            if (p.x + p.w <= b.x + 0.5) left = Math.max(left, p.x + p.w)
            if (p.x >= b.x + b.w - 0.5) right = Math.min(right, p.x)
        }
        if (b.x - left > 400 && right - b.x - b.w > 400)
            hits.push({rule: "detached-text", item: String(item.text), left: Math.round(b.x - left), right: Math.round(right - b.x - b.w)})
    }
    return hits
}
