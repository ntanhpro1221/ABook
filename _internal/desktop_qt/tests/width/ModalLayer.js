.pragma library

// Máy dò lớp hộp thoại: hộp (Modal) đang mở thì chữ / nền / nút của trang không được vẽ đè lên mặt hộp. Chọn một lưới điểm trong khung hộp,
// với mỗi điểm đi từ gốc cửa sổ xuống như Qt vẽ (con z lớn hơn vẽ sau, cùng z thì con khai báo sau vẽ sau) và lấy phần tử NHÌN THẤY trên cùng;
// phần tử đó phải nằm trong hộp. Item.childAt không dùng được: nó bỏ qua z.
// Dùng: VisualReady.render gọi assertAbove sau mỗi lần dựng xong, nên mọi ảnh chụp / phép thử đều bị kiểm.

const GRID_COLUMNS = 7
const GRID_ROWS = 5
const INSET = 12
const PANELS = ["modalPanel", "popoverPanel"]

function opaque(color) { return color !== undefined && color !== null && color.a > 0 }

// Phần tử có tự vẽ gì (hoặc nhận chuột) ở điểm nó phủ không. Item trống / vùng chứa thì không tính.
function paints(item) {
    if (item.acceptedButtons !== undefined) return item.enabled                     // MouseArea: nhận bấm
    if (item.border !== undefined && item.radius !== undefined)                     // Rectangle
        return opaque(item.color) || (item.border.width > 0 && opaque(item.border.color)) || (item.gradient !== undefined && item.gradient !== null)
    if (item.contentWidth !== undefined && typeof item.text === "string")           // Text, TextInput, TextEdit
        return item.text !== "" && opaque(item.color)
    if (item.fillMode !== undefined && item.source !== undefined) return true       // Image
    if (item.rendererType !== undefined) return true                                // Shape (icon lucide)
    if (typeof item.getContext === "function") return true                          // Canvas
    return false
}

function reaches(item, x, y) {
    if (!item.visible || item.opacity <= 0 || item.width <= 0 || item.height <= 0) return false
    return item.contains(Qt.point(x, y))
}

// Thứ tự vẽ của con: z tăng dần, cùng z thì thứ tự khai báo (children giữ thứ tự khai báo)
function paintOrder(item) {
    return item.children.map((child, index) => ({child: child, index: index}))
        .sort((a, b) => a.child.z - b.child.z || a.index - b.index).map(entry => entry.child)
}

// Phần tử trên cùng thật sự vẽ ở điểm (rx, ry) của hệ toạ độ `root`; null nếu không có gì
function topAt(item, root, rx, ry) {
    const local = item.mapFromItem(root, rx, ry)
    if (!reaches(item, local.x, local.y)) return null
    const order = paintOrder(item)
    for (let i = order.length - 1; i >= 0; i--) {
        if (order[i].z < 0) break
        const found = topAt(order[i], root, rx, ry)
        if (found) return found
    }
    if (paints(item)) return item
    for (let i = order.length - 1; i >= 0 && order[i].z < 0; i--) {
        const found = topAt(order[i], root, rx, ry)
        if (found) return found
    }
    return null
}

function inside(item, ancestor) {
    for (let node = item; node; node = node.parent) if (node === ancestor) return true
    return false
}

// Mọi lớp nổi trong cây: phần tử có con `modalPanel` (Modal.qml) hay `popoverPanel` (Popover.qml)
function layersIn(item, found) {
    const out = found || []
    for (const child of item.children) {
        if (PANELS.indexOf(child.objectName) >= 0 && typeof item.open === "boolean") out.push(item)
        layersIn(child, out)
    }
    return out
}

function describe(item) {
    const label = item.objectName ? "#" + item.objectName : ""
    const text = typeof item.text === "string" && item.text !== "" ? " \"" + item.text.slice(0, 24) + "\"" : ""
    const owner = item.parent ? " in " + (item.parent.objectName ? "#" + item.parent.objectName : String(item.parent).split("(")[0]) : ""
    return String(item).split("(")[0] + label + text + owner
}

// Điểm của lưới trong khung hộp, toạ độ `root`
function samplePoints(panel, root) {
    const points = []
    const w = panel.width
    const h = panel.height
    for (let row = 0; row < GRID_ROWS; row++) {
        for (let column = 0; column < GRID_COLUMNS; column++) {
            const px = INSET + (w - 2 * INSET) * column / (GRID_COLUMNS - 1)
            const py = INSET + (h - 2 * INSET) * row / (GRID_ROWS - 1)
            const point = panel.mapToItem(root, px, py)
            points.push({x: point.x, y: point.y, px: px, py: py})
        }
    }
    return points
}

// Danh sách lỗi của một lớp: mỗi điểm lưới mà thứ nhìn thấy trên cùng không thuộc lớp đó (hay một lớp nổi khác đang mở, vd hộp con trên hộp)
function panelOf(layer) { return layer.children.filter(child => PANELS.indexOf(child.objectName) >= 0)[0] }

function violationsOf(modal, root, others) {
    const panel = panelOf(modal)
    if (!panel || panel.width <= 0 || panel.height <= 0) return []
    const bad = []
    for (const point of samplePoints(panel, root)) {
        const top = topAt(root, root, point.x, point.y)
        if (top && !inside(top, modal) && !others.some(other => inside(top, other))) bad.push("(" + Math.round(point.px) + "," + Math.round(point.py) + ") " + describe(top))
    }
    return bad
}

// Hộp đã mở hẳn (shown = 1) mới kiểm: lúc đang trượt vào khung còn nhỏ hơn.
function violations(root) {
    const out = []
    const open = layersIn(root).filter(layer => layer.open && layer.shown === 1 && layer.visible)
    for (const modal of open) {
        const bad = violationsOf(modal, root, open.filter(other => other !== modal))
        if (bad.length > 0) out.push({modal: modal, objectName: modal.objectName, title: modal.title, points: bad})
    }
    return out
}

function report(list) {
    return list.map(entry => "modal \"" + (entry.title || entry.objectName) + "\" is covered at " + entry.points.length + " points: " + entry.points.slice(0, 6).join("; ")).join(" | ")
}

function assertAbove(test, root) {
    const list = violations(root)
    test.verify(list.length === 0, report(list))
}

function anyOpen(root) { return layersIn(root, []).some(layer => layer.open || layer.shown > 0) }

// Mọi phần tử của `item` VÀ của các lớp nổi do `item` mở (khai báo bên trong nó, nay nằm ở gốc cửa sổ) mà `accept(node)` đúng. Các phép thử
// trang / màn trước đây "đi xuống theo children" nên thấy luôn hộp con; Modal / Popover đã tự đặt ở gốc cửa sổ nên phải đi cả hai đường.
function collect(item, accept) {
    let top = item
    while (top.parent) top = top.parent
    const layers = layersIn(top, [])
    const scopes = [item]
    for (let grew = true; grew;) {
        grew = false
        for (const layer of layers) {
            if (scopes.indexOf(layer) >= 0 || !layer.owner) continue
            if (scopes.some(scope => inside(layer.owner, scope))) { scopes.push(layer); grew = true }
        }
    }
    const found = []
    const visit = node => { if (found.indexOf(node) < 0 && accept(node)) found.push(node); for (const child of node.children || []) visit(child) }
    for (const scope of scopes) visit(scope)
    return found
}

function findAll(item, name) { return collect(item, node => node.objectName === name) }
