import QtQuick
import ABook
import "EditBookLogic.js" as Logic

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
        EditBookSkeleton { x: 12; y: 8; width: parent.width - 24; count: 3; label: "Đang tải bài nhạc"; height: implicitHeight + 16 }
    }
    EditBookError {
        width: parent.width
        open: root.failed && !root.loading
        message: "Bạn hãy kiểm tra kết nối rồi tìm lại bài nhạc."
        onRetry: root.load()
    }
    Collapse {
        width: parent.width
        open: !root.loading && !root.failed && root.mine.length === 0
        HintText { x: 12; width: parent.width - 24; topPadding: 8; bottomPadding: 8; text: "Chưa có bài nào khác trong Nhạc của tôi." }
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
                Rectangle { visible: row.index > 0; width: parent.width; height: 1; color: Theme.line }
                Rectangle { anchors.fill: parent; color: Theme.bg; opacity: 0.4; z: -1 }
                Column {
                    id: words
                    x: 12
                    y: 8
                    width: parent.width - 24 - pin.width - 12
                    Text { width: parent.width; text: row.modelData.title; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall }
                    Text {
                        width: parent.width
                        visible: text !== ""
                        text: [row.modelData.creator, row.modelData.duration ? Logic.formatClock(row.modelData.duration) : ""].filter(part => !!part).join(" · ")
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                        font.features: {"tnum": 1}
                    }
                    Text {
                        width: parent.width
                        visible: text !== ""
                        text: Logic.mineNote(row.modelData)
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                    }
                }
                Button {
                    id: pin
                    x: parent.width - width - 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Chọn"
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
}
