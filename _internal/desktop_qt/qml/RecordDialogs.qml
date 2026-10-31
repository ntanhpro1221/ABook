import QtQuick
import ABook
import "RecordLogic.js" as Logic

// Hộp và việc của "Hồ sơ nghe" (RecordPicker của listen/BookScreen.tsx), đặt MỘT lần ở Main.qml như CastDialogs: trang sách phát
// `recordRequested(loại, dữ liệu)` rồi Main gọi begin(). loại: "create" | "rename" | "move" | "delete" mở hộp (một lớp của ngăn xếp Back, Modal);
// "activate" chuyển thẳng sang hồ sơ khác (không hộp). Việc đi đúng các đường của web: POST/PUT/DELETE /api/listen/books/<mã>/records[/<hồ sơ>[/activate|move]].
// Cuốn đang nạp trong trình phát thì trình phát theo sang hồ sơ mới (switchRecord của player.tsx): đóng, đổi, rồi nạp lại ở trạng thái dừng
// - riêng "Tạo và nghe từ đầu" phát luôn từ chương đầu. Hộp đóng ngay khi bấm; thành công / lỗi báo bằng lời báo.
// data: {bookId, book (cuốn đầy đủ), dialog ({kind, name}), record (cho "activate")}.
Modal {
    id: root
    objectName: "recordDialog"
    panelWidth: 448
    property string bookId: ""
    property var book: ({})
    property var dialog: null               // {kind, name, target} - giữ nguyên sau khi đóng để chữ không đổi giữa lúc hộp mờ đi
    property string library: "loading"      // loading | ready | failed (cuốn nhận hồ sơ)
    property var options: []
    property int generation: 0
    signal openBook(string id)              // lời báo "Mở cuốn ấy" sau khi chuyển hồ sơ sang cuốn khác
    readonly property var active: Logic.activeRecord(book)
    readonly property int recordCount: (book.records || []).length
    title: dialog ? Logic.dialogTitle(dialog, active) : ""
    description: dialog ? Logic.dialogDescription(dialog, recordCount) : ""
    onClosed: generation++

    function begin(kind, data) {
        if (kind === "activate") { activate(data); return }
        generation++
        bookId = data.bookId; book = data.book
        dialog = Object.assign({}, data.dialog)
        nameField.text = dialog.name || ""
        if (dialog.kind === "move") loadLibrary()
        show()
        if (dialog.kind === "move") picker.forceActiveFocus(Qt.TabFocusReason)
        else if (dialog.kind !== "delete") { nameField.forceActiveFocus(Qt.TabFocusReason); nameField.selectAll() }
    }
    // Mọi cuốn trong thư viện trừ cuốn này; chỉ hỏi thư viện lúc hộp đang mở
    function loadLibrary() {
        const mine = generation
        library = "loading"
        Api.quiet("GET", "/api/listen/library", null, function(data, error) {
            if (mine !== root.generation) return
            if (error || !Array.isArray(data)) { root.library = "failed"; return }
            root.options = Logic.moveTargets(data, root.bookId)
            root.library = "ready"
        })
    }
    function setTarget(id) {
        const found = options.filter(option => option.value === id)[0]
        if (found) dialog = Object.assign({}, dialog, {target: {id: found.value, title: found.label}})
    }
    function submit() {
        if (!dialog || !open || !Logic.canConfirm(dialog)) return
        const kind = dialog.kind
        const typed = Object.assign({}, dialog, {name: nameField.text})
        const spec = Logic.request(bookId, kind, active, typed, null)
        const message = Logic.doneMessage(kind, active, typed, null)
        const target = typed.target
        const opens = kind === "move" ? {label: "Mở cuốn ấy", run: function() { root.openBook(target.id) }} : null
        root.dismiss()
        perform(bookId, book, spec, message, opens, kind === "create", kind !== "rename")
    }
    function activate(data) {
        const record = data.record
        perform(data.bookId, data.book, Logic.request(data.bookId, "activate", null, null, record), Logic.doneMessage("activate", null, null, record), null, false, true)
    }
    // Việc ghi hồ sơ. `follow`: cuốn đang nạp trong trình phát thì đóng nó trước, đổi, rồi nạp lại ở trạng thái dừng; `startOver`: phát từ chương đầu.
    function perform(id, full, spec, message, action, startOver, follow) {
        const loaded = follow && Player.loaded && Player.bookId === id
        if (loaded) Player.close()
        Api.quiet(spec.method, spec.path, spec.body, function(data, error) {
            if (error) { Api.notice = error; return }
            Api.editedBook(id)
            if (startOver) {
                const first = Logic.firstPlayable(full.chapters)
                if (first) Player.open(id, first.id, 0, true)
            } else if (loaded) Player.open(id, -1, -1, false)
            Api.toast(message, action ? {action: action} : undefined)
        })
    }

    Column {
        width: parent.width
        spacing: 12
        // Chọn cuốn nhận hồ sơ: đang mở thư viện / chưa có cuốn nào khác / ô chọn, mờ qua tại chỗ
        Collapse {
            width: parent.width
            open: root.dialog !== null && root.dialog.kind === "move"
            Column {
                width: parent.width
                Text {
                    objectName: "recordLoading"
                    visible: root.library === "loading"
                    width: parent.width
                    text: "Đang mở thư viện…"
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Text {
                    objectName: "recordNoOthers"
                    visible: root.library !== "loading" && root.options.length === 0
                    width: parent.width
                    text: "Thư viện chưa có cuốn nào khác."
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Select {
                    id: picker
                    objectName: "recordTarget"
                    visible: root.library === "ready" && root.options.length > 0
                    width: parent.width
                    label: "Chuyển sang cuốn"
                    placeholder: "Chọn cuốn…"
                    options: root.options
                    value: root.dialog && root.dialog.target ? root.dialog.target.id : ""
                    onPicked: value => root.setTarget(value)
                }
            }
        }
        Collapse {
            width: parent.width
            open: root.dialog !== null && (root.dialog.kind === "create" || root.dialog.kind === "rename")
            FormField {
                id: nameField
                objectName: "recordName"
                width: parent.width
                label: "Tên hồ sơ"
                placeholderText: "Tên hồ sơ"
                onTextChanged: if (text.length > 60) text = text.slice(0, 60)
                onAccepted: root.submit()
            }
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "recordCancel"; text: "Huỷ"; kind: "ghost"; onClicked: root.close() }
            Button {
                objectName: "recordConfirm"
                text: root.dialog ? Logic.confirmLabel(root.dialog.kind) : ""
                kind: root.dialog && root.dialog.kind === "delete" ? "danger" : "primary"
                enabled: root.dialog !== null && Logic.canConfirm(Object.assign({}, root.dialog, {name: nameField.text}))
                onActivated: root.submit()
            }
        }
    ]
}
