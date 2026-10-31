import QtQuick
import ABook

// Hàng flex-wrap của bản web (flex flex-wrap items-center gap-2): con xếp theo thứ tự, hết chỗ thì xuống dòng; con có `flexGrow: true` (flex-1 basis-N)
// chiếm phần thừa của dòng nó đứng, rộng tối thiểu `flexBasis`; con còn lại rộng theo implicitWidth. Mỗi dòng canh giữa theo chiều dọc. Con ẩn
// (visible false) không chiếm chỗ. Con tự khai `property bool flexGrow` / `property real flexBasis`.
Item {
    id: root
    property real spacing: 8
    default property alias items: holder.data
    implicitHeight: plan.height
    height: implicitHeight

    function baseWidth(child) {
        const wanted = child.flexGrow === true ? (child.flexBasis || 0) : child.implicitWidth
        return Math.min(wanted, root.width)
    }
    // Tính vị trí (đọc mọi thứ phụ thuộc nên tự tính lại khi con đổi cỡ / ẩn hiện)
    function computePlan() {
        const kids = []
        for (let i = 0; i < holder.children.length; ++i) if (holder.children[i].visible) kids.push(holder.children[i])
        const rects = []
        let line = []
        let y = 0
        function flush() {
            if (!line.length) return
            let used = 0
            let growers = 0
            for (const entry of line) { used += entry.w; if (entry.kid.flexGrow === true) ++growers }
            used += root.spacing * (line.length - 1)
            const extra = growers > 0 ? Math.max(0, root.width - used) / growers : 0
            let height = 0
            for (const entry of line) { if (entry.kid.flexGrow === true) entry.w += extra; height = Math.max(height, entry.kid.implicitHeight) }
            let x = 0
            for (const entry of line) {
                rects.push({kid: entry.kid, x: x, y: y + (height - entry.kid.implicitHeight) / 2, w: entry.w, h: entry.kid.implicitHeight})
                x += entry.w + root.spacing
            }
            y += height + root.spacing
            line = []
        }
        let x = 0
        for (const kid of kids) {
            const w = baseWidth(kid)
            if (line.length && x + root.spacing + w > root.width + 0.5) { flush(); x = 0 }
            x += (line.length ? root.spacing : 0) + w
            line.push({kid: kid, w: w})
        }
        flush()
        return {rects: rects, height: Math.max(0, y - root.spacing)}
    }
    property var plan: computePlan()
    function apply() {
        for (const rect of plan.rects) { rect.kid.x = rect.x; rect.kid.y = rect.y; rect.kid.width = rect.w; rect.kid.height = rect.h }
    }
    onPlanChanged: apply()
    Component.onCompleted: apply()
    Item { id: holder; width: root.width }
}
