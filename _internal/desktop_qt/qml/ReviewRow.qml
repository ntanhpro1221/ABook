import QtQuick
import ABook
import "ReviewLogic.js" as R
import "WorkLogic.js" as W

// Một hàng "Cần nghe lại" (Row của ReviewQueue.tsx): nút nghe 40 (hoặc dấu nói thẳng vì sao không nghe được), câu, MỘT dòng lý do · chương (lý do mang màu mức nặng), điều máy nghe ra
// khi KHÁC câu, cách đọc đang chờ áp, "Sửa cách đọc" / "Mở Kịch bản", và hai phán quyết Ổn / Cần thu lại. Rộng thì phán quyết nằm bên phải, hẹp thì xuống dưới câu thẳng mép chữ.
// Hàng đã có cách xử lý thì mờ đi (chưa xem -> đã xem), trừ lúc đang sửa chữ.
Item {
    id: root
    objectName: "reviewRow"
    property var work: null
    property var item: ({})
    property var twins: []
    property bool editing: false
    signal verdict(var value)
    signal openScript(int chapterId, string stableId)
    signal spoken()

    readonly property string key: item.stableId || ""
    readonly property string clipId: "review-" + item.segmentId
    readonly property var source: work && work.store ? R.clipOf(item, work.bookId, work.store.path) : null
    readonly property bool handled: R.handled(item)
    readonly property bool wide: width >= 560
    readonly property string unplayable: R.unplayableText(item)
    readonly property bool playing: Clip.current === clipId
    readonly property real verdictsWidth: (okButton.visible ? okButton.implicitWidth + 4 : 0) + redoButton.implicitWidth
    readonly property color reasonInk: { const tone = R.reasonTone(item.kind); return tone === "danger" ? Theme.danger : tone === "warning" ? Theme.warning : Theme.text2 }
    readonly property real textWidth: Math.max(120, width - 64 - 12 - (wide ? verdictsWidth + 8 : 0))
    width: parent ? parent.width : 600
    height: 12 + Math.max(40, details.height + (wide ? 0 : 4 + verdicts.height)) + 12
    opacity: handled && !editing ? 0.7 : 1
    Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }

    // Tiêu điểm vào nút bấm được đầu tiên của hàng (nút nghe, không có thì phán quyết)
    function focusFirst() { (play.visible ? play : redoButton).forceActiveFocus() }

    HoverHandler { id: hover }
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.hover
        opacity: hover.hovered && !(root.handled && !root.editing) ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    }

    // Một nút chữ nhỏ có biểu tượng, mực phụ (ngữ cảnh phụ: để hai phán quyết giữ vai chính)
    component LinkAction: Interactive {
        id: link
        property string text: ""
        property string icon: ""
        implicitWidth: lead.width + 4 + word.implicitWidth
        implicitHeight: Math.max(Theme.hit, word.height + 8)
        width: Math.min(implicitWidth, parent ? parent.width : implicitWidth)
        Accessible.role: Accessible.Button
        Accessible.name: text
        Icon { id: lead; anchors.verticalCenter: parent.verticalCenter; name: link.icon; size: 14; color: link.hovered ? Theme.text : Theme.text2 }
        Text {
            id: word
            x: lead.width + 4
            width: parent.width - x
            anchors.verticalCenter: parent.verticalCenter
            text: link.text
            color: link.hovered ? Theme.text : Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
            font.weight: Theme.weightMedium
            font.underline: link.hovered
        }
    }

    Interactive {
        id: play
        objectName: "reviewPlay"
        visible: root.source !== null
        x: 12
        y: 12
        width: 40
        height: 40
        ringRadius: 20
        Accessible.role: Accessible.Button
        Accessible.name: root.playing ? "Dừng" : "Nghe câu: " + (root.item.text || "")
        onClicked: if (root.source) Clip.toggle(root.clipId, root.source.src, root.source.start, root.source.end)
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: root.playing ? Theme.accent : play.hovered || play.pressed ? Theme.line : Theme.hover
            Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        }
        Icon {
            anchors.centerIn: parent
            name: "play"
            size: 16
            color: Theme.text
            opacity: root.playing ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        }
        Icon {
            anchors.centerIn: parent
            name: "loader-circle"
            size: 16
            color: Theme.accentInk
            opacity: root.playing && Clip.loading ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
            RotationAnimator on rotation { running: root.playing && Clip.loading && Nav.uiVisible && !Theme.reduceMotion; from: 0; to: 360; duration: 1000; loops: Animation.Infinite }
        }
        Icon {
            anchors.centerIn: parent
            name: "audio-lines"
            size: 16
            color: Theme.accentInk
            opacity: root.playing && !Clip.loading ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        }
    }
    // Không có gì để nghe thì không có nút nhìn như bấm được: một dấu nói thẳng lý do (câu hỏng / đã dọn bản thu)
    Rectangle {
        objectName: "reviewMute"
        visible: root.source === null
        x: 12
        y: 12
        width: 40
        height: 40
        radius: width / 2
        color: root.item.kind === "failed" ? Theme.dangerSoft : Theme.hover
        Accessible.role: Accessible.Graphic
        Accessible.name: root.unplayable
        Icon { anchors.centerIn: parent; name: root.item.kind === "failed" ? "triangle-alert" : "volume-x"; size: 16; color: root.item.kind === "failed" ? Theme.danger : Theme.text3 }
    }

    Column {
        id: details
        x: 64
        y: 12
        width: root.textWidth
        spacing: 0
        Text {
            objectName: "reviewText"
            width: parent.width
            text: root.item.text || ""
            color: Theme.text
            wrapMode: Text.Wrap
            lineHeight: 1.375
            font.pixelSize: 16
        }
        // Câu trước, rồi MỘT dòng nói vì sao nó ở đây (lý do · chương); lý do mang màu mức nặng
        Text {
            objectName: "reviewReason"
            width: parent.width
            topPadding: 4
            textFormat: Text.RichText
            text: "<span style=\"color:" + W.cssColor(root.reasonInk) + "\">" + W.esc(root.item.reason || "") + "</span> · " + W.esc(root.item.chapterTitle || "")
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        // Máy nghe ra đúng chữ thì không có gì để so - chỉ hiện khi KHÁC câu
        Item {
            objectName: "reviewHeard"
            visible: R.showsHeard(root.item)
            width: parent.width
            height: visible ? heard.height + 4 : 0
            Icon { x: 0; y: 6; name: "ear"; size: 14; color: Theme.text2 }
            Text {
                id: heard
                x: 18
                y: 4
                width: parent.width - 18
                textFormat: Text.RichText
                text: W.esc(R.heardLine(root.item)) + "<span style=\"color:" + W.cssColor(Theme.text3) + "\">" + W.esc(R.similarityText(root.item)) + "</span>"
                color: Theme.text2
                wrapMode: Text.Wrap
                lineHeight: 1.3
                font.pixelSize: 13
            }
        }
        Text {
            objectName: "reviewUnplayable"
            visible: root.source === null
            width: parent.width
            topPadding: 4
            text: root.unplayable + "."
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        Item {
            objectName: "reviewPending"
            visible: root.item.pendingSpoken !== null && root.item.pendingSpoken !== undefined
            width: parent.width
            height: visible ? pending.height + 4 : 0
            Icon { x: 0; y: 5; name: "clock"; size: 14; color: Theme.text2 }
            Text {
                id: pending
                x: 20
                y: 4
                width: parent.width - 20
                textFormat: Text.RichText
                text: root.item.pendingSpoken
                    ? "Sẽ đọc là “<span style=\"color:" + W.cssColor(Theme.text) + "\">" + W.esc(root.item.pendingSpoken) + "</span>” - " + W.esc(root.work ? root.work.pendingNote : "") + "."
                    : "Sẽ đọc lại đúng chữ sách - " + W.esc(root.work ? root.work.pendingNote : "") + "."
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
        }
        Text {
            objectName: "reviewSpoken"
            visible: (root.item.pendingSpoken === null || root.item.pendingSpoken === undefined) && Boolean(root.item.spoken)
            width: parent.width
            topPadding: 4
            textFormat: Text.RichText
            text: "Đang đọc là: <span style=\"color:" + W.cssColor(Theme.text) + "\">" + W.esc(root.item.spoken || "") + "</span>"
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        Collapse {
            id: editor
            width: parent.width
            open: root.editing
            Loader {
                width: parent.width
                active: root.editing || !editor.settled
                sourceComponent: Component {
                    ReviewSpoken {
                        work: root.work
                        item: root.item
                        twins: root.twins
                        onFinished: saved => { root.editing = false; if (saved !== null) root.spoken() }
                    }
                }
            }
        }
        Collapse {
            id: links
            width: parent.width
            open: !root.editing
            Flow {
                width: parent.width
                topPadding: 6
                spacing: 16
                LinkAction {
                    objectName: "reviewEdit"
                    visible: Boolean(root.item.textSha256)
                    icon: "pen-line"
                    text: R.spokenEditLabel(root.twins.length)
                    onClicked: root.editing = true
                }
                LinkAction {
                    objectName: "reviewScript"
                    visible: root.item.verdict === "redo" || root.item.kind === "failed"
                    icon: "file-text"
                    text: "Mở Kịch bản"
                    onClicked: root.openScript(root.item.chapterId, root.item.stableId)
                }
            }
        }
    }

    // Hai phán quyết là việc chính của hàng. Không có gì để nghe thì không phán "Ổn" được - chỉ còn thu lại.
    Flow {
        id: verdicts
        objectName: "reviewVerdicts"
        x: root.wide ? root.width - root.verdictsWidth : 50
        y: root.wide ? 12 : 12 + details.height + 4
        width: root.wide ? root.verdictsWidth : root.width - 62
        spacing: 4
        ReviewVerdict {
            id: okButton
            objectName: "verdictOk"
            visible: root.source !== null
            text: "Ổn"
            icon: "check"
            tone: "ok"
            on: root.item.verdict === "ok"
            onClicked: root.verdict(root.item.verdict === "ok" ? null : "ok")
        }
        ReviewVerdict {
            id: redoButton
            objectName: "verdictRedo"
            text: root.source !== null ? "Cần thu lại" : "Thu lại câu này"
            icon: "rotate-ccw"
            tone: "redo"
            on: root.item.verdict === "redo"
            onClicked: root.verdict(root.item.verdict === "redo" ? null : "redo")
        }
    }
}
