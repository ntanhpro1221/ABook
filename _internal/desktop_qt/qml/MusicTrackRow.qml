import "UiStrings.js" as S
import QtQuick
import ABook
import "MusicLibraryLogic.js" as Logic
import "TextWrap.js" as TextWrap

// Một dòng của Kho nhạc (TrackRow của ui/src/music/MusicScreen.tsx): nút nghe thử · tên (xuống dòng, không cắt) + người sáng tác · thời lượng
// · phong cách · trạng thái tải (phần trăm / dấu tích / lỗi), chế độ chọn thêm nút "Dùng". Bấm dòng mở chi tiết (mũi tên ">"). Mất mạng: nút nghe thử của bài
// chưa tải mờ đi, không bấm được. "Đã tải" là trạng thái, không phải nút xoá ngầm: xoá bản tải nằm ở chi tiết ("Xoá bản tải" + hộp xác nhận).
Interactive {
    id: root
    property var track: ({})
    property var downloads: null
    property var styles: []
    property bool online: true
    property bool previewing: false
    property bool previewLoading: false
    property bool picking: false
    property bool first: false
    signal preview()
    signal use()
    signal save()
    signal cancelDownload()
    readonly property var load: Logic.loadOf(track, downloads)
    readonly property bool canPlay: online || !!track.downloaded
    implicitHeight: Math.max(words.height, 40) + 2 * Theme.s12 + 1 + (progress.open ? progress.implicitHeight : 0)
    Accessible.name: (track.title || "") + (track.creator ? ", " + track.creator : "")

    Rectangle { width: parent.width; height: 1; color: Theme.line; Reveal { shown: !root.first }}
    Rectangle {
        anchors.fill: parent; anchors.topMargin: 0
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.pressed ? 0.08 : (root.hovered ? 0.04 : 0)
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    MusicArt {
        id: art
        x: 0; y: 1 + Theme.s12
        width: 40; height: 40
        track: root.track
    }
    IconButton {
        id: play
        objectName: "musicRowPreview"
        x: art.width + Theme.s8; y: 1 + Theme.s12
        icon: root.previewing && !Clip.paused ? "pause" : "play"
        pending: root.previewing && root.previewLoading
        enabled: root.canPlay
        opacity: root.canPlay ? 1 : 0.45
        ink: root.previewing ? Theme.accentText : Theme.text
        tip: (root.previewing && root.previewLoading ? S.s_buffering : root.previewing && !Clip.paused ? S.s_tam_dung_67635815 : S.s_nghe_thu_fa024065) + ": " + (root.track.title || "")
        onActivated: root.preview()
    }
    Column {
        id: words
        x: play.x + play.width + Theme.s12
        y: 1 + Theme.s12
        width: root.width - x - tail.width - Theme.s12 - chevron.width - Theme.s4
        spacing: 4
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
                property string metadataText: root.load.kind === "failed" ? S.s_chua_tai_xong_b257419d : root.load.kind === "loading" && root.load.percent !== null && root.load.percent !== undefined ? S.s_dang_tai_0_e9a97892(root.load.percent) : root.track.duration ? Logic.clock(root.track.duration) : ""
                text: metadataText ? (root.track.creator ? "\u00a0·\u00a0" : "") + metadataText : ""
                color: root.load.kind === "failed" ? Theme.danger : Theme.text2; font.pixelSize: Theme.sizeBodySmall
            }
        }
    }
    // Bấm dòng mở chi tiết: mũi tên như web (ChevronRight ở cuối khối chữ) và điện thoại (ChevronIcon trước cột nút).
    Icon {
        id: chevron
        objectName: "musicRowChevron"
        x: root.width - tail.width - Theme.s12 - width; y: 1 + Theme.s12 + 2
        name: "chevron-right"; size: 16; color: Theme.text3
    }
    Row {
        id: tail
        anchors.right: parent.right
        y: Theme.s12
        spacing: Theme.s8
        Button {
            objectName: "musicRowUse"
            Reveal { shown: root.picking }
            text: S.s_dung_7927ca4e; kind: "ghost"; size: "sm"
            Accessible.name: S.s_dung_7927ca4e + ": " + (root.track.title || "")
            onActivated: root.use()
        }
        // One fixed slot: the download / stop / retry button and the "downloaded" status cross-fade in place.
        Item {
            width: Theme.buttonHeight
            height: Theme.buttonHeight
            IconButton {
                objectName: "musicRowDownload"
                anchors.fill: parent
                Reveal { shown: root.load.kind !== "done" }
                indicateRequest: root.load.kind !== "loading"
                icon: root.load.kind === "loading" || root.load.kind === "done" ? "" : "download"
                ink: root.load.kind === "failed" ? Theme.danger : Theme.text2
                enabled: root.load.kind !== "done" && (root.online || root.load.kind === "loading")
                opacity: enabled ? 1 : 0.45
                tip: root.load.kind === "loading" ? S.s_stop_download : root.load.kind === "failed" ? S.s_thu_lai_c58d068c : S.s_tai_ve_9b5bdb44
                onActivated: root.load.kind === "loading" ? root.cancelDownload() : root.save()
                DownloadRing {
                    objectName: "musicRowLoading"
                    anchors.centerIn: parent; Reveal { shown: root.load.kind === "loading" }
                    percent: root.load.kind === "loading" && root.load.percent !== null && root.load.percent !== undefined ? root.load.percent : -1
                }
            }
            Item {
                objectName: "musicRowDownloaded"
                anchors.fill: parent
                Reveal { shown: root.load.kind === "done" }
                Accessible.role: Accessible.Graphic
                Accessible.name: S.s_da_tai_b7362bbf
                Rectangle { anchors.centerIn: parent; width: 20; height: 20; radius: width / 2; color: Theme.accent
                    StateIcon { anchors.centerIn: parent; name: "arrow-down"; size: 14; color: Theme.accentInk }
                }
            }
        }
    }
    // The listening bar starts under the preview button (art 40 + gap 8), as on web and the phone.
    Collapse { id: progress; x: play.x; y: Math.max(words.height, 40) + 2 * Theme.s12; width: root.width - x; open: root.previewing
        MusicListeningProgress { width: parent.width }
    }
}
