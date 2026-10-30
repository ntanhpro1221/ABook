import QtQuick
import ABook
import "ReviewLogic.js" as R

// Sửa chữ đem đọc ngay trên hàng (SpokenEditor): câu tượng thanh ("Tách tách tách", "Coong…") hay chữ lạ hỏng sau mọi lần thử thì thu lại y chữ cũng hỏng y như cũ - viết lại thành
// chữ máy đọc được mới chữa được. Chữ của sách không đổi; câu được thu lại bằng chữ mới khi sách chạy tiếp. Câu giống hệt (tượng thanh hay lặp) sửa một lần cho cả nhóm.
Column {
    id: root
    property var work: null
    property var item: ({})
    property var twins: []
    property bool busy: false
    readonly property string typed: field.text.trim()
    signal finished(var saved)                  // chữ đã ghi ("" = trả về chữ sách), null = huỷ

    function save(lines) {
        if (busy) return
        busy = true
        const spoken = typed === String(item.text).trim() ? "" : typed
        let step = 0
        function next() {
            if (step >= lines.length) {
                root.busy = false
                root.work.say(R.spokenSaved(lines.length))
                root.finished(spoken)
                return
            }
            const line = lines[step]
            root.work.post("/line", {stableId: line.stableId, textSha256: line.textSha256, spoken: spoken}, function(status, data) {
                if (!root.work.ok(status)) { root.busy = false; root.work.fail("Chưa ghi được", status, data); return }
                step++
                next()
            })
        }
        next()
    }
    Component.onCompleted: { field.text = item.pendingSpoken !== null && item.pendingSpoken !== undefined ? item.pendingSpoken : (item.spoken !== null && item.spoken !== undefined ? item.spoken : item.text); field.forceActiveFocus() }

    spacing: 0
    Item { width: 1; height: 8 }
    Text { width: parent.width; text: "Máy đọc câu này thành"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
    Item { width: 1; height: 4 }
    FormField {
        id: field
        objectName: "spokenField"
        width: parent.width
        label: "Máy đọc câu này thành"
        topPadding: 8
        bottomPadding: 8
        implicitHeight: Math.max(36, contentHeight + 16)
        escapeLocal: true
        onEscaped: root.finished(null)
        onAccepted: if (root.typed !== "" || root.item.spoken) root.save([root.item])
    }
    Text { width: parent.width; topPadding: 4; text: "Viết cách đọc thành tiếng; để trống để dùng chữ gốc."; color: Theme.text3; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
    Flow {
        width: parent.width
        topPadding: 8
        spacing: 6
        Button {
            objectName: "spokenSave"
            size: "sm"
            text: "Lưu"
            busy: root.busy
            enabled: root.typed !== "" || Boolean(root.item.spoken)
            onActivated: root.save([root.item])
        }
        Button {
            objectName: "spokenSaveAll"
            visible: root.twins.length > 0
            size: "sm"
            kind: "ghost"
            text: "Lưu " + (root.twins.length + 1) + " câu"
            enabled: !root.busy
            onClicked: root.save([root.item].concat(root.twins))
        }
        Button { objectName: "spokenCancel"; size: "sm"; kind: "ghost"; text: "Huỷ"; enabled: !root.busy; onClicked: root.finished(null) }
    }
    Item { width: 1; height: 4 }
}
