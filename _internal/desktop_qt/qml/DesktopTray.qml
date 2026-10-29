import QtQuick
import Qt.labs.platform as Native
import ABook

// Windows cung cấp khay và menu native qua QPA, giữ QGuiApplication, không thêm QtWidgets.
Native.SystemTrayIcon {
    id: root
    property var windowMode: null
    property TrayMenuModel model: TrayMenuModel { windowMode: root.windowMode }
    visible: true
    icon.source: "qrc:/app/app.ico"
    tooltip: model.tooltip
    onActivated: reason => { if (reason === Native.SystemTrayIcon.Trigger) model.activate() }
    menu: Native.Menu {
        Instantiator {
            model: root.model.actions
            delegate: Native.MenuItem {
                required property var modelData
                separator: modelData.separator === true
                text: modelData.label || ""
                enabled: modelData.separator === true || modelData.enabled === true
                onTriggered: root.model.dispatch(modelData.action)
            }
            onObjectAdded: (index, object) => root.menu.insertItem(index, object)
            onObjectRemoved: (index, object) => root.menu.removeItem(object)
        }
    }
}
