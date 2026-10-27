import QtQuick
import ABook
import "LibraryBooks.js" as Books
import "PeerStudio.js" as Peer

// Thư viện: lưới bìa luôn mở (DESIGN.md mục 7). Số cột tự giãn để bìa rộng 160-200 px theo cửa sổ; bàn phím di chuyển giữa các ô,
// Enter mở trang sách, F5 tải lại. Lưới chỉ dựng ô đang thấy; bìa giải mã ngoài luồng giao diện đúng cỡ hiển thị.
// Đang xem máy tính đã ghép (Nav.studioPeer, "Về Thư viện" từ Studio của máy ấy): thư viện của MÁY ẤY qua cầu nối, như trang `?peer=` của web.
FocusScope {
    id: root
    signal openBook(var book)
    signal addRequested(var paths)
    signal openFileRequested()
    signal studioRequested()
    property bool fileOpening: false

    readonly property real avail: Math.max(0, width - 2 * Theme.margin)
    readonly property int gap: Theme.s24
    readonly property int cols: Math.max(1, Math.min(Math.floor((avail + gap) / (Theme.coverMin + gap)), Math.ceil((avail + gap) / (Theme.coverMax + gap))))
    property real coverW: Math.min(Theme.coverMax, (avail - (cols - 1) * gap) / cols)
    Behavior on coverW {
        NumberAnimation {
            duration: Theme.reduceMotion ? 0 : Theme.motionMedium
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }
    readonly property real cellW: coverW + gap
    // ---- thư viện của máy đang xem (máy kia) ----
    readonly property string peer: Nav.studioPeer
    property var peerBooks: []
    property bool peerLoading: false
    property string peerError: ""
    property int peerAsked: 0
    function loadPeer() {
        const mine = ++peerAsked
        const peer = root.peer
        if (!peer || !Api.transport) return
        if (!peerBooks.length) peerLoading = true
        Api.transport.request("GET", Peer.throughPeer("/api/listen/library", peer), null, function(status, data) {
            if (mine !== root.peerAsked || peer !== root.peer) return
            peerLoading = false
            if (status >= 200 && status < 300) {
                peerBooks = Books.books(data, peer)
                peerError = ""
                return
            }
            peerError = data && (data.message || data.error) || "Chưa lấy được thư viện. Bạn thử lại."
            // máy ấy im: thanh trên cùng báo và tự nối lại (PEER_SILENT_EVENT)
            if (data && data.unreachable) Nav.peerSilent = data.error || data.message || "Máy kia không trả lời"
        })
    }
    onPeerChanged: { peerBooks = []; peerError = ""; current = 0; if (peer) loadPeer(); else { peerAsked++; peerLoading = false } }
    Connections { target: Nav; function onPeerRevisionChanged() { if (root.peer) root.loadPeer() } }
    function refresh() { if (peer) loadPeer(); else Backend.refreshLibrary() }
    function bookAt(index) { return peer ? (peerBooks[index] || ({})) : Backend.library.book(index) }

    readonly property bool failed: !peer && Backend.state === Backend.Failed
    readonly property bool loading: peer ? peerLoading : !failed && !Backend.libraryLoaded
    readonly property int count: peer ? peerBooks.length : Backend.library.count
    readonly property bool libraryError: peer ? peerError !== "" : Backend.library.error !== ""
    readonly property string libraryErrorText: peer ? peerError : Backend.library.error
    property int current: 0              // ô đang giữ tiêu điểm bàn phím (chỉ số trong danh sách)
    property alias list: list

    function select(index) {
        current = Math.max(0, Math.min(count - 1, index))
        list.positionViewAtIndex(Math.floor(current / cols), ListView.Contain)
    }

    ScreenHeader {
        id: header
        x: Theme.margin
        width: parent.width - 2 * Theme.margin
        title: "Thư viện"
        subtitle: root.loading || root.failed || root.count === 0 ? "" : root.count + " cuốn"
        // Thêm sách vào máy đang xem chưa có ở bản này: nút chỉ ở thư viện của máy này
        Button { visible: !root.peer; text: "Thêm sách"; icon: "plus"; kind: "ghost"; onClicked: root.addRequested([]) }
    }

    // Kéo file vào thư viện (DropToAdd.tsx): thả một hay nhiều file thì mở "Thêm sách" ở đúng hàng xem trước; đang có hộp khác mở thì nhắc đóng hộp rồi thả lại
    DropArea {
        id: dropArea
        anchors.fill: parent
        z: 5
        onEntered: drag => { drag.accepted = drag.hasUrls }
        onDropped: drop => {
            if (!drop.hasUrls) return
            const paths = drop.urls.map(url => DesktopApi.localPath(url)).filter(path => path !== "")
            if (!paths.length) return
            drop.acceptProposedAction()
            if (Nav.layers.length > 0) Api.notice = "Đóng hộp đang mở rồi thả lại file nhé"
            else root.addRequested(paths)
        }
        ImportDrop { anchors.fill: parent; shown: dropArea.containsDrag && Nav.layers.length === 0 }
    }

    // Lưới ảo hoá theo HÀNG: mỗi delegate là một hàng N ô, cao bằng ô cao nhất của hàng (tên dài xuống dòng đủ, không cắt).
    ListView {
        id: list
        anchors.top: header.bottom
        anchors.topMargin: Theme.s16
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        visible: !root.loading && !root.failed && root.count > 0
        focus: true
        clip: true
        model: root.count > 0 ? Math.ceil(root.count / root.cols) : 0
        bottomMargin: Theme.s32
        cacheBuffer: 400
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: false
        reuseItems: true

        delegate: Item {
            id: rowItem
            required property int index
            readonly property int first: index * root.cols
            width: ListView.view.width
            height: cells.childrenRect.height + root.gap
            Item {
                id: cells
                readonly property int count: Math.max(0, Math.min(root.cols, root.count - rowItem.first))
                objectName: "libraryGridRow"
                width: count * root.cellW - root.gap
                x: (parent.width - width) / 2
                Behavior on x {
                    NumberAnimation {
                        duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: Theme.easeStandard
                    }
                }
                Repeater {
                    model: cells.count
                    BookCell {
                        id: cell
                        required property int index
                        readonly property int at: rowItem.first + index
                        readonly property var info: { Backend.library.revision; root.peerBooks; return root.bookAt(at) }
                        x: index * root.cellW
                        Behavior on x {
                            NumberAnimation {
                                duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                                easing.type: Easing.BezierSpline
                                easing.bezierCurve: Theme.easeStandard
                            }
                        }
                        coverWidth: root.coverW
                        title: info.title || ""
                        subtitle: info.subtitle || ""
                        coverKey: info.coverKey || ""
                        progress: info.progress || 0
                        source: info.source || ""
                        externalFocus: at === root.current && list.activeFocus
                        // Sách của máy đang xem: trang sách / nghe qua cầu nối chưa có ở bản này (PROGRESS.md D4 Open) - ô chỉ để xem
                        enabled: !root.peer
                        onClicked: {
                            root.current = at
                            list.forceActiveFocus(Qt.MouseFocusReason)
                            root.openBook(info)
                        }
                    }
                }
            }
        }
        Keys.onReturnPressed: if (!root.peer) root.openBook(Backend.library.book(root.current))
        Keys.onEnterPressed: if (!root.peer) root.openBook(Backend.library.book(root.current))
        Keys.onPressed: (event) => {
            const rows = Math.max(1, Math.floor(height / (Theme.coverMax * Theme.coverRatio)) - 1)
            let handled = true
            switch (event.key) {
            case Qt.Key_Left: root.select(root.current - 1); break
            case Qt.Key_Right: root.select(root.current + 1); break
            case Qt.Key_Up: root.select(root.current - root.cols); break
            case Qt.Key_Down: root.select(root.current + root.cols); break
            case Qt.Key_PageUp: root.select(root.current - rows * root.cols); break
            case Qt.Key_PageDown: root.select(root.current + rows * root.cols); break
            case Qt.Key_Home: root.select(0); break
            case Qt.Key_End: root.select(root.count - 1); break
            case Qt.Key_F5: root.refresh(); break
            case Qt.Key_R:
                if (event.modifiers & Qt.ControlModifier) root.refresh()
                else handled = false
                break
            default: handled = false
            }
            event.accepted = handled
        }
        SmoothWheel { flick: list }
        Scrollbar { target: list }
    }

    // Đang tải: khung xám đúng hình nội dung, nhịp mờ 0,6 <-> 1 chu kỳ 1,6 s (DESIGN.md 2). Không vòng xoay.
    Item {
        id: skeleton
        readonly property real skeletonCellH: Math.round(root.coverW * Theme.coverRatio) + 71 + root.gap
        anchors.top: header.bottom
        anchors.topMargin: Theme.s16
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        clip: true
        visible: root.loading
        SequentialAnimation {
            running: skeleton.visible && !Theme.reduceMotion
            loops: Animation.Infinite
            OpacityAnimator { target: skeleton; from: 1; to: 0.6; duration: 800; easing.type: Easing.InOutSine }
            OpacityAnimator { target: skeleton; from: 0.6; to: 1; duration: 800; easing.type: Easing.InOutSine }
        }
        Repeater {
            model: Math.max(0, root.cols * Math.ceil(skeleton.height / skeleton.skeletonCellH))
            Item {
                required property int index
                x: (root.width - (root.cols * root.cellW - root.gap)) / 2 + (index % root.cols) * root.cellW
                y: Math.floor(index / root.cols) * skeleton.skeletonCellH
                width: root.coverW
                height: skeleton.skeletonCellH
                Rectangle { width: parent.width; height: Math.round(root.coverW * Theme.coverRatio); radius: Theme.radiusCover; color: Theme.sunken }
                Rectangle { y: Math.round(root.coverW * Theme.coverRatio) + 14; width: parent.width * 0.85; height: 12; radius: Theme.radiusControl; color: Theme.sunken }
                Rectangle { y: Math.round(root.coverW * Theme.coverRatio) + 34; width: parent.width * 0.5; height: 10; radius: Theme.radiusControl; color: Theme.sunken }
            }
        }
    }

    // Trống / lỗi: một câu + một nút dẫn tới việc tiếp theo (DESIGN.md 2). Lỗi nói tại chỗ cách sửa, không hộp thoại chặn.
    Column {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 40
        spacing: Theme.s16
        visible: root.failed || root.libraryError || (!root.loading && root.count === 0)
        // Thư viện trống (EmptyLibrary của desktop/App.tsx): ô icon tai nghe, một câu + một nút chính "Thêm sách"; các lối khác cùng kiểu chữ-có-icon ở hàng dưới
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !root.failed && !root.libraryError
            width: 56; height: 56; radius: Theme.radiusCover
            color: Theme.accentSoft
            Icon { anchors.centerIn: parent; name: "headphones"; size: 28; color: Theme.accentText }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.failed ? "Chưa mở được ABook" : (root.libraryError ? "Chưa tải được thư viện" : "Chưa có sách")
            color: Theme.text
            font.pixelSize: Theme.sizeSection
            font.weight: Theme.weightMedium
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(root.width - 2 * Theme.margin, 460)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: root.failed ? Backend.message : (root.libraryError ? root.libraryErrorText : root.peer ? "" : "Thêm truyện hoặc tạo sách nói.")
            visible: text !== ""
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
        }
        Button {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.failed || root.libraryError
            text: "Thử lại"
            onClicked: root.failed ? Backend.restart() : root.refresh()
        }
        Button {
            objectName: "emptyAdd"
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !root.failed && !root.libraryError && !root.peer
            text: "Thêm sách"
            icon: "plus"
            size: "lg"
            onClicked: root.addRequested([])
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: !root.failed && !root.libraryError && !root.peer
            spacing: 4
            Button { objectName: "emptyStudio"; text: "Tạo sách nói"; icon: "clapperboard"; kind: "ghost"; onClicked: root.studioRequested() }
            Button { objectName: "emptyOpenFile"; text: root.fileOpening ? "Đang mở…" : "Mở file sách"; icon: "file-audio"; kind: "ghost"; enabled: !root.fileOpening; onClicked: root.openFileRequested() }
        }
    }

    Component.onCompleted: { list.forceActiveFocus(); if (peer) loadPeer() }
    onVisibleChanged: if (visible) list.forceActiveFocus()
}
