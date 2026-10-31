import QtQuick
import ABook

// Ghi công bài nhạc đang phát, dưới tên chương (như MusicCreditLine của bản web): "Nhạc nền: tên · tác giả", bấm thì mở dần lời ghi công
// đầy đủ, giấy phép (liên kết), lời "Đã chỉnh sửa" khi giấy phép đòi, trang của bài. Đổi bài thì gập lại. Hiện / ẩn dần khi nhạc phát / im.
Item {
    id: root
    readonly property bool shown: Player.playing && (Music.credit.label || "") !== ""
    property var credit: ({})
    property bool open: false

    // Giữ lời ghi công cuối trong lúc mờ đi, không để chữ biến mất trước khung.
    function refresh() {
        if ((Music.credit.label || "") !== "") credit = Music.credit
        open = false
    }
    function esc(value) { return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;") }
    Component.onCompleted: refresh()
    Connections {
        target: Music
        function onCreditChanged() { root.refresh() }
    }

    // Cuốn có nhạc: giữ chỗ một dòng kể cả khi nhạc im (dừng nghe, đoạn không nhạc) - bìa lớn không đổi cỡ mỗi lần bấm phát / dừng.
    implicitHeight: shown ? body.implicitHeight : (Music.hasMusic ? body.topPadding + caption.implicitHeight : 0)
    height: implicitHeight
    opacity: shown ? 1 : 0
    clip: height < body.implicitHeight
    Behavior on implicitHeight { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }

    Column {
        id: body
        width: parent.width
        topPadding: 2
        spacing: 0

        Interactive {
            id: toggle
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width, caption.implicitWidth)
            height: caption.implicitHeight
            pressScaling: false
            tip: root.credit.text || root.credit.label || ""
            onClicked: root.open = !root.open
            Text {
                id: caption
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                textFormat: Text.PlainText
                text: "Nhạc nền: " + (root.credit.label || "")
                color: toggle.hovered ? Theme.text : Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                Behavior on color { ColorAnimation { duration: Theme.motionFast } }
            }
        }

        // Phần mở: cao và mờ cùng đi (Collapse của bản web).
        Item {
            id: collapse
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width, 384)
            height: root.open ? details.implicitHeight : 0
            opacity: root.open ? 1 : 0
            clip: height < details.implicitHeight
            visible: height > 0
            Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }

            Column {
                id: details
                width: parent.width
                topPadding: Theme.s4
                Line { text: root.credit.text || "" }
                Line {
                    visible: (root.credit.license || "") !== ""
                    rich: true
                    text: "Giấy phép: " + (root.credit.licenseUrl
                        ? "<a href=\"" + root.esc(root.credit.licenseUrl) + "\">" + root.esc(root.credit.license) + "</a>" : root.esc(root.credit.license))
                }
                Line { visible: root.credit.modified === true; text: root.credit.modifiedNote || "" }
                Line {
                    visible: (root.credit.landing || "") !== ""
                    rich: true
                    text: "<a href=\"" + root.esc(root.credit.landing) + "\">Trang của bài nhạc</a>"
                }
            }
        }
    }

    component Line: Text {
        property bool rich: false
        width: parent.width
        textFormat: rich ? Text.StyledText : Text.PlainText
        linkColor: Theme.text2
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
        onLinkActivated: (link) => Qt.openUrlExternally(link)
        HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
    }
}
