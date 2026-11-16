import QtQuick
import ABook

// Nút phụ: icon trơn, vùng bấm 40x40 trên máy tính, chú thích khi rê chuột (DESIGN.md mục 6b).
Interactive {
    id: root
    property bool pending: false
    property bool indicateRequest: true
    property int ownedRequest: 0
    signal activated()
    Listen { target: Api; function onRequestDone(id) { if (root.ownedRequest === id) root.ownedRequest = 0 } }
    onClicked: {
        if (ownedRequest > 0) return
        const before = Api.requestSerial
        root.activated()
        if (Api.requestSerial !== before && Api.requestsPending[Api.requestSerial]) root.ownedRequest = Api.requestSerial
    }
    property string icon: ""
    property int iconSize: 20
    property color ink: Theme.text           // nút ✕ của hộp thoại: mực ba, rê chuột thì mực thường
    property color hoverInk: ink
    implicitWidth: Theme.buttonHeight
    implicitHeight: Theme.buttonHeight
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.pressed ? 0.10 : (root.hovered ? 0.06 : 0)
        Behavior on opacity { NumberAnimation { duration: root.pressed ? Theme.motionFastOut : Theme.motionFast } }
    }
    PendingIndicator { id: wait; anchors.centerIn: parent; pending: root.pending || (root.indicateRequest && root.ownedRequest > 0); color: root.ink }
    StateIcon {
        anchors.centerIn: parent
        name: wait.shown ? "" : root.icon
        size: root.iconSize
        color: root.hovered ? root.hoverInk : root.ink
    }
}
