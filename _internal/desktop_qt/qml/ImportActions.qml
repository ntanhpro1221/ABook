import QtQuick
import ABook

// Chân hộp Thêm sách (DialogActions của bản web: flex-wrap + justify-end, cách 8): hàng nút thẳng mép phải, hết chỗ thì xuống dòng và MỖI dòng vẫn thẳng mép phải
// (Flow của Qt chỉ canh trái). Cả hàng mở / khép bằng chiều cao (motionMedium) khi hộp đổi bước (chọn -> xem trước -> xong). Mỗi nút bọc trong một ImportSlot để tự
// nở / co tại chỗ; nút trần (hộp hỏi) cũng được.
Item {
    id: root
    property bool open: true
    default property alias content: holder.data
    property real reveal: open ? 1 : 0
    readonly property real spacing: 8
    readonly property real rowsHeight: holder.height
    // Chữ ký bố cục: bề ngang hộp + bề ngang / hiện của từng nút; đổi thì xếp lại
    readonly property string signature: {
        let text = String(width)
        for (let i = 0; i < holder.children.length; ++i) {
            const c = holder.children[i]
            text += "|" + (c.visible ? Math.ceil(c.width) + "x" + Math.ceil(c.height) : "-")
        }
        return text
    }
    objectName: "importActions"
    height: Theme.reduceMotion ? (open ? rowsHeight : 0) : rowsHeight * reveal
    clip: reveal < 1
    enabled: open
    onSignatureChanged: relayout()
    Component.onCompleted: relayout()
    Behavior on reveal {
        NumberAnimation {
            duration: Theme.reduceMotion ? Theme.motionFast : (root.open ? Theme.motionMedium : Theme.motionMediumOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.open ? Theme.easeStandard : Theme.easeAccelerate
        }
    }
    function relayout() {
        const kids = []
        for (let i = 0; i < holder.children.length; ++i) {
            const c = holder.children[i]
            if (c.visible && c.width > 0) kids.push(c)
        }
        // Chia dòng theo thứ tự, mỗi dòng thẳng mép phải
        const rows = []
        let row = [], used = 0
        for (const c of kids) {
            if (row.length && used + spacing + c.width > width + 0.5) { rows.push(row); row = []; used = 0 }
            used += (row.length ? spacing : 0) + c.width
            row.push(c)
        }
        if (row.length) rows.push(row)
        let y = 0
        for (const items of rows) {
            let total = (items.length - 1) * spacing, tall = 0
            for (const c of items) { total += c.width; tall = Math.max(tall, c.height) }
            let x = width - total
            for (const c of items) { c.x = x; c.y = y + (tall - c.height) / 2; x += c.width + spacing }
            y += tall + spacing
        }
        holder.height = Math.max(0, y - spacing)
    }
    Item {
        id: holder
        width: parent.width
        opacity: root.reveal
    }
}
