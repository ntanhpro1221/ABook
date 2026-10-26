import QtQuick
import ABook

// Một hàng chương: tên chương (hay tên riêng nếu có), dòng phụ độ dài / "Chưa có audio", dấu đã nghe xong, vạch tiến độ chương dở dang, chương đang phát tô màu nhấn.
// Dùng ở trang sách, ngăn Chương và cột phải của Đang nghe khi chưa có chữ chạy theo. Bấm hàng không nghe được thì không làm gì.
Interactive {
    id: root
    property string title: ""
    property string subtitle: ""
    property string length: ""
    property string status: ""
    property bool playable: true
    property bool done: false
    property bool current: false
    property real progress: 0
    readonly property string headline: subtitle !== "" ? subtitle : title
    readonly property string detail: [subtitle !== "" ? title : "", status !== "" ? status : length].filter(s => s !== "").join(" · ")
    implicitHeight: Math.max(56, textColumn.implicitHeight + 2 * Theme.s12)
    opacity: playable ? 1 : 0.55

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: root.current ? Theme.accentSoft : Theme.text
        opacity: root.current ? 1 : (root.pressed && root.playable ? 0.10 : (root.hovered && root.playable ? 0.05 : 0))
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Item {
        id: mark
        x: Theme.s12
        width: 20
        height: parent.height
        Icon {
            anchors.centerIn: parent
            visible: root.current || root.done
            name: root.current ? "audio-lines" : "check"
            size: 16
            color: root.current ? Theme.accentText : Theme.success
        }
    }
    Column {
        id: textColumn
        x: mark.x + mark.width + Theme.s12
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - x - Theme.s12
        spacing: 2
        Text {
            width: parent.width
            text: root.headline
            color: root.current ? Theme.accentText : Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
            font.weight: root.current ? Theme.weightMedium : Theme.weightRegular
        }
        Text {
            visible: root.detail !== ""
            width: parent.width
            text: root.detail
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }
    Rectangle {
        visible: root.progress > 0.01 && !root.done
        x: Theme.s12 + 20 + Theme.s12
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        width: (parent.width - x - Theme.s12) * Math.min(1, root.progress)
        height: 2
        radius: height / 2
        color: Theme.accent
    }
}
