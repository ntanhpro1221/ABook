import QtQuick
import ABook
import "ExportLogic.js" as Logic

// Danh sách từng thay đổi đang chờ áp, mỗi dòng có nút bỏ (PendingList của studio/ApplyChanges.tsx), cao tối đa 288 rồi cuộn trong khung. Dòng vào / ra bằng chiều cao.
// `dropping`: mã (`section:key`) của dòng đang bỏ dở - lúc ấy mọi nút bỏ tắt để khỏi bấm hai lần; việc ĐÃ áp thì máy chủ từ chối nên nút bỏ không cần khoá theo sách chạy.
Item {
    id: root
    objectName: "pendingList"
    property var items: []
    property string dropping: ""
    property bool showLines: true
    property var voiceTry: null
    signal dropRequested(var item)
    signal tryRequested(var item)
    implicitHeight: Math.min(288, scroll.contentHeight)
    height: implicitHeight

    function sync() { entries.update((root.items || []).map(function(item) { return Object.assign({id: Logic.pendingKey(item)}, item) })) }
    onItemsChanged: sync()
    Component.onCompleted: sync()
    DevicesRows { id: entries }

    Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: column
            width: scroll.width
            Repeater {
                model: entries.model
                PendingRow {
                    id: row
                    required property int index
                    required property var model
                    width: column.width
                    rows: entries
                    rowId: model.rowId
                    json: model.json
                    present: model.present
                    fresh: model.fresh
                    first: entries.revision >= 0 && entries.presentBefore(row.index) === 0
                    dropping: root.dropping
                    showLines: root.showLines
                    voiceTry: root.voiceTry
                    onDropRequested: item => root.dropRequested(item)
                    onTryRequested: item => root.tryRequested(item)
                }
            }
        }
        SmoothWheel { flick: scroll }
    }
    Scrollbar { target: scroll }
}
