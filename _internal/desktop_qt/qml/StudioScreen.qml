import QtQuick
import ABook
import "PeerStudio.js" as Peer

// Studio: danh sách dự án (ProjectsScreen), trang một dự án (ProjectScreen) và trình tạo dự án (NewProjectScreen), DESIGN.md mục 7. Ba màn con là MỘT lớp
// của Back (Esc / Alt+Left về danh sách) và đổi qua nhau bằng mờ + trượt 8 px; chọn lại "Studio" ở thanh bên cũng về danh sách.
// Studio của máy tính đã ghép (Nav.studioPeer, "Mở Studio" ở Máy tính khác; desktop/App.tsx + PeerBar.tsx): hỏi /api/app của máy ấy qua cầu nối
// (webui/peer_studio.py) - vào được thì thanh "Đang mở Studio của <máy>" + "Về máy này" và CÙNG các màn con ấy, mọi lời gọi đi qua
// /api/peers/<mã>/studio/... (StudioStore); máy ấy chỉ cho nghe thì nói bật quyền ở đâu (StudioClosed); chưa vào được thì nói vì sao (PeerTrouble),
// máy ấy im thì tự hỏi lại mỗi 5 giây và tự mở khi nó trả lời.
Item {
    id: root
    UiActivity { target: root; id: activity; onResumed: { root.ask(); dataStore.refreshNow() } }
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
        goList()
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
    // ---- dữ liệu và đường đi ----
    StudioStore {
        id: dataStore
        peer: root.peer
        peerInfo: root.peerInfo
        active: activity.running
        libraryWanted: (root.view === "own" || root.view === "open") && root.route === "list"
    }
    readonly property var studioStore: dataStore
    readonly property var projectsScreenModel: projects.rowKeys
    readonly property string projectsKind: projects.kind
    readonly property var projectsList: projects.list
    readonly property string shownTab: projectLoader.item ? projectLoader.item.shownTab : ""
    readonly property var projectScreenList: projectLoader.item ? projectLoader.item.list : null
    property string route: "list"           // "list" | "project" | "new"
    property string newMode: ""             // "" | "redo" | "continue"
    property bool layerOpen: false
    property bool newAfterPeer: false       // "Tạo trên <máy>": vào Studio của máy ấy rồi mở thẳng trình tạo
    property bool pickNow: false            // tới từ nút "Dự án mới": mở luôn hộp chọn file
    readonly property var newStore: newLoader.item
    function goList() { route = "list"; newMode = ""; pickNow = false }
    function openProject(id) { dataStore.openBook(id); route = "project"; pickNow = false }
    // Trình tạo dựng muộn (lần đầu mở) và sống tiếp để nháp không mất khi rời trang; "Sửa thiết lập" / "Làm tiếp" điền sẵn từ máy chủ một lần
    function openNew(mode, id) {
        newMode = mode || ""
        newLoader.active = true
        pickNow = !newMode
        route = "new"
        if (newMode === "redo") newStore.loadRedo(id)
        else if (newMode === "continue") newStore.loadContinuation(id)
    }
    onViewChanged: if (view === "open" && newAfterPeer) { newAfterPeer = false; openNew("", "") }
    onRouteChanged: {
        if (route === "list") { dataStore.openBook(""); if (layerOpen) { Nav.closedLayer(routeLayer); layerOpen = false } }
        else if (!layerOpen) { Nav.openLayer(routeLayer); layerOpen = true }
    }
    QtObject { id: routeLayer; readonly property bool route: true; function close() { root.goList() } }
    Component.onDestruction: if (layerOpen) Nav.closedLayer(routeLayer)
    Connections { target: Nav.stack; function onReselected(index) { if (index === 1) root.goList() } }

    // Màn đang hiện: mờ qua kèm trượt 8 px (MotionRegion của web); cái cũ khép hết rồi cái mới mới vào, không hai lớp chồng nhau
    readonly property string screenKey: (view === "own" || view === "open") ? "route:" + route : view
    property string shownKey: screenKey
    property real phase: 1
    onScreenKeyChanged: swap.restart()
    SequentialAnimation {
        id: swap
        NumberAnimation { target: root; property: "phase"; to: 0; duration: Theme.motionFastOut; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
        ScriptAction { script: root.shownKey = root.screenKey }      // màn MỚI NHẤT lúc cái cũ đã khép (đổi liền hai lần vẫn ra đúng màn cuối)
        NumberAnimation { target: root; property: "phase"; to: 1; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
    }
    readonly property string shownView: shownKey.indexOf("route:") === 0 ? (peer ? "open" : "own") : shownKey

    // ---- danh sách / trang dự án / chỗ giữ cho trình tạo ----
    Item {
        id: content
        objectName: "studioContent"
        y: bar.height
        width: parent.width
        height: parent.height - y
        visible: root.shownView === "own" || root.shownView === "open"
        opacity: root.phase
        transform: Translate { y: Theme.reduceMotion ? 0 : 8 * (1 - root.phase) }
        // Dữ liệu của trình tạo sách: dựng muộn, sống tiếp khi rời trang (nháp không mất)
        Loader {
            id: newLoader
            active: false
            sourceComponent: NewProjectStore {
                store: dataStore
                active: root.route === "new"
                onCreated: id => root.openProject(id)
                onLeaveRequested: id => { if (id) root.openProject(id); else root.goList() }
            }
        }
        ProjectsScreen {
            id: projects
            objectName: "projectsScreen"
            anchors.fill: parent
            visible: root.shownKey === "route:list"
            enabled: visible
            store: dataStore
            onProjectOpened: id => root.openProject(id)
            onNewRequested: root.openNew("", "")
            onNewProjectRequested: (mode, id) => root.openNew(mode, id)
            onListenRequested: id => root.listen(id)
        }
        Loader {
            id: projectLoader
            anchors.fill: parent
            active: root.shownKey === "route:project"
            sourceComponent: ProjectScreen {
                objectName: "projectScreen"
                store: dataStore
                onBackRequested: root.goList()
                onListenRequested: id => root.listen(id)
                onNewProjectRequested: (mode, id) => root.openNew(mode, id)
            }
        }
        Loader {
            id: newScreenLoader
            anchors.fill: parent
            active: newLoader.active && root.shownKey === "route:new"
            sourceComponent: NewProjectScreen {
                objectName: "newProjectScreen"
                form: root.newStore
                pickOnOpen: root.pickNow
                onSetupRequested: root.goList()
                onProjectRequested: id => root.openProject(id)
                onPeerRequested: id => { root.newAfterPeer = true; Nav.openPeerStudio(id) }
            }
        }
    }
    function listen(id) {
        if (root.peer) { Api.notice = "Sách của máy ấy nghe ở Thư viện của máy ấy."; return }
        Nav.bookRequested(id)
    }

    // ---- các trạng thái của Studio máy khác ----
    ScreenHeader {
        id: header
        objectName: "studioHeader"
        visible: !content.visible
        x: (parent.width - root.bodyWidth) / 2
        y: bar.height
        width: root.bodyWidth
        title: "Studio"
    }
    Item {
        id: body
        objectName: "studioBody"
        x: (parent.width - root.bodyWidth) / 2
        y: header.y + header.height
        width: root.bodyWidth
        height: parent.height - y
        visible: !content.visible
        opacity: root.phase
        transform: Translate { y: Theme.reduceMotion ? 0 : 8 * (1 - root.phase) }
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
