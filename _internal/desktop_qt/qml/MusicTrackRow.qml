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
    signal save()
    signal cancelDownload()
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
            maximumLineCount: 2 // text-cut-ok: owner requests two title lines in music rows; details show the full title.
            elide: Text.ElideRight // text-cut-ok: the full title is in the detail sheet.
            font.pixelSize: Theme.sizeBody
        }
        Row {
            width: parent.width
            Text {
                width: Math.min(implicitWidth, Math.max(0, parent.width - duration.width))
                text: TextWrap.keepDots(root.track.creator || "")
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
                elide: Text.ElideRight // text-cut-ok: only the creator yields space to the duration in the compact music row.
            }
            ClockLabel {
                id: duration
                text: root.track.duration ? (root.track.creator ? "\u00a0·\u00a0" : "") + Logic.clock(root.track.duration) : ""
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            }
        }
    }
    Row {
        id: tail
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.s8
        Button {
            objectName: "musicRowUse"
            visible: root.picking
            text: S.s_dung_7927ca4e; kind: "ghost"; size: "sm"
            Accessible.name: S.s_dung_7927ca4e + ": " + (root.track.title || "")
            onActivated: root.use()
        }
        IconButton {
            objectName: "musicRowDownload"
            icon: root.load.kind === "done" ? "circle-check" : root.load.kind === "failed" ? "circle-alert" : root.load.kind === "loading" ? "" : "download"
            ink: root.load.kind === "done" ? Theme.success : root.load.kind === "failed" ? Theme.danger : Theme.text2
            enabled: root.load.kind === "loading" || (root.online && root.load.kind !== "done")
            opacity: enabled || root.load.kind === "done" ? 1 : 0.45
            tip: root.load.kind === "loading" ? S.s_huy_tai_1a9ff73d : root.load.kind === "done" ? S.s_da_tai_b7362bbf : S.s_tai_ve_9b5bdb44
            onClicked: root.load.kind === "loading" ? root.cancelDownload() : root.save()
            DownloadRing {
                objectName: "musicRowLoading"
                anchors.centerIn: parent; visible: root.load.kind === "loading"
                percent: root.load.kind === "loading" && root.load.percent !== null && root.load.percent !== undefined ? root.load.percent : -1
            }
        }
    }
}
