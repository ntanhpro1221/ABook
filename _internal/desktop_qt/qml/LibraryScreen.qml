import QtQuick
import ABook
import "LibraryLogic.js" as LibraryLogic

// Thư viện: lưới bìa luôn mở (DESIGN.md mục 7). Số cột tự giãn để bìa rộng 160-200 px theo cửa sổ; bàn phím di chuyển giữa các ô,
// Enter mở trang sách, F5 tải lại. Lưới chỉ dựng ô đang thấy; bìa giải mã ngoài luồng giao diện đúng cỡ hiển thị.
FocusScope {
    id: root
    signal openBook(var book)
    signal addRequested(var paths)
    signal openFileRequested()
    signal studioRequested()
    signal readRequested(var book)
    property bool fileOpening: false

    readonly property real avail: Math.max(0, width - 2 * Theme.margin)
    readonly property int gap: Theme.s24
    readonly property int cols: Math.max(1, Math.min(Math.floor((avail + gap) / (Theme.coverMin + gap)), Math.ceil((avail + gap) / (Theme.coverMax + gap))))
    property real coverW: Math.min(Theme.coverMax, (avail - (cols - 1) * gap) / cols)
    Behavior on coverW {
        NumberAnimation {
            duration: Theme.reduceMotion ? 0 : Theme.motionMedium
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }
    readonly property real cellW: coverW + gap
    // Every section uses the same column frame, including a partially filled
    // final row. The number of books never changes the row's leading edge.
    readonly property real contentW: cols * cellW - gap
    readonly property real contentX: (width - contentW) / 2
    readonly property bool failed: Backend.state === Backend.Failed
    readonly property bool loading: !failed && !Backend.libraryLoaded
    readonly property int total: Backend.library.count
    property var books: {
        Backend.library.revision
        const rows = []
        for (let i = 0; i < total; ++i) {
            const b = Backend.library.book(i)
            rows.push(Object.assign({}, b, {bookId: b.bookId || b.id || String(i)}))
        }
        return rows
    }
    property string filter: "all"
    property string query: ""
    property string sortOrder: "recent"
    readonly property var sortOptions: [{value: "recent", label: "Nghe gần đây"}, {value: "title", label: "Tên sách"}, {value: "author", label: "Tác giả"}, {value: "added", label: "Mới thêm"}]
    readonly property var filtered: LibraryLogic.sort(books.filter(b => LibraryLogic.matches(b, filter, query)), sortOrder)
    readonly property var sections: LibraryLogic.sections(filtered)
    property var shownSections: []
    property string appliedSelection: "all\u0000\u0000recent"
    readonly property int count: shownSections.length
    property real resultsOpacity: 1
    property real contentOpacity: !loading && !failed && !libraryError ? 1 : 0
    Behavior on contentOpacity { NumberAnimation { duration: Theme.motionMedium } }
    readonly property var continuing: LibraryLogic.listening(books, Player.loaded ? Player.bookId : "")
    onSectionsChanged: { resultMotion.stop(); resultMotion.start() }
    SequentialAnimation {
        id: resultMotion
        NumberAnimation { target: root; property: "resultsOpacity"; to: 0; duration: Theme.reduceMotion ? 60 : Theme.motionFastOut }
        ScriptAction { script: {
            const selection = root.filter + "\u0000" + root.query + "\u0000" + root.sortOrder
            const previousY = list.contentY
            root.shownSections = root.sections
            if (selection !== root.appliedSelection) { root.current = 0; list.positionViewAtBeginning() }
            else list.contentY = previousY
            root.appliedSelection = selection
        } }
        NumberAnimation { target: root; property: "resultsOpacity"; to: 1; duration: Theme.reduceMotion ? 90 : Theme.motionMedium }
    }
    readonly property bool libraryError: Backend.library.error !== ""
    property int current: 0              // ô đang giữ tiêu điểm bàn phím (chỉ số trong danh sách)
    property alias list: list

    function select(index) {
        current = Math.max(0, Math.min(count - 1, index))
        list.positionViewAtIndex(Math.floor(current / cols), ListView.Contain)
    }

    ScreenHeader {
        id: header
        objectName: "libraryHeader"
        x: root.contentX
        width: root.contentW
        title: "Thư viện"
        subtitle: root.loading || root.failed || root.total === 0 ? "" : root.query.trim() ? root.filtered.length + " trong " + root.total + " cuốn" : root.total + " cuốn"
        Button { opacity: root.total > 0 ? 1 : 0; enabled: opacity > 0; text: "Thêm sách"; icon: "plus"; kind: "ghost"; onClicked: root.addRequested([]); Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
    }

    // Desktop: continue across the full grid width, filters on the next row;
    // search is a Back layer. Sorting sits beside search, close to the results.
    Column {
        id: libraryTools
        objectName: "libraryTools"
        x: root.contentX; y: header.height + Theme.s16
        width: root.contentW
        spacing: Theme.s16
        opacity: root.total > 0 ? root.contentOpacity : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
        Collapse {
            width: parent.width
            open: !!root.continuing
            LibraryContinue {
                width: parent.width
                book: root.continuing || ({})
                onOpenRequested: root.openBook(book)
            }
        }
        Item {
            objectName: "libraryFilterRow"
            width: parent.width
            height: Math.max(filters.height, trailing.height) + (stacked ? trailing.height + Theme.s8 : 0)
            readonly property bool stacked: filters.implicitWidth + trailing.width + Theme.s16 > width
            Row {
                id: filters
                Accessible.role: Accessible.Grouping
                Accessible.name: "Lọc sách"
                spacing: Theme.s4
                Repeater {
                    model: [{value: "all", label: "Tất cả"}, {value: "listening", label: "Nghe dở"}, {value: "new", label: "Chưa nghe"}, {value: "finished", label: "Xong"}]
                    ChoiceChip {
                        required property var modelData
                        objectName: "filter_" + modelData.value
                        text: modelData.label
                        Accessible.name: modelData.value === "finished" ? "Nghe xong" : modelData.label
                        selected: root.filter === modelData.value
                        onClicked: root.filter = modelData.value
                    }
                }
            }
            Row {
                id: trailing
                x: parent.width - width
                y: parent.stacked ? filters.height + Theme.s8 : 0
                spacing: Theme.s8
                Behavior on y { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                Button {
                    id: order; objectName: "librarySort"
                    kind: "ghost"; text: "Xếp theo"; icon: "arrow-down-wide-narrow"
                    tip: `Xếp theo: ${root.sortOptions.find(o => o.value === root.sortOrder).label}`
                    onClicked: sortMenu.toggle()
                }
                IconButton { id: searchButton; objectName: "librarySearch"; icon: "search"; tip: "Tìm sách"; onClicked: search.open ? search.close() : search.show() }
            }
        }
        Collapse {
            id: search
            width: parent.width
            function show() { open = true; Nav.openLayer(search); searchField.forceActiveFocus() }
            function close() { if (!open) return; open = false; root.query = ""; Nav.closedLayer(search); searchButton.forceActiveFocus() }
            Component.onDestruction: Nav.closedLayer(search)
            Row {
                width: parent.width; spacing: Theme.s8
                FormField {
                    id: searchField; objectName: "librarySearchField"
                    width: parent.width - clear.width - Theme.s8
                    label: "Tìm sách"; placeholderText: "Tên sách, tác giả, giọng"
                    Accessible.description: "Gõ không dấu cũng được"
                    text: root.query
                    onTextChanged: root.query = text
                    escapeLocal: true; onEscaped: search.close()
                }
                IconButton { id: clear; objectName: "librarySearchClear"; icon: "x"; tip: root.query ? "Xoá ô tìm" : "Đóng tìm kiếm"; onClicked: root.query ? root.query = "" : search.close() }
            }
        }
    }
    Popover {
        id: sortMenu; objectName: "librarySortMenu"; anchorItem: order; panelWidth: 232
        Column {
            width: parent.width
            Repeater {
                model: root.sortOptions
                ChoiceChip {
                    required property var modelData
                    fullWidthReason: "Single-column menu (DESIGN 6)"
                    width: parent.width; text: modelData.label; selected: root.sortOrder === modelData.value
                    onClicked: { root.sortOrder = modelData.value; Api.store("abook-library-sort", modelData.value); sortMenu.close() }
                }
            }
        }
    }
    Modal {
        id: seriesDialog; objectName: "librarySeries"
        property var group: ({title: "", books: []})
        title: group.title
        panelWidth: 560
        Column {
            width: parent.width; spacing: Theme.s8
            Repeater {
                model: seriesDialog.group.books
                Button {
                    required property var modelData
                    width: parent.width; wrap: true; kind: "ghost"; text: modelData.title
                    onClicked: { seriesDialog.close(); root.openBook(modelData) }
                }
            }
        }
    }
    function activate(index) {
        const section = shownSections[index]
        if (!section) return
        if (section.books.length > 1) { seriesDialog.group = section; seriesDialog.show() }
        else openBook(section.books[0])
    }

    // Kéo file vào thư viện (DropToAdd.tsx): thả một hay nhiều file thì mở "Thêm sách" ở đúng hàng xem trước; đang có hộp khác mở thì nhắc đóng hộp rồi thả lại
    DropArea {
        id: dropArea
        anchors.fill: parent
        z: 5
        onEntered: drag => { drag.accepted = drag.hasUrls }
        onDropped: drop => {
            if (!drop.hasUrls) return
            const paths = drop.urls.map(url => DesktopApi.localPath(url)).filter(path => path !== "")
            if (!paths.length) return
            drop.acceptProposedAction()
            if (Nav.layers.length > 0) Api.notice = "Đóng hộp đang mở rồi thả lại file nhé"
            else root.addRequested(paths)
        }
        ImportDrop { anchors.fill: parent; shown: dropArea.containsDrag && Nav.layers.length === 0 }
    }

    // Lưới ảo hoá theo HÀNG: mỗi delegate là một hàng N ô, cao bằng ô cao nhất của hàng (tên dài xuống dòng đủ, không cắt).
    ListView {
        id: list
        anchors.top: libraryTools.bottom
        anchors.topMargin: Theme.s16
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        opacity: root.resultsOpacity * root.contentOpacity
        visible: opacity > 0 && root.count > 0
        focus: true
        clip: true
        model: root.count > 0 ? Math.ceil(root.count / root.cols) : 0
        bottomMargin: Theme.s32
        cacheBuffer: 400
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: false
        reuseItems: true
        Accessible.role: Accessible.List
        Accessible.name: "Sách"

        delegate: Item {
            id: rowItem
            required property int index
            readonly property int first: index * root.cols
            width: ListView.view.width
            height: cells.childrenRect.height + root.gap
            Item {
                id: cells
                readonly property int count: Math.max(0, Math.min(root.cols, root.count - rowItem.first))
                objectName: "libraryGridRow"
                width: root.contentW
                x: root.contentX
                Behavior on x {
                    NumberAnimation {
                        duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: Theme.easeStandard
                    }
                }
                Repeater {
                    model: cells.count
                    BookCell {
                        id: cell
                        required property int index
                        readonly property int at: rowItem.first + index
                        readonly property var section: root.shownSections[at] || {title: "", books: [{}]}
                        readonly property var info: section.books[0]
                        x: index * root.cellW
                        Behavior on x {
                            NumberAnimation {
                                duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                                easing.type: Easing.BezierSpline
                                easing.bezierCurve: Theme.easeStandard
                            }
                        }
                        coverWidth: root.coverW
                        title: section.books.length > 1 ? section.title : info.title || ""
                        subtitle: section.books.length > 1 ? section.books.length + " tập" : info.subtitle || ""
                        Accessible.name: section.books.length > 1 ? `Mở bộ ${section.title}` : title
                        Accessible.description: section.remote && section.books.length > 1 ? "Có sách trên máy khác" : ""
                        book: info
                        playVisible: section.books.length === 1
                        onReadRequested: root.readRequested(info)
                        coverKey: info.coverKey || ""
                        progress: info.progress || 0
                        source: section.remote ? (section.books.find(b => b.source) || {}).source || "" : ""
                        remoteSeries: section.books.length > 1 && !!section.remote
                        externalFocus: at === root.current && list.activeFocus
                        onClicked: {
                            if (cell.onPlayButton) return
                            root.current = at
                            list.forceActiveFocus(Qt.MouseFocusReason)
                            root.activate(at)
                        }
                    }
                }
            }
        }
        Keys.onReturnPressed: root.activate(root.current)
        Keys.onEnterPressed: root.activate(root.current)
        Keys.onPressed: (event) => {
            const rows = Math.max(1, Math.floor(height / (Theme.coverMax * Theme.coverRatio)) - 1)
            let handled = true
            switch (event.key) {
            case Qt.Key_Left: root.select(root.current - 1); break
            case Qt.Key_Right: root.select(root.current + 1); break
            case Qt.Key_Up: root.select(root.current - root.cols); break
            case Qt.Key_Down: root.select(root.current + root.cols); break
            case Qt.Key_PageUp: root.select(root.current - rows * root.cols); break
            case Qt.Key_PageDown: root.select(root.current + rows * root.cols); break
            case Qt.Key_Home: root.select(0); break
            case Qt.Key_End: root.select(root.count - 1); break
            case Qt.Key_F5: Backend.refreshLibrary(); break
            case Qt.Key_R:
                if (event.modifiers & Qt.ControlModifier) Backend.refreshLibrary()
                else handled = false
                break
            default: handled = false
            }
            event.accepted = handled
        }
        SmoothWheel { flick: list }
        Scrollbar { target: list }
    }
    ChapterReader { id: reader }
    onReadRequested: book => reader.begin(book.bookId, -1)

    // Đang tải: khung xám đúng hình nội dung, nhịp mờ 0,6 <-> 1 chu kỳ 1,6 s (DESIGN.md 2). Không vòng xoay.
    Item {
        id: skeleton
        readonly property real skeletonCellH: Math.round(root.coverW * Theme.coverRatio) + 71 + root.gap
        anchors.top: header.bottom
        anchors.topMargin: Theme.s16
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        clip: true
        opacity: root.loading ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
        SequentialAnimation {
            running: skeleton.visible && !Theme.reduceMotion
            loops: Animation.Infinite
            OpacityAnimator { target: skeleton; from: 1; to: 0.6; duration: 800; easing.type: Easing.InOutSine }
            OpacityAnimator { target: skeleton; from: 0.6; to: 1; duration: 800; easing.type: Easing.InOutSine }
        }
        Repeater {
            model: Math.max(0, root.cols * Math.ceil(skeleton.height / skeleton.skeletonCellH))
            Item {
                required property int index
                x: root.contentX + (index % root.cols) * root.cellW
                y: Math.floor(index / root.cols) * skeleton.skeletonCellH
                width: root.coverW
                height: skeleton.skeletonCellH
                Rectangle { width: parent.width; height: Math.round(root.coverW * Theme.coverRatio); radius: Theme.radiusCover; color: Theme.sunken }
                Rectangle { y: Math.round(root.coverW * Theme.coverRatio) + 14; width: parent.width * 0.85; height: 12; radius: Theme.radiusControl; color: Theme.sunken }
                Rectangle { y: Math.round(root.coverW * Theme.coverRatio) + 34; width: parent.width * 0.5; height: 10; radius: Theme.radiusControl; color: Theme.sunken }
            }
        }
    }

    // Trống / lỗi: một câu + một nút dẫn tới việc tiếp theo (DESIGN.md 2). Lỗi nói tại chỗ cách sửa, không hộp thoại chặn.
    Column {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 40
        spacing: Theme.s16
        opacity: root.failed || root.libraryError || (!root.loading && root.total === 0) ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
        // Thư viện trống (EmptyLibrary của desktop/App.tsx): ô icon tai nghe, một câu + một nút chính "Thêm sách"; các lối khác cùng kiểu chữ-có-icon ở hàng dưới
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !root.failed && !root.libraryError
            width: 56; height: 56; radius: Theme.radiusCover
            color: Theme.accentSoft
            Icon { anchors.centerIn: parent; name: "headphones"; size: 28; color: Theme.accentText }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.failed ? "Chưa mở được ABook" : (root.libraryError ? "Chưa tải được thư viện" : "Chưa có sách")
            color: Theme.text
            font.pixelSize: Theme.sizeSection
            font.weight: Theme.weightMedium
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(root.width - 2 * Theme.margin, 460)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: root.failed ? Backend.message : (root.libraryError ? Backend.library.error : "Thêm truyện hoặc tạo sách nói.")
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
        }
        Button {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.failed || root.libraryError
            text: "Thử lại"
            onClicked: root.failed ? Backend.restart() : Backend.refreshLibrary()
        }
        Button {
            objectName: "emptyAdd"
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !root.failed && !root.libraryError
            text: "Thêm sách"
            icon: "plus"
            size: "lg"
            onClicked: root.addRequested([])
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !root.failed && !root.libraryError
            spacing: 4
            Button { objectName: "emptyStudio"; text: "Tạo sách nói"; icon: "clapperboard"; kind: "ghost"; onClicked: root.studioRequested() }
            Button { objectName: "emptyOpenFile"; text: root.fileOpening ? "Đang mở…" : "Mở file sách"; icon: "file-audio"; kind: "ghost"; enabled: !root.fileOpening; onClicked: root.openFileRequested() }
        }
    }

    EmptyState {
        anchors.top: libraryTools.bottom; anchors.topMargin: Theme.s32
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width - 2 * Theme.margin, 560)
        opacity: !root.loading && !root.failed && !root.libraryError && root.total > 0 && root.count === 0 ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
        icon: "search"
        title: root.query ? "Không tìm thấy sách nào khớp “" + root.query + "”" : "Không có sách ở đây"
        text: root.query ? "Thử tên sách hoặc tác giả khác." : root.filter === "listening" ? "Chưa nghe dở cuốn nào - chọn một cuốn để bắt đầu." : root.filter === "finished" ? "Chưa có cuốn nào nghe xong." : "Cuốn nào cũng đã được nghe ít nhất một đoạn."
    }
    Component.onCompleted: { root.shownSections = root.sections; const saved = Api.store("abook-library-sort"); if (root.sortOptions.some(o => o.value === saved)) root.sortOrder = saved; list.forceActiveFocus() }
    onVisibleChanged: if (visible) list.forceActiveFocus()
}
