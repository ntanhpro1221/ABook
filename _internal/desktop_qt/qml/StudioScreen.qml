import QtQuick
import ABook
import "PeerStudio.js" as Peer

// Studio. Studio của máy này: chỗ giữ (chưa port). Studio của máy đã ghép vào được: bảng dự án gọn chỉ đọc (ProjectsList - tên · trạng thái ·
// tiến độ · cập nhật, DESIGN.md mục 7; ProjectsScreen.tsx của web).
// Studio của máy tính đã ghép (Nav.studioPeer, "Mở Studio" ở Máy tính khác; desktop/App.tsx + PeerBar.tsx): hỏi /api/app của máy ấy qua cầu nối
// (webui/peer_studio.py) và đặt Nav.peerInfo - vào được thì thanh "Đang mở Studio của <máy>" + "Về máy này" (PeerBar của Main, trên mọi màn);
// máy ấy chỉ cho nghe thì nói bật quyền ở đâu (StudioClosed, "Về Thư viện" = Thư viện của máy ấy); chưa vào được thì nói vì sao (PeerTrouble),
// máy ấy im thì tự hỏi lại mỗi 5 giây và tự mở khi nó trả lời.
Item {
    id: root
    // Bảng dự án rộng tới 1180 (max-w-[1180px] của ProjectsScreen); các màn khác giữ 800
    readonly property real bodyWidth: Math.min(width - 2 * Theme.margin, shownView === "open" ? 1180 : 800)
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
    function home() { Nav.goHome() }
    onPeerChanged: {
        peerInfo = null; trouble = ""; silent = false; watchedMs = 0
        library = null; libraryFailed = false; libraryAsked++
        if (peer) ask(); else asked++
    }

    // Danh sách dự án của máy ấy (useLibrary: GET /api/library qua cầu nối): hỏi lại mỗi 5 giây khi có cuốn đang chạy, không thì 15 giây
    property var library: null
    property bool libraryFailed: false
    property int libraryAsked: 0
    readonly property bool libraryLive: Boolean(library && Array.isArray(library.books) && library.books.some(b => b && (b.running || b.starting)))
    function loadLibrary() {
        const mine = ++libraryAsked
        const peer = root.peer
        if (!peer || !Api.transport) return
        Api.transport.request("GET", Peer.throughPeer("/api/library", peer), null, function(status, data) {
            if (mine !== root.libraryAsked || peer !== root.peer) return
            if (status >= 200 && status < 300 && data && typeof data === "object") {
                root.library = data
                root.libraryFailed = false
                return
            }
            root.libraryFailed = true
            if (status === 503 && data && data.unreachable) Nav.peerSilent = data.message || data.error || "Máy kia không trả lời"
        })
    }
    Connections { target: Nav; function onPeerRevisionChanged() { if (root.view === "open") root.loadLibrary() } }
    Timer {
        interval: root.libraryLive ? 5000 : 15000
        repeat: true
        running: root.view === "open" && Nav.peerSilent === ""
        onTriggered: root.loadLibrary()
    }
    Component.onCompleted: if (peer) ask()
    // Máy kia im: hỏi lại mỗi 5 giây, thôi sau 30 phút (watchUntilBack)
    Timer {
        interval: Peer.WATCH_EVERY_MS
        repeat: true
        running: root.view === "trouble" && root.silent && root.watchedMs < Peer.WATCH_GIVE_UP_MS
        onTriggered: { root.watchedMs += interval; root.ask() }
    }

    // Cho cả app biết đang xem máy nào (thanh trên cùng, Thư viện của máy ấy)
    Binding { target: Nav; property: "peerInfo"; value: root.peerInfo; when: root.peer !== "" }
    // Một lời gọi qua cầu nối gặp máy kia im (Nav.peerSilent): hỏi lại /api/app mỗi 5 giây; máy ấy trả lời thì các màn của máy ấy nạp lại (usePeerSilent)
    Timer {
        interval: Peer.WATCH_EVERY_MS
        repeat: true
        running: root.peer !== "" && Nav.peerSilent !== ""
        onTriggered: {
            const peer = root.peer
            if (!Api.transport) return
            Api.transport.request("GET", Peer.throughPeer("/api/app", peer), null, function(status, data) {
                if (peer !== root.peer || status < 200 || status >= 300) return
                root.peerInfo = data
                Nav.peerSilent = ""
                Nav.peerRevision++
            })
        }
    }
    // Đổi màn = mờ qua kèm trượt 8 px (MotionRegion của web): cái cũ khép hết rồi cái mới mới vào, không hai lớp chồng nhau
    property string shownView: view
    property real phase: 1
    onViewChanged: {
        swap.restart()
        if (view === "open" && !library) loadLibrary()
    }
    SequentialAnimation {
        id: swap
        NumberAnimation { target: root; property: "phase"; to: 0; duration: Theme.motionFastOut; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
        ScriptAction { script: root.shownView = root.view }      // màn MỚI NHẤT lúc cái cũ đã khép (đổi liền hai lần vẫn ra đúng màn cuối)
        NumberAnimation { target: root; property: "phase"; to: 1; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
    }
    // Cả màn cuộn (đầu màn đi cùng bảng, như trang web)
    Flickable {
        id: page
        objectName: "studioPage"
        anchors.fill: parent
        contentWidth: width
        contentHeight: Math.max(height, root.shownView === "open" ? body.y + projects.implicitHeight + 64 : height)
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        interactive: contentHeight > height
        SmoothWheel { flick: page }
        ScreenHeader {
            id: header
            x: (root.width - root.bodyWidth) / 2
            width: root.bodyWidth
            title: "Studio"
            // Rỗng: lời giữa trang đã nói "Chưa có dự án" - dòng phụ giữ một dòng trống, không lặp lại
            subtitle: root.shownView === "open" ? (projects.books.length ? projects.books.length + " dự án" : "\u00a0") : ""
        }
        Item {
            id: body
            x: (root.width - root.bodyWidth) / 2
            y: header.y + header.height
            width: root.bodyWidth
            height: page.contentHeight - y
            opacity: root.phase
            transform: Translate { y: Theme.reduceMotion ? 0 : 8 * (1 - root.phase) }
            Text {
                objectName: "studioPlaceholder"
                visible: root.shownView === "own"
                anchors.centerIn: parent
                anchors.verticalCenterOffset: 40 - body.y / 2
                width: root.bodyWidth
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                text: "Studio chưa mở trong bản này."
                color: Theme.text2
                font.pixelSize: Theme.sizeBodySmall
            }
            // Máy ấy cho sửa: bảng dự án của nó (chỉ đọc)
            ProjectsList {
                id: projects
                objectName: "projectsTable"
                visible: root.shownView === "open"
                width: parent.width
                library: root.library
                loading: root.library === null && !root.libraryFailed
                failed: root.libraryFailed
                peer: root.peer
                computer: Peer.listenOnlyOwner(root.peerInfo)
                onRetry: root.loadLibrary()
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
                // Thư viện của máy đang xem (navigate("/") của web, vẫn trong trang của máy ấy) - không phải của máy này
                Button { objectName: "studioClosedLibrary"; text: "Về Thư viện"; onClicked: Nav.showLibrary() }
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
    Scrollbar { target: page }
}
