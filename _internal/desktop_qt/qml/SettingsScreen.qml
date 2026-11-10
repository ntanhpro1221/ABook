import "UiStrings.js" as S
import QtQuick
import ABook

// Cài đặt (desktop/SettingsScreen.tsx + shared/SettingsNav.tsx): cùng cây nhóm với điện thoại. Rộng (>= expanded): danh sách nhóm 260 px bên
// trái, nội dung nhóm bên phải (cách 32, cả trang tối đa 1180, giữa màn); tiêu đề "Cài đặt" và tên nhóm (24 đậm) chung một chân chữ. Đổi nhóm
// như đổi tab (không chồng Back). Hẹp: trang gốc là danh sách, mỗi nhóm một màn con có nút ← "Về Cài đặt" (Back về danh sách). Cả trang cuộn.
FocusScope {
    id: root
    readonly property bool expanded: Theme.widthClass(width) >= 2
    property bool layoutExpanded: expanded
    readonly property real layoutPhase: navigationSwap.phase
    property string active: ""
    property string displayedActive: ""
    readonly property real navigationPhase: navigationSwap.phase
    signal studioRequested()
    readonly property real bodyWidth: Math.min(width - 2 * Theme.margin, layoutExpanded ? 1180 : 760)
    readonly property var groups: {
        // desktopGroups(info, touchOnly=false) của bản web, máy này (không điều khiển từ xa)
        const info = Api.info || {}
        const ids = ["voice", "listen", "sleep", "look", "devices"]
        if (info.studio) ids.push("studio")
        ids.push("advanced")
        return all.filter(g => ids.includes(g.key))
    }
    readonly property var all: [
        {key: "voice", label: S.s_giong_doc_11f2548d, icon: "audio-lines"},
        {key: "listen", label: S.s_nghe_a43aafef, icon: "headphones"},
        {key: "sleep", label: S.s_hen_gio_ngu_21073488, icon: "moon-star"},
        {key: "look", label: S.s_giao_dien_0813b59e, icon: "palette"},
        {key: "devices", label: S.s_thiet_bi_eb706979, icon: "monitor-smartphone"},
        {key: "studio", label: S.s_studio_0aa91af2, icon: "clapperboard"},
        {key: "advanced", label: S.s_nang_cao_d16fca15, icon: "wrench"}
    ]
    readonly property string shown: groups.some(g => g.key === displayedActive) ? displayedActive : (layoutExpanded && groups.length ? groups[0].key : "")
    readonly property string groupTitle: (all.find(g => g.key === shown) || {}).label || ""
    property var sync: null
    property QtObject backLayer: QtObject { function close() { root.active = "" } }
    function syncLayer() {
        Nav.closedLayer(backLayer)
        if (active && !expanded) Nav.openLayer(backLayer)
    }
    onActiveChanged: {
        syncLayer()
        const target = active
        navigationSwap.change(function() { root.displayedActive = target; page.contentY = 0 }, active === "")
    }
    onExpandedChanged: {
        const target = expanded
        navigationSwap.change(function() { root.layoutExpanded = target; root.syncLayer() }, !expanded)
    }
    ContentSlide { id: navigationSwap; objectName: "settingsContentSlide"; anchors.fill: parent; sourceItem: page }
    Component.onDestruction: Nav.closedLayer(backLayer)
    Component.onCompleted: {
        displayedActive = active
        Api.bind(DesktopApi, Theme)
        if (!Api.loaded) Api.load()
        Api.ensureVoiceName()
        Api.call("GET", "/api/sync", null, function(data, error) { if (!error) root.sync = data })
    }

    // Dòng tóm tắt dưới tên nhóm (useRows của bản web; shared/settingsSummary.ts)
    function summary(key) {
        const p = Api.preferences || {}
        const info = Api.info || {}
        if (key === "voice") return Api.voiceName
        if (key === "listen") return (p.autoRewind !== false ? S.s_tu_lui_6fc7685a : S.s_khong_tu_lui_8aec206c) + "\u00a0·\u00a0" + (p.autoMusic !== false ? S.s_nhac_tu_chon_31bdb97d : S.s_khong_nhac_nen_0e54f623)
        if (key === "sleep") {
            if (p.sleepSchedule) return S.s_lich_dem_cd78826f + p.sleepSchedule.from + "–" + p.sleepSchedule.to
            return S.s_tat_3286064e
        }
        if (key === "look") return p.theme === "light" ? S.s_sang_8f0c677d : p.theme === "dark" ? S.s_toi_4ac2d267 : S.s_tu_dong_a25c8028
        if (key === "devices") return root.sync ? (root.sync.enabled ? (root.sync.devices || []).length + S.s_thiet_bi_da_ghep_0dac64c4 : S.s_dang_tat_53bfa8b7) : ""
        if (key === "studio") return info.studio && info.studio.installed ? S.s_da_cai_e0159635 : S.s_chua_cai_17f9d6d7
        if (key === "advanced") return info.update ? S.s_co_ban_moi_fa2f1de5 + info.update.version : info.version ? S.s_phien_ban_52b00626 + info.version : ""
        return ""
    }

    Flickable {
        id: page
        anchors.fill: parent
        transform: Translate { x: navigationSwap.incomingShift }
        opacity: Theme.reduceMotion ? root.navigationPhase : 1
        contentWidth: width
        contentHeight: frame.height + 64
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        SmoothWheel { flick: page }

        Item {
            id: frame
            objectName: "settingsFrame"
            x: (root.width - root.bodyWidth) / 2
            width: root.bodyWidth
            height: Math.max(navigation.visible ? navigation.y + navigation.height : 0, content.visible ? content.y + content.height : 0)

            ScreenHeader {
                id: header
                objectName: "settingsHeader"
                width: root.layoutExpanded ? 260 : parent.width
                title: !root.layoutExpanded && root.shown ? root.groupTitle : S.s_cai_dat_202e0e9b
                backLabel: S.s_ve_cai_dat_0c328887
                showBack: !root.layoutExpanded && root.shown !== ""
            }
            // Tên nhóm ở đầu cột phải: 24 đậm, chân chữ thẳng chân chữ của "Cài đặt" (32) bên trái.
            Text {
                id: groupHeading
                objectName: "settingsGroupHeading"
                visible: root.layoutExpanded
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
                visible: !root.layoutExpanded && !root.shown && Boolean(Api.info && Api.info.update)
                y: header.height + 16
                width: parent.width
                title: Api.info && Api.info.update ? S.s_co_abook_39ccc742 + Api.info.update.version : ""
                icon: "download"
                onClicked: root.active = "advanced"
            }
            Column {
                id: navigation
                objectName: "settingsGroups"
                y: header.height + (updateNotice.visible ? updateNotice.height + 16 : 0) + 20
                width: root.layoutExpanded ? 260 : parent.width
                visible: root.layoutExpanded || !root.shown
                Accessible.name: S.s_nhom_cai_dat_8cf2ef86
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
                            current: root.layoutExpanded && root.shown === modelData.key
                            onClicked: root.active = modelData.key
                        }
                    }
                }
            }
            Item {
                id: content
                objectName: "settingsContent"
                property bool wholeRows: true     // mọi hàng chạy hết cột: danh sách trong đây cũng vậy (Theme.listWidth)
                x: root.layoutExpanded ? 260 + Theme.s32 : 0
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
