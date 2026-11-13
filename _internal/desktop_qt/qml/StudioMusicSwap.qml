import "UiStrings.js" as S
import QtQuick
import ABook
import "StudioMusicLogic.js" as Logic
import "MyMusicText.js" as Music

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
        EditBookSkeleton { width: parent.width; count: 3; label: S.s_dang_tai_bai_khac_2c0e1ec8 }
    }
    InlineError {
        width: parent.width
        open: root.failed && !root.loading
        message: S.s_ban_hay_kiem_tra_ket_noi_roi_tim_lai_bai_n_acc346b4
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
                Reveal { shown: root.alternatives.length === 0 }
                text: S.s_khong_con_bai_nao_khac_trong_danh_muc_du_h_970fe053
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        Column {
            width: parent.width
            spacing: 4
            Text { text: S.s_nhac_cua_toi_f65b7ac6; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium; Accessible.role: Accessible.Heading }
            Repeater {
                model: root.mine
                StudioMusicTrackRow {
                    required property var modelData
                    objectName: "musicMine"
                    width: parent.width
                    item: modelData
                    note: Music.mineNote(modelData)
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
                Reveal { shown: root.mine.length === 0 }
                text: root.remote ? S.s_chua_co_bai_nao_them_nhac_cua_ban_tren_may_0f4b6b30 : S.s_chua_co_bai_nao_bam_them_nhac_cua_ban_o_da_dfd69e49
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
    }
    // Dòng cuối: cả Kho nhạc ở chế độ chọn cho đoạn này (Main.qml đẩy MusicScreen {pickBook, pickScene}; cùng đường lưu ghim).
    // Studio của máy đã ghép thì không: kho và bản tải là của máy này
    DisclosureRow {
        objectName: "swapOpenLibrary"
        Reveal { shown: !root.remote }
        width: parent.width
        icon: "library"
        title: S.s_xem_ca_kho_fa30b353
        onClicked: Nav.musicPickRequested(root.bookId, root.sceneKey)
    }
}
