.pragma library

// Máy dò chữ-đè-icon (bản Qt của gallery_inspect, Lead 31-10): trên mọi cảnh đã dựng, (1) MỰC của chữ (từng dòng) không được giao với
// icon trong cùng một control - kể cả chữ đặt absolute (số "15" từng đè vòng nút lùi ở bản web); (2) icon đứng cạnh nhãn duy nhất của một
// control (nút, chip, dòng menu) phải cùng tâm dọc với DÒNG ĐẦU của nhãn; (3) nút icon trơn (IconButton, không nền) không được đặt
// trên bìa - bìa tối nuốt mất nút (Lead soát 0.4.151); trên bìa dùng CoverButton (tròn, nền panel, bóng).
// "Cùng control" = có tổ tiên chung trong vài cấp, để hộp nổi trên trang không bị so với chữ của trang bên dưới.
// `probe` (qtVisualReady) cho các dòng Qt đã dàn của Text: khối chữ nhiều dòng không phải một hình chữ nhật (bút ngay sau chữ cuối).
// Dùng: VisualReady.render gọi assertClean sau mỗi lần dựng, nên mọi cảnh chụp (L_/W_/D_) và mọi phép thử đều bị kiểm; scan() cho bộ thử lực.

const OVERLAP_LEVELS = 3     // chữ + icon cùng nằm trong một control nhỏ
const ALIGN_LEVELS = 2       // icon + nhãn là anh em hay cách một cấp (Row trong nút)
const ALIGN_GAP = 20         // khoảng ngang tối đa giữa icon và nhãn của nó
const ALIGN_TOLERANCE = 2    // lệch tâm dọc tối đa, px
const MIN_AREA = 1           // px², giao nhỏ hơn là chạm mép do làm tròn

