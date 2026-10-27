import QtQuick
import ABook
import "ProjectsLogic.js" as Logic
import "PeerStudio.js" as Peer

// Bảng dự án Studio của máy đang xem (studio/ProjectsScreen.tsx), CHỈ ĐỌC: tên · trạng thái · tiến độ · cập nhật, vạch mảnh giữa các mục,
// không khung. Cột như COLUMNS của web ở màn md (40 | 1fr | 190 | 170 | 36) và xl, cửa sổ từ 1280 (40 | 1fr | 230 | 190 | 100, thêm cột
// Cập nhật). Hàng không bấm được và không có "…" (trang dự án, menu dự án chưa port - PROGRESS.md D4 "Open"). Tên dài xuống dòng, không cắt.
Item {
    id: root
    property var library: null         // lời đáp /api/library của máy ấy ({root, rootMissing, books}); null = chưa có
    property bool loading: true
    property bool failed: false        // lần hỏi gần nhất lỗi
    property string peer: ""
    property string computer: "máy tính"   // tên máy đang xem (OnComputerOnly)
    property real nowMs: Date.now()
    signal retry()

    readonly property var books: library && Array.isArray(library.books) ? library.books : []
    readonly property var entries: Logic.ordered(books).map(e => ({key: Logic.entryKey(e), entry: e}))
    readonly property bool wide: (Window.width || width) >= 1280
    readonly property var columns: wide ? [40, 230, 190, 100] : [40, 190, 170, 36]
    readonly property int gap: 16
    // Ô x / rộng của bốn cột cố định quanh cột tên (1fr)
    readonly property real nameX: columns[0] + gap
    readonly property real tailWidth: columns[1] + columns[2] + columns[3] + 3 * gap
    readonly property real nameW: Math.max(0, width - nameX - tailWidth)
    readonly property real statusX: nameX + nameW + gap
    readonly property real progressX: statusX + columns[1] + gap
    readonly property real updatedX: progressX + columns[2] + gap
    readonly property string state_: loading && !library ? "loading" : failed && !books.length ? "error" : library && library.rootMissing ? "missing" : !books.length ? "empty" : "list"

    function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
    implicitHeight: content.y + content.height
    // Đồng hồ cho "N phút trước": đi theo phút, không nháy mỗi giây
    Timer { interval: 30000; repeat: true; running: root.visible; onTriggered: root.nowMs = Date.now() }

    // Đầu bảng: cùng một hàng khi đang tải và khi đã có dự án - khung chờ đứng đúng chỗ các hàng thật
    // Nhãn cột (label-section: 12 px, 600, chữ hoa giãn 0,06em)
    component HeadText: Text {
        color: Theme.text2
        font.pixelSize: Theme.sizeCaption
        font.weight: 600
        font.capitalization: Font.AllUppercase
        font.letterSpacing: Theme.sizeCaption * 0.06
        height: 16
        verticalAlignment: Text.AlignVCenter
    }
    component TableHead: Item {
        width: root.width
        height: 16 + 8 + 1
        HeadText { x: root.nameX; text: "Dự án" }
        HeadText { x: root.statusX; text: "Trạng thái" }
        HeadText { x: root.progressX; text: "Tiến độ" }
        HeadText { visible: root.wide; x: root.updatedX; width: root.columns[3]; horizontalAlignment: Text.AlignRight; text: "Cập nhật" }
        Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.line }
    }

    // Viên trạng thái (StatusPill): nền nhạt của tông, chấm 6 px hay vạch nhạc khi đang chạy
    component StatusPill: Rectangle {
        id: pill
        property string label: ""
        property string tone: "muted"
        property bool live: false
        readonly property color ink: ({accent: Theme.accentText, success: Theme.success, danger: Theme.danger, warning: Theme.warning, muted: Theme.text2})[tone] || Theme.text2
        objectName: "projectStatus"
        width: pillRow.implicitWidth + 20
        height: 24
        radius: height / 2
        color: ({accent: Theme.accentSoft, success: Theme.successSoft, danger: Theme.dangerSoft, warning: Theme.warningSoft, muted: Theme.hover})[tone] || Theme.hover
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        Row {
            id: pillRow
            x: 10
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            Rectangle { visible: !pill.live; width: 6; height: 6; radius: width / 2; color: pill.ink; anchors.verticalCenter: parent.verticalCenter }
            Vu { visible: pill.live; color: pill.ink; anchors.verticalCenter: parent.verticalCenter }
            Text { text: pill.label; color: pill.ink; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
        }
    }
    // Vạch nhạc (Vu của shared/ui.tsx, .vu của styles.css): bốn vạch 3 px nhảy 0,3 <-> 1, lệch pha; giảm chuyển động thì đứng yên
    component Vu: Item {
        id: vu
        property color color: Theme.text2
        property real t: 0
        objectName: "projectVu"
        width: 4 * 3 + 3 * 2
        height: 10
        NumberAnimation on t { from: 0; to: 1; duration: 1000; loops: Animation.Infinite; running: vu.visible && !Theme.reduceMotion }
        function scaleAt(delay) {
            if (Theme.reduceMotion) return 1
            const p = ((vu.t - delay) % 1 + 1) % 1
            const tri = p < 0.5 ? p * 2 : (1 - p) * 2
            const eased = tri < 0.5 ? 2 * tri * tri : 1 - Math.pow(-2 * tri + 2, 2) / 2
            return 0.3 + 0.7 * eased
        }
        Repeater {
            model: [-0.0, -0.35, -0.7, -0.2]
            Rectangle {
                required property int index
                required property real modelData
                x: index * 5
                width: 3
                height: vu.height * vu.scaleAt(modelData)
                y: vu.height - height
                radius: width / 2
                color: vu.color
            }
        }
    }
    // Thanh tiến độ cỡ sm (Progress): rãnh line, phần đã làm màu nhấn khi đang chạy (có vệt sáng chạy qua), mực ba khi đứng
    component Bar: Rectangle {
        id: bar
        property real value: 0
        property bool running: false
        objectName: "projectBar"
        height: 6
        radius: height / 2
        color: Theme.line
        clip: true
        Rectangle {
            id: fill
            objectName: "projectBarFill"
            width: bar.width * Math.max(0, Math.min(1, bar.value))
            height: parent.height
            radius: height / 2
            color: bar.running ? Theme.accent : Theme.text3
            clip: true
            Behavior on width { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Behavior on color { ColorAnimation { duration: Theme.motionMedium } }
            Rectangle {
                id: sheen
                visible: bar.running && !Theme.reduceMotion
                width: fill.width * 0.4
                height: parent.height
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "transparent" }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 250 / 255, 240 / 255, 0.35) }
                    GradientStop { position: 1; color: "transparent" }
                }
                property real p: 0
                x: -width + p * 3.5 * width          // translateX(-100%) -> translateX(250%)
                NumberAnimation on p { from: 0; to: 1; duration: 1800; loops: Animation.Infinite; easing.type: Easing.InOutQuad; running: sheen.visible }
            }
        }
    }
    component Skel: Rectangle { color: Theme.line; radius: Theme.radiusControl }

    // Một dòng dự án
    component ProjectRow: Item {
        id: row
        property var book: ({})
        readonly property var status: Logic.projectStatus(book)
        readonly property bool live: Boolean(book.running || book.starting)
        readonly property bool done: book.phase === "done"
        readonly property string detail: Logic.detail(book)
        readonly property var needs: Logic.needs(book)
        readonly property string sub: Logic.subLine(book)
        objectName: "projectRow"
        width: root.width
        height: Math.max(40, nameCol.height, statusPill.height, progressCol.height, updated.height) + 20
        CoverView {
            x: 0
            y: (row.height - height) / 2
            width: 40
            height: 40
            radius: Theme.radiusControl
            small: true
            title: row.book.title || ""
            part: row.book.series ? row.book.series.part || 0 : 0
            coverKey: Logic.coverKey(row.book, root.peer)
        }
        Column {
            id: nameCol
            x: root.nameX
            y: (row.height - height) / 2
            width: root.nameW
            Text {
                objectName: "projectTitle"
                width: parent.width
                text: row.book.title || ""
                color: Theme.text
                wrapMode: Text.Wrap
                lineHeightMode: Text.FixedHeight
                lineHeight: 24
                font.pixelSize: Theme.sizeBody
                font.weight: Theme.weightMedium
            }
            Text {
                objectName: "projectSub"
                visible: text !== ""                             // DotJoin rỗng không chiếm dòng
                width: parent.width
                text: row.sub
                color: Theme.text2
                wrapMode: Text.Wrap
                lineHeightMode: Text.FixedHeight
                lineHeight: 19.5
                font.pixelSize: 13
            }
        }
        // Xong là mặc định, không đeo nhãn trên mọi hàng; chỉ dự án chưa xong (hay đang xếp hàng) mới có viên trạng thái
        StatusPill {
            id: statusPill
            visible: !(row.done && !row.book.queuePosition)
            x: root.statusX
            y: (row.height - height) / 2
            label: row.status.label
            tone: row.status.tone
            live: row.status.live
            Accessible.name: row.status.label
        }
        Item {
            id: progressCol
            x: root.progressX
            y: (row.height - height) / 2
            width: root.columns[2]
            height: row.done ? doneText.height : running.height
            // Sách "Hoàn tất" mà còn việc của mình: nói ngay trên dòng
            Text {
                id: doneText
                objectName: "projectDone"
                visible: row.done
                width: parent.width
                text: row.needs.length ? root.esc(row.detail) + "<span style=\"color:" + Theme.warning + ";font-weight:500\"> · " + root.esc(row.needs.join(" · ")) + "</span>" : row.detail
                textFormat: row.needs.length ? Text.StyledText : Text.PlainText
                color: Theme.text2
                wrapMode: Text.Wrap
                lineHeightMode: Text.FixedHeight
                lineHeight: 16
                font.pixelSize: Theme.sizeCaption
            }
            Column {
                id: running
                visible: !row.done
                width: parent.width
                spacing: 4
                Item {
                    width: parent.width
                    height: 16
                    Bar {
                        width: parent.width - 36 - 8
                        anchors.verticalCenter: parent.verticalCenter
                        value: (row.book.progress || {}).overall || 0
                        running: row.live
                        Accessible.role: Accessible.ProgressBar
                        Accessible.name: "Tiến độ: " + (row.book.title || "")
                    }
                    Text {
                        objectName: "projectPercent"
                        x: parent.width - 36
                        width: 36
                        height: 16
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignRight
                        text: Logic.formatPercent((row.book.progress || {}).overall || 0)
                        color: Theme.text
                        font.pixelSize: Theme.sizeCaption
                        font.weight: Theme.weightMedium
                        font.features: {"tnum": 1}
                    }
                }
                Text {
                    objectName: "projectDetail"
                    width: parent.width
                    text: row.detail
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    lineHeightMode: Text.FixedHeight
                    lineHeight: 16
                    font.pixelSize: Theme.sizeCaption
                }
            }
        }
        // Trạng thái đã ở cột Trạng thái - cột này chỉ nói lúc nào
        Text {
            id: updated
            objectName: "projectUpdated"
            visible: root.wide
            x: root.updatedX
            y: (row.height - height) / 2
            width: root.columns[3]
            horizontalAlignment: Text.AlignRight
            wrapMode: Text.Wrap
            text: row.live ? "vừa xong" : Logic.formatRelative(row.book.updatedAt, root.nowMs)
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
            font.features: {"tnum": 1}
        }
    }

    Item {
        id: content
        y: 32
        width: root.width
        height: root.state_ === "loading" ? skeleton.y + skeleton.height
              : root.state_ === "error" ? 48 + error.height
              : root.state_ === "missing" ? 48 + missing.height
              : root.state_ === "empty" ? 48 + empty.height
              : list.y + list.height

        TableHead { visible: root.state_ === "loading" || root.state_ === "list" }

        // Khung chờ đúng hình một hàng của bảng: hai vạch đứng trong hai hộp dòng của tên và dòng phụ
        Column {
            id: skeleton
            objectName: "projectsSkeleton"
            visible: root.state_ === "loading"
            y: 25
            width: root.width
            SequentialAnimation on opacity {
                running: skeleton.visible && !Theme.reduceMotion
                loops: Animation.Infinite
                NumberAnimation { to: 0.6; duration: 800; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1; duration: 800; easing.type: Easing.InOutSine }
            }
            Repeater {
                model: 5
                Item {
                    required property int index
                    width: root.width
                    height: 63.5
                    Rectangle { visible: index > 0; width: parent.width; height: 1; color: Theme.line }
                    Skel { x: 0; y: (parent.height - 40) / 2; width: 40; height: 40 }
                    Column {
                        x: root.nameX
                        y: (parent.height - 43.5) / 2
                        width: root.nameW
                        Item { width: parent.width; height: 24; Skel { width: parent.width / 2; height: 16; anchors.verticalCenter: parent.verticalCenter } }
                        Item { width: parent.width; height: 19.5; Skel { width: parent.width / 3; height: 12; anchors.verticalCenter: parent.verticalCenter } }
                    }
                    Skel { x: root.statusX; y: (parent.height - 24) / 2; width: 112; height: 24; radius: height / 2 }
                    Skel { x: root.progressX; y: (parent.height - 6) / 2; width: root.columns[2]; height: 6; radius: height / 2 }
                    Skel { visible: root.wide; x: root.updatedX + root.columns[3] - 64; y: (parent.height - 12) / 2; width: 64; height: 12 }
                }
            }
        }

        DevicesError {
            id: error
            objectName: "projectsError"
            y: 48
            width: root.width
            open: root.state_ === "error"
            visible: root.state_ === "error"
            message: "Chưa tải được danh sách dự án; bạn hãy kiểm tra kết nối rồi thử lại."
            onRetry: root.retry()
        }

        // Thư mục thư viện của máy ấy không còn (MissingLibrary, nhánh Studio từ xa: chọn lại chỉ làm được ở máy ấy)
        EmptyState {
            id: missing
            objectName: "projectsMissing"
            visible: root.state_ === "missing"
            y: 48
            width: root.width
            icon: "folder-x"
            title: "Không thấy thư mục thư viện"
            text: "Ổ chưa cắm, hay thư mục đã đổi tên. Cắm lại ổ hoặc chọn chỗ mới; chỗ đang nghe vẫn giữ."
            Rectangle {
                objectName: "onComputerOnly"
                width: chip.implicitWidth + 20
                height: 24
                radius: height / 2
                color: Theme.sunken
                Row {
                    id: chip
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    Icon { name: "monitor"; size: 14; color: Theme.text2; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: Peer.onComputerLine("Chọn lại thư mục thư viện", root.computer); color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                }
            }
        }

        // Rỗng: một câu, không khung (chỉ đọc: chưa có nút "Dự án mới" - PROGRESS.md D4 "Open")
        EmptyState {
            id: empty
            objectName: "projectsEmpty"
            visible: root.state_ === "empty"
            y: 48
            width: root.width
            icon: "clapperboard"
            title: "Chưa có dự án"
            text: "Biến một truyện thành sách nói nhiều giọng."
        }

        // Các mục: một dự án, hay các phần của một cuốn dưới một dòng tên nhóm; vạch mảnh giữa các mục
        StudioRows {
            id: list
            objectName: "projectsList"
            visible: root.state_ === "list"
            y: 25
            width: root.width
            items: root.entries
            keyField: "key"
            delegate: Component {
                Column {
                    property var modelData: null
                    readonly property var entry: modelData ? modelData.entry : null
                    width: root.width
                    Text {
                        objectName: "projectGroup"
                        visible: entry !== null && entry.kind === "series"
                        width: parent.width
                        topPadding: 12
                        bottomPadding: 2
                        wrapMode: Text.Wrap
                        textFormat: Text.StyledText
                        text: visible ? root.esc(entry.name) + "<span style=\"font-weight:400\"> · " + entry.books.length + " " + entry.unit + "</span>" : ""
                        color: Theme.text2
                        font.pixelSize: Theme.sizeCaption
                        font.weight: Theme.weightMedium
                    }
                    Repeater {
                        model: entry ? (entry.kind === "book" ? [entry.book] : entry.books) : []
                        ProjectRow { required property var modelData; book: modelData }
                    }
                }
            }
        }
    }
}
