import "UiStrings.js" as S
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
    title: S.s_luu_thanh_13374e92
    description: S.s_luu_cuon_nay_kem_nhung_thay_doi_cua_ban_th_ab80dd34

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
            if (error) Api.notice = Logic.toastText(S.s_chua_luu_duoc_file_sach_964ff92c, error)
            // Không có thay đổi nào vẫn lưu được, nhưng file giống hệt bản gốc: nói điều đó thành cảnh báo cùng dòng.
            else {
                // "Mở thư mục": mở thư mục chứa file vừa lưu (máy chủ mở bằng trình quản lý file của máy)
                const folder = result.folder
                Api.toast(Logic.toastText(S.s_da_luu_file_sach_baab68d2, result.edits ? "" : S.s_chua_co_thay_doi_nao_file_giong_ban_goc_f109003f), {
                    duration: 8000,
                    action: folder ? {label: S.s_mo_thu_muc_4bf5b127, run: function() { Api.quiet("POST", "/api/reveal-export", {folder: folder}) }} : null
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
        title: S.s_chon_noi_luu_2965936c
        onAccepted: root.folder = DesktopApi.localPath(selectedFolder)
    }
    Column {
        width: parent.width
        spacing: 12
        ChoiceRow {
            objectName: "saveKind"
            label: S.s_loai_file_74f0a115
            width: parent.width
            options: [{value: "abook", label: S.s_sach_nghe_abook_cb8e508e}, {value: "abookproj", label: S.s_du_an_abookproj_71e42c40}]
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
                     ? S.s_ca_du_an_kem_thay_doi_cua_ban_mo_bang_stud_f33ca39c
                     : S.s_chi_co_phan_nghe_va_thay_doi_cua_ban_studi_09cd637e)
                  : S.s_sach_nghe_mo_duoc_bang_abook_tren_may_tinh_ef9eba65
                    + (root.book.wishes ? S.s_cung_b54371b6 + root.book.wishes + S.s_viec_dang_cho_may_lam_sach_chua_lam_gi_tro_367c1281 : "") + "."
        }
        Flow {
            width: parent.width
            spacing: 8
            Button { text: S.s_chon_thu_muc_1fe47e38; kind: "ghost"; size: "sm"; onClicked: folders.open() }
            Text {
                width: Math.min(implicitWidth, parent.width)
                height: 40
                verticalAlignment: Text.AlignVCenter
                text: root.folder || S.s_mac_dinh_thu_muc_da_xuat_65fabfd2
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        HintText {
            width: parent.width
            color: Theme.text3
            text: S.s_da_co_file_cung_ten_trong_thu_muc_ay_thi_f_ca6cb2a9
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "saveCancel"; text: S.s_thoi_e68f9e88; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "saveGo"; text: S.s_luu_e91f26c0; icon: "file-down"; busy: root.saving; onActivated: root.submit() }
        }
    ]
}
