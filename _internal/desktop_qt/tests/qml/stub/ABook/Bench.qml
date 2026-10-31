pragma Singleton
import QtQuick
QtObject {
    readonly property bool hiddenDesktop: true
    readonly property bool enabled: false
    function noteOnce(event) {}
    function attach(window) {}
    function note(name) {}
}
