import QtQuick
import ABook

FocusScope {
    id: root
    readonly property bool expanded: width >= Theme.widthExpanded
    property string active: ""
    property real split: expanded ? 1 : 0
    readonly property real bodyWidth: Math.min(width - 2 * Theme.margin, 1180)
    readonly property var groups: [
        {key: "voice", label: "Giọng đọc", icon: "audio-lines"},
        {key: "listen", label: "Nghe", icon: "headphones"},
        {key: "sleep", label: "Hẹn giờ ngủ", icon: "moon-star"},
        {key: "look", label: "Giao diện", icon: "palette"},
        {key: "devices", label: "Thiết bị", icon: "monitor-smartphone"},
        {key: "studio", label: "Studio", icon: "clapperboard"},
        {key: "advanced", label: "Nâng cao", icon: "wrench"}
    ].filter(g => g.key !== "studio" || Boolean(Api.info.studio))
    readonly property string shown: active || (expanded ? "voice" : "")
    readonly property string groupTitle: (groups.find(g => g.key === shown) || {}).label || ""
    property var backLayer: QtObject { function close() { root.active = "" } }
    onActiveChanged: {
        Nav.closedLayer(backLayer)
        if (active && !expanded) Nav.openLayer(backLayer)
    }
    onExpandedChanged: {
        Nav.closedLayer(backLayer)
        if (active && !expanded) Nav.openLayer(backLayer)
    }
    Component.onDestruction: Nav.closedLayer(backLayer)
    Component.onCompleted: { Api.bind(DesktopApi, Theme); if (!Api.loaded) Api.load() }
    Behavior on split { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    function summary(key) {
        const p = Api.preferences
        if (key === "voice") return p.readAloudVoice || ""
        if (key === "listen") return (p.autoRewind !== false ? "Tự lùi" : "Không tự lùi") + " · " + (p.autoMusic !== false ? "nhạc tự chọn" : "không nhạc nền")
        if (key === "look") return p.theme === "light" ? "Sáng" : p.theme === "dark" ? "Tối" : "Tự động"
        if (key === "advanced") return Api.info.version ? "Phiên bản " + Api.info.version : ""
        if (key === "studio") return Api.info.studio && Api.info.studio.installed ? "Đã cài" : "Chưa cài"
        return ""
    }
    ScreenHeader {
        id: header
        x: (root.width - root.bodyWidth) / 2
        width: root.bodyWidth
        title: !root.expanded && root.shown ? root.groupTitle : "Cài đặt"
        backLabel: !root.expanded && root.shown ? "Về Cài đặt" : ""
        showBack: !root.expanded && root.shown !== ""
    }
    Column {
        id: navigation
        objectName: "settingsGroups"
        x: header.x
        y: header.height + 20
        width: root.expanded ? 260 : root.bodyWidth
        visible: root.expanded || !root.shown
        Repeater {
            model: root.groups
            Interactive {
                required property var modelData
                width: navigation.width
                height: Math.max(64, labels.height + 24)
                Accessible.name: modelData.label
                Accessible.role: Accessible.Button
                onClicked: root.active = modelData.key
                Rectangle { anchors.fill: parent; color: root.shown === modelData.key ? Theme.accentSoft : (parent.hovered ? Theme.sunken : "transparent"); radius: Theme.radiusControl }
                Icon { x: 12; y: 20; name: modelData.icon; color: root.shown === modelData.key ? Theme.accentText : Theme.text2; size: 20 }
                Column {
                    id: labels
                    x: 44; y: 12; width: parent.width - 72; spacing: 3
                    FormLabel { width: parent.width; text: modelData.label; font.weight: Theme.weightMedium }
                    FormLabel { width: parent.width; text: root.summary(modelData.key); visible: text !== ""; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                }
                Icon { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; name: "chevron-right"; size: 16; color: Theme.text3 }
                Rectangle { width: parent.width; height: 1; anchors.bottom: parent.bottom; color: Theme.line }
            }
        }
    }
    FormLabel {
        x: header.x + 292; y: header.height - height - 4
        width: root.bodyWidth - 292
        visible: root.expanded
        text: root.groupTitle
        font.pixelSize: Theme.sizeTitlePhone; font.weight: Theme.weightBold
    }
    Flickable {
        id: scroll
        objectName: "settingsContent"
        x: header.x + 292 * root.split
        y: header.height + 8
        width: root.bodyWidth - 292 * root.split
        height: root.height - y
        visible: root.shown !== ""
        clip: true
        contentHeight: content.height + 40
        boundsBehavior: Flickable.StopAtBounds
        SettingsBody { id: content; width: scroll.width; group: root.shown }
        SmoothWheel { flick: scroll }
    }
    Scrollbar { target: scroll }
}
