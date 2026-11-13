import "UiStrings.js" as S
import QtQuick
import QtQuick.Dialogs
import ABook

// Hộp chọn file / thư mục của hệ điều hành cho trình tạo sách (pickFiles / pickFolder của studio/data.ts; cùng hộp mà "Thêm sách" dùng): chương TXT, hay một
// file sách (EPUB, DOCX, PDF). Dựng muộn (Loader trong NewSource) - chỉ khi bấm lần đầu. Chọn xong thì `picked(đường dẫn[], thêm vào danh sách?)`.
Item {
    id: root
    property bool append: false
    property string sourceHint: ""
    property bool continuing: false
    signal picked(var paths, bool append)
    function chooseFiles(add) { append = add; files.currentFolder = DesktopApi.pickerFolder(sourceHint); files.open() }
    function chooseFolder() { append = false; folder.currentFolder = DesktopApi.pickerFolder(sourceHint); folder.open() }
    FileDialog {
        id: files
        title: root.continuing ? S.s_continuation_choose : S.s_chon_file_sach_1f25282c
        fileMode: FileDialog.OpenFiles
        nameFilters: [S.s_truyen_txt_epub_docx_pdf_33caae66, S.s_tat_ca_file_05ec85ad]
        onAccepted: root.picked(selectedFiles.map(file => DesktopApi.localPath(file)).filter(path => path !== ""), root.append)
    }
    FolderDialog {
        id: folder
        title: S.s_chon_thu_muc_txt_dd0d140c
        onAccepted: root.picked([DesktopApi.localPath(selectedFolder)], false)
    }
}
