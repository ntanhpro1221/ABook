import QtQuick
import ABook
import "MyMusicText.js" as Music

// Một bài trong "Nhạc của tôi" (hàng của MyMusicSection + AutoPickNote của bản web): nốt nhạc, "tên · nghệ sĩ · m:ss", dòng tự chọn (nhãn + nút đổi), và
// "Xoá" -> "Xoá bài" / "Giữ lại" (hai bước). Hàng vào / ra bằng chiều cao (useListPresence): `leaving` khép hàng lại trước khi gỡ.
Collapse {
    id: root
    property var track: ({})
    property bool canImport: true
    property bool confirming: false     // đang hỏi lại xoá bài này
    property bool removing: false       // đang gửi lệnh xoá
    property bool leaving: false
    property bool entered: false
    property bool first: false
    property bool picking: false        // đang gửi công tắc tự chọn
    property bool canPreview: false     // tab Nhạc nền của Studio có "Nghe thử" ở mỗi bài; Cài đặt thì không
    property bool previewing: false
    signal preview()
    signal askRemove()
    signal keep()
    signal remove()
    signal pick(var next)
    open: entered && !leaving
    Component.onCompleted: Later.call(root, function() { root.entered = true })

    readonly property var switcher: Music.autoSwitch(track)
    readonly property string note: Music.autoLabel(track) || Music.analysisLabel(track)
    readonly property string line: {
        const dim = Qt.color(Theme.text2).toString()
        let html = Music.escapeHtml(track.title || "")
        if (track.creator) html += "<font color=\"" + dim + "\"> · " + Music.escapeHtml(track.creator) + "</font>"
        if (track.duration) html += "<font color=\"" + dim + "\"> · " + Music.formatClock(track.duration) + "</font>"
        return html
    }

    Item {
        width: parent.width
        height: Math.max(words.height, buttons.height) + 16 + 1
        Rectangle { width: parent.width; height: 1; color: Theme.line; visible: !root.first }
        Item {
            id: row
            y: 1 + 8
            width: parent.width
            height: Math.max(words.height, buttons.height)
            Icon { id: noteIcon; y: 2; name: "eighth-note"; size: 16; color: Theme.accentText }
            Column {
                id: words
                x: noteIcon.width + 6
                width: row.width - x - (buttons.width > 0 ? buttons.width + 12 : 0)
                Text {
                    width: parent.width
                    text: root.line
                    textFormat: Text.StyledText
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                    font.features: {"tnum": 1}
                }
                Flow {
                    width: parent.width
                    topPadding: 2
                    spacing: 8
                    Text { id: noteText; text: root.note; color: Theme.text2; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; width: Math.min(implicitWidth, parent.width); font.pixelSize: Theme.sizeCaption; height: 24; verticalAlignment: Text.AlignVCenter }
                    Interactive {
                        id: switchButton
                        width: switchLabel.implicitWidth + 16
                        height: 24
                        opacity: root.picking ? 0.45 : 1
                        Accessible.role: Accessible.Button
                        Accessible.name: root.switcher.text + ": " + (root.track.title || "")
                        onClicked: if (!root.picking) root.pick(root.switcher.next)
                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.radiusControl
                            color: Theme.hover
                            opacity: switchButton.hovered || switchButton.pressed ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                        }
                        Text {
                            id: switchLabel
                            anchors.centerIn: parent
                            text: root.switcher.text
                            color: Theme.accentText
                            font.pixelSize: Theme.sizeCaption
                            font.weight: Theme.weightMedium
                        }
                    }
                }
            }
            // Nút bên phải: "Xoá" co lại về 0 trong khi "Xoá bài" + "Giữ lại" mở ra (chiều ngang tween)
            Row {
                id: buttons
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                visible: root.canImport || root.canPreview
                width: (root.canPreview ? listen.width + (root.canImport ? spacing : 0) : 0)
                       + (root.canImport ? (ask.width + confirm.width + (ask.width > 0 && confirm.width > 0 ? spacing : 0)) : 0)
                Button {
                    id: listen
                    objectName: "musicPreview"
                    visible: root.canPreview
                    text: root.previewing ? "Dừng nghe" : "Nghe thử"
                    icon: root.previewing ? "square" : "play"
                    kind: "ghost"; size: "sm"
                    Accessible.name: text + ": " + (root.track.title || "")
                    onActivated: root.preview()
                }
                Item {
                    id: ask
                    visible: root.canImport
                    width: root.confirming ? 0 : askButton.implicitWidth
                    height: askButton.implicitHeight
                    clip: true
                    Behavior on width { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                    opacity: root.confirming ? 0 : 1
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                    Button {
                        id: askButton
                        text: "Xoá"; icon: "trash"; kind: "ghost"; size: "sm"
                        enabled: !root.confirming
                        Accessible.name: "Xoá: " + (root.track.title || "")
                        onClicked: root.askRemove()
                    }
                }
                Item {
                    id: confirm
                    visible: root.canImport
                    width: root.confirming ? confirmRow.implicitWidth : 0
                    height: confirmRow.implicitHeight
                    clip: true
                    Behavior on width { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                    opacity: root.confirming ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                    Row {
                        id: confirmRow
                        spacing: 4
                        Button {
                            id: removeButton
                            text: "Xoá bài"; icon: "trash"; kind: "ghost"; size: "sm"
                            busy: root.removing
                            enabled: root.confirming
                            Accessible.name: "Xoá bài: " + (root.track.title || "")
                            onActivated: root.remove()
                        }
                        Button {
                            text: "Giữ lại"; kind: "ghost"; size: "sm"
                            enabled: root.confirming && !root.removing
                            Accessible.name: "Giữ lại: " + (root.track.title || "")
                            onClicked: root.keep()
                        }
                    }
                }
            }
        }
    }
}
