import QtQuick

// Chỗ của WindowChrome (C++, QWindowKit, chỉ có trên Windows) trong bộ thử: Main.qml nạp được trên Linux offscreen, khung cửa sổ không làm gì.
// Nhớ lại những gì Main.qml khai (attached / kept / mini) để tst_titlebar.qml khoá phần QML của hợp đồng với src/windowchrome.cpp.
QtObject {
    property var attached: null
    property var kept: []
    property bool mini: false
    function attach(window, titleBar, minimize, maximize, close) {
        attached = {window: window, titleBar: titleBar, minimize: minimize, maximize: maximize, close: close}
        return true
    }
    function keepClickable(item) { kept = kept.concat([item]) }
    function setMini(value) { mini = value }
    function cursorInside(item) { return false }
}
