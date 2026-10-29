import QtQuick
import ABook
import "NameLogic.js" as N
import "StudioLogic.js" as Studio
import "WorkLogic.js" as W

// Tab Nhân vật, mục "Cách đọc tên" (NameReadings.tsx, webui/name_readings.py): mọi tên riêng máy đọc thế nào - kể cả tên máy chắc và cách người nghe đã chọn, hai thứ hộp việc không bao giờ
// hỏi lại. Sửa ở đây đi đúng đường của thẻ cách đọc: ghi mong muốn, dây chuyền áp ở ranh giới chương và thu lại những câu có tên ấy. Tìm không phân biệt hoa thường, dấu, gạch nối; gõ đúng
// một chữ liền mà không khớp tên nào thì mời thêm cách đọc cho nó. `jump`: mở từ nút "Mọi cách đọc tên…" trên thẻ hộp việc - cuộn tới mục khi danh sách đã tải; `name`: tên của thẻ ấy, điền sẵn vào ô tìm.
Item {
    id: root
    objectName: "nameReadings"
    property var work: null
    property bool jump: false
    property string name: ""
    property string query: ""
    property int limit: N.PAGE
    property bool revealed: false
    property string heldTyped: ""
    signal revealRequested(var target)

    readonly property var view: work && work.names.data ? work.names.data : null
    readonly property bool shown: view !== null && ((view.items || []).length > 0 || Boolean(view.unseen))
    readonly property string typed: query.trim()
    readonly property var items: view ? view.items || [] : []
    readonly property var found: N.found(items, typed)
    // Bất kỳ chữ liền nhau nào ("TP.HCM", "km/h") cũng thêm được, không chỉ tên
    readonly property bool addable: found.length === 0 && N.single(typed)
    readonly property bool analyzed: work ? work.analyzed : true
    // Tính lại từ gốc (không đọc `addable`): thứ tự cập nhật các thuộc tính phụ thuộc không đảm bảo trong lúc `typed` vừa đổi
    function holdFresh() { if (N.found(items, typed).length === 0 && N.single(typed)) heldTyped = typed }
    onAddableChanged: holdFresh()
    onTypedChanged: holdFresh()
    width: parent ? parent.width : 600
    height: outer.height
    visible: outer.height > 0

    function setQuery(text) { query = text; search.text = text; limit = N.PAGE }
    onNameChanged: if (name !== "") setQuery(name)
    Component.onCompleted: if (name !== "") setQuery(name)
    // Cuộn tới mục khi danh sách đã tải (cuộn sớm hơn thì phần phía trên hiện ra sau đẩy mục xuống khỏi màn)
    onShownChanged: reveal()
    onJumpChanged: reveal()
    function reveal() {
        if (!jump || !shown || revealed) return
        revealed = true
        Qt.callLater(function() { root.revealRequested(heading) })
    }

    Collapse {
        id: outer
        width: root.width
        open: root.shown
        Column {
            width: parent.width
            Item { width: 1; height: 32 }
            Text {
                id: heading
                objectName: "nameReadingsTitle"
                width: parent.width
                height: Math.max(56, implicitHeight)
                verticalAlignment: Text.AlignVCenter
                textFormat: Text.RichText
                text: "Cách đọc tên <span style=\"color:" + W.cssColor(Theme.text2) + "; font-weight:400\">" + W.esc(N.heading(root.analyzed, N.countedNames(root.items))) + "</span>"
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeSection
                font.weight: Theme.weightMedium
            }
            Text { width: Math.min(parent.width, 672); topPadding: 4; text: N.INTRO; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            SharedOffer { work: root.work; width: parent.width }
            NameAddWord { work: root.work; width: parent.width }
            Item { width: 1; height: 12 }
            // Ô tìm: kính lúp trái, nút xoá phải (mờ vào / ra tại chỗ)
            Item {
                width: Math.min(parent.width, 400)
                height: search.height
                FormField {
                    id: search
                    objectName: "nameSearch"
                    width: parent.width
                    label: "Tìm tên"
                    placeholderText: "Tìm tên, hoặc gõ một chữ để thêm cách đọc"
                    fill: Theme.panel
                    topPadding: 8
                    bottomPadding: 8
                    leftPadding: 34
                    rightPadding: 34
                    implicitHeight: Math.max(36, contentHeight + 16)
                    onTextChanged: { root.query = text; root.limit = N.PAGE }
                }
                Icon { x: 10; y: (search.height - height) / 2; name: "search"; size: 16; color: Theme.text3 }
                IconButton {
                    objectName: "nameSearchClear"
                    x: parent.width - 30
                    y: (search.height - height) / 2
                    implicitWidth: 24
                    implicitHeight: 24
                    icon: "x"
                    iconSize: 14
                    ink: Theme.text3
                    hoverInk: Theme.text
                    tip: "Xoá ô tìm"
                    Accessible.name: "Xoá ô tìm"
                    opacity: root.query !== "" ? 1 : 0
                    visible: opacity > 0
                    enabled: root.query !== ""
                    Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
                    onClicked: { search.text = ""; search.forceActiveFocus() }
                }
            }
            Item { width: 1; height: 12 }
            StudioRows {
                objectName: "nameRows"
                width: parent.width
                items: root.found.slice(0, root.limit)
                keyField: "surface"
                delegate: Component {
                    NameRow {
                        property var modelData: ({surface: "", spoken: "", byListener: false, lines: 0, requested: null, example: null})
                        work: root.work
                        item: modelData || ({})
                    }
                }
            }
            // Chữ vừa gõ để thêm: một dòng riêng (chưa có trong danh sách)
            Collapse {
                width: parent.width
                open: root.addable
                NameRow {
                    objectName: "nameFresh"
                    work: root.work
                    fresh: true
                    item: N.freshItem(root.heldTyped)
                }
            }
            Collapse {
                width: parent.width
                open: root.found.length === 0 && !root.addable && root.typed !== ""
                Text { objectName: "nameNoMatch"; width: parent.width; topPadding: 12; text: N.noMatch(root.typed); color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            }
            Collapse {
                width: parent.width
                open: root.found.length > root.limit
                Item {
                    width: parent.width
                    height: 12 + more.height
                    TextLink {
                        id: more
                        objectName: "nameMore"
                        y: 12
                        text: N.moreNames(root.found.length - root.limit)
                        onClicked: root.limit += N.PAGE * 3
                    }
                }
            }
            Collapse {
                width: parent.width
                open: Boolean(root.view && root.view.unseen > 0) && root.typed === ""
                Text { objectName: "nameUnseen"; width: parent.width; topPadding: 8; text: root.view ? N.unseenLine(root.view.unseen) : ""; color: Theme.text3; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
            }
            Item { width: 1; height: 24 }
        }
    }
}
