import QtQuick
import ABook
import "ExportLogic.js" as Logic

// Hộp "Áp dụng N thay đổi?" (ApplyChangesDialog của studio/ApplyChanges.tsx): liệt kê đủ từng thay đổi đang chờ bằng lời (máy chủ: store.pending_details), mỗi dòng bỏ được ngay
// tại đây; đổi giọng nghe thử được trên một câu của chính người ấy; dòng cuối nói thu lại bao nhiêu câu ở chương nào và mất chừng bao lâu. Sách đang chạy (`running`) thì máy tự
// áp ở ranh giới chương kế nên KHÔNG có nút "Áp dụng" - chỉ xem và bỏ được việc chưa áp. `book` là bản sống của dự án (số thay đổi giảm khi bỏ).
StudioConfirm {
    id: root
    objectName: "applyChanges"
    property var store: null
    property var snapshot: ({})
    property var live: null
    readonly property var book: live && live.id === snapshot.id ? live : snapshot
    property var data: null
    property string dropping: ""
    readonly property string bookId: book.id || ""
    readonly property int count: book.pendingChanges || 0
    readonly property string running: Logic.applyRunning(book)
    readonly property alias voiceTry: tryVoice
    signal applied()

    panelWidth: 560
    title: Logic.applyHeading(count, running !== "")
    description: Logic.applyDescription(running !== "")
    actions: running !== ""
        ? [{key: "later", text: Logic.applyClose(true), kind: "ghost"}]
        : [{key: "later", text: Logic.applyClose(false), kind: "ghost"}, {key: "go", text: "Áp dụng", icon: "refresh-cw", kind: "primary"}]
    onChosen: key => {
        if (key === "go") { dismiss(); applied() }
        else close()
    }
    onClosed: { Clip.stop(); tryVoice.reset() }
    onCountChanged: if (open) load()

    function begin(opened) {
        snapshot = opened
        data = null
        dropping = ""
        show()
        load()
    }
    // Đọc lại danh sách (số trên nút đổi khi bỏ một mục: queryKey của bản web có `count`)
    function load() {
        if (!store || bookId === "") return
        const id = bookId
        store.quiet("GET", "/api/books/" + id + "/pending-changes", null, function(result, error) { if (!error && id === root.bookId) root.data = result })
    }
    // Bỏ một mục ngay tại đây; mọi màn đọc lại (số trên nút, Việc cần duyệt, Kịch bản)
    function drop(item) {
        dropping = Logic.pendingKey(item)
        const remaining = count
        store.quiet("POST", "/api/books/" + bookId + "/pending-changes/withdraw", {section: item.section, key: item.key, keys: item.keys, requestedAt: item.requestedAt}, function(result, error) {
            root.dropping = ""
            if (error) { root.store.say("Chưa bỏ được thay đổi này", error); return }
            if (remaining <= 1) root.dismiss()
            root.store.refresh(root.bookId)
            root.load()
        })
    }
    function tryItem(item) { tryVoice.ask(item.voice, item.voiceLabel || "mới", Logic.pendingKey(item), null) }

    VoiceTry { id: tryVoice; store: root.store; bookId: root.bookId }

    Collapse {
        objectName: "applyLoading"
        width: parent.width
        open: root.data === null
        Text { width: parent.width; text: "Đang xem các thay đổi…"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
    }
    Collapse {
        objectName: "applyBody"
        width: parent.width
        open: root.data !== null
        spacing: 12
        PendingList {
            width: parent.width
            items: root.data ? root.data.items || [] : []
            dropping: root.dropping
            voiceTry: tryVoice
            onDropRequested: item => root.drop(item)
            onTryRequested: item => root.tryItem(item)
        }
        // Máy đang làm gì với câu thử / đã đọc câu nào / vì sao chưa nghe được (giữ chữ cũ lúc dòng khép lại)
        Collapse {
            width: parent.width
            open: tryVoice.said !== null
            Text {
                id: sayText
                objectName: "applyTryNote"
                property var kept: ({text: "", status: false})
                Connections { target: tryVoice; function onSaidChanged() { if (tryVoice.said) sayText.kept = tryVoice.said } }
                width: parent.width
                text: kept.text
                color: kept.status ? Theme.text2 : Theme.text3
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeCaption
            }
        }
        Text {
            objectName: "applySummary"
            width: parent.width
            text: root.data ? Logic.applySummary(root.data) : ""
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
}
