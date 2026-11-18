import QtQuick

// Composite the surface, its border and its shadow once before fading the window.
// Reserve the full shadow image extent; a layer sized to the panel would cut it.
Item {
    id: root
    readonly property int shadowPadding: Theme.dark ? 130 : 96
    default property alias surfaceData: surface.data
    readonly property alias composition: composite
    data: Item {
        id: composite
        x: -root.shadowPadding
        y: -root.shadowPadding
        width: root.width + 2 * root.shadowPadding
        height: root.height + 2 * root.shadowPadding
        // A closed surface has no pixels to composite. Keep the layer until
        // the exit fade has finished, then release its render target.
        // Bộ vẽ phần mềm (QT_QUICK_BACKEND=software - bộ chụp ảnh soát WidthTests) để lại phần lớp không được vẽ lại thành ĐEN
        // đặc: cả lề bóng quanh hộp thoại hoá khung đen (0.4.173 soát tay). App thật chạy RHI (D3D11) không bị - đã chụp cùng
        // cảnh bằng D3D11 ẩn (ABOOK_WIDTH_REAL_BACKEND=1): lề bóng đúng. Ở bộ vẽ phần mềm chỉ dựng lớp lúc đang mờ dần (opacity < 1,
        // để mặt + bóng vẫn mờ như một nhóm - tst_surface_motion); đứng yên thì vẽ thẳng: ảnh tĩnh y hệt, không còn khung đen.
        layer.enabled: root.visible && (root.GraphicsInfo.api !== GraphicsInfo.Software || root.opacity < 1)
        Item {
            id: surface
            x: root.shadowPadding
            y: root.shadowPadding
            width: root.width
            height: root.height
        }
    }
}
