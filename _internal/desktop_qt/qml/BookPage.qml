import QtQuick
import ABook
import "EditBookLogic.js" as Logic
import "CastLogic.js" as Cast
import "RecordLogic.js" as Records
import "BookLogic.js" as BookText

// One width rule on the content area. Geometry interpolates without reparenting,
// so the cover, chapter scroll position and delegates survive a class change.
Item {
    id: root
    signal editRequested(var data)
    signal saveRequested(var data)
    signal saveAsRequested(var data)
    signal renameRequested(var data, var chapter)       // "Đổi tên chương…" ở menu "…" của dòng chương: hộp EditBookRename của Main.qml
    signal castRequested(string kind, var data)         // hộp của tab Nhân vật (CastDialogs của Main.qml): "merge" | "rename" | "gender" | "voice" | "narrator"
    signal recordRequested(string kind, var data)       // hộp / việc của hồ sơ nghe (RecordDialogs của Main.qml): "create" | "rename" | "move" | "delete" | "activate"
    property var book: ({})
    readonly property bool expanded: width >= Theme.widthExpanded
    property real split: expanded ? 1 : 0
    // First make room horizontally, then lift the chapter list beside the summary.
    // The reverse follows the same route, keeping text clear of the moving cover.
    readonly property real summaryT: Math.min(1, split * 2)
    readonly property real chapterT: Math.max(0, split * 2 - 1)
    Behavior on split {
        NumberAnimation {
            duration: Theme.reduceMotion ? 0 : Theme.motionMedium
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }
    readonly property real leftWidth: Math.min(380, 320 + Math.max(0, width - Theme.widthExpanded) * 0.06)
    readonly property real compositionWidth: Math.min(width - 2 * Theme.margin, 1360, leftWidth + Theme.s32 + Theme.listMeasure)
    readonly property real compactCoverH: Math.min(150, height * 0.25)
    readonly property real wideCoverH: Math.max(0, Math.min(height * 0.4, stage.height - info.height - Theme.s16))
    readonly property real stackedHeight: Math.max(compactCoverH, info.height) + Theme.s24

    BookDetail {
        id: bookDetail          // không đặt tên `detail`: trong hàng chương, `detail` là thuộc tính chữ của ChapterRow
        bookId: root.book.bookId || ""
    }
    ScreenHeader {
        id: header
        objectName: "bookHeader"
        // Nút ← thẳng mép khối nội dung, kể cả khi khối bị giới hạn 1360 và căn giữa ở khổ rất lớn.
        x: stage.x
        width: stage.width
        showBack: true
        backLabel: "Về Thư viện"
        title: ""
        implicitHeight: Theme.s32 + Theme.headerRow
    }
    // Cuốn đầy đủ (quyền sửa, số thay đổi...): nạp lúc mở trang và sau mỗi lần sửa
    property var fullBook: ({})
    function loadFull() {
        const id = root.book.bookId
        if (!id) return
        Api.call("GET", "/api/listen/books/" + id, null, function(data, error) { if (!error && id === root.book.bookId) root.fullBook = data })
    }
    onBookChanged: if (root.book.bookId && root.book.bookId !== fullBook.id) loadFull()
    Connections {
        target: Api
        function onEdited(bookId) {
            if (bookId !== root.book.bookId) return
            bookDetail.reload()         // dấu "đã nghe" của từng chương theo hồ sơ nghe vừa đổi
            Api.call("GET", "/api/listen/books/" + bookId, null, function(data, error) {
                if (!error) {
                    root.fullBook = data
                    root.book = Object.assign({}, root.book, data, {bookId: data.id, coverKey: data.cover ? data.id + "/" + (data.cover.version || 0) : ""})
                }
            })
        }
    }
    // Việc với hồ sơ nghe khi cuốn chỉ có MỘT hồ sơ (singleRecordActions của BookScreen.tsx): "Hồ sơ mới", "Chuyển hồ sơ", "Đổi tên hồ sơ…" ở đầu menu,
    // "Xoá hồ sơ…" ở cuối dưới vạch ngăn; nhiều hồ sơ thì nút "Hồ sơ nghe:" lo. "Đã nghe xong / Chưa nghe xong" cho cả cuốn nằm dưới các việc ấy.
    readonly property var recordRows: Records.singleActions(fullBook)
    readonly property bool loaded: fullBook.id !== undefined
    readonly property bool listening: Player.loaded && Player.bookId === root.book.bookId
    readonly property bool speaks: Api.voiceList.length > 0
    readonly property bool textOnly: fullBook.stage === "text"
    readonly property bool moreMenu: items.hasItems || root.recordRows.length > 0 || root.canToggleFinished
    // Đọc: đang nghe cuốn này thì mở đúng chương đang phát; không thì chỗ đọc đã lưu (hay chương đầu).
    function read() {
        const saved = BookText.latestReading(root.fullBook)
        reader.begin(root.book.bookId, root.listening ? Player.chapterId : saved ? saved.chapterId : -1, root.listening || !saved ? -1 : saved.index)
    }
    // "Từ đầu" / "Nghe lại từ đầu": cuốn đang nạp thì nhảy như mọi cú nhảy khác (bộ phát nhớ chỗ cũ); không thì phát từ chương đầu và
    // cho 8 giây "Quay lại chỗ cũ" khi chỗ cũ khác hẳn.
    function restart() {
        const first = bookDetail.firstPlayable()
        if (first < 0) return
        const id = root.book.bookId
        if (root.listening) { Player.jumpTo(first, 0); return }
        const before = bookDetail.point()
        Player.open(id, first, 0, true)
        if (before.chapterId !== undefined && (before.chapterId !== first || before.at > 30))
            Api.toast("Đang nghe lại từ đầu", {duration: 8000, action: {label: "Quay lại chỗ cũ", run: function() { Player.open(id, before.chapterId, before.at, true) }}})
    }
    function primary() {
        if (!bookDetail.hasPoint) root.read()
        else if (bookDetail.finished) root.restart()
        else bookDetail.activate()
    }
    function find() { finder.begin(root.book.bookId, root.book.title || root.fullBook.title || "", root.fullBook.chapters || []) }
    readonly property bool canToggleFinished: fullBook.id !== undefined && fullBook.stage !== "text"
    readonly property bool finishedNow: Boolean(fullBook.progress && fullBook.progress.finished)
    function recordRequest(kind, dialog, record) {
        if (fullBook.id === undefined) return
        root.recordRequested(kind, {bookId: root.book.bookId, book: root.fullBook, dialog: dialog, record: record})
    }
    // Đánh dấu cả cuốn đã nghe xong / chưa (POST .../finished), ghi vào hồ sơ nghe đang hiện
    function setFinished(finished) {
        const id = root.book.bookId
        const active = Records.activeRecord(root.fullBook)
        Api.call("POST", "/api/listen/books/" + id + "/finished", active ? {finished: finished, record: active.id} : {finished: finished}, function(data, error) {
            if (error) { if (/^Hồ sơ nghe này/.test(error)) root.loadFull(); return }
            bookDetail.reload()
            root.loadFull()
            if (Api.transport) Api.transport.refreshLibrary()
        })
    }
    // Menu "Thêm" (ActionMenu "Việc với sách" của web): các việc với hồ sơ nghe, đã nghe xong, các mục sửa sách.
    Popover {
        id: more
        objectName: "bookMoreMenu"
        Accessible.name: "Việc với sách"
        anchorItem: moreButton
        panelWidth: 280
        pad: Theme.s8
        Column {
            width: parent.width
            Repeater {
                model: root.recordRows.filter(row => !row.danger)
                MenuRow {
                    required property var modelData
                    objectName: "recordRow." + modelData.key
                    width: parent.width
                    icon: modelData.icon
                    text: modelData.label
                    onClicked: { more.close(); root.recordRequest(modelData.key, modelData.dialog, null) }
                }
            }
            MenuRow {
                objectName: "menuFinished"
                visible: root.canToggleFinished
                width: parent.width
                height: visible ? implicitHeight : 0
                icon: "check-check"
                text: root.finishedNow ? "Chưa nghe xong" : "Đã nghe xong"
                onClicked: { more.close(); root.setFinished(!root.finishedNow) }
            }
            EditBookItems {
                id: items
                width: parent.width
                book: root.fullBook
                onEditRequested: { more.close(); root.editRequested(root.fullBook) }
                onSaveRequested: { more.close(); root.saveRequested(root.fullBook) }
                onSaveAsRequested: { more.close(); root.saveAsRequested(root.fullBook) }
            }
            Item {
                visible: root.recordRows.some(row => row.danger)
                width: parent.width
                height: visible ? 9 : 0
                Rectangle { y: 4; width: parent.width; height: 1; color: Theme.line }
            }
            Repeater {
                model: root.recordRows.filter(row => row.danger)
                MenuRow {
                    required property var modelData
                    objectName: "recordRow." + modelData.key
                    width: parent.width
                    icon: modelData.icon
                    text: modelData.label
                    danger: true
                    onClicked: { more.close(); root.recordRequest(modelData.key, modelData.dialog, null) }
                }
            }
        }
    }
    // Nhiều hồ sơ: danh sách của nút "Hồ sơ nghe:" (RecordMenu)
    Popover {
        id: recordMenu
        objectName: "recordMenu"
        anchorItem: recordChip
        panelWidth: 288
        pad: 6
        RecordMenu {
            width: parent.width
            book: root.fullBook
            onActivate: record => {
                recordMenu.close()
                if (!record.active) root.recordRequest("activate", null, record)
            }
            onAction: dialog => { recordMenu.close(); root.recordRequest(dialog.kind, dialog, null) }
        }
    }
    // Menu chương dùng cùng màn đọc với Thư viện và Đang nghe.
    property var menuChapter: null          // {chapterId, title, subtitle, fullTitle, playable, done}
    readonly property bool canRename: Logic.canEditLayer(fullBook.capabilities)
    // Mục của sách: Chương | Lịch sử | Nhân vật (0, 1, 2). Sách chỉ có chữ (chưa phân vai) không có dàn nhân vật nên không có mục cuối.
    property int tab: 0
    readonly property bool hasCast: fullBook.id !== undefined && fullBook.stage !== "text"
    readonly property var tabLabels: hasCast ? ["Chương", "Lịch sử", "Nhân vật"] : ["Chương", "Lịch sử"]
    readonly property int paneIndex: Math.min(tab, tabLabels.length - 1)
    // Việc sửa dàn nhân vật theo khả năng của cuốn (BookScreen.tsx: editable / waiting / workshop): đổi tên - mọi cuốn sửa được; giới tính và gộp - cuốn chờ
    // Studio (file .abook) hay cuốn có xưởng; đổi giọng, bỏ gộp, đổi giọng người kể - cuốn có xưởng (bản Qt chưa có Studio nên làm ngay ở đây). Cuốn của máy khác: chỉ nghe.
    readonly property bool remote: Boolean(root.book.remote)
    readonly property bool workshop: Boolean(fullBook.capabilities && fullBook.capabilities.workshop)
    readonly property bool castWaiting: canRename && !workshop && !remote
    readonly property var castCaps: ({
        rename: canRename && !remote,
        merge: canRename && !remote,
        gender: canRename && !remote,
        voice: canRename && workshop && !remote,
        unmerge: canRename && workshop && !remote,
        narrator: canRename && workshop && !remote,
        waiting: castWaiting})
    // Người của các chương sau chỗ đang nghe ẩn tới khi bấm "Hiện chương sau" (không lộ nội dung chưa nghe tới)
    readonly property var castUntil: Player.loaded && Player.bookId === root.book.bookId ? Player.chapterId
        : (fullBook.state && fullBook.state.last ? fullBook.state.last.chapterId : undefined)
    readonly property var castReached: fullBook.chapters && fullBook.chapters.length ? Cast.reachedTitles(fullBook.chapters, castUntil) : null
    function openCastMenu(anchor, person) { castMenu.openFor(anchor, person) }
    function castRequest(kind, person) {
        if (kind === "unmerge") { castUnmerge.run(root.book.bookId, person); return }
        const data = {bookId: root.book.bookId, person: person, waiting: castWaiting}
        if (kind === "merge") data.people = castList.characters
        root.castRequested(kind, data)
    }
    CastUnmerge { id: castUnmerge }
    function openChapterMenu(anchor, row) {
        menuChapter = row
        chapterMenu.anchorItem = anchor
        chapterMenu.show()
    }
    // Đã nghe xong / Chưa nghe: ghi vào hồ sơ nghe đang hiện (shownRecord), rồi nạp lại trang và thư viện
    function setChapterDone(chapterId, done) {
        const id = root.book.bookId
        const records = root.fullBook.records || []
        const active = records.filter(r => r.active)[0]
        const body = active ? {done: done, record: active.id} : {done: done}
        Api.call("POST", "/api/listen/books/" + id + "/chapters/" + chapterId + "/done", body, function(data, error) {
            if (error) { if (/^Hồ sơ nghe này/.test(error)) root.loadFull(); return }
            bookDetail.reload()
            if (Api.transport) Api.transport.refreshLibrary()
        })
    }
    Popover {
        id: chapterMenu
        objectName: "chapterMenu"
        panelWidth: 220
        pad: 6
        Column {
            width: parent.width
            readonly property var c: root.menuChapter || ({})
            // Cao đúng tổng các hàng đang hiện: bảng nổi đo chỗ (mở lên hay xuống) ngay lúc mở, khi `visible` của hàng còn đọc ra false
            height: Theme.buttonHeight * (1 + (c.playable ? 2 : 0) + (root.canRename ? 1 : 0))
            MenuRow {
                objectName: "chapterRead"
                width: parent.width; icon: "book-open"; text: "Đọc chương này"
                onClicked: { chapterMenu.close(); reader.begin(root.book.bookId, parent.c.chapterId) }
            }
            MenuRow {
                objectName: "chapterFromStart"
                visible: Boolean(parent.c.playable)
                width: parent.width
                icon: "play"
                text: "Nghe từ đầu chương"
                onClicked: { chapterMenu.close(); Player.open(root.book.bookId, parent.c.chapterId, 0, true) }
            }
            MenuRow {
                objectName: "chapterDone"
                visible: Boolean(parent.c.playable)
                width: parent.width
                icon: parent.c.done ? "circle-dashed" : "check-check"
                text: parent.c.done ? "Chưa nghe" : "Đã nghe xong"
                onClicked: { chapterMenu.close(); root.setChapterDone(parent.c.chapterId, !parent.c.done) }
            }
            MenuRow {
                objectName: "chapterRename"
                visible: root.canRename
                width: parent.width
                icon: "text-cursor-input"
                text: "Đổi tên chương…"
                onClicked: {
                    chapterMenu.close()
                    const c = parent.c
                    root.renameRequested(root.fullBook, {id: c.chapterId, title: c.title, subtitle: c.subtitle, fullTitle: c.fullTitle})
                }
            }
        }
    }
    // Menu "…" của một người ở tab Nhân vật (CastMenu, dùng chung với Studio)
    CastMenu {
        id: castMenu
        caps: root.castCaps
        onPicked: (kind, person) => root.castRequest(kind, person)
    }
    Item {
        id: stage
        objectName: "bookStage"
        opacity: bookDetail.status === "failed" && !root.loaded ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
        x: (parent.width - width) / 2
        y: header.height + Theme.s16
        width: parent.width - 2 * Theme.margin + (root.compositionWidth - (parent.width - 2 * Theme.margin)) * root.split
        height: parent.height - y - Theme.s16

        Item {
            id: summary
            objectName: "bookSummary"
            width: stage.width + (root.leftWidth - stage.width) * root.summaryT
            height: Math.max(cover.height, info.y + info.height)
            CoverView {
                id: cover
                objectName: "bookCover"
                height: root.compactCoverH + (root.wideCoverH - root.compactCoverH) * root.summaryT
                width: height / Theme.coverRatio
                x: 0
                coverKey: root.book.coverKey || ""
                title: root.book.title || ""
                radius: Theme.radiusCover
            }
            Column {
                id: info
                objectName: "bookInfo"
                x: (cover.width + Theme.s24) * (1 - Math.max(0, (root.summaryT - 0.2) / 0.8))
                y: (cover.height + Theme.s16) * Math.min(1, root.summaryT / 0.2)
                width: summary.width - x
                spacing: Theme.s4 + (Theme.s8 - Theme.s4) * root.summaryT

                Text {
                    objectName: "bookTitle"
                    width: parent.width
                    text: root.book.title || ""
                    color: Theme.text
                    wrapMode: Text.Wrap
                    lineHeight: 1.15
                    font.pixelSize: Theme.sizeSection + (Theme.sizeTitlePhone - Theme.sizeSection) * root.summaryT
                    font.weight: Theme.weightBold
                }
                Text {
                    visible: !!root.book.author
                    width: parent.width
                    text: root.book.author || ""
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBody
                }
                Text {
                    visible: text !== ""
                    width: parent.width
                    text: [root.book.detail, root.book.chapters > 0 ? root.book.chapters + " chương" : ""].filter(s => !!s).join(" · ")
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                // Tình trạng của cuốn: một dòng chữ nhỏ (chỉ có chữ / chưa đủ chương), không hộp, không viên thuốc màu.
                Text {
                    objectName: "bookStatusLine"
                    visible: text !== ""
                    width: parent.width
                    text: root.loaded ? BookText.statusLine(root.fullBook, root.speaks) : ""
                    color: root.textOnly ? Theme.text2 : Theme.accentText
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Item { width: 1; height: Theme.s8 * root.summaryT }
                Rectangle {          // tiến độ mảnh ("Đã nghe")
                    objectName: "bookProgress"
                    visible: root.loaded && !root.textOnly
                    width: Math.min(parent.width, 448)
                    height: 4
                    radius: height / 2
                    color: Theme.sunken
                    Accessible.role: Accessible.ProgressBar
                    Accessible.name: "Đã nghe"
                    readonly property var progress: BookText.progressOf(root.fullBook)
                    Rectangle {
                        width: parent.width * Math.max(0, Math.min(1, Number(parent.progress.fraction || 0)))
                        height: parent.height
                        radius: parent.radius
                        color: parent.progress.finished ? Theme.success : Theme.accent
                        Behavior on width { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                    }
                }
                Text {
                    objectName: "bookProgressLine"
                    visible: root.loaded && !root.textOnly
                    width: parent.width
                    text: root.loaded ? BookText.progressLine(root.fullBook, root.listening, Player.error !== "") : ""
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeCaption
                    font.features: { "tnum": 1 }
                }
                Item {          // "Hồ sơ nghe: {tên}" (chỉ khi cuốn có từ hai hồ sơ)
                    visible: Records.hasPicker(root.fullBook)
                    width: parent.width
                    height: visible ? recordChip.height + Theme.s4 : 0
                    RecordChip {
                        id: recordChip
                        objectName: "recordChip"
                        y: Theme.s4
                        maxWidth: parent.width
                        name: Records.activeRecord(root.fullBook) ? Records.activeRecord(root.fullBook).name : ""
                        onClicked: recordMenu.toggle()
                    }
                }
                Item { width: 1; height: Theme.s8 * root.summaryT }
                // Đúng MỘT nút chính: nghe (hay nghe tiếp) - sách không nghe được ở máy này thì "Đọc"; nghe hết phần đã có thì một dòng thay nút.
                // Chương không lấy được (máy chủ không trả danh sách chương) mà sách có: vẫn đọc / tìm / "Thêm" được.
                // Bố cục rộng: một cột như web. Bố cục vừa (bìa nhỏ cạnh chữ, danh sách chương ở dưới): web cuộn cả trang còn ở đây danh sách
                // chương có khung riêng, nên khi đủ chỗ thì hàng nút phụ đứng cạnh nút chính để phần trên không ăn mất chỗ của chương.
                Grid {
                    id: actions
                    objectName: "bookActions"
                    visible: bookDetail.status === "ready" || (bookDetail.status === "failed" && root.loaded)
                    width: parent.width
                    columns: !root.expanded && width >= 2 * rowWidth + Theme.s16 ? 2 : 1
                    rowSpacing: Theme.s12
                    columnSpacing: Theme.s16
                    verticalItemAlignment: Grid.AlignVCenter
                    readonly property real rowWidth: Math.min(width, Math.max(256, primaryButton.implicitWidth))
                    Text {
                        objectName: "bookCaughtUp"
                        visible: bookDetail.caughtUp
                        width: actions.columns === 1 ? parent.width : Math.max(0, parent.width - actions.rowWidth - actions.columnSpacing)
                        text: "Đã nghe hết phần đã có. Chương mới sẽ hiện ở đây khi làm xong."
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    Button {
                        id: primaryButton
                        objectName: "bookPrimary"
                        visible: !bookDetail.caughtUp
                        size: "lg"
                        wrap: true
                        width: actions.rowWidth          // web: cột w-fit min-w-[16rem], nút giãn bằng cột
                        text: bookDetail.hasPoint ? bookDetail.primaryText : BookText.readLabel(root.fullBook, root.listening)
                        icon: bookDetail.hasPoint ? bookDetail.primaryIcon : "book-open"
                        onClicked: root.primary()
                    }
                    // Hàng phụ "Việc với sách": luôn cùng chỗ, cùng thứ tự - nút chưa dùng được thì mờ đi chứ không biến mất; hai đầu thẳng hai mép nút chính.
                    Item {
                        objectName: "bookSecondary"
                        width: actions.rowWidth
                        height: secondary.height
                        Accessible.role: Accessible.Grouping
                        Accessible.name: "Việc với sách"
                        Row {
                            id: secondary
                            readonly property var shown: [readButton, findButton, restartButton, moreButton].filter(b => b.visible)
                            readonly property real used: shown.reduce((sum, b) => sum + b.width, 0)
                            spacing: shown.length > 1 ? Math.max(0, (actions.rowWidth - used) / (shown.length - 1)) : 0
                            ActionButton {
                                id: readButton
                                objectName: "bookRead"
                                visible: bookDetail.hasPoint || bookDetail.caughtUp
                                icon: "book-open"
                                label: "Đọc"
                                Accessible.name: BookText.readLabel(root.fullBook, root.listening)
                                onClicked: root.read()
                            }
                            ActionButton {
                                id: findButton
                                objectName: "bookFind"
                                icon: "search"
                                label: "Tìm"
                                Accessible.name: "Tìm chữ trong sách"
                                enabled: (root.fullBook.chapters || []).length > 0
                                onClicked: root.find()
                            }
                            ActionButton {
                                id: restartButton
                                objectName: "bookRestart"
                                visible: !root.textOnly || bookDetail.hasPoint
                                icon: "rotate-ccw"
                                label: "Từ đầu"
                                Accessible.name: "Nghe lại từ đầu"
                                enabled: bookDetail.started && bookDetail.hasPoint && !bookDetail.finished
                                onClicked: root.restart()
                            }
                            ActionButton {
                                id: moreButton
                                objectName: "bookMore"
                                visible: root.moreMenu
                                icon: "ellipsis"
                                label: "Thêm"
                                Accessible.name: "Thêm việc với sách"
                                active: more.open
                                onClicked: more.toggle()
                            }
                        }
                    }
                }
            }
        }
        Item {
            id: chapterRegion
            objectName: "bookChapterRegion"
            x: (root.leftWidth + Theme.s32) * root.summaryT
            y: Math.max(root.stackedHeight, summary.height + Theme.s24) * (1 - root.chapterT)
            width: Math.min(stage.width - x, Theme.listMeasure)
            height: Math.max(0, stage.height - y)
            PageSwitch {
                id: tabs
                objectName: "bookTabs"
                label: "Mục của sách"
                labels: root.tabLabels
                index: root.paneIndex
                onPicked: index => root.tab = index
            }
            readonly property real headHeight: tabs.height
            readonly property int fade: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : Theme.motionMedium
            ListView {
                id: list
                objectName: "bookChapters"
                y: chapterRegion.headHeight + Theme.s8
                width: parent.width
                height: Math.max(0, parent.height - y)
                clip: true
                opacity: root.paneIndex === 0 ? 1 : 0
                visible: opacity > 0
                enabled: root.paneIndex === 0
                Behavior on opacity { NumberAnimation { duration: chapterRegion.fade } }
                model: bookDetail.chapters
                boundsBehavior: Flickable.StopAtBounds
                bottomMargin: Theme.s16
                delegate: ChapterRow {
                    id: row
                    required property var model
                    objectName: "bookChapterRow"
                    width: list.width
                    title: model.title
                    subtitle: model.subtitle
                    length: model.length
                    status: model.status
                    playable: model.playable
                    done: model.done
                    current: model.current
                    progress: model.progress
                    fullTitle: model.fullTitle
                    hasMenu: true
                    menuOpen: chapterMenu.open && root.menuChapter !== null && root.menuChapter.chapterId === model.chapterId
                    Accessible.name: model.playable ? model.current && Player.playing ? `Tạm dừng ${model.fullTitle}` : `Nghe ${model.fullTitle}` : `Đọc ${model.fullTitle} (chưa có audio)`
                    onClicked: {
                        if (row.onMenuButton) return
                        if (model.playable) bookDetail.playChapter(model.chapterId)
                        else reader.begin(root.book.bookId, model.chapterId)
                    }
                    onMenuRequested: anchor => root.openChapterMenu(anchor, {chapterId: model.chapterId, title: model.title, subtitle: model.subtitle,
                        fullTitle: model.fullTitle, playable: model.playable, done: model.done})
                }
                SmoothWheel { flick: list }
                Scrollbar { target: list }
            }
            ScrollEdges {
                x: list.x; y: list.y; width: list.width; height: list.height
                target: list
                opacity: list.opacity
                visible: list.visible
            }
            HistoryList {
                id: historyList
                y: chapterRegion.headHeight + Theme.s8
                width: parent.width
                height: Math.max(0, parent.height - y)
                bookId: root.book.bookId || ""
                active: root.paneIndex === 1
                chapters: root.fullBook.chapters || []
                opacity: root.paneIndex === 1 ? 1 : 0
                visible: opacity > 0
                enabled: root.paneIndex === 1
                Behavior on opacity { NumberAnimation { duration: chapterRegion.fade } }
                onPlay: (chapterId, seconds) => Player.open(root.book.bookId, chapterId, seconds, true)
            }
            CastList {
                id: castList
                y: chapterRegion.headHeight + Theme.s8
                width: parent.width
                height: Math.max(0, parent.height - y)
                bookId: root.book.bookId || ""
                active: root.paneIndex === 2
                caps: root.castCaps
                reached: root.castReached
                opacity: root.paneIndex === 2 ? 1 : 0
                visible: opacity > 0
                enabled: root.paneIndex === 2
                Behavior on opacity { NumberAnimation { duration: chapterRegion.fade } }
                onRequest: (kind, person) => root.castRequest(kind, person)
                onMenuRequested: (anchor, person) => root.openCastMenu(anchor, person)
            }
        }
    }
    ChapterReader { id: reader }
    FindInBook {
        id: finder
        onPicked: hit => reader.begin(root.book.bookId, hit.chapterId, hit.sentence, root.listening && Player.playing, true)
    }
    // Không tìm thấy sách này (đã chuyển thư mục / đã xoá): cả trang thành màn trống, nút ← vẫn ở trên.
    EmptyState {
        objectName: "bookMissing"
        anchors.top: header.bottom; anchors.topMargin: 80
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width - 2 * Theme.margin, 560)
        opacity: bookDetail.status === "failed" && !root.loaded ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
        icon: "book-open-text"
        title: "Không tìm thấy sách này"
        text: "Sách có thể đã bị chuyển sang thư mục khác hoặc bị xoá khỏi thư viện."
        Button { objectName: "bookMissingBack"; text: "Về thư viện"; onClicked: Nav.back() }
    }
}
