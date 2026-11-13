import "UiStrings.js" as S
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
                if (!root.work.ok(status)) { root.busy = false; root.work.fail(S.s_chua_ghi_duoc_9fa87a7d, status, data); return }
                step++
                next()
            })
        }
        next()
    }
    Component.onCompleted: { field.text = item.pendingSpoken !== null && item.pendingSpoken !== undefined ? item.pendingSpoken : (item.spoken !== null && item.spoken !== undefined ? item.spoken : item.text); field.forceActiveFocus() }

    spacing: 0
    Item { width: 1; height: 8 }
    Text { width: parent.width; text: S.s_may_doc_cau_nay_thanh_b4750403; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
    Item { width: 1; height: 4 }
    FormField {
        id: field
        objectName: "spokenField"
        width: parent.width
        label: S.s_may_doc_cau_nay_thanh_b4750403
        topPadding: 8
        bottomPadding: 8
        implicitHeight: Math.max(36, contentHeight + 16)
        escapeLocal: true
        onEscaped: root.finished(null)
        onAccepted: if (root.typed !== "" || root.item.spoken) root.save([root.item])
    }
    Text { width: parent.width; topPadding: 4; text: S.s_viet_cach_doc_thanh_tieng_de_trong_de_dung_0f9e441a; color: Theme.text3; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
    Flow {
        width: parent.width
        topPadding: 8
        spacing: 8
        Button {
            objectName: "spokenSave"
            size: "sm"
            text: S.s_luu_e91f26c0
            busy: root.busy
            enabled: root.typed !== "" || Boolean(root.item.spoken)
            onActivated: root.save([root.item])
        }
        Button {
            objectName: "spokenSaveAll"
            Reveal { shown: root.twins.length > 0 }
            size: "sm"
            kind: "ghost"
            text: S.s_luu_8c00346c + (root.twins.length + 1) + S.s_cau_b07e1008
            enabled: !root.busy
            onClicked: root.save([root.item].concat(root.twins))
        }
        Button { objectName: "spokenCancel"; size: "sm"; kind: "ghost"; text: S.s_huy_96732485; enabled: !root.busy; onClicked: root.finished(null) }
    }
    Item { width: 1; height: 4 }
}
