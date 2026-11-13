import "UiStrings.js" as S
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
        title: S.s_studio_0aa91af2
        subtitle: root.loading || root.failed ? " " : Logic.projectsSubtitle(root.books.length)
        Button {
            objectName: "newProject"
            opacity: root.listed ? 1 : 0
            enabled: opacity > 0
            text: S.s_du_an_moi_992d22b2
            icon: "plus"
            kind: "ghost"
            onClicked: root.newRequested()
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionFast } }
        }
        IconButton {
            id: studioMore
            objectName: "studioMore"
            Reveal { shown: Boolean(root.store && root.store.info && root.store.info.dialogs) }
            icon: "ellipsis"
            iconSize: 20
            tip: S.s_tuy_chon_studio_16c07366
            Accessible.name: S.s_tuy_chon_studio_16c07366
            onClicked: { studioMenu.anchorItem = studioMore; studioMenu.show() }
        }
    }

    // Thẻ cài / sửa / cập nhật Studio (StudioSetupCard): chỉ hiện khi app đóng gói chưa cài Studio, nằm giữa đầu màn và bảng
    StudioSetupCard {
        id: setupCard
        objectName: "projectsSetupCard"
        x: root.contentX
        y: header.height
        width: root.contentW
        store: root.store
        active: root.visible && Boolean(root.store && root.store.active)
    }

    // Khung chữ dưới đầu màn: mép trái thẳng tiêu đề; bảng tràn ra 12 px mỗi bên (nền rê chuột, vạch kẻ), phần chữ thẳng mép
    Item {
        id: frame
        objectName: "projectsBody"
        x: root.contentX
        y: header.height + setupCard.height + 24
        width: root.contentW
        height: root.height - y
        // ---- đầu bảng ----
        Item {
            id: head
            objectName: "tableHead"
            Reveal { shown: (root.loading || root.listed) && root.kind !== "stacked" }
            x: -12
            y: 0
            width: root.rowW
            height: visible ? 28 : 0
            Rectangle { x: 12; y: parent.height - 1; width: parent.width - 24; height: 1; color: Theme.line }
            Text { x: root.cols.nameX; y: 4; width: root.cols.nameW; text: S.s_du_an_4f139d43; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
            Text { x: root.cols.statusX; y: 4; width: root.cols.statusW; text: S.s_trang_thai_cb31de81; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
            Text { x: root.cols.progressX; y: 4; width: root.cols.progressW; text: S.s_tien_do_e5947845; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
            Text { Reveal { shown: root.kind === "wide" } x: root.cols.updatedX; y: 4; width: root.cols.updatedW; horizontalAlignment: Text.AlignRight; text: S.s_cap_nhat_5293d03c; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
        }

        // ---- khung chờ ----
        EditBookSkeleton {
            objectName: "projectsSkeleton"
            Reveal { shown: root.loading }
            x: 0
            y: head.y + (head.visible ? head.height : 0) + 12
            width: root.contentW
            shape: "rows"
            count: 5
            label: S.s_dang_tai_danh_sach_du_an_269d378e
        }

        // ---- bảng ----
        ListView {
            id: list
            objectName: "projectsList"
            Reveal { target: list; shown: root.listed }
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
            add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionMedium } }
            remove: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionFastOut } }
            displaced: Transition { NumberAnimation { properties: "y"; duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
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
                        computer: root.store ? root.store.computerName : S.s_may_tinh_8eafc226
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
        InlineError {
            objectName: "projectsError"
            x: 0
            y: 24
            width: root.contentW
            open: root.failed
            message: S.s_chua_tai_duoc_danh_sach_du_an_ban_hay_kiem_7f4ca36c
            onRetry: root.store.loadLibrary()
        }
        EmptyState {
            id: projectsMissing
            objectName: "projectsMissing"
            Reveal { target: projectsMissing; shown: root.rootMissing }
            x: 0
            y: 48 - 56
            width: root.contentW
            icon: "folder-x"
            title: root.local && root.store && root.store.libraryData && root.store.libraryData.root
                   ? S.s_khong_thay_thu_muc_thu_vien_a160d7be + Logic.folderName(root.store.libraryData.root) + "”" : S.s_khong_thay_thu_muc_thu_vien_8c2af7eb
            text: S.s_o_chua_cam_hay_thu_muc_da_doi_ten_cam_lai_713e694c
            Button { Reveal { shown: root.local } text: S.s_chon_thu_muc_1fe47e38; icon: "settings"; onClicked: if (Nav.stack) Nav.stack.show(2) }
            OnComputerPill { Reveal { shown: !root.local } verb: S.s_chon_lai_thu_muc_thu_vien_2d290748; computer: root.store ? root.store.computerName : S.s_may_tinh_8eafc226 }
        }
        EmptyState {
            id: projectsEmpty
            objectName: "projectsEmpty"
            Reveal { target: projectsEmpty; shown: root.empty }
            x: 0
            y: 48 - 56
            width: root.contentW
            icon: "clapperboard"
            title: S.s_chua_co_du_an_dd6cd3d2
            text: S.s_bien_mot_truyen_thanh_sach_noi_nhieu_giong_3e0bcdc1
            Button { objectName: "newProjectEmpty"; text: S.s_du_an_moi_992d22b2; icon: "plus"; size: "lg"; onClicked: root.newRequested() }
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
        items: [Logic.item("openExisting", "folder-open", S.s_mo_du_an_co_san_344c8318)]
        onPicked: root.store.openExisting(function(id) { root.projectOpened(id) })
    }
    StudioDialogs {
        id: dialogs
        store: root.store
        local: root.local
        computer: root.store ? root.store.computerName : S.s_may_tinh_8eafc226
        onListenRequested: id => root.listenRequested(id)
        onNewProjectRequested: (mode, id) => root.newProjectRequested(mode, id)
    }
}
