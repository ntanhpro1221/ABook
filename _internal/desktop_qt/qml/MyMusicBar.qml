import QtQuick
import ABook

// Thanh tiến độ cỡ sm của Progress (shared/ui.tsx): rãnh cao 6 bo tròn màu --line, phần đã tải màu nhấn.
Rectangle {
    id: root
    property real value: 0              // 0..1
    property string label: ""
    height: 6
    radius: height / 2
    color: Theme.line
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label
    Rectangle {
        width: parent.width * Math.max(0, Math.min(1, root.value))
        height: parent.height
        radius: height / 2
        color: Theme.accent
        // Phần tô theo giá trị tự đổi: vẽ thẳng, không Behavior (luật chủ sách 30-10; điện thoại native cũng vậy)
    }
}
