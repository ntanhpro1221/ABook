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
        title: "Chọn ảnh bìa"
        nameFilters: ["Ảnh (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"]
        onAccepted: root.picked(selectedFile)
    }
}
