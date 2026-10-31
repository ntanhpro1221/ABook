pragma Singleton
import QtQuick
QtObject {
    property var devices: [{id: "", name: "Mặc định"}, {id: "speaker", name: "Loa ngoài của máy tính"}, {id: "gone", name: "Tai nghe đã ngắt"}]
    property string selected: ""
    property string error: ""
    property bool busy: false
    property int refreshes: 0
    function refresh() { refreshes++; error = "" }
    function select(id) {
        error = id === "gone" ? "Chưa đổi được thiết bị phát. Vẫn dùng thiết bị trước." : ""
        if (!error) selected = id
    }
}
