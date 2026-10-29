import QtQuick
import QtQuick.Dialogs
import ABook

// Hộp chọn file / thư mục của hệ điều hành cho trình tạo sách (pickFiles / pickFolder của studio/data.ts; cùng hộp mà "Thêm sách" dùng): chương TXT, hay một
// file sách (EPUB, DOCX, PDF). Dựng muộn (Loader trong NewSource) - chỉ khi bấm lần đầu. Chọn xong thì `picked(đường dẫn[], thêm vào danh sách?)`.
Item {
    id: root
    property bool append: false
    signal picked(var paths, bool append)
    function chooseFiles(add) { append = add; files.open() }
    function chooseFolder() { append = false; folder.open() }
    FileDialog {
        id: files
        title: "Chọn các chương TXT hay một file sách (EPUB, DOCX, PDF)"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Truyện (*.txt *.epub *.docx *.pdf)", "Tất cả file (*)"]
        onAccepted: root.picked(selectedFiles.map(file => DesktopApi.localPath(file)).filter(path => path !== ""), root.append)
    }
    FolderDialog {
        id: folder
        title: "Chọn thư mục chứa các chương TXT"
        onAccepted: root.picked([DesktopApi.localPath(selectedFolder)], false)
    }
}
