import "UiStrings.js" as S
import QtQuick
import ABook
import "MusicLibraryLogic.js" as Logic
import "SizeFormat.js" as Size

// Phần "Nhạc trong sách" của trang sách (BookMusic.tsx của web): các bài của danh mục cuốn này dùng (gộp trùng, số đoạn mỗi bài, GET
// /api/books/<id>/music/library) + "Lưu tất cả (X MB)" - lưu = ghim + tải về, nghe không mạng. Bấm bài mở chi tiết kèm "Vì sao bài này"
// (cảm xúc máy đọc được ở đoạn đầu tiên dùng bài). The dedicated tab has explicit loading, empty and retry states.
ListView {
    id: root
    objectName: "bookMusic"
    property string bookId: ""
    property var data: null
    property var downloads: null
    property var meta: null
    property bool loading: true
    property string problem: ""
    readonly property var tracks: data && data.tracks ? data.tracks : []
    readonly property var unsaved: data && data.unsaved ? data.unsaved : []
    readonly property bool busy: !!(downloads && downloads.active && Object.keys(downloads.active).length)
    readonly property string previewing: Clip.current.indexOf("library:") === 0 ? Clip.current.slice(8) : ""
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    model: root.tracks
    bottomMargin: Theme.s16

    function refresh() {
        if (!bookId) { data = null; loading = false; return }
        const asked = bookId
        loading = true; problem = ""
        Api.quiet("GET", "/api/books/" + encodeURIComponent(bookId) + "/music/library", null, function(next, error) {
            if (asked !== root.bookId) return
            loading = false; problem = error ? S.s_chua_tai_duoc_kho_nhac_9577b7c7 : ""; data = error ? null : next
        })
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

    header: Column {
        width: root.width
        spacing: Theme.s8
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
            Reveal { shown: root.unsaved.length > 0 }
            text: S.s_luu_tat_ca_0_e16e7860(Size.formatSize(root.data ? root.data.missingBytes : 0))
            icon: "download"; kind: "ghost"; size: "sm"
            onActivated: root.change("/api/music/library/save", root.unsaved)
        }
        }
        Text {
            id: status
            objectName: "bookMusicStatus"
            width: parent.width
            text: root.loading ? S.s_dang_tai_465b1987 : root.problem || (root.tracks.length === 0 ? S.s_chua_co_nhac_ed5dc66e : "")
            Reveal { shown: status.text !== "" }
            wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeBody
            Accessible.role: Accessible.StaticText
        }
        Button {
            objectName: "bookMusicRetry"
            Reveal { shown: root.problem !== "" }
            text: S.s_thu_lai_c58d068c
            onActivated: root.refresh()
        }
    }
    delegate: Item {
            objectName: "bookMusicRow"
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
            previewLoading: Clip.loading
                onPreview: { const start = Number(modelData.audibleStart) || 0; Clip.toggle("library:" + modelData.link, Logic.previewPath(modelData.link), start, undefined, Logic.previewVolume(modelData.lufs)) }
                onSave: root.change("/api/music/library/save", [modelData.link])
                onCancelDownload: root.change("/api/music/library/unsave", [modelData.link])
                onDeleteDownload: root.change("/api/music/library/unsave", [modelData.link])
                onClicked: detail.show(modelData.link, modelData.scene ? {book: root.bookId, scene: modelData.scene} : null)
            }
            Text {
                id: scenes
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                text: S.s_0_doan_c2eb5200(modelData.scenes)
                color: Theme.text2; font.pixelSize: Theme.sizeCaption
            }
    }
    MusicTrackDetail {
        id: detail
        meta: root.meta
        downloads: root.downloads
        previewing: root.previewing !== "" && root.previewing === detail.link
        previewLoading: Clip.loading
        onPreview: if (detail.detail) { const start = Number(detail.detail.audibleStart) || 0; Clip.toggle("library:" + detail.link, Logic.previewPath(detail.link), start, undefined, Logic.previewVolume(detail.detail.lufs)) }
        onSave: root.change("/api/music/library/save", [detail.link])
        onUnsave: root.change("/api/music/library/unsave", [detail.link])
        onCancelDownload: root.change("/api/music/library/unsave", [detail.link])
    }
}
