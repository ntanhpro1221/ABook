pragma Singleton
import QtQuick
QtObject {
    property bool hiddenDesktop: true   // tst_tray_quit đặt false để Main dựng khay (TrayIcon giả)
    readonly property bool enabled: false
    function noteOnce(event) {}
    function attach(window) {}
    function note(name) {}
}
