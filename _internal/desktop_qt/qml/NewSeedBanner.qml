import QtQuick
import ABook
import "NewProjectLogic.js" as Logic

// Khung "Phần N của …" khi tạo phần nối tiếp (SeedBanner): nối sau phần nào, mang theo gì, thiếu gì; "Bỏ nối tiếp" thì sách phân vai lại từ đầu (Hoàn tác trong toast).
// Hẹp: nút bỏ xuống dưới đoạn chữ thay vì ép chữ thành cột hẹp.
Item {
    id: root
    property var form: null
    readonly property var seed: form ? form.draft.seed : undefined
    readonly property bool hasFiles: Boolean(form && form.scan && form.scan.files.length)
    readonly property bool wide: width >= 640
    implicitHeight: shown.height
    height: implicitHeight

    Collapse {
        id: shown
        width: parent.width
        open: Boolean(root.seed)
        // Giữ nội dung cuối trong lúc khép
        property var last: null
        Connections { target: root; function onSeedChanged() { if (root.seed) shown.last = root.seed } }
        Component.onCompleted: last = root.seed
        Item {
            id: box
            readonly property var seed: root.seed || shown.last
            width: parent.width
            height: 20 + Math.max(body.height, root.wide ? drop.height : body.height + 4 + drop.height) + 16
            Icon { x: 0; y: 20 + 16 + 2; name: "layers"; size: 16; color: Theme.accentText }
            Column {
                id: body
                objectName: "newSeedBanner"
                x: 28
                y: 36
                width: root.wide ? parent.width - 28 - drop.width - 12 : parent.width - 28
                spacing: 2
                Prose { strong: true; tone: Theme.text; text: box.seed ? "Phần " + box.seed.part + " của “" + box.seed.title + "”" : " " }
                Prose {
                    visible: Boolean(box.seed) && Boolean(box.seed.clickedTitle)
                    text: box.seed ? "Nối sau “" + (box.seed.latestTitle || box.seed.title) + "”, giữ " + Logic.carriedText(box.seed.carries) + "." : ""
                }
                Prose {
                    visible: Boolean(box.seed) && !box.seed.clickedTitle
                    text: box.seed ? "Giữ " + Logic.carriedText(box.seed.carries) + ", giọng và cách đọc tên." : ""
                }
                // Khung "chưa có chương mới" tắt ngay khi đã chọn / thêm được file
                Prose {
                    objectName: "newSeedEmpty"
                    visible: Boolean(box.seed) && box.seed.empty && !root.hasFiles
                    topPadding: visible ? 4 : 0
                    text: box.seed ? (box.seed.folder ? "Chọn file mới sau " + (box.seed.lastChapter || "chương cuối phần trước") + " ở dưới." : "Chọn file chương mới ở dưới.") : ""
                }
                Prose {
                    objectName: "newSeedModelMissing"
                    visible: Boolean(box.seed) && Boolean(box.seed.analysisModelMissing)
                    topPadding: visible ? 4 : 0
                    tone: Theme.warning
                    text: "Thiếu bộ phân tích của phần trước; đổi bộ có thể đổi phân vai. Chọn lại ở Chất lượng."
                }
                Prose {
                    objectName: "newSeedUnanalyzed"
                    visible: Boolean(box.seed) && !box.seed.analyzed
                    topPadding: visible ? 4 : 0
                    tone: Theme.warning
                    text: "Phần trước chưa phân tích xong - chỉ mang được những gì đã có tới lúc này."
                }
            }
            TextLink {
                id: drop
                objectName: "newSeedDrop"
                x: root.wide ? parent.width - width : 28
                y: root.wide ? 20 + 12 : 36 + body.height + 4
                text: "Bỏ nối tiếp"
                small: true
                onClicked: root.form.dropSeed()
            }
        }
    }
}
