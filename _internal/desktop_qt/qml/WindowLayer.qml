import QtQuick

// Gốc chung của mọi lớp nổi (Modal, Popover). `z` chỉ xếp hạng giữa các anh em cùng cha: lớp khai báo sâu trong một màn (hay đứng trước trang
// trong cùng một khung) sẽ bị phần còn lại của trang vẽ đè lên, kể cả khi z của nó lớn. Vì vậy mỗi lớp tự dời mình lên gốc của cửa sổ
// (Window.contentItem) ngay khi có cửa sổ: ở đó z là thật - trên mọi màn, thanh bên và dải tiêu đề của Main, dưới lời báo (90) và chú thích (100).
// Chỗ khai báo chỉ còn quyết định ai sở hữu lớp (huỷ cùng chỗ khai báo); không nơi dùng nào phải tự đặt `parent`.
FocusScope {
    id: root
    anchors.fill: parent
    readonly property Item scene: Window.contentItem
    property Item owner: null            // nơi khai báo (cha lúc dựng): ai sở hữu lớp này; dùng cho phép thử tìm lớp theo trang đã mở nó
    onSceneChanged: reparent()
    Component.onCompleted: reparent()
    function reparent() {
        if (!scene || parent === scene) return
        if (!owner) owner = parent
        parent = scene
    }
}
