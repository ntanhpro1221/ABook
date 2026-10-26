import QtQuick
import ABook
import "EditBookLogic.js" as Logic

// One width rule on the content area. Geometry interpolates without reparenting,
// so the cover, chapter scroll position and delegates survive a class change.
Item {
    id: root
    signal editRequested(var data)
    signal saveRequested(var data)
    signal saveAsRequested(var data)
    signal renameRequested(var data, var chapter)       // "Đổi tên chương…" ở menu "…" của dòng chương: hộp EditBookRename của Main.qml
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
    readonly property real compositionWidth: Math.min(width - 2 * Theme.margin, 1360)
    readonly property real compactCoverH: Math.min(150, height * 0.25)
    readonly property real wideCoverH: Math.max(0, Math.min(height * 0.4, stage.height - info.height - Theme.s16))
    readonly property real stackedHeight: Math.max(compactCoverH, info.height) + Theme.s24

    BookDetail {
        id: bookDetail          // không đặt tên `detail`: trong hàng chương, `detail` là thuộc tính chữ của ChapterRow
        bookId: root.book.bookId || ""
    }
    ScreenHeader {
        id: header
        // Nút ← thẳng mép khối nội dung, kể cả khi khối bị giới hạn 1360 và căn giữa ở khổ rất lớn.
        x: stage.x
        width: stage.width
        showBack: true
        backLabel: "Về Thư viện"
        title: ""
        implicitHeight: Theme.s32 + Theme.headerRow
        // Menu "Thêm": các mục sửa sách (hiện khi cuốn có gì để sửa / giải thích vì sao chưa sửa được)
        Button {
            id: moreButton
            objectName: "bookMore"
            visible: items.hasItems
            text: "Thêm"; icon: "ellipsis"; kind: "text"
            Accessible.name: "Thêm việc với sách"
            onClicked: more.toggle()
        }
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
            Api.call("GET", "/api/listen/books/" + bookId, null, function(data, error) {
                if (!error) {
                    root.fullBook = data
                    root.book = Object.assign({}, root.book, data, {bookId: data.id, coverKey: data.cover ? data.id + "/" + (data.cover.version || 0) : ""})
                }
            })
        }
    }
    Popover {
        id: more
        anchorItem: moreButton
        panelWidth: 280
        pad: Theme.s8
        EditBookItems {
            id: items
            width: parent.width
            book: root.fullBook
            onEditRequested: { more.close(); root.editRequested(root.fullBook) }
            onSaveRequested: { more.close(); root.saveRequested(root.fullBook) }
            onSaveAsRequested: { more.close(); root.saveAsRequested(root.fullBook) }
        }
    }
    // Menu "…" của một dòng chương (DropdownMenu trong ChapterRow của listen/BookScreen.tsx). "Đọc chương này" chưa có: bản Qt chưa có màn đọc.
    property var menuChapter: null          // {chapterId, title, subtitle, fullTitle, playable, done}
    readonly property bool canRename: Logic.canEditLayer(fullBook.capabilities)
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
            height: Theme.buttonHeight * ((c.playable ? 2 : 0) + (root.canRename ? 1 : 0))
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
    Item {
        id: stage
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
                Item { width: 1; height: Theme.s8 * root.summaryT }
                Rectangle {          // tiến độ mảnh
                    visible: root.book.progress > 0.005
                    width: parent.width
                    height: 4
                    radius: height / 2
                    color: Theme.sunken
                    Rectangle {
                        width: parent.width * Math.min(1, root.book.progress || 0)
                        height: parent.height
                        radius: parent.radius
                        color: Theme.accent
                    }
                }
                Text {
                    visible: root.book.progress > 0.005
                    width: parent.width
                    text: root.book.progress >= 0.995 ? "Đã nghe xong"
                        : "Đã nghe " + Math.floor((root.book.progress || 0) * 100) + "%"
                          + (root.book.lastChapter ? " · " + root.book.lastChapter : "")
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Item { width: 1; height: Theme.s8 * root.summaryT }
                Flow {
                    visible: bookDetail.canListen
                    width: parent.width
                    spacing: Theme.s8
                    Button {
                        text: bookDetail.primaryText
                        icon: bookDetail.primaryIcon
                        onClicked: bookDetail.activate()
                    }
                    Button {
                        kind: "text"
                        icon: "list-ordered"
                        text: "Chương"
                        onClicked: { list.positionViewAtBeginning(); list.forceActiveFocus() }
                    }
                }
                Text {
                    visible: bookDetail.primaryCaption !== ""
                    width: parent.width
                    text: bookDetail.primaryCaption
                    wrapMode: Text.Wrap
                    color: Theme.text2
                    font.pixelSize: Theme.sizeBodySmall
                }
                Text {
                    visible: bookDetail.message !== ""
                    width: parent.width
                    text: bookDetail.message
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Text {
                    visible: bookDetail.status === "failed"
                    width: parent.width
                    text: "Chưa lấy được danh sách chương."
                    color: Theme.danger
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
        }
        Item {
            id: chapterRegion
            objectName: "bookChapterRegion"
            x: (root.leftWidth + Theme.s32) * root.summaryT
            y: Math.max(root.stackedHeight, summary.height + Theme.s24) * (1 - root.chapterT)
            width: stage.width - x
            height: Math.max(0, stage.height - y)
            Text {
                id: chaptersTitle
                visible: bookDetail.chapters.count > 0
                width: parent.width
                text: "Chương"
                wrapMode: Text.Wrap
                color: Theme.text
                font.pixelSize: Theme.sizeSection
                font.weight: Theme.weightMedium
            }
            ListView {
                id: list
                objectName: "bookChapters"
                y: chaptersTitle.height + Theme.s8
                width: parent.width
                height: Math.max(0, parent.height - y)
                clip: true
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
                    hasMenu: model.playable || root.canRename
                    menuOpen: chapterMenu.open && root.menuChapter !== null && root.menuChapter.chapterId === model.chapterId
                    onClicked: if (model.playable && !row.onMenuButton) bookDetail.playChapter(model.chapterId)
                    onMenuRequested: anchor => root.openChapterMenu(anchor, {chapterId: model.chapterId, title: model.title, subtitle: model.subtitle,
                        fullTitle: model.fullTitle, playable: model.playable, done: model.done})
                }
                SmoothWheel { flick: list }
                Scrollbar { target: list }
            }
            ScrollEdges {
                x: list.x; y: list.y; width: list.width; height: list.height
                target: list
            }
        }
    }
}
