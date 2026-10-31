import QtQuick
import ABook
import "StudioMusicLogic.js" as Logic
import "EditBookLogic.js" as Book

// "Đổi bài" của một đoạn nhạc trong Studio (Alternatives của MusicTab.tsx): các bài khác trong danh mục hợp đoạn này, hợp nhất trước (cùng cách
// chấm điểm với lúc máy chọn); dưới là nhóm "Nhạc của tôi" - mọi bài bạn đã nhập, kể cả bài chưa phân tích (máy không tự chọn, nhưng ghim được).
// Chọn = ghim. Mỗi lần mở (`active`) hỏi lại `GET /api/books/<mã>/music/scenes/<khoá>/alternatives` qua đường của Studio (máy này hay máy đã ghép).
Column {
    id: root
    property var store: null
    property string bookId: ""
    property string sceneKey: ""
    property bool active: false
    property bool busy: false
    property string choosing: ""
    property string previewing: ""
    property bool canPreviewMine: true
    property bool remote: false
    property bool loading: true
    property bool failed: false
    property var alternatives: []
    property var mine: []
    property int generation: 0
    property int libraryVersion: 0
    onLibraryVersionChanged: if (active) load()
    signal preview(string link)
    signal stopPreview()
    signal choose(string link)
    spacing: 12

    function load() {
        const ask = ++generation
        loading = true; failed = false
        store.request("GET", "/api/books/" + bookId + "/music/scenes/" + encodeURIComponent(sceneKey) + "/alternatives", null, function(status, data) {
            if (ask !== root.generation) return
            root.loading = false
            if (!root.store.ok(status) || !data) { root.failed = true; return }
            root.alternatives = data.alternatives || []
            root.mine = data.mine || []
        })
    }
    // Đóng danh sách (hay mở đoạn khác) thì bài nghe thử dừng
    onActiveChanged: if (active) load(); else stopPreview()
    Component.onDestruction: if (active) stopPreview()

    Collapse {
        width: parent.width
        open: root.loading
        EditBookSkeleton { width: parent.width; count: 3; label: "Đang tải bài khác" }
    }
    EditBookError {
        width: parent.width
        open: root.failed && !root.loading
        message: "Bạn hãy kiểm tra kết nối rồi tìm lại bài nhạc."
        onRetry: root.load()
    }
    Collapse {
        width: parent.width
        open: !root.loading && !root.failed
        spacing: 12
        Collapse {
            width: parent.width
            open: root.busy
            Text { width: parent.width; text: Logic.SAVING; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; Accessible.role: Accessible.StaticText }
        }
        Column {
            objectName: "musicAlternatives"
            width: parent.width
            spacing: 4
            Repeater {
                model: root.alternatives
                StudioMusicTrackRow {
                    required property var modelData
                    width: parent.width
                    item: modelData
                    busy: root.busy
                    choosing: root.choosing
                    previewing: root.previewing
                    onPreview: link => root.preview(link)
                    onChoose: link => root.choose(link)
                }
            }
            Text {
                width: parent.width
                visible: root.alternatives.length === 0
                text: "Không còn bài nào khác trong danh mục đủ hợp đoạn này."
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        Column {
            width: parent.width
            spacing: 4
            Text { text: "Nhạc của tôi"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium; Accessible.role: Accessible.Heading }
            Repeater {
                model: root.mine
                StudioMusicTrackRow {
                    required property var modelData
                    objectName: "musicMine"
                    width: parent.width
                    item: modelData
                    note: Book.mineNote(modelData)
                    canPreview: root.canPreviewMine
                    busy: root.busy
                    choosing: root.choosing
                    previewing: root.previewing
                    onPreview: link => root.preview(link)
                    onChoose: link => root.choose(link)
                }
            }
            Text {
                width: parent.width
                visible: root.mine.length === 0
                text: root.remote ? "Chưa có bài nào. Thêm nhạc của bạn trên máy tính chủ sách." : "Chưa có bài nào - bấm “Thêm nhạc của bạn” ở đầu trang."
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
    }
}
