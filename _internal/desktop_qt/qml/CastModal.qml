import "UiStrings.js" as S
import QtQuick
import ABook
import "EditBookLogic.js" as Logic

// Nền chung của các hộp ở tab Nhân vật (Gộp, Đổi tên, Đổi giới tính, Giọng): sách đang sửa, đang lưu, lỗi dạng "tiêu đề + lý do", và "Hoàn tác" một lần
// đổi giọng / giới (undoAction của studio/decisions.ts: POST .../voice với withdraw, 15 giây). Mỗi hộp là một lớp Back của chính nó (Modal).
Modal {
    id: root
    property string bookId: ""
    property bool saving: false
    // Studio: `store` đưa mọi lời gọi qua StudioStore (cả máy tính ghép, /api/peers/<mã>/studio); không có thì là trang sách của máy này (Api)
    property var store: null
    property int generation: 0
    readonly property int undoMs: 15000
    onClosed: generation++

    function ask(method, path, body, done) { return store ? store.quiet(method, path, body, done) : Api.quiet(method, path, body, done) }
    function media(url) { return store ? store.path(url) : url }
    function fail(title, error) { Api.notice = Logic.toastText(title, error) }
    // Lần ghi xong: thư viện + trang sách + dàn nhân vật đọc lại (Api.edited)
    function saved(id) { const book = id || bookId; if (store) store.editedCast(book); else Api.editedBook(book) }
    // Lời báo "Hoàn tác" cho lần đổi giọng / giới vừa ghi; hoàn tác xong thì lời báo nói đúng điều đã xảy ra
    function offerUndo(text, character, requestedAt, message) {
        const book = bookId
        Api.toast(text, {duration: undoMs, action: {label: S.s_hoan_tac_e72ff675, run: function() {
            root.ask("POST", "/api/books/" + book + "/voice", {character: character, requestedAt: requestedAt, keep: false, withdraw: true}, function(data, error) {
                if (error) { Api.notice = Logic.toastText(S.s_chua_hoan_tac_duoc_164b754b, error); return }
                root.saved(book)
                Api.notice = data && data.restored ? S.s_da_hoan_tac_may_doc_lai_theo_cach_cu_15e82a15 : message ? S.s_da_hoan_tac_fd822d19 + message : S.s_da_hoan_tac_2ef55fca
            })
        }}})
    }
}
