pragma Singleton
import QtQuick

// Chỗ của Platform (C++) trong bộ thử thanh bên: chỉ phần Sidebar dùng. Lưu vào một object thường, không báo đổi (như bản C++).
QtObject {
    property var store: ({})
    property int writes: 0
    property int exits: 0   // Platform.exitApp(): bộ thử không thoát thật, chỉ đếm
    readonly property bool keyboardNav: false
    function setting(key, fallback) { return store[key] !== undefined ? store[key] : fallback }
    function setSetting(key, value) { store[key] = value; writes++ }
    function exitApp() { exits++ }
    function reset() { store = ({}); writes = 0; exits = 0 }
    function workArea(window, position) { return Qt.rect(0, 0, 1920, 1080) }
}
