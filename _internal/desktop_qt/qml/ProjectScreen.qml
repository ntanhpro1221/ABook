import QtQuick
import ABook
import "StudioLogic.js" as Logic
import "PrecastLogic.js" as Precast
import "EditBookLogic.js" as Edit

// Studio › một dự án (ProjectScreen.tsx; DESIGN.md mục 7): tên + dòng trạng thái, MỘT nút chính theo trạng thái (Bắt đầu · Tạm dừng · Tiếp tục · Nghe trong Thư viện;
// sách xong còn thay đổi chờ thì "Áp dụng N thay đổi"), mọi việc khác trong "…". Dưới là hàng tab (Chương · Việc cần duyệt · Cần nghe lại · Nhân vật · Nhạc nền;
// còn lại trong "Thêm") và nội dung tab: Chương, Việc cần duyệt, Cần nghe lại, Nhân vật (dàn người, đổi giọng / tên / giới / gộp, công tắc tự kể, cách đọc tên), Duyệt trước khi thu, Nhật ký, Nhạc nền (StudioMusic); các tab khác nói gọn là chưa mở.
// "Tạm dừng" gọi lệnh tạm dừng, KHÔNG BAO GIỜ dừng (dừng giữa pha phân tích là đổi quyển sách, AGENTS.md); "Dừng…" chỉ ở "…" kèm lời cảnh báo.
// Cả danh sách cuộn MỘT khung: phần đầu là header của ListView, hàng chương / nhật ký giữ theo khoá nên nhịp hỏi 3 s / 15 s không làm nhảy chỗ cuộn.
FocusScope {
    id: root
    property var store: null
    signal backRequested()
    signal listenRequested(string id)
    signal newProjectRequested(string mode, string id)

    readonly property var book: store ? store.book : null
    readonly property bool remote: store ? store.remote : false
    readonly property real contentW: Math.min(width - 2 * Theme.margin, 960)
    readonly property bool narrowHead: width < 640
    readonly property real contentX: (width - contentW) / 2
    readonly property string failure: store ? store.bookFailure : ""
    property string tab: "chapters"
    property string shownTab: "chapters"
    property real swap: 1
    property int next: 0
    property var activityData: null
    property bool activityLoading: false
    property string activityMode: "story"
    property int activityAsk: 0
    property var menuChapter: ({})
    property var retakeChapter: ({})
    readonly property var primary: book ? Logic.primaryButton(book, {pause: store.pausing, start: store.starting}) : null
    readonly property bool analyzedAll: !!book && book.segments.total > 0 && book.segments.analyzed === book.segments.total
    readonly property bool hasPrecast: !!book && Logic.canReview(book)
    property var rowByKey: ({})
    readonly property alias list: list
    readonly property alias dialogs: dialogs

    // ---- tab ----
    // Đổi tab ở hàng tab bỏ hết dấu vết lần nhảy trước (bộ lọc, thẻ, nơi về) như đổi địa chỉ của bản web; NHẢY từ một thẻ sang tab khác thì nhớ tab cũ, thẻ và bộ lọc để "Về màn trước" trả về đúng chỗ
    property string workKind: "all"
    property string workCard: ""
    property string cameFrom: ""
    property string nameParam: ""
    property bool focusNames: false
    property string precastStep: "cast"
    // Tab Kịch bản mở từ thẻ việc / menu chương: {chapter, line, pick} (tham số chapter/line/pick của web); đổi tab ở hàng tab thì bỏ
    property var scriptAt: null
    // Cùng kho UI state với Api.store (Platform -> desktop_qt.ini), riêng từng máy/sách.
    readonly property string viewKey: store && store.bookId ? "studio.view." + encodeURIComponent(store.peer || "local") + "." + encodeURIComponent(store.bookId) : ""
    property string loadedViewKey: ""
    property var viewState: ({})
    property bool viewReady: false
    property bool viewDirty: false
    function flushView() {
        viewWrite.stop()
        if (viewDirty && loadedViewKey) Platform.setSetting(loadedViewKey, JSON.stringify(viewState))
        viewDirty = false
    }
    function restoreView() {
        flushView()
        viewReady = false
        loadedViewKey = viewKey
        let saved = {}
        try { saved = viewKey ? JSON.parse(Platform.setting(viewKey, "{}")) || {} : {} } catch (error) {}
        if (typeof saved !== "object" || Array.isArray(saved)) saved = {}
        viewState = saved
        scriptAt = null
        tab = Logic.tabOf(saved.tab || "chapters")
        viewReady = true
    }
    function rememberView(change) {
        if (!viewReady || !loadedViewKey) return
        const next = Object.assign({}, viewState, change)
        if (JSON.stringify(next) === JSON.stringify(viewState)) return
        viewState = next
        viewDirty = true
        // Throttle, không restart khi con trỏ tiếp tục đi: tối đa một lần ghi/400 ms.
        if (!viewWrite.running) viewWrite.start()
    }
    onViewKeyChanged: if (viewReady) restoreView()
    Timer { id: viewWrite; interval: 400; onTriggered: root.flushView() }
    Component.onDestruction: flushView()
    readonly property var fromLabels: ({work: "Việc cần duyệt", review: "Cần nghe lại", precast: "Duyệt trước khi thu"})
    function pickTab(key) {
        workKind = "all"; workCard = ""; cameFrom = ""; nameParam = ""; focusNames = false; precastStep = "cast"; scriptAt = null
        tab = Logic.tabOf(key)
    }
    function jump(next, from, card, name, names) {
        if (card) workCard = card
        cameFrom = from
        nameParam = name || ""
        focusNames = Boolean(names)
        tab = Logic.tabOf(next)
    }
    function jumpBack() {
        const target = cameFrom || "chapters"
        cameFrom = ""; nameParam = ""; focusNames = false
        tab = Logic.tabOf(target)
    }
    // Cuộn danh sách tới khi `target` (một thẻ, một hàng, tiêu đề mục) hiện trọn trong khung, cách mép 16
    function reveal(target) {
        if (!target || !list.visible) return
        const top = target.mapToItem(list.contentItem, 0, 0).y
        const bottom = top + target.height
        if (top < list.contentY + 16) list.contentY = Math.max(list.originY - list.topMargin, top - 16)
        else if (bottom > list.contentY + list.height - 16) list.contentY = bottom - list.height + 16
    }
    onTabChanged: { tabSwap.restart(); rememberView({tab: tab}) }
    SequentialAnimation {
        id: tabSwap
        NumberAnimation { target: root; property: "swap"; to: 0; duration: Theme.motionFastOut; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
        ScriptAction { script: { root.shownTab = root.tab; list.positionViewAtBeginning() } }
        NumberAnimation { target: root; property: "swap"; to: 1; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
    }

    // ---- việc cần bạn: hộp việc, câu cần nghe lại, cách đọc tên, yêu cầu từ điện thoại ----
    WorkStore {
        id: studioWork
        store: root.store
        book: root.book
        bookId: root.book ? root.book.id : ""
        workWanted: root.shownTab === "work" || root.shownTab === "precast"
        namesWanted: root.shownTab === "cast"
        counting: root.visible
    }

    // ---- nhân vật: người, giọng, tên, giới, gộp (tab Nhân vật và màn "Duyệt trước khi thu") ----
    // Việc làm được với một người: Studio sửa mọi thứ như web (máy chủ từ chối thì báo lời của máy chủ)
    readonly property var castCaps: ({rename: true, merge: true, gender: true, voice: true, unmerge: true, narrator: !!book && Boolean(book.castLocked), waiting: false})
    function castRequest(kind, person) {
        if (!book || !store) return
        if (kind === "unmerge") { castUnmerge.run(book.id, person); return }
        const data = {bookId: book.id, person: person, waiting: false}
        if (kind !== "merge") { castDialogs.begin(kind, data); return }
        // Người có thể nhận phần gộp: cả vai chính và vai phụ, đọc mới lúc bấm (như useCast của web)
        const id = book.id
        store.quiet("GET", "/api/books/" + id + "/cast", null, function(cast, error) {
            if (!root.book || root.book.id !== id) return
            if (error || !cast) { Api.notice = Edit.toastText("Chưa gộp được", error || "Không làm được lúc này."); return }
            data.people = (cast.characters || []).concat(cast.extras || [])
            castDialogs.begin("merge", data)
        })
    }
    CastDialogs { id: castDialogs; objectName: "studioCastDialogs"; store: root.store }
    CastUnmerge { id: castUnmerge; store: root.store }
    CastMenu {
        id: castMenu
        caps: root.castCaps
        onPicked: (kind, person) => root.castRequest(kind, person)
    }

    // ---- nhật ký ----
    function loadActivity() {
        if (!store || !book) return
        const ask = ++activityAsk
        const id = book.id
        if (activityData === null) activityLoading = true
        store.loadActivity(id, activityMode === "technical", function(status, data) {
            if (ask !== root.activityAsk || !root.book || id !== root.book.id) return
            root.activityLoading = false
            if (status >= 200 && status < 300) { if (Array.isArray(data)) root.activityData = data; root.activityError = "" }
            else root.activityError = status === 404 ? "" : root.store.errorText(status, data)
        })
    }
    // Lời lỗi của một nguồn phụ đang hỏng (nhân vật, yêu cầu thiết bị, nhật ký - useSideError của bản web), "" khi không có; sách đã mất (404) không tính
    property string activityError: ""
    function queryError(query) { return query && query.error && query.error.status !== 404 ? query.error.text : "" }
    readonly property string sideError: queryError(studioWork.cast) || queryError(studioWork.inbox) || activityError
    property string shownSideError: ""        // giữ chữ khi dải đang khép lại
    onSideErrorChanged: if (sideError !== "") shownSideError = sideError
    readonly property bool wantsActivity: shownTab === "activity" && !!book
    onWantsActivityChanged: if (wantsActivity) loadActivity()
    onActivityModeChanged: { activityData = null; if (wantsActivity) loadActivity() }
    Timer {
        objectName: "activityPoll"
        interval: 5000
        repeat: true
        running: root.store && root.store.active && root.wantsActivity && root.book && root.book.running
        onTriggered: root.loadActivity()
    }
    Connections {
        target: root.store
        function onBookIdChanged() {
            root.activityData = null; root.activityError = ""; root.next = 0
            root.workKind = "all"; root.workCard = ""; root.cameFrom = ""; root.nameParam = ""; root.focusNames = false; root.precastStep = "cast"
            Later.call(root, root.refreshNext)
        }
    }

    // "Thêm N chương": chỉ hỏi khi phân tích đã xong
    function refreshNext() {
        if (!analyzedAll || !book || !store) { next = 0; return }
        const id = book.id
        store.loadContinuation(id, function(count) { if (root.book && root.book.id === id) root.next = count })
    }
    onAnalyzedAllChanged: refreshNext()

    // ---- hàng của danh sách ----
    function buildRows() {
        const rows = []
        if (!book) return rows
        if (shownTab === "chapters") {
            for (const chapter of store.chapters) rows.push({key: "c" + chapter.id, kind: "chapter", chapter: chapter})
        } else if (shownTab === "activity" && activityData !== null) {
            if (activityData.length > 0) rows.push({key: "ahead", kind: "ahead", count: activityData.length})
            if (activityMode === "technical") {
                for (const entry of activityData) rows.push({key: "t" + entry.id, kind: "tech", entry: entry})
            } else {
                for (const group of Logic.activityGroups(activityData)) {
                    rows.push({key: "d" + group.day, kind: "day", day: group.day})
                    for (const entry of group.items) rows.push({key: "l" + entry.id, kind: "log", entry: entry})
                }
            }
        }
        // ListView không hàng nào thì mỗi lần dàn lại (footer đổi cao) Qt kéo về đầu (QQuickItemViewPrivate::layout, model rỗng): tab đặt nội dung
        // ở footer (Nhạc nền...) giữ một hàng rỗng cao 0 để mở / đóng một khối không làm trang nhảy lên đầu
        if (!rows.length) rows.push({key: "rest", kind: "rest"})
        return rows
    }
    readonly property var rowList: buildRows()
    onRowListChanged: sync()
    function sync() {
        const byKey = {}
        for (const row of rowList) byKey[row.key] = row
        rowByKey = byKey
        let same = rowList.length === rowModel.count
        for (let i = 0; same && i < rowList.length; ++i) same = rowModel.get(i).key === rowList[i].key
        if (same) return
        rowModel.clear()
        for (const row of rowList) rowModel.append({key: row.key})
    }
    ListModel { id: rowModel }
    Component.onCompleted: { restoreView(); sync() }

    function bookMenuItems() {
        const extras = Logic.actionExtras(book, {next: next, remote: remote})
        return Logic.projectMenu(book, {extras: extras, remote: remote, computer: store.computerName})
    }
    function chapterMenuItems(chapter) {
        const items = []
        if (chapter.playable && !remote) items.push(Logic.item("play", "play", "Nghe chương"))
        items.push(Logic.item("script", "book-open-text", "Kịch bản chương này"))
        if (chapter.segments.finished > 0) { items.push(Logic.separator()); items.push(Logic.item("retake", "refresh-cw", "Thu lại cả chương…")) }
        return items
    }

    // ---- lời nói thẳng khi chưa có sách ----
    EditBookSkeleton {
        objectName: "projectSkeleton"
        visible: !!root.store && root.store.bookLoading
        x: root.contentX
        y: Theme.s32 + Theme.headerRow + 32
        width: root.contentW
        shape: "rows"
        count: 6
        label: "Đang mở dự án"
    }
    EmptyState {
        objectName: "projectGone"
        visible: root.failure === "gone"
        x: root.contentX
        y: 80 - 56
        width: root.contentW
        icon: "circle-alert"
        title: "Dự án này không còn"
        text: "Cuốn này đã bị xoá hoặc chuyển đi khỏi thư viện."
        Button { objectName: "projectGoneBack"; text: "Về danh sách dự án"; onClicked: root.backRequested() }
    }
    EmptyState {
        objectName: "projectError"
        visible: root.failure === "error"
        x: root.contentX
        y: 80 - 56
        width: root.contentW
        icon: "circle-alert"
        title: "Không mở được sách"
        text: root.store && root.store.bookError ? Logic.failureText(root.store.bookError.status, root.store.bookError.text) : ""
        Button { objectName: "projectRetry"; text: "Thử lại"; kind: "ghost"; onClicked: root.store.loadBook() }
        Button { objectName: "projectErrorBack"; text: "Về Studio"; onClicked: root.backRequested() }
    }

    // ---- danh sách ----
    ListView {
        id: list
        objectName: "projectList"
        visible: !!root.book && root.failure !== "gone" && root.failure !== "error"
        x: root.contentX - 8
        width: root.contentW + 16
        height: parent.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: rowModel
        bottomMargin: 64
        cacheBuffer: 600
        header: Item {
            width: list.width
            height: headCol.height
            Column {
                id: headCol
                x: 8
                width: root.contentW
                spacing: 12
                ScreenHeader {
                    id: top
                    objectName: "projectHeader"
                    width: parent.width
                    showBack: true
                    backLabel: "Về Studio"
                    title: root.book ? root.book.title : ""
                    Button {
                        id: primaryButton
                        objectName: "primaryButton"
                        visible: root.primary !== null
                        text: root.primary ? root.primary.label : ""
                        icon: root.primary && root.primary.icon ? root.primary.icon : ""
                        busy: root.primary ? Boolean(root.primary.busy) : false
                        enabled: root.primary ? root.primary.enabled : false
                        onActivated: dialogs.runPrimary(root.primary.kind, root.book)
                    }
                    IconButton {
                        id: moreButton
                        objectName: "bookMore"
                        icon: "ellipsis"
                        iconSize: 20
                        tip: "Tuỳ chọn dự án"
                        Accessible.name: "Tuỳ chọn dự án " + (root.book ? root.book.title : "")
                        onClicked: { bookMenu.items = root.bookMenuItems(); bookMenu.anchorItem = moreButton; bookMenu.show() }
                    }
                }
                // Dải báo khi lần hỏi gần nhất hỏng mà vẫn còn bản cũ
                Row {
                    objectName: "projectStale"
                    visible: root.failure === "stale"
                    width: parent.width
                    spacing: 8
                    Icon { name: "circle-alert"; size: 16; color: Theme.warning; y: 2 }
                    Text {
                        width: parent.width - 16 - 8 - retry.width - 8
                        text: root.store && root.store.bookError ? Logic.staleLine(root.store.bookError.status, root.store.bookError.text) : ""
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    Button { id: retry; size: "sm"; kind: "ghost"; text: "Thử lại"; onClicked: root.store.loadBook() }
                }
                // Bìa thật (CoverEditor.tsx) bên trái; trạng thái, số liệu, tiến độ và lời nhắn bên phải. Màn hẹp: bìa 96, nút chỉ còn biểu tượng.
                Row {
                    id: headRow
                    objectName: "projectHead"
                    width: parent.width
                    spacing: root.narrowHead ? 16 : 28
                    CoverEditor {
                        objectName: "coverEditor"
                        narrow: root.narrowHead
                        store: root.store
                        book: root.book
                        visible: Boolean(root.book)
                    }
                    Column {
                        id: headRest
                        width: parent.width - (Boolean(root.book) ? (root.narrowHead ? 96 : 176) + headRow.spacing : 0)
                        spacing: 12
                        Flow {
                            width: parent.width
                            spacing: 12
                            StatusPill {
                                objectName: "projectStatus"
                                label: root.book ? Logic.projectStatus(root.book).label : ""
                                tone: root.book ? Logic.projectStatus(root.book).tone : "muted"
                                live: root.book ? Logic.projectStatus(root.book).live : false
                                y: 1
                            }
                            Text {
                                objectName: "projectMeta"
                                width: Math.min(implicitWidth, parent.width)
                                height: 26
                                verticalAlignment: Text.AlignVCenter
                                textFormat: Text.StyledText
                                wrapMode: Text.Wrap
                                text: root.book ? Logic.metaLine(root.book, Theme.warning) : ""
                                color: Theme.text2
                                font.pixelSize: Theme.sizeBodySmall
                            }
                        }
                        // Tiến độ chung: chỉ khi sách đang làm dở
                        Flow {
                            id: projectProgress
                            objectName: "projectProgress"
                            visible: !!root.book && root.book.phase !== "done" && root.book.phase !== "idle"
                            width: parent.width
                            spacing: 12
                            readonly property bool moving: !!root.book && (root.book.running || root.book.starting) && !root.book.paused && !root.book.stopping
                            Row {
                                width: Math.min(320, parent.width)
                                height: 22
                                spacing: 12
                                StudioBar {
                                    objectName: "projectBar"
                                    width: parent.width - 40 - 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    size: "xs"
                                    value: root.book && root.book.progress ? root.book.progress.overall : 0
                                    tone: projectProgress.moving ? "accent" : "muted"
                                    label: "Tiến độ cả sách"
                                }
                                Text {
                                    width: 40
                                    horizontalAlignment: Text.AlignRight
                                    text: Logic.formatPercent(root.book && root.book.progress ? root.book.progress.overall : 0)
                                    color: Theme.text
                                    font.pixelSize: Theme.sizeBodySmall
                                    font.weight: Theme.weightMedium
                                    font.features: { "tnum": 1 }
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            Text {
                                objectName: "projectProgressNote"
                                visible: text !== ""
                                width: Math.min(implicitWidth, parent.width)
                                height: Math.max(22, implicitHeight)
                                verticalAlignment: Text.AlignVCenter
                                text: root.book ? Logic.progressNote(root.book) : ""
                                color: Theme.text2
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.sizeBodySmall
                            }
                        }
                        // Lời nói thêm dưới hàng nút: hàng chờ, đang dừng, phân tích bị ngắt, chương chờ thu lại, tạm dừng vì pin, Studio chưa cài, lỗi lần làm sách
                        Column {
                            objectName: "projectNotes"
                            width: parent.width
                            spacing: 6
                            Repeater {
                                model: root.book ? Logic.actionNotes(root.book, root.remote).concat([Logic.studioMissingNote(root.store.info && root.store.info.studio, root.book, root.remote)]).filter(Boolean) : []
                                delegate: Text {
                                    required property string modelData
                                    objectName: "projectNote"
                                    width: parent.width
                                    text: modelData
                                    color: Theme.text2
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.sizeBodySmall
                                }
                            }
                            MoreInfo {
                                objectName: "projectBattery"
                                visible: battery.text !== ""
                                width: parent.width
                                label: "Dùng pin"
                                HintText { id: battery; width: parent.width; text: root.book ? Logic.batteryInfo(root.book, root.remote) : "" }
                            }
                            Flow {
                                objectName: "projectStartError"
                                visible: !!root.book && !!root.book.startError
                                width: parent.width
                                spacing: 8
                                Accessible.role: Accessible.AlertMessage
                                Accessible.name: startErrorText.text
                                Row {
                                    width: parent.width - (startRetry.visible ? startRetry.width + 8 : 0)
                                    spacing: 8
                                    Icon { name: "circle-alert"; size: 16; color: Theme.danger; y: 2 }
                                    Text {
                                        id: startErrorText
                                        width: parent.width - 16 - 8
                                        text: root.book && root.book.startError ? "Không khởi động được: " + root.book.startError : ""
                                        color: Theme.danger
                                        wrapMode: Text.Wrap
                                        font.pixelSize: Theme.sizeBodySmall
                                    }
                                }
                                Button {
                                    id: startRetry
                                    objectName: "projectStartRetry"
                                    visible: !!root.book && !root.book.starting && !root.book.running
                                    size: "sm"
                                    kind: "ghost"
                                    icon: "rotate-ccw"
                                    text: "Thử lại"
                                    busy: !!root.store && root.store.starting
                                    onActivated: root.store.start(root.book.id)
                                }
                            }
                            Column {
                                id: problem
                                objectName: "projectProblem"
                                readonly property var shown: root.book ? Logic.bookProblem(root.book, !!(root.store.info && root.store.info.studio), false) : null
                                visible: shown !== null
                                width: parent.width
                                spacing: 2
                                Text { width: parent.width; text: problem.shown ? problem.shown.summary : ""; color: Theme.danger; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
                                Text { width: parent.width; text: problem.shown ? problem.shown.hint : ""; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                            }
                        }
                    }
                }
                // Các bước làm sách khi sách chưa xong (ProductionPanel)
                Collapse {
                    width: parent.width
                    open: !!root.book && root.book.phase !== "done"
                    ProjectSteps { width: parent.width; book: root.book }
                }
                // Trước mốc phân tích xong: đặt sẵn "Duyệt trước khi thu" cho cuốn này (webui/precast.py)
                Collapse {
                    width: parent.width
                    open: !!root.book && root.book.phase !== "done" && !root.book.castLocked && !!root.book.precast
                    PrecastWait { store: root.store; book: root.book }
                }
                // Phân tích xong mà chưa thu bao nhiêu: lối vào "Duyệt trước khi thu" đúng lúc sửa còn miễn phí
                Collapse {
                    width: parent.width
                    open: !!root.book && Precast.bannerShown(root.book, root.tab)
                    PrecastBanner { book: root.book; onOpened: root.pickTab("precast") }
                }
                Collapse {
                    width: parent.width
                    open: root.sideError !== "" && root.failure !== "stale"
                    Row {
                        objectName: "projectSideError"
                        width: parent.width
                        spacing: 8
                        Icon { name: "circle-alert"; size: 16; color: Theme.warning; y: 2 }
                        Text {
                            width: parent.width - 16 - 8
                            text: "Chưa tải được " + root.shownSideError + "; tự thử lại, hoặc làm mới trang."
                            color: Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                    }
                }
                Item { width: 1; height: 12 }
                StudioTabs {
                    id: tabs
                    objectName: "projectTabs"
                    width: parent.width
                    tab: root.tab
                    precast: root.hasPrecast
                    counts: ({chapters: root.book ? root.book.chapters.total : 0, precast: studioWork.precastCount || undefined, work: studioWork.workCount || undefined, review: studioWork.reviewCount || undefined})
                    onPicked: key => root.pickTab(key)
                    onMoreRequested: anchor => { moreMenu.items = Logic.moreItems(root.hasPrecast); moreMenu.anchorItem = anchor; moreMenu.show() }
                }
                // Hàng tiêu đề của bảng chương, thẳng cột với StudioChapterRow (ô của ListView rộng hơn nội dung 8 mỗi bên)
                StudioChapterHead {
                    objectName: "chapterHead"
                    x: -8
                    width: root.contentW + 16
                    visible: root.shownTab === "chapters" && !!root.store && root.store.chapters.length > 0
                    opacity: root.swap
                }
            }
        }
        delegate: Item {
            id: cell
            required property string key
            readonly property var row: root.rowByKey[key] || ({})
            width: ListView.view.width
            height: body.item ? body.item.height : 0
            opacity: root.swap
            Loader {
                id: body
                width: parent.width
                sourceComponent: cell.row.kind === "chapter" ? chapterRow : cell.row.kind === "ahead" ? aheadRow : cell.row.kind === "day" ? dayRow
                                 : cell.row.kind === "log" ? logRow : cell.row.kind === "tech" ? techRow : null
            }
            Component {
                id: chapterRow
                StudioChapterRow {
                    chapter: cell.row.chapter
                    running: !!root.book && Boolean(root.book.running)
                    studio: !!(root.store.info && root.store.info.studio)
                    canPlay: !root.remote
                    current: Player.loaded && !!root.book && Player.bookId === root.book.id && Player.chapterId === cell.row.chapter.id
                    menuOpen: chapterMenu.open && root.menuChapter.id === cell.row.chapter.id
                    onPlayRequested: if (cell.row.chapter.playable) {
                        if (current) Player.toggle(); else Player.review(root.book.id, cell.row.chapter.id)
                    }
                    onErrorRequested: anchor => chapterError.openFor(anchor, cell.row.chapter.lastError, !!(root.store.info && root.store.info.studio))
                    onMenuRequested: anchor => {
                        root.menuChapter = cell.row.chapter
                        chapterMenu.items = root.chapterMenuItems(cell.row.chapter)
                        chapterMenu.anchorItem = anchor
                        chapterMenu.show()
                    }
                }
            }
            Component {
                id: aheadRow
                Item {
                    height: 44
                    Text {
                        objectName: "activityCount"
                        x: 8; anchors.verticalCenter: parent.verticalCenter
                        text: cell.row.count + " mục gần nhất"
                        color: Theme.text2
                        font.pixelSize: Theme.sizeCaption
                    }
                    Interactive {
                        id: technical
                        objectName: "activityTechnical"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.rightMargin: 8
                        width: techLabel.implicitWidth + 16
                        height: 32
                        Accessible.role: Accessible.Button
                        Accessible.name: techLabel.text
                        onClicked: root.activityMode = root.activityMode === "technical" ? "story" : "technical"
                        Text {
                            id: techLabel
                            anchors.centerIn: parent
                            text: root.activityMode === "technical" ? "Ẩn chi tiết kỹ thuật" : "Chi tiết kỹ thuật"
                            color: Theme.accentText
                            font.pixelSize: Theme.sizeCaption
                            font.weight: Theme.weightMedium
                        }
                    }
                }
            }
            Component {
                id: dayRow
                Item {
                    height: dayText.height + 20 + 8
                    Text {
                        id: dayText
                        objectName: "activityDay"
                        x: 8; y: 20
                        width: parent.width - 16
                        text: cell.row.day || ""
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeCaption
                        font.weight: Theme.weightMedium
                    }
                }
            }
            Component {
                id: logRow
                Item {
                    height: Math.max(36, logText.height + 12)
                    Rectangle { x: 8; width: 1; height: parent.height; color: Theme.line }
                    Rectangle {
                        x: 8 - 3.5; y: 17 - 4; width: 8; height: 8; radius: width / 2
                        color: cell.row.entry.level === "error" ? Theme.danger : cell.row.entry.level === "warning" ? Theme.warning
                               : cell.row.entry.level === "success" ? Theme.success : Theme.text3
                    }
                    Text {
                        id: logTime
                        x: 8 + 20; y: 6
                        text: Logic.activityTime(cell.row.entry)
                        color: Theme.text3
                        font.pixelSize: Theme.sizeCaption
                        font.features: { "tnum": 1 }
                        height: 24; verticalAlignment: Text.AlignVCenter
                    }
                    Text {
                        id: logText
                        objectName: "activityText"
                        x: logTime.x + 56
                        y: 6
                        width: parent.width - x - 8
                        text: cell.row.entry.text
                        color: cell.row.entry.level === "warning" ? Theme.text : Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                        height: Math.max(24, implicitHeight)
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
            Component {
                id: techRow
                Item {
                    height: techText.height + 6
                    Text {
                        id: techText
                        objectName: "activityTech"
                        x: 8; y: 3
                        width: parent.width - 16
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        font.family: "Consolas"
                        font.pixelSize: 12
                        color: cell.row.entry.level === "error" ? Theme.danger : cell.row.entry.level === "warning" ? Theme.warning : Theme.text2
                        text: Logic.formatTime(cell.row.entry.at) + "  " + (cell.row.entry.code || "") + "  " + cell.row.entry.text
                    }
                }
            }
        }
        footer: Item {
            width: list.width
            readonly property bool chaptersEmpty: root.shownTab === "chapters" && root.store && root.store.chapters.length === 0
            readonly property bool activityEmpty: root.shownTab === "activity" && root.activityData !== null && root.activityData.length === 0
            readonly property bool notReady: root.shownTab === "precast" && !root.hasPrecast
            readonly property bool placeholder: notReady
            readonly property real innerHeight: chaptersEmpty || activityEmpty ? emptyBlock.height : placeholder ? placeholderText.height + 48 : root.shownTab === "activity" && root.activityLoading ? 160 : 0
            height: backWrap.height + innerHeight + panels.height + (musicTab.item ? musicTab.item.height + 48 : 0) + (scriptTab.item ? scriptTab.item.height + 48 : 0)
            opacity: root.swap
            // "Về màn trước": sau khi nhảy từ một thẻ sang tab khác, trả về đúng thẻ và bộ lọc vừa rời
            Collapse {
                id: backWrap
                objectName: "jumpBackWrap"
                x: 8
                width: root.contentW
                open: root.cameFrom !== "" && root.fromLabels[root.cameFrom] !== undefined && root.shownTab !== root.cameFrom
                Item {
                    width: parent.width
                    height: 16 + jumpBack.height
                    Button {
                        id: jumpBack
                        objectName: "jumpBack"
                        y: 16
                        size: "sm"
                        kind: "ghost"
                        icon: "arrow-left"
                        text: "Về màn trước"
                        onClicked: root.jumpBack()
                    }
                }
            }
            EmptyState {
                id: emptyBlock
                objectName: "tabEmpty"
                visible: parent.chaptersEmpty || parent.activityEmpty
                x: 8
                y: backWrap.height
                width: root.contentW
                icon: "book-open-text"
                title: parent.activityEmpty ? "Chưa có gì" : "Chưa có chương nào"
                text: parent.activityEmpty ? "Diễn biến sẽ hiện ở đây khi sách bắt đầu chạy." : ""
                height: visible ? implicitHeight : 0
            }
            Text {
                id: placeholderText
                objectName: "tabPlaceholder"
                visible: parent.placeholder
                x: 8; y: backWrap.height + 32
                width: root.contentW
                text: parent.notReady ? Precast.NOT_READY : Logic.tabPlaceholder(root.shownTab)
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            EditBookSkeleton {
                objectName: "activitySkeleton"
                visible: root.shownTab === "activity" && root.activityLoading
                x: 8; y: backWrap.height + 24
                width: root.contentW * 2 / 3
                shape: "rows"
                count: 4
                label: "Đang tải nhật ký"
            }
            StudioPanels {
                id: panels
                x: 8
                y: backWrap.height + parent.innerHeight
                width: root.contentW
                store: root.store
                book: root.book
                work: studioWork
                caps: root.castCaps
                precastStep: root.precastStep
                tab: root.shownTab
                workKind: root.workKind
                workCard: root.workCard
                nameParam: root.nameParam
                focusNames: root.focusNames
                onKindChosen: value => { root.workKind = value; root.workCard = "" }
                onJumped: (next, from, card, name, names) => root.jump(next, from, card, name, names)
                onRevealRequested: target => root.reveal(target)
                onPersonRequest: (kind, person) => root.castRequest(kind, person)
                onPersonMenu: (anchor, person) => castMenu.openFor(anchor, person)
                onPrecastStepChosen: value => root.precastStep = value
                onPrecastOpened: root.pickTab("precast")
                onPrecastClosed: root.pickTab("chapters")
                onRedoRequested: if (root.book) root.newProjectRequested("redo", root.book.id)
                onScriptOpened: (chapterId, stableId, pick) => root.scriptAt = {chapter: chapterId, line: stableId, pick: pick}
            }
            // Tab Nhạc nền: dựng khi mở tab, gỡ khi rời (rời tab thì bài nghe thử dừng)
            Loader {
                id: musicTab
                objectName: "musicTab"
                x: 8
                y: backWrap.height + parent.innerHeight + panels.height
                width: root.contentW
                active: root.shownTab === "music" && !!root.book
                sourceComponent: StudioMusic {
                    store: root.store
                    bookId: root.book ? root.book.id : ""
                    chapters: root.store ? root.store.chapters : []
                    overlay: root
                }
            }
            // Tab Kịch bản: dựng khi mở tab (kể cả hỏi dấu đổi 6 giây một lần), gỡ khi rời
            Loader {
                id: scriptTab
                objectName: "scriptTab"
                x: 8
                y: backWrap.height + parent.innerHeight + panels.height
                width: root.contentW
                active: root.shownTab === "script" && !!root.book
                sourceComponent: ScriptTab {
                    store: root.store
                    work: studioWork
                    bookId: root.book ? root.book.id : ""
                    flick: list
                    overlay: root
                    target: root.scriptAt
                    remembered: root.viewState.script || null
                    onPositionChanged: (chapter, line) => root.rememberView({script: {chapter: chapter, line: line}})
                }
            }
        }
        SmoothWheel { flick: list }
    }
    ScrollEdges { target: list; color: Theme.bg; x: list.x; y: list.y; width: list.width; height: list.height; visible: list.visible }
    Scrollbar { target: list; visible: list.visible && scrollable && opacity > 0 }

    // ---- menu ----
    ProjectMenu {
        id: bookMenu
        objectName: "bookMenu"
        onPicked: key => dialogs.perform(key, root.book)
    }
    ProjectMenu {
        id: moreMenu
        objectName: "moreMenu"
        onPicked: key => root.pickTab(key)
    }
    ProjectMenu {
        id: chapterMenu
        objectName: "chapterMenu"
        onPicked: key => {
            const chapter = root.menuChapter
            if (key === "play") Player.review(root.book.id, chapter.id)
            else if (key === "script") { root.pickTab("script"); root.scriptAt = {chapter: chapter.id, line: "", pick: false} }
            else if (key === "retake") {
                root.retakeChapter = chapter
                retake.title = "Thu lại cả " + chapter.displayTitle + "?"
                retake.description = "Thu lại " + chapter.segments.finished + " câu; giọng giữ nguyên, cách nói đổi."
                retake.actions = [{key: "later", text: "Thôi"}, {key: "go", text: "Thu lại " + chapter.segments.finished + " câu", icon: "refresh-cw", kind: "primary"}]
                retake.show()
            }
        }
    }
    ChapterError { id: chapterError }
    StudioConfirm {
        id: retake
        objectName: "retakeConfirm"
        panelWidth: 480
        onChosen: key => {
            retake.dismiss()
            if (key === "go") root.store.retakeChapter(root.book.id, root.retakeChapter)
        }
        // Thu lại cùng chữ không chữa được sai người nói / sai chữ: lối sang Kịch bản của chương ấy, và vì sao
        Button {
            objectName: "retakeEdit"
            kind: "ghost"
            text: "Sửa chữ"
            onActivated: {
                const chapter = root.retakeChapter
                retake.dismiss()
                root.pickTab("script")
                root.scriptAt = {chapter: chapter.id, line: "", pick: false}
            }
        }
        MoreInfo {
            objectName: "retakeMore"
            width: parent.width
            label: "Thu lại chương"
            HintText { width: parent.width; text: "Dùng hạt giống mới cho cả chương. Sai người nói hoặc chữ thì sửa Kịch bản trước; thu lại cùng chữ không chữa được." }
        }
    }
    StudioDialogs {
        id: dialogs
        store: root.store
        local: !root.remote
        computer: root.store ? root.store.computerName : "máy tính"
        next: root.next
        onListenRequested: id => root.listenRequested(id)
        onNewProjectRequested: (mode, id) => root.newProjectRequested(mode, id)
        onRemoved: root.backRequested()
    }
}
