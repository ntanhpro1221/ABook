import QtQuick

// Chỗ của WindowChrome (C++, QWindowKit, chỉ có trên Windows) trong bộ thử: Main.qml nạp được trên Linux offscreen, khung cửa sổ không làm gì.
QtObject {
    function attach(window, titleBar, minimize, maximize, close) { return true }
    function keepClickable(item) {}
    function setMini(mini) {}
}
