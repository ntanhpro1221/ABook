import "UiStrings.js" as S
import QtQuick
import ABook

// Thanh bên của máy tính (DESIGN.md mục 3): Thư viện · Studio ở trên, Cài đặt ở đáy; không nhóm tiêu đề thừa.
// Phím tắt Ctrl+1 / Ctrl+2 / Ctrl+3 (đặt ở Main.qml) hiện trong chú thích. Nền mục đang mở là một khối trượt giữa các mục.
// Thu gọn / mở rộng như Claude Desktop: nút ở đầu thanh (hay Ctrl+B) đổi giữa thanh đầy đủ và dải hẹp chỉ có biểu tượng (cùng độ cao từng mục).
// Dải hẹp: rê vào ~150 ms thì thanh đầy đủ mở tạm ĐÈ LÊN nội dung (có bóng, không đẩy, không bố cục lại nội dung); rê ra ~300 ms thì đóng; bấm một mục
// thì đi tới đó và đóng. Chữ nhãn bị phần cắt của khung trượt che / hé ra theo bề rộng, không bao giờ bị rút gọn "…"; không có mờ dần. Trạng thái nhớ qua Platform.
Item {
    id: root
    property int currentSection: 0
    property alias chip: chip
    property alias toggleButton: toggleButton
    property alias selector: selector
    property alias panel: panel
    signal sectionRequested(int index)
    signal projectRequested(string bookId)
    signal precastRequested(string bookId)
    property string openProject: ""
    Accessible.role: Accessible.Pane
    Accessible.name: S.s_dieu_huong_chinh_84d2467a

    readonly property real railWidth: 56            // tâm biểu tượng ở 28: lề mục 8 + lề biểu tượng 11 + nửa biểu tượng 9
    readonly property real fullWidth: 232
    property bool expanded: Platform.setting("sidebarExpanded", "1") !== "0"
    property bool peek: false                       // dải hẹp đang mở tạm
    property bool peekBlocked: false                // vừa bấm nút / mục: chưa mở tạm lại cho tới khi con trỏ rời thanh
    readonly property bool hovered: hover.hovered
    readonly property real overlay: Math.max(0, panel.width - width)     // phần thanh đầy đủ đang đè lên nội dung

    // Bề rộng chiếm chỗ trong bố cục (nội dung neo vào mép phải của nó); mở tạm KHÔNG đổi giá trị này
    width: expanded ? fullWidth : railWidth
    Behavior on width { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }

    function toggle() {
        expanded = !expanded
        peek = false
        peekBlocked = hover.hovered
        openTimer.stop()
        closeTimer.stop()
        Platform.setSetting("sidebarExpanded", expanded ? "1" : "0")
    }
    function choose(index) {
        if (peek) {
            peek = false
            peekBlocked = true
        }
        root.sectionRequested(index)
    }

    Shortcut { sequences: ["Ctrl+B"]; onActivated: root.toggle() }

    Timer { id: openTimer; interval: 150; onTriggered: if (hover.hovered && !root.expanded && !root.peekBlocked) root.peek = true }
    Timer { id: closeTimer; interval: 300; onTriggered: if (!hover.hovered) root.peek = false }
    Connections {
        target: hover
        function onHoveredChanged() {
            if (hover.hovered) {
                closeTimer.stop()
                if (!root.expanded && !root.peek && !root.peekBlocked) openTimer.restart()
            } else {
                openTimer.stop()
                root.peekBlocked = false
                if (root.peek) closeTimer.restart()
            }
        }
    }

    // Khung vẽ: rộng bằng thanh đầy đủ khi mở / mở tạm, bằng dải khi thu gọn. Cắt ngang nên nhãn hé ra theo bề rộng.
    Item {
        id: panel
        width: root.expanded || root.peek ? root.fullWidth : root.railWidth
        height: parent.height
        clip: true
        Behavior on width { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }

        // Follow the visible panel, including its overlay beyond the 56 px layout rail.
        // Watching the rail instead closes the menu while the pointer moves onto its labels.
        HoverHandler { id: hover }

        // Nền: chỉ đục khi đè lên nội dung (lúc đứng yên cùng màu cửa sổ nên không thấy)
        Rectangle { anchors.fill: parent; color: Theme.bg }

        IconButton {
            id: toggleButton
            x: 12                  // tâm biểu tượng ở 28 như các mục; vùng bấm 32 lọt trong dải tiêu đề cao 40
            y: 4
            width: Theme.hit
            height: Theme.hit
            icon: root.expanded ? "panel-left-close" : "panel-left-open"
            iconSize: 18
            tip: root.expanded ? S.s_thu_gon_ctrl_b_8388742c : S.s_mo_rong_ctrl_b_efa58bb4
            onClicked: root.toggle()
        }

        // Khối nền của mục đang mở
        Rectangle {
            id: selector
            readonly property Item target: [library, studio, settings, music][root.currentSection] || library
            x: target.x
            y: target.y
            width: target.width
            height: target.height
            radius: Theme.radiusControl
            color: Theme.sunken
            Behavior on y {
                NumberAnimation {
                    duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: Theme.easeStandard
                }
            }
        }

        NavItem {
            id: library
            x: Theme.s8
            y: 48
            width: panel.width - 2 * Theme.s8
            text: S.s_thu_vien_58145555
            icon: "library"
            shortcut: "Ctrl+1"
            current: root.currentSection === 0
            onClicked: root.choose(0)
        }
        // Nhạc là nội dung, không phải cài đặt: mục gốc ngay sau Thư viện (DESIGN.md §7 "Nhạc"); trong ngăn xếp là roots[3]
        NavItem {
            id: music
            objectName: "sidebarMusic"
            x: Theme.s8
            y: library.y + library.height + Theme.s4
            width: panel.width - 2 * Theme.s8
            text: S.s_nhac_0e4413e9
            icon: "list-music"
            shortcut: "Ctrl+4"
            current: root.currentSection === 3
            onClicked: root.choose(3)
        }
        NavItem {
            id: studio
            x: Theme.s8
            y: music.y + music.height + Theme.s4
            width: panel.width - 2 * Theme.s8
            text: S.s_studio_0aa91af2
            icon: "clapperboard"
            shortcut: "Ctrl+2"
            current: root.currentSection === 1
            onClicked: root.choose(1)
        }
        ConnectionChip {
            id: chip
            x: Theme.s8
            y: settings.y - height - Theme.s4
            width: panel.width - 2 * Theme.s8
        }
        Flickable {
            id: productionScroll
            x: Theme.s16; y: studio.y + studio.height + Theme.s8
            width: root.fullWidth - 2 * Theme.s16
            height: Math.max(0, chip.y - y - Theme.s8)
            contentHeight: production.height + update.height
            clip: true; boundsBehavior: Flickable.StopAtBounds
            visible: root.expanded || root.peek
            SidebarProgress {
                id: production; width: parent.width; height: implicitHeight
                openProject: root.openProject
                onProjectRequested: id => { root.choose(1); root.projectRequested(id) }
                onPrecastRequested: id => { root.choose(1); root.projectRequested(id); root.precastRequested(id) }
                onAllRequested: root.choose(1)
            }
            Collapse {
                id: update; y: production.height; width: parent.width
                open: !!Api.info.update && !Api.info.remote
                Button {
                    objectName: "sidebarUpdate"; width: parent.width; wrap: true; kind: "ghost"; icon: "download"
                    text: S.s_co_abook_39ccc742 + (Api.info.update ? Api.info.update.version : "") + S.s_bam_de_cap_nhat_186823a8
                    onClicked: { root.choose(2); if (Nav.stack) Nav.stack.rootContent(2).active = "advanced" }
                }
            }
            SmoothWheel { flick: productionScroll }
        }
        NavItem {
            id: settings
            x: Theme.s8
            y: root.height - height - Theme.s16
            width: panel.width - 2 * Theme.s8
            text: S.s_cai_dat_202e0e9b
            icon: "settings"
            shortcut: "Ctrl+3"
            current: root.currentSection === 2
            onClicked: root.choose(2)
        }
    }

    // Bóng mép phải khi thanh đầy đủ đè lên nội dung: đậm dần theo phần đang đè (không phải mờ dần theo thời gian)
    Rectangle {
        x: panel.width
        width: 16
        height: parent.height
        visible: root.overlay > 0.5
        opacity: Math.min(1, root.overlay / (root.fullWidth - root.railWidth))
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Theme.dark ? "#66000000" : "#26000000" }
            GradientStop { position: 1; color: "#00000000" }
        }
    }
    Rectangle {
        x: panel.width - 1
        width: 1
        height: parent.height
        visible: root.overlay > 0.5
        color: Theme.line
    }
}
