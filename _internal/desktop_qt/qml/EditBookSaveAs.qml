import QtQuick
import QtQuick.Dialogs
import ABook
import "EditBookLogic.js" as Logic

// "Lưu thay đổi" và "Lưu thành…" (useSaveBook + SaveAsDialog của listen/EditBook.tsx): đóng cuốn (kèm thay đổi của người nghe) thành file mới, GIỮ loại
// file cuốn đã đến (`.abookproj` mang theo xưởng của nó, `.abook` thì không). `POST /api/books/<mã>/save {target?, as?}`. Máy tính ghi vào thư
// mục xuất (hay thư mục đã chọn). `quick(book)` = "Lưu thay đổi" (không hộp); `begin(book)` = hộp "Lưu thành…".
Modal {
    id: root
    panelWidth: 448
    property var book: ({})
    property string kind: ""                // đặt ở begin(): ChoiceRow chỉ vẽ gạch chân khi chỉ số đổi sau lúc dựng
    property string folder: ""
    property bool saving: false
    title: "Lưu thành…"
    description: "Lưu cuốn này kèm những thay đổi của bạn thành một file mới. File gốc không bị đụng tới."

    function begin(data) {
        book = data; saving = false; folder = ""
        kind = data.projectFile ? "abookproj" : "abook"
        show()
    }
    // Lưu rồi báo (cùng lời với toastDone của web); `done` gọi sau khi xong thành công
    function save(data, options, done) {
        if (saving) return
        saving = true
        Api.call("POST", "/api/books/" + (data.id || data.bookId) + "/save", options, function(result, error) {
            root.saving = false
            if (error) Api.notice = Logic.toastText("Chưa lưu được file sách", error)
            // Không có thay đổi nào vẫn lưu được, nhưng file giống hệt bản gốc: nói điều đó thành cảnh báo cùng dòng.
            else {
                // "Mở thư mục": mở thư mục chứa file vừa lưu (máy chủ mở bằng trình quản lý file của máy)
                const folder = result.folder
                Api.toast(Logic.toastText("Đã lưu file sách", result.edits ? "" : "Chưa có thay đổi nào - file giống bản gốc."), {
                    duration: 8000,
                    action: folder ? {label: "Mở thư mục", run: function() { Api.quiet("POST", "/api/reveal-export", {folder: folder}) }} : null
                })
            }
            if (done) done()      // như web: hộp đóng sau khi lưu, thành công hay không
        })
    }
    function quick(data) { save(data, {}) }
    function submit() {
        const options = {as: kind}
        if (folder) options.target = folder
        save(book, options, function() { root.dismiss() })
    }
    FolderDialog {
        id: folders
        title: "Chọn nơi lưu"
        onAccepted: root.folder = DesktopApi.localPath(selectedFolder)
    }
    Column {
        width: parent.width
        spacing: 12
        ChoiceRow {
            objectName: "saveKind"
            label: "Loại file"
            width: parent.width
            options: [{value: "abook", label: "Sách nghe (.abook)"}, {value: "abookproj", label: "Dự án (.abookproj)"}]
            value: root.kind
            onPicked: value => root.kind = value
        }
        Text {
            width: parent.width
            wrapMode: Text.Wrap
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
            text: root.kind === "abookproj"
                  ? (root.book.projectFile && root.book.projectFile.workshop === "present"
                     ? "Cả dự án kèm thay đổi của bạn; mở bằng Studio để áp."
                     : "Chỉ có phần nghe và thay đổi của bạn. Studio dựng lại được dự án từ file này.")
                  : "Sách nghe mở được bằng ABook trên máy tính và điện thoại, mang theo tên, bìa, tên nhân vật, tên chương, nhạc bạn đã sửa"
                    + (root.book.wishes ? ", cùng " + root.book.wishes + " việc đang chờ máy làm sách (chưa làm gì trong giọng đọc)" : "") + "."
        }
        Flow {
            width: parent.width
            spacing: 8
            Button { text: "Chọn thư mục…"; kind: "ghost"; size: "sm"; onClicked: folders.open() }
            Text {
                width: Math.min(implicitWidth, parent.width)
                height: 40
                verticalAlignment: Text.AlignVCenter
                text: root.folder || "Mặc định: thư mục Đã xuất"
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        HintText {
            width: parent.width
            color: Theme.text3
            text: "Đã có file cùng tên trong thư mục ấy thì file mới thêm số (2) ở cuối tên - không đè lên file cũ."
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "saveCancel"; text: "Thôi"; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "saveGo"; text: "Lưu"; icon: "file-down"; busy: root.saving; onActivated: root.submit() }
        }
    ]
}
