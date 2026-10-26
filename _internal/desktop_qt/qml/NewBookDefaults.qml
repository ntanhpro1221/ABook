import QtQuick
import ABook

// Mặc định cho sách MỚI (NewBookDefaults của desktop/SettingsScreen.tsx): giọng kể và chất lượng, mỗi lần tạo sách khỏi chọn lại như lần
// trước. "Làm tiếp cuốn này" vẫn theo phần trước. Rộng >= 640: hai cột (sm:grid-cols-2); hẹp: một cột. Cách 12, đệm trên / dưới 12 (py-3).
SettingsItem {
    id: root
    property var voices: []
    readonly property bool wide: (Window.window ? Window.window.width : 1000) >= 640
    // PROFILE_LABEL của studio/bookTemplates.ts, đúng thứ tự khoá
    readonly property var profiles: [{value: "high_quality", label: "Chất lượng cao"}, {value: "balanced", label: "Cân bằng"}, {value: "fast", label: "Nhanh"}]
    readonly property var narrators: [{value: "", label: "Máy đề xuất"}].concat((voices || []).map(v => ({value: v.name, label: v.name + " · " + v.gender + ", miền " + v.region})))
    padding: 12
    function load() {
        if (!Api.transport) return
        Api.transport.request("GET", "/api/voices", null, function(status, data) { if (status >= 200 && status < 300 && Array.isArray(data)) root.voices = data })
    }
    Component.onCompleted: load()

    Item {
        width: parent.width
        implicitHeight: root.wide ? Math.max(narrator.height, quality.height) : narrator.height + 12 + quality.height
        height: implicitHeight
        Column {
            id: narrator
            width: root.wide ? (parent.width - 12) / 2 : parent.width
            spacing: 4
            Text { width: parent.width; text: "Giọng kể"; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
            Select {
                objectName: "newBookNarrator"
                width: parent.width
                label: "Giọng kể"
                options: root.narrators
                value: Api.preferences.newBookNarrator ?? ""
                onPicked: value => Api.update({newBookNarrator: value})
            }
        }
        Column {
            id: quality
            x: root.wide ? narrator.width + 12 : 0
            y: root.wide ? 0 : narrator.height + 12
            width: narrator.width
            spacing: 4
            Text { width: parent.width; text: "Chất lượng"; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
            Select {
                objectName: "newBookProfile"
                width: parent.width
                label: "Chất lượng"
                options: root.profiles
                value: Api.preferences.newBookProfile ?? "high_quality"
                onPicked: value => Api.update({newBookProfile: value})
            }
        }
    }
}
