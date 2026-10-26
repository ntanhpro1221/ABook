import QtQuick
import QtQuick.Dialogs
import ABook
Modal {
    id: root
    property var book: ({})
    property string bookTitle: ""
    property string author: ""
    property string savedTitle: ""
    property string savedAuthor: ""
    property bool searching: false
    property bool busy: false
    property bool revert: false
    property string problem: ""
    property string notice: ""
    property int generation: 0
    readonly property bool workshop: Boolean(book.capabilities?.workshop)
    title: searching ? "Tìm ảnh bìa" : "Sửa sách"
    description: searching ? "Bạn chọn ảnh từ các nguồn sách hoặc trên máy." : "Đổi có hiệu lực ngay và chỉ trên máy này - audio và chữ của người làm sách giữ nguyên."
    function begin(data) {
        generation++; book = data; bookTitle = savedTitle = data.title || ""; author = savedAuthor = data.author || ""
        searching = false; busy = false; revert = false; problem = ""; notice = ""; show()
        titleField.forceActiveFocus(Qt.TabFocusReason)
    }
    function mutate(method, suffix, body, message, field) {
        if (busy) return
        busy = true; problem = ""
        const mine = generation, id = book.id || book.bookId
        Api.call(method, "/api/books/" + id + suffix, body, function(data, error) {
            if (mine !== root.generation) return
            root.busy = false
            if (error) { root.problem = error; return }
            root.notice = message
            if (field === "title") root.savedTitle = body.title.trim().replace(/\s+/g," ")
            if (field === "author") root.savedAuthor = data.author ?? body.author.trim().replace(/\s+/g," ")
            Api.editedBook(id)
            Api.call("GET", "/api/listen/books/" + id, null, function(fresh, failure) { if (!failure && mine === root.generation) root.book = fresh })
        })
    }
    function search() { searching = true; coverSearch.begin(book.id || book.bookId, book.title || "") }
    keepOpen: function() {
        if (searching) { coverSearch.cancel(); searching = false; return true }
        if (revert) { revert = false; return true }
        generation++
        return false
    }
    onOpenChanged: if (!open) { generation++; coverSearch.cancel(); images.close() }
    Column {
        width: parent.width; visible: !root.searching; spacing: 16
        SectionBlock {
            width: parent.width; topPadding: 0; title: "Tên sách"
            FormField { id: titleField; objectName: "editTitle"; width: parent.width; label: "Tên sách"; text: root.bookTitle; onTextChanged: root.bookTitle = text; onAccepted: if (saveTitle.enabled) saveTitle.clicked() }
            Button { id: saveTitle; text: "Lưu tên"; enabled: !root.busy && root.bookTitle.trim() !== "" && root.bookTitle.trim() !== root.savedTitle; onClicked: root.mutate("PUT", "/title", {title: root.bookTitle}, "Đã đổi tên sách", "title") }
        }
        SectionBlock {
            width: parent.width; title: "Tác giả"; visible: root.book.stage === "text" && !root.workshop
            FormLabel { width: parent.width; text: "Để trống nếu không rõ tác giả. Hiện ở thư viện, trang sách và trong file sách nói xuất ra."; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
            FormField { id: authorField; objectName: "editAuthor"; width: parent.width; label: "Tác giả"; placeholderText: "Không rõ tác giả"; text: root.author; onTextChanged: root.author = text; onAccepted: if (saveAuthor.enabled) saveAuthor.clicked() }
            Button { id: saveAuthor; text: "Lưu tác giả"; enabled: !root.busy && root.author.trim().replace(/\s+/g," ") !== root.savedAuthor.trim().replace(/\s+/g," "); onClicked: root.mutate("PUT", "/author", {author: root.author}, root.author.trim() ? "Đã đổi tác giả" : "Đã bỏ tên tác giả", "author") }
        }
        SectionBlock {
            width: parent.width; title: "Ảnh bìa"
            Flow {
                width: parent.width; spacing: 16
                Item {
                    width: 112; height: 168
                    CoverView { anchors.fill: parent; title: root.book.title || ""; coverKey: root.book.cover ? (root.book.id || root.book.bookId) + "/" + (root.book.cover.version || 0) : "" }
                }
                Column {
                    spacing: 4
                    Button { text: root.book.cover ? "Đổi ảnh bìa…" : "Chọn ảnh bìa…"; kind: "text"; icon: "image-plus"; enabled: !root.busy; onClicked: images.open() }
                    Button { text: "Tìm bìa…"; kind: "text"; icon: "globe"; enabled: !root.busy; onClicked: root.search() }
                    Button { text: "Bỏ ảnh bìa"; kind: "text"; icon: "trash-2"; visible: Boolean(root.book.cover); enabled: !root.busy; onClicked: root.mutate("DELETE", "/cover", null, "Đã bỏ ảnh bìa - sách dùng bìa vẽ từ tên", "") }
                }
            }
        }
        SectionBlock {
            width: parent.width; title: "Nhạc nền"; fold: "wip"; visible: root.book.stage !== "text"
            FormLabel { width: parent.width; visible: root.workshop; text: "Cuốn này có xưởng - nhạc nền chỉnh đầy đủ (chọn bài, im lặng từng đoạn) ở Studio."; color: Theme.text2 }
            BookMusicSettings { width: parent.width; visible: !root.workshop; bookId: root.book.id || root.book.bookId || "" }
        }
        SectionBlock {
            width: parent.width; title: root.book.stage === "text" ? "Tên chương" : "Tên riêng"
            FormLabel { width: parent.width; text: root.book.stage === "text" ? "Bấm “…” ở dòng chương để đổi tên chương." : "Bấm “…” ở dòng chương để đổi tên chương, “…” ở tab Nhân vật để đổi tên người."; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        }
        SectionBlock {
            width: parent.width; title: "Bỏ mọi thay đổi (" + (root.book.edits || 0) + ")"; visible: !root.workshop && (root.book.edits || 0) > 0
            FormLabel { width: parent.width; text: "Sách trở về đúng như người làm sách đã đóng gói."; color: Theme.text2 }
            Button { text: root.revert ? "Bỏ hết thay đổi" : "Bỏ mọi thay đổi…"; kind: "text"; enabled: !root.busy; onClicked: { if (!root.revert) root.revert = true; else { root.revert = false; root.mutate("DELETE", "/edits", null, "Đã bỏ mọi thay đổi - sách như người làm sách đã đóng gói", "") } } }
            Button { text: "Thôi"; kind: "text"; visible: root.revert; onClicked: root.revert = false }
        }
    }
    Column {
        width: parent.width; visible: root.searching; spacing: 12
        Button { text: "Sửa sách"; icon: "arrow-left"; kind: "text"; onClicked: { coverSearch.cancel(); root.searching = false } }
        CoverSearch {
            id: coverSearch
            width: parent.width
            onChosen: { root.searching = false; root.notice = "Đã đặt ảnh bìa"; Api.editedBook(root.book.id || root.book.bookId); Api.call("GET", "/api/listen/books/" + (root.book.id || root.book.bookId), null, function(data, error) { if (!error && root.open) root.book = data }) }
            onChooseFile: { root.searching = false; images.open() }
        }
    }
    FormLabel { width: parent.width; text: root.problem || root.notice; visible: text !== ""; color: root.problem ? Theme.danger : Theme.success }
    FileDialog {
        id: images
        title: "Chọn ảnh bìa"
        nameFilters: ["Ảnh (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"]
        onAccepted: {
            const image = DesktopApi.imageData(selectedFile)
            if (!image) { root.problem = "Không đọc được file ảnh"; return }
            root.mutate("PUT", "/cover", {image: image}, "Đã đặt ảnh bìa", "")
        }
    }
}
