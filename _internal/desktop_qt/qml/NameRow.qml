import QtQuick
import ABook
import "NameLogic.js" as N
import "StudioLogic.js" as Studio
import "WorkLogic.js" as W

// Một dòng của "Cách đọc tên" (ReadingRow của NameReadings.tsx): nút nghe câu mẫu, tên + "đọc là “…”", dòng nhỏ (bao nhiêu câu · đã chọn / máy đoán, dùng chung, cách đọc chờ áp dụng) và
// nút "Sửa" mở ô sửa tại chỗ (NameEdit). `fresh`: chữ người nghe vừa gõ để thêm (chưa có dòng) - dòng nhỏ nói nó chạm tới bao nhiêu câu, bao nhiêu câu đã thu phải thu lại.
Item {
    id: root
    objectName: "nameRow"
    property var work: null
    property var item: ({})
    property bool fresh: false
    property bool editing: false
    property string asked: ""
    readonly property string surface: item.surface || ""
    readonly property var example: item.example || null
    readonly property string clipId: example ? "reading-" + example.segmentId : ""
    readonly property bool playing: clipId !== "" && Clip.current === clipId
    readonly property var reach: reachQuery.data
    readonly property bool sharedHere: Boolean(N.sharedEntry(work && work.shared.data ? work.shared.data.entries : [], surface, item.requested !== null && item.requested !== undefined ? item.requested : item.spoken))
    readonly property bool sideEdit: editing ? width >= 760 : width >= 420
    readonly property real sideWidth: editing ? 384 : editButton.width
    readonly property real infoWidth: Math.max(120, width - 56 - 12 - (sideEdit ? sideWidth + 12 : 0))
    readonly property real tailHeight: Math.max(editButton.height * (1 - editor.reveal), editor.height)
    readonly property string statusHtml: W.esc(N.rowStatus(item, work ? work.analyzed : true, fresh, reach, false))
        + (sharedHere ? "<span style=\"color:" + W.cssColor(Theme.text3) + "\"> · dùng chung</span>" : "")
        + (item.requested ? "<span style=\"color:" + W.cssColor(Theme.accentText) + "; font-weight:600\">" + W.esc(N.waitingPart(item)) + "</span>" : "")
    width: parent ? parent.width : 600
    height: 10 + Math.max(32, info.height, sideEdit ? tail.height : 0) + (sideEdit ? 0 : 8 + tail.height) + 10
    onSurfaceChanged: { if (fresh) { settle.restart(); if (editing) editing = false } }
    Component.onCompleted: asked = surface.trim()

    // Gõ xong mới hỏi (mỗi phím một lượt hỏi là phí)
    Timer { id: settle; interval: 350; onTriggered: root.asked = root.surface.trim() }
    StudioQuery {
        id: reachQuery
        store: root.work ? root.work.store : null
        path: root.fresh && root.asked !== "" && root.work ? root.work.path("/pronunciations/reach?surface=" + encodeURIComponent(root.asked)) : ""
        wanted: root.fresh && root.asked !== "" && root.work !== null
    }

    // Ô sửa đóng lại thì tiêu điểm trả về nút "Sửa" của chính dòng ấy - chỉ khi tiêu điểm đang rơi vào khoảng trống hay còn trong ô sửa (đã bấm sang chỗ khác thì không giành lại)
    function closeEditor() {
        editing = false
        const focus = Window.window ? Window.window.activeFocusItem : null
        let inside = !focus || focus === Window.window.contentItem
        for (let n = focus; n && !inside; n = n.parent) if (n === editor) inside = true
        if (inside) editButton.forceActiveFocus()
    }

    // Nghe câu mẫu có tên ấy (câu đã thu nếu có)
    Interactive {
        id: sample
        objectName: "nameSample"
        visible: Boolean(root.example && root.example.hasAudio)
        x: 12
        y: 10
        width: 32
        height: 32
        ringRadius: 16
        tip: root.example ? root.example.chapterTitle + " · câu " + root.example.seq : ""
        Accessible.role: Accessible.Button
        Accessible.name: root.playing ? "Dừng" : root.example ? N.sampleLabel(root.item) : ""
        onClicked: Clip.toggle(root.clipId, root.work.store.path("/media/books/" + root.work.bookId + "/samples/" + root.example.segmentId))
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: sample.hovered || sample.pressed ? Theme.line : Theme.hover
            Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        }
        Icon { anchors.centerIn: parent; name: "play"; size: 14; color: sample.hovered ? Theme.text : Theme.text2; opacity: root.playing ? 0 : 1; Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } } }
        Icon { anchors.centerIn: parent; name: "pause"; size: 14; color: sample.hovered ? Theme.text : Theme.text2; opacity: root.playing ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } } }
    }

    Column {
        id: info
        x: 56
        y: 10
        width: root.infoWidth
        Text {
            objectName: "nameTitle"
            width: parent.width
            textFormat: Text.RichText
            text: "<b>" + W.esc(root.surface) + "</b>"
                + (root.item.spoken ? " <span style=\"color:" + W.cssColor(Theme.text2) + "; font-size:14px\">đọc là</span> <span style=\"font-weight:500\">“" + W.esc(Studio.shownReading(root.item.spoken)) + "”</span>" : "")
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: 16
        }
        Text {
            objectName: "nameStatus"
            width: parent.width
            textFormat: Text.RichText
            text: root.statusHtml
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }

    Item {
        id: tail
        x: root.sideEdit ? root.width - 12 - root.sideWidth : 56
        y: root.sideEdit ? 10 : 10 + info.height + 8
        width: root.sideEdit ? root.sideWidth : root.width - 56 - 12
        height: root.tailHeight
        Button {
            id: editButton
            objectName: "nameEdit"
            size: "sm"
            kind: "ghost"
            wrap: true
            width: Math.min(implicitWidth, root.width - 68)
            visible: opacity > 0
            opacity: 1 - editor.reveal
            text: N.addLabel(root.item, root.fresh)
            Accessible.name: N.editLabel(root.item, root.fresh)
            onClicked: root.editing = true
        }
        Collapse {
            id: editor
            width: parent.width
            open: root.editing
            Loader {
                width: parent.width
                active: root.editing || !editor.settled
                sourceComponent: Component {
                    NameEdit {
                        work: root.work
                        item: root.item
                        fresh: root.fresh
                        reach: root.fresh ? root.reach : null
                        onDone: root.closeEditor()
                    }
                }
            }
        }
    }
}
