import "UiStrings.js" as S
import QtQuick
import ABook
import "EditBookLogic.js" as Logic
import "MyMusicText.js" as Music
import "TextWrap.js" as TextWrap

// "Đổi bài" của một đoạn nhạc (SwapTrack của listen/MyMusic.tsx): chọn một bài trong "Nhạc của tôi" thay bài người làm sách gắn. Mỗi lần mở
// (`active`) hỏi lại `GET /api/books/<mã>/music/scenes/<khoá>/alternatives`. Đang tải: khung chờ; lỗi: câu + "Thử lại"; chưa có bài: một câu;
// có bài: danh sách có vạch chia, mỗi bài một nút "Chọn".
Column {
    id: root
    property string bookId: ""
    property string cueKey: ""
    property bool active: false
    property bool busy: false
    property string choosing: ""         // liên kết bài đang được chọn (vòng xoay trên nút)
    property bool loading: true
    property bool failed: false
    property var mine: []
    property int generation: 0
    signal choose(string link)

    function load() {
        const mine = ++generation
        loading = true; failed = false
        Api.call("GET", "/api/books/" + bookId + "/music/scenes/" + encodeURIComponent(cueKey) + "/alternatives", null, function(data, error) {
            if (mine !== root.generation) return
            root.loading = false
            if (error) { Api.notice = ""; root.failed = true; return }
            root.mine = data.mine || []
        })
    }
    onActiveChanged: if (active) load()

    Collapse {
        width: parent.width
        open: root.loading
        EditBookSkeleton { x: 12; y: 8; width: parent.width - 24; count: 3; label: S.s_dang_tai_bai_nhac_0c9498d1; height: implicitHeight + 16 }
    }
    InlineError {
        width: parent.width
        open: root.failed && !root.loading
        message: S.s_ban_hay_kiem_tra_ket_noi_roi_tim_lai_bai_n_acc346b4
        onRetry: root.load()
    }
    Collapse {
        width: parent.width
        open: !root.loading && !root.failed && root.mine.length === 0
        HintText { x: 12; width: parent.width - 24; topPadding: 8; bottomPadding: 8; text: S.s_chua_co_bai_nao_khac_trong_nhac_cua_toi_811d988a }
    }
    Collapse {
        width: parent.width
        open: !root.loading && !root.failed && root.mine.length > 0
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        Repeater {
            model: root.mine
            Item {
                id: row
                required property var modelData
                required property int index
                width: root.width
                height: Math.max(words.height, pin.height) + 16
                Rectangle { Reveal { shown: row.index > 0 } width: parent.width; height: 1; color: Theme.line }
                Rectangle { anchors.fill: parent; color: Theme.bg; opacity: 0.4; z: -1 }
                Column {
                    id: words
                    x: 12
                    y: 8
                    width: parent.width - 24 - pin.width - 12
                    Text { width: parent.width; text: TextWrap.keepDots(row.modelData.title); color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall }
                    Text { id: textItem;
                        width: parent.width
                        Reveal { shown: textItem.text !== "" }
                        text: [row.modelData.creator, row.modelData.duration ? Logic.formatClock(row.modelData.duration) : ""].filter(part => !!part).join("\u00a0·\u00a0")   // tick-ok: độ dài cố định của bài
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                    }
                    Text { id: textItem2;
                        width: parent.width
                        Reveal { shown: textItem2.text !== "" }
                        text: Music.mineNote(row.modelData)
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                    }
                }
                Button {
                    id: pin
                    x: parent.width - width - 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: S.s_chon_1171ca97
                    icon: "pin"
                    kind: "ghost"
                    size: "sm"
                    enabled: !root.busy
                    busy: root.choosing === row.modelData.link
                    onActivated: root.choose(row.modelData.link)
                }
            }
        }
    }
    // Dòng cuối: cả Kho nhạc ở chế độ chọn cho đoạn này (Main.qml đẩy MusicScreen {pickBook, pickScene}; cùng đường lưu ghim)
    DisclosureRow {
        objectName: "swapOpenLibrary"
        width: parent.width
        icon: "library"
        title: S.s_xem_ca_kho_fa30b353
        onClicked: Nav.musicPickRequested(root.bookId, root.cueKey)
    }
}
