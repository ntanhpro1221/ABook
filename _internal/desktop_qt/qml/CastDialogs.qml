import QtQuick
import ABook

// Các hộp của tab Nhân vật, đặt MỘT lần ở Main.qml (như EditBookRename): trang sách phát `castRequested(loại, dữ liệu)` rồi Main gọi begin(). Mỗi hộp là một lớp
// của ngăn xếp Back (Modal), phủ cả cửa sổ. loại: "merge" | "rename" | "gender" | "voice" | "narrator" (cùng một hộp giọng).
Item {
    id: root
    anchors.fill: parent
    property var store: null                // Studio: StudioStore của dự án đang mở (lời gọi đi đúng máy); trang sách của máy này để trống
    function begin(kind, data) {
        if (kind === "merge") merge.begin(data)
        else if (kind === "rename") rename.begin(data)
        else if (kind === "gender") gender.begin(data)
        else if (kind === "voice" || kind === "narrator") voice.begin(data)
    }
    CastMerge { id: merge; store: root.store; objectName: "castMergeDialog" }
    CastRename { id: rename; store: root.store; objectName: "castRenameDialog" }
    CastGender { id: gender; store: root.store; objectName: "castGenderDialog" }
    CastVoice { id: voice; store: root.store; objectName: "castVoiceDialog" }
}
