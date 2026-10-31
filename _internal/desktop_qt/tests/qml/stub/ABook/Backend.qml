pragma Singleton
import QtQuick

// Chỗ của Backend (C++) trong bộ thử thanh bên: ConnectionChip chỉ đọc trạng thái.
QtObject {
    enum State { Starting, Ready, Failed }
    property int state: 1
    property bool libraryLoaded: true
    property string version: "0.4.32"
    property string logPath: ""
    property string message: "Bạn thử mở lại ABook."
    // Kênh của vỏ (Backend C++ đọc dòng JSON của host): bộ thử phát tay
    signal hostEvent(string name, var detail)
    signal updateChecked(var detail)
    function refreshLibrary() {}
    property QtObject library: QtObject {
        property int count: 200
        property int revision: 0
        property string error: ""
        property var items: null
        function book(i) { return items ? items[i] || {} : {title: "Sách " + (i + 1), subtitle: "Tác giả", coverKey: "", progress: 0, source: ""} }
    }
}
