import QtQuick
import ABook

// Khay hệ thống viết thẳng bằng Win32 (src/trayicon.cpp): không Qt.labs.platform nên không kéo Qt6Widgets.dll vào bản phân phối.
TrayIcon {
    id: root
    property var mode: null   // WindowMode của Main
    property TrayMenuModel model: TrayMenuModel { windowMode: root.mode }
    visible: true
    tooltip: model.tooltip
    actions: model.actions
    onActivated: model.activate()
    onTriggered: action => model.dispatch(action)
}
