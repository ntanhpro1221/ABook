import QtQuick
import ABook

// Cùng bìa và nút của trình phát; chữ luôn xuống dòng, chiều cao theo nội dung.
Rectangle {
    id: root
    property var windowMode: null
    property string bookTitle: Player.bookTitle
    property string chapterTitle: Player.chapterTitle
    readonly property real naturalHeight: Math.max(112, details.implicitHeight + 48)
    implicitWidth: 360
    implicitHeight: naturalHeight
    color: Theme.panel
    radius: Theme.radiusSheet
    border.color: Theme.line
    MouseArea {
        anchors.fill: parent
        onPressed: if (root.windowMode) root.windowMode.window.startSystemMove()
    }
    CoverView {
        id: cover
        objectName: "miniCover"
        x: 12; y: 12
        height: 88; width: height / Theme.coverRatio
        radius: Theme.radiusCover
        coverKey: Player.coverKey
        title: root.bookTitle
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: if (root.windowMode) root.windowMode.expand()
            onDoubleClicked: if (root.windowMode) root.windowMode.expand()
        }
    }
    Row {
        id: tools
        anchors.right: parent.right; anchors.rightMargin: 8
        y: 4
        IconButton {
            objectName: "miniPin"
            width: 28; height: 28; iconSize: 16
            icon: root.windowMode && !root.windowMode.pinned ? "pin-off" : "pin"
            tip: "Ghim trên cùng"
            onClicked: if (root.windowMode) root.windowMode.pinned = !root.windowMode.pinned
        }
        IconButton {
            objectName: "miniExpand"
            width: 28; height: 28; iconSize: 16
            icon: "maximize-2"; tip: "Mở rộng"
            onClicked: if (root.windowMode) root.windowMode.expand()
        }
    }
    Column {
        id: details
        x: cover.x + cover.width + 12
        y: 36
        width: root.width - x - 12
        spacing: 4
        Text {
            objectName: "miniBookTitle"
            width: parent.width; text: root.bookTitle; wrapMode: Text.Wrap
            color: Theme.text; font.pixelSize: Theme.sizeBody; font.weight: Theme.weightBold
        }
        Text {
            objectName: "miniChapterTitle"
            width: parent.width; text: root.chapterTitle; wrapMode: Text.Wrap
            color: Theme.text2; font.pixelSize: Theme.sizeCaption
        }
        Row {
            spacing: Theme.s8
            SkipButton { objectName: "miniBack"; forward: false; tip: `Lùi ${Player.skipSeconds} giây` }
            PlayButton { objectName: "miniPlay"; size: 40; tip: Player.playing ? "Tạm dừng" : "Phát" }
            SkipButton { objectName: "miniForward"; forward: true; tip: `Tới ${Player.skipSeconds} giây` }
        }
    }
    SeekBar {
        objectName: "miniSeek"
        compact: true; lineHeight: 3; bottomAligned: true
        x: Theme.radiusSheet; width: parent.width - 2 * x
        anchors.bottom: parent.bottom
        height: 12
    }
}
