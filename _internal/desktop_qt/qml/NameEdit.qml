import QtQuick
import ABook
import "NameLogic.js" as N
import "StudioLogic.js" as Studio

// Ô sửa một cách đọc tên (EditReading của NameReadings.tsx): ô nhập + "Huỷ" + "Nghe thử" + "Lưu" + ô "Dùng cho mọi sách", lời của nút nghe thử, lý do lưu không được, lỗi máy chủ
// (kèm bản sửa mời dùng). Lưu là ghi MONG MUỐN - dây chuyền áp ở ranh giới chương rồi thu lại đúng những câu có tên ấy. Ô hiện như dòng bên cạnh (chữ đầu mỗi từ viết hoa); lưu mà chỉ
// khác hoa thường thì gửi đúng cách đang lưu (asStored), không thành một thay đổi bắt thu lại. Là một lớp Back: Esc / Back đóng ô. Tên đã có trong cách đọc chung thì ô tự tích.
Column {
    id: root
    objectName: "nameEdit"
    property var work: null
    property var item: ({})
    property bool fresh: false
    property var reach: null                    // chữ vừa gõ để thêm: nó chạm tới những câu nào
    property bool saving: false
    property string problem: ""
    property string suggestion: ""
    property bool everywhere: false
    signal done()

    readonly property string typed: field.text.trim()
    readonly property var sharedEntry: N.sharedEntry(work && work.shared.data ? work.shared.data.entries : [], item.surface || "")
    readonly property bool never: reach && reach.never !== undefined ? Boolean(reach.never) : Boolean(item.never)
    readonly property string current: item.requested !== null && item.requested !== undefined ? item.requested : (item.spoken || "")
    readonly property bool canSave: typed !== "" && !never && (fresh || everywhere || N.asStored(item, typed) !== current)
    onSharedEntryChanged: if (sharedEntry) everywhere = true

    function save(spoken) {
        if (saving) return
        saving = true
        work.saveName(item, spoken, everywhere, function(message, hint) {
            root.saving = false
            if (message === "") root.finish()
            else { root.problem = message; root.suggestion = hint }
        })
    }
    function use(spoken) { field.text = spoken; problem = ""; suggestion = ""; save(spoken) }
    // Đóng ô: rời ngăn xếp Back ngay (không đợi ô khép xong) rồi báo dòng chứa nó
    function finish() { Nav.closedLayer(backLayer); done() }
    function submit() { if (canSave) save(N.asStored(item, typed)) }
    Component.onCompleted: {
        everywhere = Boolean(sharedEntry)
        field.text = Studio.shownReading(current)
        field.forceActiveFocus()
        Nav.openLayer(backLayer)
    }
    Component.onDestruction: Nav.closedLayer(backLayer)
    property QtObject backLayer: QtObject { function close() { root.finish() } }

    spacing: 4
    Flow {
        width: parent.width
        spacing: 8
        WorkField {
            id: field
            objectName: "nameField"
            width: root.width < 400 ? root.width : 176
            label: "Cách đọc mới cho " + root.item.surface
            placeholderText: "vd Hên-khơ"
            invalid: root.problem !== ""
            escapeLocal: true
            onEscaped: root.finish()
            onAccepted: root.submit()
            onTextChanged: { root.problem = ""; root.suggestion = "" }
        }
        // "Huỷ" trước "Lưu": nút ở đúng chỗ nút "Sửa" vừa bấm là "Lưu" (mờ khi chưa đổi gì) - bấm đúp không huỷ ngay
        Button { objectName: "nameCancel"; size: "sm"; kind: "ghost"; text: "Huỷ"; onClicked: root.finish() }
        TryButton { objectName: "nameTry"; reading: tryIt }
        Button {
            objectName: "nameSave"
            size: "sm"
            text: "Lưu"
            busy: root.saving
            enabled: root.canSave
            onActivated: root.save(N.asStored(root.item, root.typed))
        }
    }
    Row {
        spacing: 8
        height: 28
        ImportBox {
            id: box
            objectName: "nameEverywhere"
            anchors.verticalCenter: parent.verticalCenter
            checked: root.everywhere
            label: "Dùng cho mọi sách"
            onToggled: value => root.everywhere = value
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Dùng cho mọi sách"
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
            TapHandler { onTapped: root.everywhere = !root.everywhere }
        }
    }
    TryNote { reading: tryIt; width: parent.width }
    Text {
        objectName: "nameNever"
        visible: root.never
        width: parent.width
        text: N.neverText(root.item.surface || "")
        color: Theme.warning
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
    }
    ReadingProblem { width: parent.width; problem: root.problem; suggestion: root.suggestion; onUsed: spoken => root.use(spoken) }
    TryReading {
        id: tryIt
        work: root.work
        surface: root.item.surface || ""
        spoken: root.typed
        blocked: root.problem !== ""
        onRejected: (message, hint) => { root.problem = message; root.suggestion = hint }
    }
}
