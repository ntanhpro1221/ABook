import QtQuick
import ABook

// Hàng nút ở chân hộp (DialogActions của shared/ui.tsx: flex-wrap justify-end gap-2): nút dồn về mép phải, hộp hẹp thì xuống dòng - nút
// không bao giờ tràn ra ngoài. Thứ tự khai báo là thứ tự Tab và thứ tự đọc; nút chính khai báo cuối nên nằm ngoài cùng bên phải.
Item {
    id: root
    default property alias content: holder.data
    height: 0
    property var watched: []
    function relayout() {
        const kids = []
        for (let i = 0; i < holder.children.length; ++i) if (holder.children[i].visible) kids.push(holder.children[i])
        const lines = [[]]
        let used = 0
        for (const kid of kids) {
            const w = Math.min(kid.implicitWidth, root.width)
            if (used > 0 && used + 8 + w > root.width) { lines.push([]); used = 0 }
            lines[lines.length - 1].push(kid)
            used += (used > 0 ? 8 : 0) + w
        }
        let y = 0
        for (const line of lines) {
            let total = 0
            for (const kid of line) total += Math.min(kid.implicitWidth, root.width) + (total > 0 ? 8 : 0)
            let x = root.width - total, tall = 0
            for (const kid of line) {
                kid.width = Math.min(kid.implicitWidth, root.width)
                kid.x = x
                kid.y = y
                x += kid.width + 8
                tall = Math.max(tall, kid.height)
            }
            y += tall + 8
        }
        root.height = Math.max(0, y - 8)
    }
    onWidthChanged: Qt.callLater(relayout)
    Item {
        id: holder
        width: parent.width
        onChildrenChanged: {
            for (let i = 0; i < children.length; ++i) {
                const kid = children[i]
                if (root.watched.indexOf(kid) >= 0) continue
                root.watched.push(kid)
                kid.implicitWidthChanged.connect(root.relayout)
                kid.visibleChanged.connect(root.relayout)
            }
            Qt.callLater(root.relayout)
        }
    }
}
