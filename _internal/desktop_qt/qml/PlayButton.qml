import "UiStrings.js" as S
import QtQuick
import ABook

// Nút phát / tạm dừng tròn màu nhấn. Chờ tải âm thanh: một cung nhỏ quay quanh nút (không chữ).
Interactive {
    id: root
    property int size: 44
    implicitWidth: size
    implicitHeight: size
    ringRadius: size / 2
    enabled: Player.loaded
    opacity: enabled ? 1 : 0.4
    tip: Player.playing ? (Player.buffering ? (Player.speaking ? S.s_dang_chuan_bi_giong_doc_25f86ccf : S.s_dang_tai_am_thanh_e59cf158) : S.s_tam_dung_space_c826d0e6) : S.s_phat_space_7207d81e
    Accessible.role: Accessible.Button
    Accessible.name: tip
    onClicked: Player.toggle()

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Theme.accent
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Theme.pressInk
            opacity: root.pressed ? Theme.pressShade : (root.hovered ? 0.04 : 0)
            Behavior on opacity { NumberAnimation { duration: root.pressed ? Theme.motionFastOut : Theme.motionFast } }
        }
    }
    Icon {
        anchors.centerIn: parent
        anchors.horizontalCenterOffset: Player.playing ? 0 : 1
        name: Player.playing ? "pause" : "play"
        size: Math.round(root.size * 0.42)
        color: Theme.accentInk
    }
    // Cung quay khi đang chờ âm thanh
    Canvas {
        id: arc
        anchors.fill: parent
        anchors.margins: -4
        visible: Player.buffering && Player.playing
        onVisibleChanged: if (visible) requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.lineWidth = 2
            ctx.strokeStyle = Theme.accent
            ctx.beginPath()
            ctx.arc(width / 2, height / 2, width / 2 - 1, 0, Math.PI * 1.2)
            ctx.stroke()
        }
        RotationAnimator on rotation { from: 0; to: 360; duration: Theme.spinMs; loops: Animation.Infinite; running: arc.visible && Nav.uiVisible && !Theme.reduceMotion }
    }
}
