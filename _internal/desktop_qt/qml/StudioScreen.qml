import QtQuick
import ABook
import "PeerStudio.js" as Peer

// Studio: chỗ giữ cho D3 (bảng dự án gọn: tên · trạng thái · tiến độ · cập nhật, DESIGN.md mục 7).
// Studio của máy tính đã ghép (Nav.studioPeer, "Mở Studio" ở Máy tính khác; desktop/App.tsx + PeerBar.tsx): hỏi /api/app của máy ấy qua cầu nối
// (webui/peer_studio.py) - vào được thì thanh "Đang mở Studio của <máy>" + "Về máy này"; máy ấy chỉ cho nghe thì nói bật quyền ở đâu (StudioClosed);
// chưa vào được thì nói vì sao (PeerTrouble), máy ấy im thì tự hỏi lại mỗi 5 giây và tự mở khi nó trả lời.
Item {
    id: root
    UiActivity { target: root; id: activity; onResumed: root.ask() }
    readonly property bool expanded: Theme.widthClass(width) >= 2
    property real wideT: expanded ? 1 : 0
    Behavior on wideT {
        NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
    }
    readonly property real bodyWidth: Math.min(width - 2 * Theme.margin, 800)
    readonly property string peer: Nav.studioPeer
    property var peerInfo: null         // /api/app của máy kia (có peer.name, listenOnly)
    property string trouble: ""         // lời máy chủ khi chưa vào được ("" = chưa có lỗi)
    property bool silent: false         // máy kia không trả lời (503 unreachable): hỏi lại tới khi nó về
    property int asked: 0
    property real watchedMs: 0
    // Màn đang hiện: "own" Studio của máy này, "loading" đang hỏi máy kia, "open" đã vào, "closed" chỉ được nghe, "trouble" chưa vào được
    readonly property string view: !peer ? "own" : peerInfo ? (peerInfo.listenOnly ? "closed" : "open") : trouble !== "" ? "trouble" : "loading"

    function ask() {
        const mine = ++asked
        const peer = root.peer
        if (!peer || !Api.transport) return
        Api.transport.request("GET", Peer.throughPeer("/api/app", peer), null, function(status, data) {
            if (mine !== root.asked || peer !== root.peer) return
            if (status >= 200 && status < 300) {
                root.peerInfo = data
                root.trouble = ""
                root.silent = false
                return
            }
            root.trouble = data && (data.message || data.error) || "Máy kia không trả lời"
            root.silent = Boolean(data && data.unreachable)
        })
    }
    function home() { Nav.studioPeer = "" }
    onPeerChanged: {
        peerInfo = null; trouble = ""; silent = false; watchedMs = 0
        if (peer) ask(); else asked++
    }
    Component.onCompleted: if (peer) ask()
    // Máy kia im: hỏi lại mỗi 5 giây, thôi sau 30 phút (watchUntilBack)
    Timer {
        interval: Peer.WATCH_EVERY_MS
        repeat: true
        running: activity.running && root.view === "trouble" && root.silent && root.watchedMs < Peer.WATCH_GIVE_UP_MS
        onTriggered: { root.watchedMs += interval; root.ask() }
    }

    PeerBar {
        id: bar
        objectName: "peerBar"
        width: root.width
        open: root.view === "open"
        name: root.peerInfo && root.peerInfo.peer ? root.peerInfo.peer.name : ""
        listenOnly: Boolean(root.peerInfo && root.peerInfo.listenOnly)
        contentX: (root.width - root.bodyWidth) / 2
        contentWidth: root.bodyWidth
        onHome: root.home()
    }
    ScreenHeader {
        id: header
        x: (parent.width - root.bodyWidth) / 2
        y: bar.height
        width: root.bodyWidth
        title: "Studio"
    }
    // Đổi màn = mờ qua kèm trượt 8 px (MotionRegion của web): cái cũ khép hết rồi cái mới mới vào, không hai lớp chồng nhau
    property string shownView: view
    property real phase: 1
    onViewChanged: swap.restart()
    SequentialAnimation {
        id: swap
        NumberAnimation { target: root; property: "phase"; to: 0; duration: Theme.motionFastOut; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
        ScriptAction { script: root.shownView = root.view }      // màn MỚI NHẤT lúc cái cũ đã khép (đổi liền hai lần vẫn ra đúng màn cuối)
        NumberAnimation { target: root; property: "phase"; to: 1; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
    }
    Item {
        id: body
        x: (parent.width - root.bodyWidth) / 2
        y: header.y + header.height
        width: root.bodyWidth
        height: parent.height - y
        opacity: root.phase
        transform: Translate { y: Theme.reduceMotion ? 0 : 8 * (1 - root.phase) }
        Item {
            objectName: "studioStatus"
            visible: root.shownView === "own" || root.shownView === "open"
            anchors.centerIn: parent
            anchors.verticalCenterOffset: 40 - body.y / 2
            width: Math.min(parent.width, statusLabel.implicitWidth + 80)
            height: Math.max(48, statusLabel.y + statusLabel.height)
            Icon {
                id: statusIcon
                name: "clapperboard"; size: 48; color: Theme.text3
                x: (parent.width - width) / 2 * (1 - Math.min(1, root.wideT * 2))
            }
            Text {
                id: statusLabel
                objectName: "studioPlaceholder"
                x: 80 * Math.min(1, root.wideT * 2)
                y: 72 * (1 - Math.max(0, root.wideT * 2 - 1))
                width: Math.min(640, parent.width - x)
                height: Math.max(48, implicitHeight)
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: root.expanded ? Text.AlignLeft : Text.AlignHCenter
                wrapMode: Text.Wrap
                text: "Studio chưa mở trong bản này."
                color: Theme.text2
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        // Thiết bị này chỉ được nghe ở máy kia (StudioClosed): nói bật quyền ở đâu
        EmptyState {
            objectName: "studioClosed"
            visible: root.shownView === "closed"
            y: 96          // mt-24 của web; EmptyState tự đệm 56 trên dưới
            width: parent.width
            icon: "clapperboard"
            title: Peer.listenOnlyLine(Peer.listenOnlyOwner(root.peerInfo))
            text: "Sách của máy ấy vẫn nghe được ở Thư viện."
            Button { objectName: "studioClosedLibrary"; text: "Về Thư viện"; onClicked: { root.home(); if (Nav.stack) Nav.stack.show(0) } }
        }
        // Chưa vào được Studio của máy kia (PeerTrouble): lời máy chủ; máy ấy im thì tự mở lại khi nó trả lời
        EmptyState {
            objectName: "peerTrouble"
            visible: root.shownView === "trouble"
            y: 96          // mt-24 của web; EmptyState tự đệm 56 trên dưới
            width: parent.width
            icon: "laptop"
            title: root.trouble
            text: root.silent ? "Studio tự mở khi máy ấy trả lời lại." : ""
            Button { objectName: "peerTroubleHome"; text: "Về máy này"; onClicked: root.home() }
        }
    }
}
