import "UiStrings.js" as S
import QtQuick
import ABook
import "MusicLibraryLogic.js" as Logic
import "SizeFormat.js" as Size

// Phần "Nhạc trong sách" của trang sách (BookMusic.tsx của web): các bài của danh mục cuốn này dùng (gộp trùng, số đoạn mỗi bài, GET
// /api/books/<id>/music/library) + "Lưu tất cả (X MB)" - lưu = ghim + tải về, nghe không mạng. Bấm bài mở chi tiết kèm "Vì sao bài này"
// (cảm xúc máy đọc được ở đoạn đầu tiên dùng bài). Cuốn không có bài nào của danh mục thì phần này ẩn.
Column {
    id: root
    objectName: "bookMusic"
    property string bookId: ""
    property var data: null
    property var downloads: null
    property var meta: null
    readonly property var tracks: data && data.tracks ? data.tracks : []
    readonly property var unsaved: tracks.filter(track => !track.saved)
    readonly property bool busy: !!(downloads && downloads.active && Object.keys(downloads.active).length)
    readonly property string previewing: Clip.current.indexOf("library:") === 0 ? Clip.current.slice(8) : ""
    visible: tracks.length > 0
    height: visible ? implicitHeight : 0
    spacing: Theme.s8

    function refresh() {
        if (!bookId) { data = null; return }
        const asked = bookId
        Api.quiet("GET", "/api/books/" + encodeURIComponent(bookId) + "/music/library", null, function(next, problem) { if (asked === root.bookId) data = problem ? null : next })
    }
    function pollDownloads() { Api.quiet("GET", "/api/music/library/downloads", null, function(next, problem) { if (!problem) { const was = busy; downloads = next; if (was && !busy) refresh() } }) }
    function change(path, links) {
        Api.quiet("POST", path, {links: links}, function(next, problem) {
            if (problem) { Api.notice = problem; return }
            downloads = next; refresh(); detail.reload()
        })
    }
    onBookIdChanged: refresh()
    Component.onCompleted: { refresh(); pollDownloads(); Api.quiet("GET", "/api/music/library/meta", null, function(next, problem) { if (!problem) meta = next }) }
    Component.onDestruction: if (previewing !== "") Clip.stop()
    onVisibleChanged: if (!visible && previewing !== "") Clip.stop()
    Timer { interval: 700; repeat: true; running: root.busy && root.visible; onTriggered: root.pollDownloads() }

    Item {
        width: root.width
        height: Math.max(heading.height, saveAll.visible ? saveAll.height : 0)
        Text {
            id: heading
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - (saveAll.visible ? saveAll.width + Theme.s8 : 0)
            text: S.s_nhac_trong_sach_9070d53a
            color: Theme.text; wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium
            Accessible.role: Accessible.Heading
        }
        Button {
            id: saveAll
            objectName: "bookMusicSaveAll"
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            visible: root.unsaved.length > 0
            text: S.s_luu_tat_ca_0_e16e7860(Size.formatSize(root.data ? root.data.missingBytes : 0))
            icon: "download"; kind: "ghost"; size: "sm"
            onActivated: root.change("/api/music/library/save", root.unsaved.map(track => track.link))
        }
    }
    Repeater {
        model: root.tracks
        delegate: Item {
            required property var modelData
            required property int index
            width: root.width
            height: row.implicitHeight
            MusicTrackRow {
                id: row
                width: parent.width - scenes.width - Theme.s8
                track: modelData
                first: index === 0
                downloads: root.downloads
                styles: root.meta ? root.meta.styles : []
                previewing: root.previewing === modelData.link
                onPreview: { const start = Number(modelData.audibleStart) || 0; Clip.toggle("library:" + modelData.link, Logic.previewPath(modelData.link), start, start + Logic.PREVIEW_SECONDS) }
                onClicked: detail.show(modelData.link, modelData.scene ? {book: root.bookId, scene: modelData.scene} : null)
            }
            Text {
                id: scenes
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                text: S.s_0_doan_c2eb5200(modelData.scenes)
                color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.features: {"tnum": 1}
            }
        }
    }
    MusicTrackDetail {
        id: detail
        meta: root.meta
        downloads: root.downloads
        previewing: root.previewing !== "" && root.previewing === detail.link
        onPreview: if (detail.detail) { const start = Number(detail.detail.audibleStart) || 0; Clip.toggle("library:" + detail.link, Logic.previewPath(detail.link), start, start + Logic.PREVIEW_SECONDS) }
        onSave: root.change("/api/music/library/save", [detail.link])
        onUnsave: root.change("/api/music/library/unsave", [detail.link])
        onCancelDownload: root.change("/api/music/library/unsave", [detail.link])
    }
}
