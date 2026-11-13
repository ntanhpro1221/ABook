import "UiStrings.js" as S
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
    title: searching ? S.s_tim_anh_bia_9825b3d1 : S.s_sua_sach_79fb71d2
    description: searching ? S.s_ban_chon_anh_tu_cac_nguon_sach_hoac_tren_m_ca23c898 : Logic.editDescription(book, computer)

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
        call("renaming", "PUT", "/title", {title: titleDraft}, function() { root.done(S.s_da_doi_ten_sach_d9618322) }, S.s_chua_doi_duoc_ten_sach_d845e696)
    }
    function saveAuthor() {
        if (!Logic.authorSaveable(authorDraft, book.author)) return
        call("savingAuthor", "PUT", "/author", {author: authorDraft}, function(saved) { root.done(saved.author ? S.s_da_doi_tac_gia_cc6c70a5 : S.s_da_bo_ten_tac_gia_538a5212) }, S.s_chua_doi_duoc_tac_gia_32e393fb)
    }
    function setCoverImage(image) {
        call("settingCover", "PUT", "/cover", {image: image}, function() { root.done(S.s_da_dat_anh_bia_90470364) }, S.s_chua_dat_duoc_anh_bia_a4afb9fa)
    }
    function removeCover() {
        call("removingCover", "DELETE", "/cover", null, function() { root.done(S.s_da_bo_anh_bia_sach_dung_bia_ve_tu_ten_f562bcab) }, S.s_chua_bo_duoc_anh_bia_a4173b5d)
    }
    function revertAll() {
        call("reverting", "DELETE", "/edits", null, function() {
            root.cancelRevert()
            root.done(S.s_da_bo_moi_thay_doi_sach_nhu_nguoi_lam_sach_eecea191)
        }, S.s_chua_bo_duoc_thay_doi_e73f2d58)
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
                        title: S.s_ten_sach_d54846eb
                        first: true
                        Row {
                            width: parent.width
                            spacing: 8
                            FormField {
                                id: titleField
                                objectName: "editTitle"
                                width: parent.width - saveTitleButton.width - 8
                                label: S.s_ten_sach_d54846eb
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
                                text: S.s_luu_ten_0b3ef54a
                                busy: root.renaming
                                enabled: root.titleDraft.trim() !== "" && root.titleDraft.trim() !== root.book.title
                                onActivated: root.saveTitle()
                            }
                        }
                    }
                    // Chỉ sách chữ (nhập từ file): sách Studio không có chỗ áp tác giả
                    EditBookSection {
                        width: parent.width
                        title: S.s_tac_gia_0ec4731b
                        hint: S.s_de_trong_neu_khong_ro_tac_gia_hien_o_thu_v_04875479
                        shown: root.textBook && !root.workshop
                        Row {
                            width: parent.width
                            spacing: 8
                            FormField {
                                id: authorField
                                objectName: "editAuthor"
                                width: parent.width - saveAuthorButton.width - 8
                                label: S.s_tac_gia_0ec4731b
                                placeholderText: S.s_khong_ro_tac_gia_baaa8118
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
                                text: S.s_luu_tac_gia_cd5c8008
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
                        title: S.s_anh_bia_f224644d
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
                                    text: root.book.cover ? S.s_doi_anh_bia_178aa3bf : S.s_chon_anh_bia_a6c0a477
                                    icon: "image-plus"
                                    kind: "ghost"
                                    enabled: !root.busy
                                    onClicked: images.open()
                                }
                                Button {
                                    id: findCover
                                    objectName: "editFindCover"
                                    text: S.s_tim_bia_6db18516
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
                                        text: S.s_bo_anh_bia_696c6692
                                        icon: "trash"
                                        kind: "ghost"
                                        enabled: !root.busy
                                        onClicked: root.removeCover()
                                    }
                                }
                                Collapse {
                                    width: parent.width
                                    open: root.settingCover
                                    EditBookSkeleton { width: 160; count: 1; label: S.s_dang_dat_anh_bia_f4a60e45 }
                                }
                            }
                        }
                    }
                    EditBookSection {
                        width: parent.width
                        title: S.s_nhac_nen_271fb292
                        fold: "edit-book.music"
                        shown: !root.textBook
                        Flow {
                            width: parent.width
                            Reveal { shown: root.workshop }
                            height: visible ? implicitHeight : 0
                            spacing: 12
                            Text {
                                width: Math.min(implicitWidth, parent.width)
                                text: S.s_cuon_nay_co_xuong_nhac_nen_chinh_day_du_ch_b296f56d
                                color: Theme.text2
                                wrapMode: Text.Wrap
                                font.pixelSize: Theme.sizeBodySmall
                            }
                            Button {
                                Reveal { shown: root.canOpenStudio }
                                text: S.s_mo_tab_nhac_nen_117e60f2
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
                        title: root.textBook ? S.s_ten_chuong_9edb6c28 : S.s_ten_rieng_8a9cd50f
                        hint: root.textBook ? S.s_bam_o_dong_chuong_de_doi_ten_chuong_d2fb9984 : S.s_bam_o_dong_chuong_de_doi_ten_chuong_o_tab_733e1523
                    }
                    EditBookSection {
                        width: parent.width
                        title: S.s_cach_doc_ten_1c46e75d
                        hint: S.s_day_cach_doc_tu_thuong_la_ten_rieng_chu_gi_69023eb0
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
                        title: S.s_bo_moi_thay_doi_dd1a050a + (root.book.edits || 0) + ")"
                        hint: S.s_sach_tro_ve_dung_nhu_nguoi_lam_sach_da_don_f3a48d43
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
                                    text: S.s_bo_moi_thay_doi_bf843dbb
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
                                        text: S.s_bo_het_thay_doi_b55603a1
                                        kind: "danger"
                                        busy: root.reverting
                                        onActivated: root.revertAll()
                                    }
                                    Button {
                                        objectName: "editRevertCancel"
                                        text: S.s_thoi_e68f9e88
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
                Accessible.name: S.s_sua_sach_79fb71d2
                onClicked: root.leaveSearch()
                Row {
                    id: backRow
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    Icon { anchors.verticalCenter: parent.verticalCenter; name: "arrow-left"; size: 16; color: backToEdit.hovered ? Theme.text : Theme.text2 }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: S.s_sua_sach_79fb71d2; color: backToEdit.hovered ? Theme.text : Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                }
            }
            Item { width: 1; height: 12 }
            CoverSearch {
                id: coverSearch
                objectName: "coverSearchPanel"
                width: parent.width
                onChosen: { root.leaveSearch(false); root.done(S.s_da_dat_anh_bia_90470364) }
                onChooseFile: { root.leaveSearch(false); images.open() }
            }
        }
    }

    FileDialog {
        id: images
        title: S.s_chon_anh_bia_207ac182
        nameFilters: [S.s_anh_png_jpg_jpeg_webp_gif_bmp_8ce57f5a]
        onAccepted: {
            const image = DesktopApi.imageData(selectedFile)
            if (!image) { Api.notice = Logic.toastText(S.s_chua_dat_duoc_anh_bia_a4afb9fa, S.s_chua_doc_duoc_file_anh_09736d91); return }
            root.setCoverImage(image)
        }
    }
}
