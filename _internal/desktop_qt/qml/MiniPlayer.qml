import QtQuick
import ABook

// Cùng bìa và nút của trình phát; chữ luôn xuống dòng, chiều cao theo nội dung.
Rectangle {
    id: root
    property var windowMode: null
    // Khi lấp cả cửa sổ: cửa sổ tự là tấm (Windows 11 tự bo góc cửa sổ), tấm vuông không viền - bo thêm thì lộ nền cửa sổ ở góc.
    property bool framed: true
    property string bookTitle: Player.bookTitle
    property string chapterTitle: Player.chapterTitle
    readonly property bool expanded: Theme.widthClass(width) >= 1
    property real wideT: expanded ? 1 : 0
    Behavior on wideT {
        NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
    }
    readonly property real naturalHeight: Math.max(112, details.y + details.implicitHeight + 12,
                                                playback.y + playback.height + 12)
    implicitWidth: 360
    implicitHeight: naturalHeight
    color: Theme.panel
    radius: framed ? Theme.radiusSheet : 0
    border.color: Theme.line
    border.width: framed ? 1 : 0
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
        objectName: "miniDetails"
        x: cover.x + cover.width + 12
        y: 36
        width: Math.min(640, root.width - x - 12 - (playback.width + Theme.s24) * Math.min(1, root.wideT * 2))
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
    }
    Row {
        id: playback
        objectName: "miniPlayback"
        x: details.x + (details.width + Theme.s24) * Math.min(1, root.wideT * 2)
        y: details.y + (details.height + Theme.s4) * (1 - Math.max(0, root.wideT * 2 - 1))
        spacing: Theme.s8
        SkipButton { objectName: "miniBack"; forward: false; tip: `Lùi ${Player.skipSeconds} giây` }
        PlayButton { objectName: "miniPlay"; size: 40; tip: Player.playing ? "Tạm dừng" : "Phát" }
        SkipButton { objectName: "miniForward"; forward: true; tip: `Tới ${Player.skipSeconds} giây` }
    }
    SeekBar {
        objectName: "miniSeek"
        compact: true; lineHeight: 3; bottomAligned: true
        x: Theme.radiusSheet; width: parent.width - 2 * x
        anchors.bottom: parent.bottom
        height: 12
    }
}
