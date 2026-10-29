import QtQuick
import ABook

// Ô sách trong lưới (DESIGN.md mục 6, "Lưới bìa"): bìa 2:3 bo 12, tên và dòng phụ dưới bìa xuống dòng đủ (không bao giờ cắt chữ của
// người dùng), nên ô cao theo chữ; hàng lưới (LibraryScreen) cao theo ô cao nhất của hàng.
// Tiến độ nghe = vạch mảnh ở đáy bìa; sách của máy khác có nhãn nhỏ ở góc bìa.
Interactive {
    id: root
    property string title: ""
    property string subtitle: ""
    property string coverKey: ""
    property real progress: 0
    property string source: ""
    property bool remoteSeries: false
    property var book: ({})
    property bool playVisible: false
    signal readRequested()
    property bool onPlayButton: false
    property real coverWidth: Theme.coverMin
    readonly property real coverHeight: Math.round(coverWidth * Theme.coverRatio)
    readonly property real textBlock: 12 + titleText.implicitHeight + (subtitleText.visible ? 4 + subtitleText.implicitHeight : 0) + (sourceText.visible ? 4 + sourceText.implicitHeight : 0)

    activeFocusOnTab: false
    ringRadius: Theme.radiusCover
    ringHeight: coverHeight
    pressScaling: false
    implicitWidth: coverWidth
    implicitHeight: coverHeight + textBlock

    Item {
        id: cover
        width: root.coverWidth
        height: root.coverHeight
        // Rê chuột: bìa nhích lên 1,02; nhấn: thu 0,97 + tối 6 % (DESIGN.md 5.2). Chỉ transform / opacity.
        scale: root.pressed ? Theme.pressScale : (root.hovered && Nav.uiVisible && !Theme.reduceMotion ? 1.02 : 1)
        Behavior on scale {
            NumberAnimation {
                duration: root.pressed ? Theme.motionFastOut : Theme.motionFast
                easing.type: Easing.BezierSpline
                easing.bezierCurve: Theme.easeStandard
            }
        }
        CoverView {
            anchors.fill: parent
            coverKey: root.coverKey
            title: root.title
        }
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusCover
            color: "#000000"
            opacity: root.pressed ? Theme.pressShade : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionFastOut } }
        }
        Rectangle {          // vạch tiến độ
            visible: root.progress > 0.005 && root.progress < 0.995
            x: 8
            y: parent.height - 11
            width: parent.width - 16
            height: 3
            radius: height / 2
            color: "#66000000"
            Rectangle {
                width: parent.width * root.progress
                height: parent.height
                radius: parent.radius
                color: Theme.accent
            }
        }
        IconButton {
            id: play
            objectName: "libraryTilePlay"
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 8
            readonly property bool here: Player.loaded && Player.bookId === root.book.bookId
            readonly property bool textOnly: root.book.stage === "text"
            icon: textOnly ? "book-open" : here && Player.playing ? "pause" : "play"
            tip: textOnly ? `Đọc ${root.title}` : here && Player.playing ? `Tạm dừng ${root.title}` : `Nghe ${root.title}`
            opacity: root.playVisible && (root.hovered || root.externalFocus || play.activeFocus || here) ? 1 : 0
            visible: opacity > 0
            enabled: root.playVisible
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            onClicked: {
                root.onPlayButton = true
                Later.call(root, function() { root.onPlayButton = false })
                if (textOnly) root.readRequested()
                else if (here) Player.toggle()
                else Player.playBook(root.book.bookId)
            }
        }
    }
    Text {
        id: titleText
        x: 0
        y: root.coverHeight + 12
        width: root.coverWidth
        text: root.title
        color: Theme.text
        wrapMode: Text.Wrap
        lineHeight: 1.3
        font.pixelSize: Theme.sizeBodySmall
        font.weight: Theme.weightMedium
    }
    Text {
        id: subtitleText
        visible: text !== ""
        x: 0
        y: titleText.y + titleText.implicitHeight + 4
        width: root.coverWidth
        text: root.subtitle
        color: Theme.text3
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
    }
    // Same laptop mark and source placement as web: below the title, leaving
    // the cover's printed title unobstructed.
    Text {
        id: sourceText
        visible: root.source !== ""
        x: 18
        y: subtitleText.y + (subtitleText.visible ? subtitleText.implicitHeight + 4 : 0)
        width: root.coverWidth - x
        text: root.remoteSeries ? "Có sách trên máy khác" : "Trên " + root.source
        color: Theme.text3; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption
    }
    Icon {
        x: 0; y: sourceText.y + 2; size: 12; name: "laptop"; color: Theme.text3
        visible: sourceText.visible
        Accessible.name: root.remoteSeries ? "Có sách trên máy khác" : "Trên " + root.source
    }
}
