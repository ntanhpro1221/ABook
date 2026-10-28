import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Một hàng của bảng dự án (ProjectRow / BrokenRow của ProjectsScreen.tsx): bìa nhỏ · tên + dòng phụ · trạng thái · tiến độ · cập nhật, "…" hiện khi rê chuột /
// có tiêu điểm / đang mở menu (màn hẹp: luôn hiện). Ba khổ như web: "wide" (4 cột), "mid" (3 cột + chỗ "…"), "stacked" (trạng thái và tiến độ xếp dưới tên).
// Tên dài xuống dòng, hàng cao theo chữ - không bao giờ cắt. Nút "…" nằm NGOÀI nút của hàng (hai vùng bấm không lồng nhau).
Item {
    id: root
    property var book: ({})
    property string layoutKind: "wide"          // "wide" | "mid" | "stacked"
    property bool local: true                   // false: Studio từ xa - khôi phục / xoá chỉ làm được trên máy tính
    property string computer: "máy tính"
    property bool menuOpen: false
    signal opened()
    signal menuRequested(Item anchor)
    signal retried()
    signal revealRequested()

    readonly property bool broken: Boolean(book.broken)
    readonly property bool busy: book.brokenKind === "busy"
    readonly property bool stacked: layoutKind === "stacked"
    readonly property bool wide: layoutKind === "wide"
    readonly property real pad: 12
    readonly property real gap: 16
    readonly property real inner: width - 2 * pad
    readonly property var cols: Logic.tableColumns(width, layoutKind)
    readonly property real nameX: cols.nameX
    readonly property real nameW: cols.nameW
    readonly property real statusX: cols.statusX
    readonly property real statusW: cols.statusW
    readonly property real progressX: cols.progressX
    readonly property real progressW: cols.progressW
    readonly property real updatedX: cols.updatedX
    readonly property real updatedW: cols.updatedW
    readonly property var status: Logic.projectStatus(book)
    readonly property bool done: book.phase === "done"
    readonly property bool live: Boolean(book.running || book.starting)
    readonly property bool hot: rowButton.hovered || more.hovered || more.activeFocus || menuOpen
    readonly property bool moreShown: stacked || hot
    readonly property real stackedY: nameBlock.height + 6
    readonly property real contentH: broken ? Math.max(40, brokenText.height, actions.height) : Math.max(40, stacked ? nameBlock.height + (pill.visible ? pill.height + 6 : 0) + 4 + progressCol.height
                                                           : Math.max(nameBlock.height, progressCol.height, pill.height))
    implicitHeight: contentH + 20
    height: implicitHeight
    Accessible.role: Accessible.ListItem
    Accessible.name: book.title || ""

    // ---- dự án bình thường ----
    Item {
        visible: !root.broken
        anchors.fill: parent
        Interactive {
            id: rowButton
            objectName: "projectRowButton"
            anchors.fill: parent
            pressScaling: false
            ringRadius: Theme.radiusControl
            Accessible.role: Accessible.Button
            Accessible.name: (root.book.title || "") + ", " + root.status.label
            onClicked: root.opened()
            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusControl
                color: Theme.hover
                opacity: rowButton.hovered || more.hovered ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
            }
        }
        GeneratedCover { x: root.pad; y: stacked ? 10 : (root.height - 40) / 2; width: 40; height: 40; radius: Theme.radiusControl; title: root.book.title || "" }
        Column {
            id: nameBlock
            x: root.nameX
            y: root.stacked ? 10 : (root.height - height) / 2
            width: root.nameW
            Text {
                objectName: "projectName"
                width: parent.width
                text: root.book.title || ""
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
            }
            Text {
                objectName: "projectSubtitle"
                visible: text !== ""
                width: parent.width
                text: Logic.rowSubtitle(root.book)
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
        }
        // Xong là mặc định, không đeo nhãn trên mọi hàng; chỉ dự án chưa xong mới có viên trạng thái
        StatusPill {
            id: pill
            objectName: "projectStatus"
            visible: Logic.rowShowsPill(root.book)
            x: root.stacked ? root.nameX : root.statusX
            y: root.stacked ? 10 + root.stackedY : (root.height - height) / 2
            label: root.status.label
            tone: root.status.tone
            live: root.status.live
        }
        Column {
            id: progressCol
            x: root.stacked ? root.nameX : root.progressX
            y: root.stacked ? 10 + root.stackedY + (pill.visible ? pill.height + 4 : 0) : (root.height - height) / 2
            width: root.stacked ? root.nameW : root.progressW
            spacing: 4
            Row {
                visible: !root.done
                width: parent.width
                spacing: 8
                StudioBar {
                    objectName: "projectBar"
                    width: parent.width - 36 - 8
                    anchors.verticalCenter: parent.verticalCenter
                    value: root.book.progress ? root.book.progress.overall : 0
                    tone: root.live ? "accent" : "muted"
                    label: "Tiến độ: " + (root.book.title || "")
                }
                Text {
                    objectName: "projectPercent"
                    width: 36
                    horizontalAlignment: Text.AlignRight
                    text: Logic.formatPercent(root.book.progress ? root.book.progress.overall : 0)
                    color: Theme.text
                    font.pixelSize: Theme.sizeCaption
                    font.weight: Theme.weightMedium
                    font.features: { "tnum": 1 }
                }
            }
            Text {
                objectName: "projectDetail"
                width: parent.width
                textFormat: Text.StyledText
                wrapMode: Text.Wrap
                color: Theme.text2
                font.pixelSize: Theme.sizeCaption
                text: {
                    const needs = Logic.rowNeeds(root.book)
                    const detail = Logic.rowDetail(root.book)
                    // Sách "Hoàn tất" mà còn việc của mình: nói ngay trên dòng
                    return root.done && needs.length ? detail + "<font color=\"" + Theme.warning + "\"><b> · " + needs.join(" · ") + "</b></font>" : detail
                }
            }
        }
        Text {
            objectName: "projectUpdated"
            visible: root.wide
            x: root.updatedX
            y: (root.height - height) / 2
            width: root.updatedW
            horizontalAlignment: Text.AlignRight
            text: Logic.rowUpdated(root.book)
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
            font.features: { "tnum": 1 }
            opacity: root.hot ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        }
        IconButton {
            id: more
            objectName: "projectMore"
            x: root.width - root.pad - 32 + 4
            y: root.stacked ? 10 - 2 : (root.height - height) / 2
            width: 32
            height: 32
            icon: "ellipsis"
            iconSize: 16
            ink: Theme.text2
            hoverInk: Theme.text
            Accessible.name: "Tuỳ chọn dự án " + (root.book.title || "")
            opacity: root.moreShown ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
            onClicked: root.menuRequested(more)
        }
    }

    // ---- dự án không mở được ----
    Item {
        visible: root.broken
        anchors.fill: parent
        Rectangle { x: root.pad; y: 10; width: 40; height: 40; radius: Theme.radiusControl; color: Theme.hover }
        Column {
            id: brokenText
            x: root.nameX
            y: 10
            width: root.inner - 40 - root.gap - actions.width - root.gap
            Text {
                objectName: "projectName"
                width: parent.width
                text: root.book.title || ""
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
            }
            Text {
                objectName: "brokenLine"
                width: parent.width
                text: root.broken ? Logic.brokenLine(root.book) : ""
                color: root.busy ? Theme.warning : Theme.danger
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
        }
        Row {
            id: actions
            x: root.width - root.pad - width + 4
            y: 10 - 2
            spacing: 4
            // Đang bị chương trình khác giữ (diệt virus, sao lưu): KHÔNG phải hỏng - chỉ Thử lại / Mở thư mục, không mời xoá
            IconButton { objectName: "brokenRetry"; visible: root.busy; width: 32; height: 32; icon: "rotate-cw"; iconSize: 16; ink: Theme.text2; hoverInk: Theme.text; tip: "Thử lại"; Accessible.name: "Thử lại"; onClicked: root.retried() }
            IconButton { objectName: "brokenReveal"; visible: root.busy && root.local; width: 32; height: 32; icon: "folder-open"; iconSize: 16; ink: Theme.text2; hoverInk: Theme.text; tip: "Mở thư mục"; Accessible.name: "Mở thư mục"; onClicked: root.revealRequested() }
            IconButton {
                id: brokenMore
                objectName: "projectMore"
                visible: !root.busy && root.local
                width: 32; height: 32; icon: "ellipsis"; iconSize: 16; ink: Theme.text2; hoverInk: Theme.text
                Accessible.name: "Tuỳ chọn dự án " + (root.book.title || "")
                onClicked: root.menuRequested(brokenMore)
            }
            // Studio từ xa: khôi phục, mở thư mục, xoá đều là việc ngay trên máy tính - nói thẳng thay vì để chỗ trống
            OnComputerPill { objectName: "brokenOnComputer"; visible: !root.busy && !root.local; verb: "Khôi phục hoặc xoá"; computer: root.computer; maxWidth: 260 }
        }
    }
}
