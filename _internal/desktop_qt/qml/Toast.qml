import QtQuick
import ABook

// Lời báo của app (Toaster của desktop/App.tsx, sonner): thẻ mặt nổi ở góc trên bên phải, dòng đầu là tiêu đề, phần sau dòng đầu là mô tả mực phụ,
// nút việc ("Hoàn tác", "Mở thư mục": nền hổ phách, chữ mực-trên-nhấn) và nút ✕ "Đóng thông báo". Tự khép sau `Api.noticeDuration` (mặc định
// 4 giây như sonner), rê chuột vào thì dừng đếm. Mở: trượt xuống 16 px + thu phóng 0,96 -> 1; khép: ngược lại nhanh hơn (giảm chuyển động: chỉ mờ).
// Giữ chữ cũ trong lúc khép để không nhấp nháy; lời mới tới khi đang mở thì thay chỗ và đếm lại.
Item {
    id: root
    objectName: "toast"
    readonly property int defaultDuration: 4000
    property string slot: ""
    readonly property string noticeText: slot === "edited-elsewhere" ? (Api.elsewhereNotice ? Api.elsewhereNotice.text : "") : Api.notice
    readonly property bool shown: noticeText !== ""
    property string title: ""
    property string description: ""
    property var action: null
    property int duration: defaultDuration
    property real t: shown ? 1 : 0
    width: 356
    height: card.height
    visible: t > 0
    enabled: shown

    function take() {
        const lines = noticeText.split("\n")
        title = lines[0]
        description = lines.slice(1).join("\n")
        const message = slot === "edited-elsewhere" ? Api.elsewhereNotice : {action: Api.noticeAction, duration: Api.noticeDuration}
        action = message.action
        duration = message.duration > 0 ? message.duration : defaultDuration
        clock.restart()
    }
    Connections {
        target: Api
        function onNoticeChanged() { if (!root.slot) { if (root.shown) root.take(); else clock.stop() } }
        function onElsewhereNoticeChanged() { if (root.slot === "edited-elsewhere") { if (root.shown) root.take(); else clock.stop() } }
    }
    Component.onCompleted: if (shown) take()

    Behavior on t {
        NumberAnimation {
            duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : (root.shown ? Theme.motionMedium : Theme.motionFastOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.shown ? Theme.easeDecelerate : Theme.easeAccelerate
        }
    }
    Timer {
        id: clock
        interval: root.duration
        running: false
        onTriggered: if (!hover.hovered) Api.dismissNotice(root.slot); else restart()
    }

    Item {
        id: card
        width: root.width
        height: Math.max(48, body.height + 2 * 14)
        opacity: root.t
        transform: Translate { y: Theme.reduceMotion ? 0 : -16 * (1 - root.t) }
        scale: Theme.reduceMotion ? 1 : 0.96 + 0.04 * root.t
        transformOrigin: Item.Top
        HoverHandler { id: hover }

        // Bóng của lớp nổi (như Popover: DESIGN.md 5.5)
        Rectangle { anchors.fill: parent; anchors.margins: -8; radius: Theme.radiusCover + 8; color: "#000000"; opacity: 0.04 }
        Rectangle { anchors.fill: parent; anchors.margins: -3; anchors.topMargin: -1; anchors.bottomMargin: -5; radius: Theme.radiusCover + 3; color: "#000000"; opacity: 0.06 }
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusCover
            color: Theme.panel
            border.width: 1
            border.color: Theme.line
        }
        Item {
            id: body
            x: 16
            y: 14
            width: card.width - 32
            // Như sonner: nút ở bên phải, chữ xuống dòng bên trái (chữ không bao giờ bị cắt; từ dài không ngắt được thì ngắt giữa từ)
            height: Math.max(texts.height, actionButton.visible ? actionButton.height : 0)
            Column {
                id: texts
                width: body.width - (actionButton.visible ? actionButton.width + 12 : 0)
                y: Math.max(0, (body.height - height) / 2)
                spacing: 2
                Text {
                    id: titleText
                    objectName: "toastTitle"
                    width: parent.width
                    text: root.title
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: 13
                    font.weight: Theme.weightMedium
                }
                Text {
                    id: descriptionText
                    objectName: "toastDescription"
                    visible: root.description !== ""
                    width: parent.width
                    text: root.description
                    color: Theme.text2
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: 13
                }
            }
            Interactive {
                id: actionButton
                objectName: "toastAction"
                visible: root.action !== null
                x: body.width - width
                y: (body.height - height) / 2
                implicitWidth: actionLabel.implicitWidth + 16
                implicitHeight: Math.max(24, actionLabel.implicitHeight + 6)
                Accessible.role: Accessible.Button
                Accessible.name: actionLabel.text
                onClicked: Api.runNoticeAction(root.slot)
                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusControl
                    color: Theme.accent
                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "#000000"
                        opacity: actionButton.pressed ? Theme.pressShade : actionButton.hovered ? 0.04 : 0
                        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                    }
                }
                Text {
                    id: actionLabel
                    anchors.centerIn: parent
                    text: root.action ? root.action.label : ""
                    color: Theme.accentInk
                    font.pixelSize: 12
                    font.weight: Theme.weightBold
                }
            }
        }
        // ✕ ở góc trên bên trái, đè lên viền (closeButton của sonner)
        Interactive {
            id: close
            objectName: "toastClose"
            x: -6
            y: -6
            width: 20
            height: 20
            Accessible.role: Accessible.Button
            Accessible.name: "Đóng thông báo"
            onClicked: Api.dismissNotice(root.slot)
            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: Theme.panel
                border.width: 1
                border.color: Theme.line
                Rectangle { anchors.fill: parent; radius: parent.radius; color: Theme.hover; opacity: close.hovered ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
            }
            Icon { anchors.centerIn: parent; name: "x"; size: 12; color: Theme.text2 }
        }
    }
}
