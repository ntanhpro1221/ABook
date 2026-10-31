import QtQuick

// Chỗ của TrayIcon (C++, Shell_NotifyIcon, chỉ có trên Windows) trong bộ thử: không icon nào vào khay thật; cùng thuộc tính / tín hiệu với bản thật.
QtObject {
    property string tooltip
    property var actions: []
    property bool visible: false
    readonly property bool available: visible
    signal activated()
    signal triggered(string action)
    function showMessage(title, message) {}
}
