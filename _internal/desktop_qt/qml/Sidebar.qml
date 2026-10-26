import QtQuick
import ABook

// Thanh bên của máy tính (DESIGN.md mục 3): Thư viện · Studio ở trên, Cài đặt ở đáy; không nhóm tiêu đề thừa.
// Phím tắt Ctrl+1 / Ctrl+2 / Ctrl+3 (đặt ở Main.qml) hiện trong chú thích. Nền mục đang mở là một khối trượt giữa các mục.
Item {
    id: root
    property int currentSection: 0
    property alias chip: chip
    signal sectionRequested(int index)

    width: 232

    Text {
        x: Theme.s24
        y: Theme.s32
        text: "ABook"
        color: Theme.text
        font.pixelSize: Theme.sizeSection
        font.weight: Theme.weightBold
    }

    // Khối nền của mục đang mở
    Rectangle {
        id: selector
        readonly property Item target: root.currentSection === 0 ? library : (root.currentSection === 1 ? studio : settings)
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
        x: Theme.s12
        y: 96
        width: root.width - 2 * Theme.s12
        text: "Thư viện"
        glyph: ""
        shortcut: "Ctrl+1"
        current: root.currentSection === 0
        onClicked: root.sectionRequested(0)
    }
    NavItem {
        id: studio
        x: Theme.s12
        y: library.y + library.height + Theme.s4
        width: root.width - 2 * Theme.s12
        text: "Studio"
        glyph: ""
        shortcut: "Ctrl+2"
        current: root.currentSection === 1
        onClicked: root.sectionRequested(1)
    }
    ConnectionChip {
        id: chip
        x: Theme.s12
        y: settings.y - height - Theme.s4
        width: root.width - 2 * Theme.s12
    }
    NavItem {
        id: settings
        x: Theme.s12
        y: root.height - height - Theme.s16
        width: root.width - 2 * Theme.s12
        text: "Cài đặt"
        glyph: ""
        shortcut: "Ctrl+3"
        current: root.currentSection === 2
        onClicked: root.sectionRequested(2)
    }
}
