import "UiStrings.js" as S
import QtQuick
import QtQuick.Dialogs
import ABook

// Hộp chọn ảnh bìa của hệ điều hành (input type=file của CoverEditor.tsx). Dựng muộn (Loader trong CoverEditor) - chỉ khi bấm lần đầu.
Item {
    id: root
    signal picked(url file)
    function choose() { dialog.open() }
    FileDialog {
        id: dialog
        title: S.s_chon_anh_bia_207ac182
        nameFilters: [S.s_anh_png_jpg_jpeg_webp_gif_bmp_8ce57f5a]
        onAccepted: root.picked(selectedFile)
    }
}
