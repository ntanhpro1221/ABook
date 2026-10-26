import QtQuick
import ABook

// Cài đặt (desktop/SettingsScreen.tsx + shared/SettingsNav.tsx): cùng cây nhóm với điện thoại. Rộng (>= expanded): danh sách nhóm 260 px bên
// trái, nội dung nhóm bên phải (cách 32, cả trang tối đa 1180, giữa màn); tiêu đề "Cài đặt" và tên nhóm (24 đậm) chung một chân chữ. Đổi nhóm
// như đổi tab (không chồng Back). Hẹp: trang gốc là danh sách, mỗi nhóm một màn con có nút ← "Về Cài đặt" (Back về danh sách). Cả trang cuộn.
FocusScope {
    id: root
    readonly property bool expanded: width >= Theme.widthExpanded
    property string active: ""
    signal studioRequested()
    readonly property real bodyWidth: Math.min(width - 2 * Theme.margin, expanded ? 1180 : 760)
    readonly property var groups: {
        // desktopGroups(info, touchOnly=false) của bản web, máy này (không điều khiển từ xa)
        const info = Api.info || {}
        const ids = ["voice", "listen", "sleep", "look", "devices"]
        if (info.studio) ids.push("studio")
        ids.push("advanced")
        return all.filter(g => ids.includes(g.key))
    }
    readonly property var all: [
        {key: "voice", label: "Giọng đọc", icon: "audio-lines"},
        {key: "listen", label: "Nghe", icon: "headphones"},
        {key: "sleep", label: "Hẹn giờ ngủ", icon: "moon-star"},
        {key: "look", label: "Giao diện", icon: "palette"},
        {key: "devices", label: "Thiết bị", icon: "monitor-smartphone"},
        {key: "studio", label: "Studio", icon: "clapperboard"},
        {key: "advanced", label: "Nâng cao", icon: "wrench"}
    ]
    readonly property string shown: groups.some(g => g.key === active) ? active : (expanded && groups.length ? groups[0].key : "")
    readonly property string groupTitle: (all.find(g => g.key === shown) || {}).label || ""
    property var sync: null
    property QtObject backLayer: QtObject { function close() { root.active = "" } }
    function syncLayer() {
        Nav.closedLayer(backLayer)
        if (active && !expanded) Nav.openLayer(backLayer)
    }
    onActiveChanged: { syncLayer(); page.contentY = 0 }
    onExpandedChanged: syncLayer()
    Component.onDestruction: Nav.closedLayer(backLayer)
    Component.onCompleted: {
        Api.bind(DesktopApi, Theme)
        if (!Api.loaded) Api.load()
        Api.call("GET", "/api/sync", null, function(data, error) { if (!error) root.sync = data })
    }

    // Dòng tóm tắt dưới tên nhóm (useRows của bản web; shared/settingsSummary.ts)
    function summary(key) {
        const p = Api.preferences || {}
        const info = Api.info || {}
        if (key === "voice") return Api.voiceName
        if (key === "listen") return (p.autoRewind !== false ? "Tự lùi" : "Không tự lùi") + " · " + (p.autoMusic !== false ? "nhạc tự chọn" : "không nhạc nền")
        if (key === "sleep") {
            if (p.sleepSchedule) return "Lịch đêm " + p.sleepSchedule.from + "–" + p.sleepSchedule.to
            const hours = p.safetyStopHours ?? 2
            return hours ? "Tự tắt sau " + hours + " giờ" : "Tắt"
        }
        if (key === "look") return p.theme === "light" ? "Sáng" : p.theme === "dark" ? "Tối" : "Tự động"
        if (key === "devices") return root.sync ? (root.sync.enabled ? (root.sync.devices || []).length + " thiết bị đã ghép" : "Đang tắt") : ""
        if (key === "studio") return info.studio && info.studio.installed ? "Đã cài" : "Chưa cài"
        if (key === "advanced") return info.update ? "Có bản mới " + info.update.version : info.version ? "Phiên bản " + info.version : ""
        return ""
    }

    Flickable {
        id: page
        anchors.fill: parent
        contentWidth: width
        contentHeight: frame.height + 64
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        SmoothWheel { flick: page }

        Item {
            id: frame
            x: (root.width - root.bodyWidth) / 2
            width: root.bodyWidth
            height: Math.max(navigation.visible ? navigation.y + navigation.height : 0, content.visible ? content.y + content.height : 0)

            ScreenHeader {
                id: header
                width: root.expanded ? 260 : parent.width
                title: !root.expanded && root.shown ? root.groupTitle : "Cài đặt"
                backLabel: "Về Cài đặt"
                showBack: !root.expanded && root.shown !== ""
            }
            // Tên nhóm ở đầu cột phải: 24 đậm, chân chữ thẳng chân chữ của "Cài đặt" (32) bên trái.
            Text {
                id: groupHeading
                visible: root.expanded
                x: 260 + Theme.s32
                width: parent.width - x
                y: header.titleBaseline - baselineOffset
                text: root.groupTitle
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeTitlePhone
                font.weight: Theme.weightBold
            }
            // Ghi chú trên danh sách (chỉ hẹp): đã có bản mới -> một hàng dẫn tới Nâng cao.
            DisclosureRow {
                id: updateNotice
                visible: !root.expanded && !root.shown && Boolean(Api.info && Api.info.update)
                y: header.height + 16
                width: parent.width
                title: Api.info && Api.info.update ? "Có ABook " + Api.info.update.version : ""
                icon: "download"
                onClicked: root.active = "advanced"
            }
            Column {
                id: navigation
                objectName: "settingsGroups"
                y: header.height + (updateNotice.visible ? updateNotice.height + 16 : 0) + 20
                width: root.expanded ? 260 : parent.width
                visible: root.expanded || !root.shown
                Accessible.name: "Nhóm cài đặt"
                Repeater {
                    model: root.groups
                    Item {
                        required property var modelData
                        required property int index
                        width: navigation.width
                        height: row.height
                        Rectangle { width: parent.width; height: 1; color: Theme.line; visible: index > 0 }
                        DisclosureRow {
                            id: row
                            width: parent.width
                            title: modelData.label
                            summary: root.summary(modelData.key)
                            icon: modelData.icon
                            current: root.expanded && root.shown === modelData.key
                            onClicked: root.active = modelData.key
                        }
                    }
                }
            }
            Item {
                id: content
                objectName: "settingsContent"
                x: root.expanded ? 260 + Theme.s32 : 0
                y: header.height
                width: parent.width - x
                height: body.height
                visible: root.shown !== ""
                SettingsBody { id: body; width: parent.width; group: root.shown; onStudioRequested: root.studioRequested() }
            }
        }
    }
    Scrollbar { target: page }
}
