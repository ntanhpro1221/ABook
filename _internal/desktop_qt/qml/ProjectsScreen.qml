import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Studio › Dự án (ProjectsScreen.tsx; DESIGN.md mục 7): bảng gọn tên · trạng thái · tiến độ · cập nhật, MỘT việc chính là "Dự án mới". Đang chạy lên đầu,
// cuốn nhiều phần gom dưới một dòng tên. Chưa tải xong: khung chờ đúng hình hàng thật; không tải được / thiếu thư mục thư viện / chưa có dự án: lời
// nói thẳng kèm việc làm kế tiếp. "…" của hàng: mở thư mục, đổi tên, làm tiếp, xoá (Studio từ xa: việc chỉ làm được ở máy tính thì nói thẳng).
// Bảng giữ mô hình hàng theo KHOÁ (id dự án): nhịp hỏi 5 s / 15 s chỉ đổi nội dung hàng tại chỗ, không dựng lại - chỗ cuộn và rê chuột không nhảy.
FocusScope {
    id: root
    property var store: null
    signal projectOpened(string id)
    signal newRequested()
    signal listenRequested(string id)
    signal newProjectRequested(string mode, string id)

    readonly property real contentW: Math.min(width - 2 * Theme.margin, 1180)
    readonly property real contentX: (width - contentW) / 2
    // Hàng bù đệm 12 hai bên: bìa thẳng mép tiêu đề, cột cuối thẳng mép phải (-mx-3 của web)
    readonly property real rowW: contentW + 24
    readonly property string kind: Logic.tableKind(rowW)
    readonly property var cols: Logic.tableColumns(rowW, kind)
    readonly property var books: store ? store.books : []
    readonly property bool loading: store ? store.libraryLoading : true
    readonly property bool failed: store ? store.libraryError !== "" && store.libraryData === null : false
    readonly property bool rootMissing: !!(store && store.libraryData && store.libraryData.rootMissing)
    readonly property bool empty: !loading && !failed && !rootMissing && books.length === 0
    readonly property bool listed: !loading && !failed && !rootMissing && books.length > 0
    readonly property bool local: store ? !store.remote : true
    property var tableData: ({rows: [], byKey: ({})})
    property string menuId: ""
    property var menuBook: ({})
    readonly property alias header: header
    readonly property alias list: list
    readonly property alias dialogs: dialogs
    readonly property alias rowKeys: rowModel

    function sync() {
        const rows = Logic.tableRows(books)
        const byKey = {}
        for (const row of rows) byKey[row.key] = row
        tableData = {rows: rows, byKey: byKey}
        // Chỉ thêm / bỏ / dời đúng hàng đổi: hàng còn lại giữ nguyên bản (chỗ cuộn, rê chuột, phần đang mở)
        for (let i = rowModel.count - 1; i >= 0; --i) if (!byKey[rowModel.get(i).key]) rowModel.remove(i)
        for (let i = 0; i < rows.length; ++i) {
            if (i < rowModel.count && rowModel.get(i).key === rows[i].key) continue
            let from = -1
            for (let j = i + 1; from < 0 && j < rowModel.count; ++j) if (rowModel.get(j).key === rows[i].key) from = j
            if (from >= 0) rowModel.move(from, i, 1)
            else rowModel.insert(i, {key: rows[i].key})
        }
    }
    onBooksChanged: sync()
    Component.onCompleted: sync()
    ListModel { id: rowModel }

    function bookById(id) {
        for (const book of books) if (book.id === id) return book
        return menuBook
    }

    ScreenHeader {
        id: header
        objectName: "projectsHeader"
        x: root.contentX
        width: root.contentW
        title: "Studio"
        subtitle: root.loading || root.failed ? " " : Logic.projectsSubtitle(root.books.length)
        Button {
            objectName: "newProject"
            opacity: root.listed ? 1 : 0
            enabled: opacity > 0
            text: "Dự án mới"
            icon: "plus"
            kind: "ghost"
            onClicked: root.newRequested()
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        }
        IconButton {
            id: studioMore
            objectName: "studioMore"
            visible: Boolean(root.store && root.store.info && root.store.info.dialogs)
            icon: "ellipsis"
            iconSize: 20
            tip: "Tuỳ chọn Studio"
            Accessible.name: "Tuỳ chọn Studio"
            onClicked: { studioMenu.anchorItem = studioMore; studioMenu.show() }
        }
    }

    // Khung chữ dưới đầu màn: mép trái thẳng tiêu đề; bảng tràn ra 12 px mỗi bên (nền rê chuột, vạch kẻ), phần chữ thẳng mép
    Item {
        id: frame
        objectName: "projectsBody"
        x: root.contentX
        y: header.height + 24
        width: root.contentW
        height: root.height - y
        // ---- đầu bảng ----
        Item {
            id: head
            objectName: "tableHead"
            visible: (root.loading || root.listed) && root.kind !== "stacked"
            x: -12
            y: 0
            width: root.rowW
            height: visible ? 28 : 0
            Rectangle { x: 12; y: parent.height - 1; width: parent.width - 24; height: 1; color: Theme.line }
            Text { x: root.cols.nameX; y: 4; width: root.cols.nameW; text: "Dự án"; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
            Text { x: root.cols.statusX; y: 4; width: root.cols.statusW; text: "Trạng thái"; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
            Text { x: root.cols.progressX; y: 4; width: root.cols.progressW; text: "Tiến độ"; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
            Text { visible: root.kind === "wide"; x: root.cols.updatedX; y: 4; width: root.cols.updatedW; horizontalAlignment: Text.AlignRight; text: "Cập nhật"; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
        }

        // ---- khung chờ ----
        EditBookSkeleton {
            objectName: "projectsSkeleton"
            visible: root.loading
            x: 0
            y: head.y + (head.visible ? head.height : 0) + 12
            width: root.contentW
            shape: "rows"
            count: 5
            label: "Đang tải danh sách dự án"
        }

        // ---- bảng ----
        ListView {
            id: list
            objectName: "projectsList"
            visible: root.listed
            x: -12
            y: head.y + (head.visible ? head.height : 0)
            width: root.rowW
            height: frame.height - y
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: rowModel
            bottomMargin: 64
            reuseItems: false
            cacheBuffer: 600
            add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.reduceMotion ? 0 : Theme.motionMedium } }
            remove: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Theme.reduceMotion ? 0 : Theme.motionFastOut } }
            displaced: Transition { NumberAnimation { properties: "y"; duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            delegate: Item {
                id: cell
                required property string key
                readonly property var row: root.tableData.byKey[key] || ({})
                width: ListView.view.width
                height: body.item ? body.item.height : 0
                Loader {
                    id: body
                    width: parent.width
                    sourceComponent: cell.row.kind === "group" ? groupHead : projectRow
                }
                Component {
                    id: groupHead
                    Item {
                        height: groupText.height + 16 + 2
                        Text {
                            id: groupText
                            objectName: "groupHead"
                            x: 12; y: 12
                            width: parent.width - 24
                            text: cell.row.label || ""
                            color: Theme.text2
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeCaption
                            font.weight: Theme.weightMedium
                        }
                    }
                }
                Component {
                    id: projectRow
                    ProjectRow {
                        book: cell.row.book || ({})
                        layoutKind: root.kind
                        local: root.local
                        computer: root.store ? root.store.computerName : "máy tính"
                        menuOpen: menu.open && root.menuId === (cell.row.id || "")
                        onOpened: root.projectOpened(cell.row.id)
                        onMenuRequested: anchor => {
                            root.menuId = cell.row.id
                            root.menuBook = cell.row.book
                            menu.items = Logic.rowMenu(cell.row.book, root.local, root.store.computerName)
                            menu.anchorItem = anchor
                            menu.show()
                        }
                        onRetried: root.store.loadLibrary()
                        onRevealRequested: root.store.reveal(cell.row.id)
                    }
                }
            }
            SmoothWheel { flick: list }
        }
        ScrollEdges { target: list; color: Theme.bg; x: list.x; y: list.y; width: list.width; height: list.height }
        Scrollbar { target: list }

        // ---- lời nói thẳng ----
        DevicesError {
            objectName: "projectsError"
            x: 0
            y: 24
            width: root.contentW
            open: root.failed
            message: "Chưa tải được danh sách dự án; bạn hãy kiểm tra kết nối rồi thử lại."
            onRetry: root.store.loadLibrary()
        }
        EmptyState {
            objectName: "projectsMissing"
            visible: root.rootMissing
            x: 0
            y: 48 - 56
            width: root.contentW
            icon: "folder-x"
            title: root.local && root.store && root.store.libraryData && root.store.libraryData.root
                   ? "Không thấy thư mục thư viện “" + Logic.folderName(root.store.libraryData.root) + "”" : "Không thấy thư mục thư viện"
            text: "Ổ chưa cắm, hay thư mục đã đổi tên. Cắm lại ổ hoặc chọn chỗ mới; chỗ đang nghe vẫn giữ."
            Button { visible: root.local; text: "Chọn thư mục"; icon: "settings"; onClicked: if (Nav.stack) Nav.stack.show(2) }
            OnComputerPill { visible: !root.local; verb: "Chọn lại thư mục thư viện"; computer: root.store ? root.store.computerName : "máy tính" }
        }
        EmptyState {
            objectName: "projectsEmpty"
            visible: root.empty
            x: 0
            y: 48 - 56
            width: root.contentW
            icon: "clapperboard"
            title: "Chưa có dự án"
            text: "Biến một truyện thành sách nói nhiều giọng."
            Button { objectName: "newProjectEmpty"; text: "Dự án mới"; icon: "plus"; size: "lg"; onClicked: root.newRequested() }
        }

    }

    // ---- menu ----
    ProjectMenu {
        id: menu
        objectName: "projectMenu"
        onPicked: key => dialogs.perform(key, root.bookById(root.menuId))
    }
    ProjectMenu {
        id: studioMenu
        objectName: "studioMenu"
        items: [Logic.item("openExisting", "folder-open", "Mở dự án có sẵn…")]
        onPicked: root.store.openExisting(function(id) { root.projectOpened(id) })
    }
    StudioDialogs {
        id: dialogs
        store: root.store
        local: root.local
        computer: root.store ? root.store.computerName : "máy tính"
        onListenRequested: id => root.listenRequested(id)
        onNewProjectRequested: (mode, id) => root.newProjectRequested(mode, id)
    }
}
