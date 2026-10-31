import QtQuick
import ABook

// Một khối của thẻ giọng (space-y-3 của VieneuModuleCard): đệm trên 12 NẰM TRONG phần gập, nên khối hiện / ẩn thì chiều cao (cả khoảng cách) mở / khép
// cùng một nhịp, không nhảy ở cuối như khoảng cách của Column. `show` đổi -> Collapse. Nội dung đặt thẳng vào trong.
Item {
    id: root
    property bool show: false
    property real gap: 12
    default property alias content: pad.data
    implicitHeight: collapse.height
    height: implicitHeight
    Collapse {
        id: collapse
        width: root.width
        open: root.show
        Column { id: pad; width: parent.width; topPadding: root.gap }
    }
}
