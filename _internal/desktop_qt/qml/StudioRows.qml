import QtQuick
import ABook

// Danh sách hàng có vạch chia, hàng thêm / bớt thì khép / mở tại chỗ (AnimatedRows + `divide-y divide-line` của bản web). `items` là mảng đối
// tượng, `keyField` là trường làm khoá; `delegate` là Component có `property var modelData` (đối tượng của hàng, giữ nguyên bản cuối cùng
// trong lúc hàng đang khép). Hàng có sẵn lúc đầu hiện thẳng, không tween; hàng mới đến sau thì mở ra từ chiều cao 0.
Column {
    id: root
    property var items: []
    property string keyField: "name"
    property Component delegate: null
    property var byKey: ({})
    property bool populated: false
    readonly property int count: rows.count
    function keyOf(item) { return String(item[keyField]) }
    function indexOfKey(key) {
        for (let i = 0; i < rows.count; ++i) if (rows.get(i).key === key) return i
        return -1
    }
    function sync() {
        const keys = (items || []).map(keyOf)
        const map = Object.assign({}, byKey)
        for (const item of items || []) map[keyOf(item)] = item
        byKey = map
        for (let i = 0; i < rows.count; ++i) rows.setProperty(i, "gone", !keys.includes(rows.get(i).key))
        let at = 0
        for (const key of keys) {
            const found = indexOfKey(key)
            if (found < 0) { rows.insert(at, {key: key, gone: false, appear: populated}); ++at }
            else at = Math.max(at, found + 1)
        }
        populated = true
    }
    function drop(key) {
        const i = indexOfKey(key)
        if (i >= 0 && rows.get(i).gone) rows.remove(i)
    }
    onItemsChanged: sync()
    Component.onCompleted: sync()
    ListModel { id: rows }
    Repeater {
        model: rows
        Collapse {
            id: cell
            required property int index
            required property string key
            required property bool gone
            required property bool appear
            property bool entered: !appear
            width: root.width
            open: entered && !gone
            onSettledChanged: if (settled && gone) Qt.callLater(function() { root.drop(cell.key) })  // mỗi hàng một hàm: callLater gộp các lần gọi cùng hàm
            Component.onCompleted: if (appear) Qt.callLater(function() { cell.entered = true })
            Rectangle { width: parent.width; height: 1; color: Theme.line; visible: cell.index > 0 }
            Loader {
                id: loader
                width: parent.width
                sourceComponent: root.delegate
                onLoaded: item.modelData = Qt.binding(function() { return root.byKey[cell.key] })
            }
        }
    }
}
