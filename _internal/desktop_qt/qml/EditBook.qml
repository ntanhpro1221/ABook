import QtQuick
import QtQuick.Dialogs
import ABook
import "EditBookLogic.js" as Logic

// Hộp "Sửa sách" (EditBookDialog của listen/EditBook.tsx), "áp ngay" (docs/EDITING.md): tên sách, tác giả, ảnh bìa, nhạc nền, tên chương / tên riêng,
// cách đọc tên, bỏ mọi thay đổi. Lệnh đi tới `/api/books/<mã>/...`. Lưu một ô để hộp ở nguyên và chỉ nạp lại ô ấy - chữ gõ dở ở ô kia không mất.
// "Tìm bìa" là MỘT BƯỚC của hộp (mục chính khép, bước tìm mở, nút "Sửa sách" quay lại), không phải hộp thứ hai đè lên; bước ấy và bước hỏi lại
// "Bỏ mọi thay đổi…" mỗi bước một lớp Back: Back lùi về hộp, Back kế đóng hộp và trả tiêu điểm về chỗ đã mở.
Modal {
    id: root
    readonly property bool expanded: Theme.widthClass(width) >= 2 && !searching
    property real wideT: expanded ? 1 : 0
    Behavior on wideT {
        NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
    }
    panelWidth: expanded ? Math.min(width - 2 * Theme.margin, 1160) : 560
    property var book: ({})
    property string titleDraft: ""
    property string authorDraft: ""
    property string computer: ""                // Studio từ xa: tên máy tính đang giữ sách
    property bool canOpenStudio: false          // máy tính, cuốn có xưởng: nút "Mở tab Nhạc nền"
    property bool searching: false
    property bool confirmRevert: false
    property bool renaming: false
    property bool savingAuthor: false
    property bool settingCover: false
    property bool removingCover: false
    property bool reverting: false
    property int generation: 0
    signal openStudio()
    readonly property string bookId: book.id || book.bookId || ""
    readonly property bool workshop: Boolean(book.capabilities && book.capabilities.workshop)
    readonly property bool textBook: book.stage === "text"
    readonly property bool busy: renaming || savingAuthor || settingCover || removingCover || coverSearch.choosing
    readonly property string shownTitle: book.title || ""
    readonly property string shownAuthor: book.author || ""
    // Tên hay tác giả của sách đổi (lưu xong, nạp lại): chỉ nạp lại ô ấy
    // Chữ trong ô theo bản nháp kể cả khi ô đã bị gán tay (gán tay làm đứt ràng buộc `text:`)
    onTitleDraftChanged: if (titleField.text !== titleDraft) titleField.text = titleDraft
    onAuthorDraftChanged: if (authorField.text !== authorDraft) authorField.text = authorDraft
    onShownTitleChanged: titleDraft = shownTitle
    onShownAuthorChanged: authorDraft = shownAuthor
    title: searching ? "Tìm ảnh bìa" : "Sửa sách"
    description: searching ? "Bạn chọn ảnh từ các nguồn sách hoặc trên máy." : Logic.editDescription(book, computer)

    function begin(data) {
        generation++
        coverSearch.cancel()
        dropLayers()
        book = data
        titleDraft = data.title || ""
        authorDraft = data.author || ""
        searching = false; confirmRevert = false
        renaming = false; savingAuthor = false; settingCover = false; removingCover = false; reverting = false
        show()
        titleField.forceActiveFocus(Qt.TabFocusReason)
    }

    // ---- lớp Back của hai bước con ----
    QtObject { id: searchLayer; property bool on: false; function close() { root.leaveSearch() } }
    QtObject { id: revertLayer; property bool on: false; function close() { root.cancelRevert() } }
    function dropLayers() {
        if (searchLayer.on) { searchLayer.on = false; Nav.closedLayer(searchLayer) }
        if (revertLayer.on) { revertLayer.on = false; Nav.closedLayer(revertLayer) }
    }
    function search() {
        if (searching) return
        searching = true
        searchLayer.on = true; Nav.openLayer(searchLayer)
        coverSearch.begin(bookId, Logic.seriesName(book.title))
    }
    function leaveSearch(restoreFocus) {
        if (!searching) return
        coverSearch.cancel()
        searching = false
        if (searchLayer.on) { searchLayer.on = false; Nav.closedLayer(searchLayer) }
        if (restoreFocus !== false) findCover.forceActiveFocus(Qt.BacktabFocusReason)
    }
    function askRevert() {
        confirmRevert = true
        revertLayer.on = true; Nav.openLayer(revertLayer)
    }
    function cancelRevert() {
        confirmRevert = false
        if (revertLayer.on) { revertLayer.on = false; Nav.closedLayer(revertLayer) }
        revertButton.forceActiveFocus(Qt.BacktabFocusReason)
    }
    onClosed: { generation++; coverSearch.cancel(); searching = false; confirmRevert = false; dropLayers() }

    // ---- lệnh ----
    // Làm mới mọi chỗ hiện thứ vừa sửa (refreshAfterEdit): thư viện, trang sách, và bản sách của hộp này
    function refresh() {
        const id = bookId
        Api.editedBook(id)
        Api.call("GET", "/api/listen/books/" + id, null, function(fresh, error) {
            if (!error && root.open && (fresh.id || id) === id) root.book = fresh
        })
    }
    function done(message) { refresh(); Api.notice = message }
    // Một lệnh sửa: `flag` là cờ bận của riêng nó; lời đáp về sau khi hộp đã đổi sang cuốn khác / đã đóng thì bỏ
    function call(flag, method, suffix, body, success, failure) {
        if (root[flag]) return
        root[flag] = true
        const mine = generation
        Api.call(method, "/api/books/" + bookId + suffix, body, function(data, error) {
            if (mine !== root.generation) return
            root[flag] = false
            if (error) { Api.notice = Logic.toastText(failure, error); return }
            success(data)
        })
    }
    function saveTitle() {
        if (!titleDraft.trim() || titleDraft.trim() === book.title) return
        call("renaming", "PUT", "/title", {title: titleDraft}, function() { root.done("Đã đổi tên sách") }, "Chưa đổi được tên sách")
    }
    function saveAuthor() {
        if (!Logic.authorSaveable(authorDraft, book.author)) return
        call("savingAuthor", "PUT", "/author", {author: authorDraft}, function(saved) { root.done(saved.author ? "Đã đổi tác giả" : "Đã bỏ tên tác giả") }, "Chưa đổi được tác giả")
    }
    function setCoverImage(image) {
        call("settingCover", "PUT", "/cover", {image: image}, function() { root.done("Đã đặt ảnh bìa") }, "Chưa đặt được ảnh bìa")
    }
    function removeCover() {
        call("removingCover", "DELETE", "/cover", null, function() { root.done("Đã bỏ ảnh bìa - sách dùng bìa vẽ từ tên") }, "Chưa bỏ được ảnh bìa")
    }
    function revertAll() {
        call("reverting", "DELETE", "/edits", null, function() {
            root.cancelRevert()
            root.done("Đã bỏ mọi thay đổi - sách như người làm sách đã đóng gói")
        }, "Chưa bỏ được thay đổi")
    }

    // ---- hai trang: mục chính | bước tìm bìa; trang khép thì cao 0, trang mở lớn dần ----
    Column {
        width: parent.width
        Collapse {
            id: mainPage
            width: parent.width
            open: !root.searching
            Item {
                id: editLayout
                width: parent.width
                implicitHeight: Math.max(sections.height, extras.y + extras.height)
                height: implicitHeight
                Column {
                    id: sections
                    objectName: "editDetailsColumn"
                    width: parent.width + ((parent.width - Theme.s32) / 2 - parent.width) * Math.min(1, root.wideT * 2)

                    EditBookSection {
                        width: parent.width
                        title: "Tên sách"
                        first: true
                        Row {
                            width: parent.width
                            spacing: 8
                            FormField {
                                id: titleField
                                objectName: "editTitle"
                                width: parent.width - saveTitleButton.width - 8
                                label: "Tên sách"
                                text: root.titleDraft
                                onTextChanged: {
                                    if (text.length > 160) { text = text.slice(0, 160); return }
                                    root.titleDraft = text
                                }
                                onAccepted: root.saveTitle()
                            }
                            Button {
                                id: saveTitleButton
                                objectName: "editSaveTitle"
                                text: "Lưu tên"
                                busy: root.renaming
                                enabled: root.titleDraft.trim() !== "" && root.titleDraft.trim() !== root.book.title
                                onActivated: root.saveTitle()
                            }
                        }
                    }
                    // Chỉ sách chữ (nhập từ file): sách Studio không có chỗ áp tác giả
                    EditBookSection {
                        width: parent.width
                        title: "Tác giả"
                        hint: "Để trống nếu không rõ tác giả. Hiện ở thư viện, trang sách và trong file sách nói xuất ra."
                        shown: root.textBook && !root.workshop
                        Row {
                            width: parent.width
                            spacing: 8
                            FormField {
                                id: authorField
                                objectName: "editAuthor"
                                width: parent.width - saveAuthorButton.width - 8
                                label: "Tác giả"
                                placeholderText: "Không rõ tác giả"
                                text: root.authorDraft
                                onTextChanged: {
                                    if (text.length > 160) { text = text.slice(0, 160); return }
                                    root.authorDraft = text
                                }
                                onAccepted: root.saveAuthor()
                            }
                            Button {
                                id: saveAuthorButton
                                objectName: "editSaveAuthor"
                                text: "Lưu tác giả"
                                busy: root.savingAuthor
                                enabled: Logic.authorSaveable(root.authorDraft, root.book.author)
                                onActivated: root.saveAuthor()
                            }
                        }
                    }
                }
                Column {
                    id: extras
                    objectName: "editExtrasColumn"
                    x: (sections.width + Theme.s32) * Math.min(1, root.wideT * 2)
                    y: sections.height * (1 - Math.max(0, root.wideT * 2 - 1))
                    width: parent.width - x
                    EditBookSection {
                        width: parent.width
                        title: "Ảnh bìa"
                        separator: 1 - root.wideT
                        // Bìa 112 + cột nút; hẹp thì cột nút xuống dưới bìa thay vì tràn khỏi hộp
                        Flow {
                            width: parent.width
                            spacing: 16
                            CoverView {
                                width: 112
                                height: 168
                                title: root.book.title || ""
                                coverKey: root.book.cover ? root.bookId + "/" + (root.book.cover.version || 0) : ""
                            }
                            Column {
                                width: Math.min(implicitWidth, root.bodyWidth)
                                spacing: 4
                                Button {
                                    objectName: "editPickCover"
                                    text: root.book.cover ? "Đổi ảnh bìa…" : "Chọn ảnh bìa…"
                                    icon: "image-plus"
                                    kind: "ghost"
                                    enabled: !root.busy
                                    onClicked: images.open()
                                }
                                Button {
                                    id: findCover
                                    objectName: "editFindCover"
                                    text: "Tìm bìa…"
                                    icon: "globe"
                                    kind: "ghost"
                                    enabled: !root.busy
                                    onClicked: root.search()
                                }
                                Collapse {
                                    width: parent.width
                                    open: Boolean(root.book.cover)
                                    Button {
                                        objectName: "editRemoveCover"
                                        text: "Bỏ ảnh bìa"
                                        icon: "trash-2"
                                        kind: "ghost"
                                        enabled: !root.busy
                                        onClicked: root.removeCover()
                                    }
                                }
                                Collapse {
                                    width: parent.width
                                    open: root.settingCover
                                    EditBookSkeleton { width: 160; count: 1; label: "Đang đặt ảnh bìa" }
                                }
                            }
                        }
                    }
                    EditBookSection {
                        width: parent.width
                        title: "Nhạc nền"
                        fold: "edit-book.music"
                        shown: !root.textBook
                        Flow {
                            width: parent.width
                            visible: root.workshop
                            height: visible ? implicitHeight : 0
                            spacing: 12
                            Text {
                                width: Math.min(implicitWidth, parent.width)
                                text: "Cuốn này có xưởng - nhạc nền chỉnh đầy đủ (chọn bài, im lặng từng đoạn) ở Studio."
                                color: Theme.text2
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.sizeBodySmall
                            }
                            Button {
                                visible: root.canOpenStudio
                                text: "Mở tab Nhạc nền"
                                icon: "eighth-note"
                                kind: "ghost"
                                size: "sm"
                                onClicked: root.openStudio()
                            }
                        }
                        Loader {
                            width: parent.width
                            active: root.visible && !root.workshop && !root.textBook
                            sourceComponent: BookMusicSettings { bookId: root.bookId }
                        }
                    }
                    EditBookSection {
                        width: parent.width
                        title: root.textBook ? "Tên chương" : "Tên riêng"
                        hint: root.textBook ? "Bấm “…” ở dòng chương để đổi tên chương." : "Bấm “…” ở dòng chương để đổi tên chương, “…” ở tab Nhân vật để đổi tên người."
                    }
                    EditBookSection {
                        width: parent.width
                        title: "Cách đọc tên"
                        hint: "Dạy cách đọc từ (thường là tên riêng). Chữ giữ nguyên."
                        fold: "edit-book.readings"
                        shown: root.textBook && !root.workshop
                        Loader {
                            width: parent.width
                            active: root.visible && root.textBook && !root.workshop
                            sourceComponent: EditBookReadings { bookId: root.bookId }
                        }
                    }
                    EditBookSection {
                        width: parent.width
                        title: "Bỏ mọi thay đổi (" + (root.book.edits || 0) + ")"
                        hint: "Sách trở về đúng như người làm sách đã đóng gói."
                        shown: !root.workshop && (root.book.edits || 0) > 0
                        Item {
                            width: parent.width
                            height: revertAsk.height + revertSure.height
                            Collapse {
                                id: revertAsk
                                width: parent.width
                                open: !root.confirmRevert
                                Button {
                                    id: revertButton
                                    objectName: "editRevert"
                                    x: -14
                                    text: "Bỏ mọi thay đổi…"
                                    kind: "ghost"
                                    onClicked: root.askRevert()
                                }
                            }
                            Collapse {
                                id: revertSure
                                y: revertAsk.height
                                width: parent.width
                                open: root.confirmRevert
                                Row {
                                    spacing: 8
                                    Button {
                                        objectName: "editRevertConfirm"
                                        text: "Bỏ hết thay đổi"
                                        kind: "danger"
                                        busy: root.reverting
                                        onActivated: root.revertAll()
                                    }
                                    Button {
                                        objectName: "editRevertCancel"
                                        text: "Thôi"
                                        kind: "ghost"
                                        onClicked: root.cancelRevert()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        Collapse {
            id: searchPage
            width: parent.width
            open: root.searching
            Interactive {
                id: backToEdit
                objectName: "coverBack"
                height: 40
                width: backRow.width
                Accessible.role: Accessible.Button
                Accessible.name: "Sửa sách"
                onClicked: root.leaveSearch()
                Row {
                    id: backRow
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    Icon { anchors.verticalCenter: parent.verticalCenter; name: "arrow-left"; size: 16; color: backToEdit.hovered ? Theme.text : Theme.text2 }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: "Sửa sách"; color: backToEdit.hovered ? Theme.text : Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                }
            }
            Item { width: 1; height: 12 }
            CoverSearch {
                id: coverSearch
                objectName: "coverSearchPanel"
                width: parent.width
                onChosen: { root.leaveSearch(false); root.done("Đã đặt ảnh bìa") }
                onChooseFile: { root.leaveSearch(false); images.open() }
            }
        }
    }

    FileDialog {
        id: images
        title: "Chọn ảnh bìa"
        nameFilters: ["Ảnh (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"]
        onAccepted: {
            const image = DesktopApi.imageData(selectedFile)
            if (!image) { Api.notice = Logic.toastText("Chưa đặt được ảnh bìa", "Không đọc được file ảnh"); return }
            root.setCoverImage(image)
        }
    }
}
