import QtQuick
import ABook

// Thân của một nhóm Cài đặt (GroupBody của desktop/SettingsScreen.tsx): mỗi nhóm một file, dựng khi mở. Đổi nhóm = mờ qua (cái cũ mờ hết rồi
// cái mới mới hiện, trượt 16 px vào), không hai lớp chồng nhau; giảm chuyển động thì chỉ mờ.
Item {
    id: root
    property string group: ""
    signal studioRequested()        // nhóm Studio: "Xem tiến độ cài", "Sửa / Cập nhật Studio" -> màn Studio
    property string previous: group
    property real phase: 1
    property int direction: 1
    property bool entering: false
    readonly property Item page: loader.item
    implicitHeight: loader.item ? loader.item.implicitHeight : 0
    height: implicitHeight
    onGroupChanged: {
        if (transition.running) transition.complete()
        const keys = ["voice", "listen", "sleep", "look", "devices", "studio", "advanced"]
        direction = keys.indexOf(group) >= keys.indexOf(previous) ? 1 : -1
        entering = false
        transition.start()
    }
    SequentialAnimation {
        id: transition
        NumberAnimation { target: root; property: "phase"; to: 0; duration: root.previous === "" ? 0 : Theme.motionFastOut }
        // Read the requested group at the swap; a bound PropertyAction value
        // can still contain the old group when onGroupChanged starts it.
        ScriptAction { script: { root.previous = root.group; root.entering = true } }
        NumberAnimation { target: root; property: "phase"; to: 1; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
    }
    Loader {
        id: loader
        width: root.width
        opacity: root.phase
        transform: Translate { x: Theme.reduceMotion ? 0 : (root.entering ? 1 : -1) * root.direction * 16 * (1 - root.phase) }
        sourceComponent: ({voice: voice, listen: listen, sleep: sleep, look: look, devices: devices, studio: studio, advanced: advanced})[root.previous] || null
    }
    Component { id: voice; SettingsVoice {} }
    Component { id: listen; SettingsListen {} }
    Component { id: sleep; SettingsSleep {} }
    Component { id: look; SettingsLook {} }
    Component { id: devices; SettingsDevices {} }
    Component { id: studio; SettingsStudio { onStudioRequested: root.studioRequested() } }
    Component { id: advanced; SettingsAdvanced {} }
}
