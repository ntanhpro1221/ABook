import QtQuick
import ABook

// Danh sách hàng mở / khép tại chỗ (useListPresence của shared/motion.ts): `update(items)` đối chiếu theo `id` với lần trước, giữ nguyên
// hàng cũ (không dựng lại, nên hàng đang gập mở không bị giật), thêm hàng mới với `fresh` (mở ra từ chiều cao 0), đánh dấu hàng đã mất
// `present: false` để hàng tự khép rồi gọi `drop(id)`. Mỗi hàng giữ JSON của mục trong `json` (ListModel không giữ được object lồng).
Item {
    id: root
    visible: false
    property alias model: list
    property bool seeded: false
    property int revision: 0
    readonly property int count: list.count

    ListModel { id: list }

    function indexOfKey(key) {
        for (let i = 0; i < list.count; ++i) if (list.get(i).rowId === key) return i
        return -1
    }
    function update(items) {
        const seen = {}
        for (const item of items || []) {
            const key = String(item.id)
            seen[key] = true
            const json = JSON.stringify(item)
            const at = indexOfKey(key)
            if (at < 0) list.append({rowId: key, json: json, present: true, fresh: seeded})
            else {
                if (list.get(at).json !== json) list.setProperty(at, "json", json)
                if (!list.get(at).present) list.setProperty(at, "present", true)
            }
        }
        for (let i = 0; i < list.count; ++i)
            if (!seen[list.get(i).rowId] && list.get(i).present) list.setProperty(i, "present", false)
        seeded = true
        revision++
    }
    function drop(key) {
        const at = indexOfKey(key)
        if (at >= 0 && !list.get(at).present) { list.remove(at); revision++ }
    }
    // Số hàng còn hiện đứng trước hàng thứ `index` (vạch chia chỉ vẽ từ hàng thứ hai)
    function presentBefore(index) {
        let n = 0
        for (let i = 0; i < index && i < list.count; ++i) if (list.get(i).present) ++n
        return n
    }
    function presentCount() { let n = 0; for (let i = 0; i < list.count; ++i) if (list.get(i).present) ++n; return n }
}
