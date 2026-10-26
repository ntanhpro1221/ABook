pragma Singleton
import QtQuick

// Chỗ của Backend (C++) trong bộ thử thanh bên: ConnectionChip chỉ đọc trạng thái.
QtObject {
    enum State { Starting, Ready, Failed }
    property int state: 1
    property bool libraryLoaded: true
    property string version: "0.4.32"
    property string logPath: ""
    property QtObject library: QtObject {
        property int count: 200
        property int revision: 0
        property string error: ""
        function book(i) { return {title: "Sách " + (i + 1), subtitle: "Tác giả", coverKey: "", progress: 0, source: ""} }
    }
}
