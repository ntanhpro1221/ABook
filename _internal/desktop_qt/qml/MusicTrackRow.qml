import "UiStrings.js" as S
import QtQuick
import ABook
import "MusicLibraryLogic.js" as Logic
import "TextWrap.js" as TextWrap

// Một dòng của Kho nhạc (TrackRow của ui/src/music/MusicScreen.tsx): nút nghe thử · tên (xuống dòng, không cắt) + người sáng tác · thời lượng
// · phong cách · trạng thái tải (phần trăm / dấu tích / lỗi), chế độ chọn thêm nút "Dùng". Bấm dòng mở chi tiết. Mất mạng: nút nghe thử của bài
// chưa tải mờ đi, không bấm được.
Interactive {
    id: root
    property var track: ({})
    property var downloads: null
    property var styles: []
    property bool online: true
    property bool previewing: false
    property bool picking: false
    property bool first: false
    signal preview()
    signal use()
    readonly property var load: Logic.loadOf(track, downloads)
    readonly property bool canPlay: online || !!track.downloaded
    implicitHeight: Math.max(words.height, 40) + 2 * Theme.s12 + 1
    Accessible.name: (track.title || "") + (track.creator ? ", " + track.creator : "")

    Rectangle { width: parent.width; height: 1; color: Theme.line; visible: !root.first }
    Rectangle {
        anchors.fill: parent; anchors.topMargin: 1
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.pressed ? 0.08 : (root.hovered ? 0.04 : 0)
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    IconButton {
        id: play
        objectName: "musicRowPreview"
        x: 0; y: 1 + Theme.s12
        icon: root.previewing ? "square" : "play"
        enabled: root.canPlay
        opacity: root.canPlay ? 1 : 0.45
        ink: root.previewing ? Theme.accentText : Theme.text
        tip: (root.previewing ? S.s_dung_nghe_thu_41a2925b : S.s_nghe_thu_fa024065) + ": " + (root.track.title || "")
        onClicked: root.preview()
    }
    Column {
        id: words
        x: play.width + Theme.s12
        y: 1 + Theme.s12
        width: root.width - x - tail.width - Theme.s12
        spacing: 2
        Text {
            width: parent.width
            text: TextWrap.keepDots(root.track.title || "")
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBody
        }
        Text {
            width: parent.width
            text: [root.track.creator || "", root.track.duration ? Logic.clock(root.track.duration) : "",
                   root.track.style ? Logic.labelOf(root.styles, root.track.style) : ""].filter(part => part !== "").join("\u00a0·\u00a0")
            color: Theme.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBodySmall
            font.features: {"tnum": 1}
        }
    }
    Row {
        id: tail
        anchors.right: parent.right
        y: 1 + Theme.s12 + 8
        spacing: Theme.s8
        Text {
            objectName: "musicRowLoading"
            visible: root.load.kind === "loading"
            text: root.load.percent === null || root.load.percent === undefined ? S.s_dang_tai_465b1987 : root.load.percent + " %"
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
            font.features: {"tnum": 1}
            Accessible.name: S.s_dang_tai_0_e9a97892(root.load.percent || 0)
        }
        Icon { visible: root.load.kind === "done"; name: "circle-check"; size: 18; color: Theme.success }
        Icon { visible: root.load.kind === "failed"; name: "circle-alert"; size: 18; color: Theme.danger }
        Button {
            objectName: "musicRowUse"
            visible: root.picking
            y: -8
            text: S.s_dung_7927ca4e; kind: "ghost"; size: "sm"
            Accessible.name: S.s_dung_7927ca4e + ": " + (root.track.title || "")
            onActivated: root.use()
        }
    }
}
