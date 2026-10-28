import QtQuick
import ABook

// Một hàng chương: tên và số chương ở trái, thời lượng ở cuối hàng,
// dấu đã nghe xong, vạch tiến độ chương dở dang, chương đang phát tô màu nhấn.
// Dùng ở trang sách, ngăn Chương và cột phải của Đang nghe. Hàng chưa có audio mở chữ chương qua màn gọi.
// `hasMenu` (trang sách): nút "…" ở cuối hàng (ChapterRow của listen/BookScreen.tsx) - chỉ hiện khi rê chuột vào hàng, khi có tiêu điểm hay khi
// menu của nó đang mở; chỗ của nó luôn giữ nên hàng không xô lệch. Bấm thì `menuRequested(nút)` (bảng nổi do trang sách dựng).
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
    property bool hasMenu: false
    property bool menuOpen: false
    property string fullTitle: ""
    signal menuRequested(Item anchor)
    readonly property real menuWidth: hasMenu ? 32 + Theme.s4 : 0
    // Cú bấm trúng nút "…": TapHandler của hàng cũng thấy cú bấm ấy (nút con nhận trước) - chỗ dùng bỏ qua `clicked` khi đúng (bấm "…" không
    // phát chương). Cờ chỉ sống tới hết lượt xử lý cú bấm này.
    property bool onMenuButton: false
    readonly property string headline: subtitle !== "" ? subtitle : title
    readonly property string detail: [subtitle !== "" ? title : "", status].filter(s => s !== "").join(" · ")
    implicitHeight: Math.max(56, Math.max(textColumn.implicitHeight, duration.implicitHeight) + 2 * Theme.s12)
    opacity: playable ? 1 : 0.55

    Rectangle {
        objectName: "chapterFill"
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
        width: parent.width - x - Theme.s12 - root.menuWidth - (duration.visible ? duration.width + Theme.s16 : 0)
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
    Text {
        id: duration
        objectName: "chapterDuration"
        visible: root.status === "" && root.length !== ""
        x: parent.width - width - Theme.s12 - root.menuWidth
        anchors.verticalCenter: parent.verticalCenter
        text: root.length
        color: Theme.text3
        horizontalAlignment: Text.AlignRight
        font.pixelSize: Theme.sizeCaption
        font.features: { "tnum": 1 }
    }
    IconButton {
        id: more
        objectName: "chapterMore"
        visible: root.hasMenu
        x: parent.width - width - Theme.s8
        anchors.verticalCenter: parent.verticalCenter
        implicitWidth: 32
        implicitHeight: 32
        icon: "ellipsis"
        iconSize: 16
        ink: Theme.text2
        hoverInk: Theme.text
        Accessible.name: `Tuỳ chọn ${root.fullTitle}`
        opacity: root.hovered || more.hovered || more.activeFocus || root.menuOpen ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        onClicked: {
            root.onMenuButton = true
            Qt.callLater(function() { root.onMenuButton = false })
            root.menuRequested(more)
        }
    }
    Rectangle {
        objectName: "chapterProgress"
        visible: root.progress > 0.01 && !root.done
        x: Theme.s12 + 20 + Theme.s12
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        width: (parent.width - x - Theme.s12 - root.menuWidth) * Math.min(1, root.progress)
        height: 2
        radius: height / 2
        color: Theme.accent
    }
}
