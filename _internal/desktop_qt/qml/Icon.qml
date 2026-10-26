import QtQuick
import ABook

// Biểu tượng nét mảnh của Windows (Segoe Fluent Icons trên Windows 11, Segoe MDL2 Assets trên Windows 10): có sẵn trong hệ điều hành,
// không đóng gói ảnh, vẽ như chữ nên sắc ở mọi tỉ lệ màn hình.
Text {
    property alias glyph: icon.text
    id: icon
    property int size: 20
    font.family: Platform.iconFamily
    font.pixelSize: size
    color: Theme.text
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    width: size
    height: size
    renderType: Text.NativeRendering
}