function isIcon(item) { return /^(Icon|CaptionGlyph|SkipGlyph)(_|\()/.test(String(item)) }
function isCover(item) { return /^(CoverView|GeneratedCover)(_|\()/.test(String(item)) }
function isPlainButton(item) { return /^IconButton(_|\()/.test(String(item)) }
function shown(item) { return item.visible && item.opacity > 0.01 && item.width > 0 && item.height > 0 }
function label(item) { return item.objectName || String(item.text || item.name || "").slice(0, 60) || String(item).split("(")[0] }
function hasText(item) { return item.paintedWidth !== undefined && typeof item.text === "string" && item.text.trim() !== "" }

// Hình bao trong toạ độ `root`, sau mọi phép xoay / co giãn (mũi tên xoay 90 độ vẫn nằm đúng chỗ).
function boxOf(item, root, inset) {
    const r = item.mapToItem(root, inset, inset, item.width - 2 * inset, item.height - 2 * inset)
    return {x: r.x, y: r.y, w: r.width, h: r.height}
}

// Mực của chữ trong toạ độ `root`: danh sách hình chữ nhật (một mỗi dòng khi biết các dòng) + dòng đầu.
// Canh ngang và dọc theo alignment (số enum vì thư viện .pragma không có Text.*).
function textInk(item, root, probe) {
    if (!hasText(item) || item.paintedWidth <= 0 || item.paintedHeight <= 0) return null
    const p = item.mapToItem(root, 0, 0)
    const h = item.horizontalAlignment, v = item.verticalAlignment
    const top = item.topPadding || 0, left = item.leftPadding || 0
    const lines = probe && probe.lines ? probe.lines(item) : []
    if (lines.length > 0) {
        const room = item.height - top - (item.bottomPadding || 0)
        const dy = v === 0x40 ? room - item.paintedHeight : v === 0x80 ? (room - item.paintedHeight) / 2 : 0
        const rects = lines.filter(line => line.text.trim() !== "")
            .map(line => ({x: p.x + left + line.x, y: p.y + top + dy + line.y, w: line.w, h: line.h}))
        if (rects.length > 0) return {rects: rects, first: rects[0]}
    }
    const dx = h === 2 ? item.width - item.paintedWidth : h === 4 ? (item.width - item.paintedWidth) / 2 : 0
    const dy = v === 0x40 ? item.height - item.paintedHeight : v === 0x80 ? (item.height - item.paintedHeight) / 2 : 0
    const lineHeight = item.paintedHeight / Math.max(1, item.lineCount || 1)
    const box = {x: p.x + dx, y: p.y + dy, w: item.paintedWidth, h: item.paintedHeight}
    // TextEdit nhiều dòng: dòng cuối chỉ dài tới chữ cuối
    if ((item.lineCount || 1) > 1 && typeof item.positionToRectangle === "function") {
        const end = item.positionToRectangle(item.length)
        return {rects: [{x: box.x, y: box.y, w: box.w, h: end.y}, {x: box.x, y: p.y + end.y, w: end.x, h: end.height}],
                first: {x: box.x, y: box.y, w: box.w, h: lineHeight}}
    }
    return {rects: [box], first: {x: box.x, y: box.y, w: box.w, h: lineHeight}}
}
// Icon lucide vẽ trong lưới 24 có lề 2 đơn vị: mực nằm trong ô thu 1/12 mỗi phía.
function iconInk(item, root) { return boxOf(item, root, String(item).indexOf("Icon") === 0 ? item.width / 12 : 0) }
function ancestors(item, levels) {
    const out = []
    for (let node = item.parent; node && out.length < levels; node = node.parent) out.push(node)
    return out
}
function sharedAncestor(a, b, levels) {
    const mine = ancestors(a, levels)
    for (const node of ancestors(b, levels)) if (mine.indexOf(node) >= 0) return node
    return null
}
function overlapArea(a, b) {
    const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)
    const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)
    return w > 0 && h > 0 ? w * h : 0
}
function shownTexts(node, out) {
    if (!shown(node)) return out
    if (hasText(node)) out.push(node)
    for (const child of node.children || []) shownTexts(child, out)
    return out
}

function scan(root, probe) {
    const icons = [], texts = [], covers = [], buttons = []
    function walk(item, inCover) {
        if (!shown(item)) return
        if (isIcon(item)) { if (item.name === undefined || item.name !== "") icons.push(item); return }   // Icon tên rỗng không vẽ gì; chữ BÊN TRONG icon (số của SkipGlyph) là một phần của icon
        if (isCover(item) && !inCover) covers.push(item)                 // bìa vẽ (GeneratedCover) bên trong CoverView là cùng một bìa
        if (isPlainButton(item)) buttons.push(item)
        if (hasText(item)) texts.push(item)
        for (const child of item.children || []) walk(child, inCover || isCover(item))
    }
    walk(root, false)
    const hits = []
    for (const button of buttons)
        for (const cover of covers)
            if (overlapArea(boxOf(button, root, 0), boxOf(cover, root, 0)) >= MIN_AREA && sharedAncestor(button, cover, OVERLAP_LEVELS))
                hits.push({rule: "plain-button-on-cover", button: label(button), cover: label(cover)})
    const inks = texts.map(text => textInk(text, root, probe))
    for (const icon of icons) {
        const i = iconInk(icon, root)
        texts.forEach(function(text, index) {
            const t = inks[index]
            if (!t) return
            const area = t.rects.reduce((sum, rect) => sum + overlapArea(rect, i), 0)
            if (area >= MIN_AREA && sharedAncestor(text, icon, OVERLAP_LEVELS)) {
                hits.push({rule: "text-over-icon", text: label(text), icon: label(icon), area: Math.round(area)})
                return
            }
            const parent = sharedAncestor(text, icon, ALIGN_LEVELS)
            if (!parent || area > 0) return
            // Dòng icon đứng cạnh: icon TRƯỚC khối chữ canh theo dòng đầu; icon SAU chữ (bút sau chữ cuối) canh theo dòng nó đứng cạnh
            const gapTo = line => Math.max(i.x - (line.x + line.w), line.x - (i.x + i.w))
            const overlapY = line => Math.min(i.y + i.h, line.y + line.h) - Math.max(i.y, line.y)
            const near = t.rects.filter(line => gapTo(line) >= 0 && gapTo(line) <= ALIGN_GAP && overlapY(line) > 0)
            if (near.length === 0 || shownTexts(parent, []).length !== 1) return
            const f = i.x + i.w <= t.first.x + 1 ? t.first : near.reduce((best, line) => overlapY(line) > overlapY(best) ? line : best)
            const delta = (i.y + i.h / 2) - (f.y + f.h / 2)
            if (Math.abs(delta) > ALIGN_TOLERANCE)
                hits.push({rule: "icon-off-center", text: label(text), icon: label(icon), delta: Math.round(delta * 10) / 10})
        })
    }
    return hits
}

function assertClean(test, root, probe) {
    const hits = scan(root, probe)
    if (hits.length) console.log("ICON_TEXT " + JSON.stringify(hits))
    test.verify(hits.length === 0, "chữ đè icon / icon lệch tâm / nút trơn trên bìa: " + JSON.stringify(hits))
}
