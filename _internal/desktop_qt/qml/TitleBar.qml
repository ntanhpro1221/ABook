import QtQuick
import ABook

// Dải tiêu đề tự vẽ (thay thanh tiêu đề hệ thống). Cao 40 = Theme.buttonHeight: nút thu / mở thanh bên của Sidebar (vùng bấm 32) nằm lọt
// trong dải mà không phải co lại, ba nút cửa sổ 46 x 40 (Windows chuẩn là 46 x 32; cao hơn cho cân với dải 40 và dễ bấm). Dải không có nền
// riêng: phần trên thanh bên và phần trên nội dung cùng màu Theme.bg với vùng ngay dưới (khi thanh bên đổi màu thì vẽ nền ở đây theo nó).
// Vùng trống của dải là chỗ kéo cửa sổ; nhấp đúp phóng to / khôi phục, Aero Snap, Snap Layouts, viền đổi cỡ do Windows lo (WindowChrome).
Item {
    id: root
    property var window: null
    property var chrome: null
    readonly property bool maximized: window !== null && window.visibility === Window.Maximized
    readonly property bool windowActive: window !== null && window.active
    property alias minimizeButton: minimize
    property alias maximizeButton: maximize
    property alias closeButton: close

    height: Theme.buttonHeight

    Row {
        anchors.top: parent.top
        anchors.right: parent.right
        height: parent.height
        CaptionButton {
            id: minimize
            height: parent.height
            active: root.windowActive
            onClicked: root.window.showMinimized()
            CaptionGlyph { kind: "minimize"; color: minimize.ink }
        }
        CaptionButton {
            id: maximize
            height: parent.height
            chrome: root.chrome
            active: root.windowActive
            onClicked: root.maximized ? root.window.showNormal() : root.window.showMaximized()
            CaptionGlyph { kind: "maximize"; shown: !root.maximized; color: maximize.ink }
            CaptionGlyph { kind: "restore"; shown: root.maximized; color: maximize.ink }
        }
        CaptionButton {
            id: close
            height: parent.height
            danger: true
            active: root.windowActive
            onClicked: root.window.close()
            CaptionGlyph { kind: "close"; color: close.ink }
        }
    }
}
