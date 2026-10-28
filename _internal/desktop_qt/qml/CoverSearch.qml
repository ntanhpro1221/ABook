import QtQuick
import ABook
import "EditBookLogic.js" as Logic

// "Tìm ảnh bìa" (CoverSearchPanel của shared/CoverSearch.tsx): hỏi iTunes, Open Library, Google Books theo tên bộ truyện; người dùng chọn một
// ảnh thì `PUT /api/books/<mã>/cover {url}` (máy chủ tự tải, chỉ từ nguồn đã cho phép). Chỉ là gợi ý - không bao giờ tự đặt. Là MỘT BƯỚC của hộp
// "Sửa sách" (EditBook.qml dựng lớp Back và nút "Sửa sách" quay lại). `begin` mỗi lần vào bước: ô tìm điền tên bộ truyện và tự tìm một lần.
// Lời đáp về muộn (đã rời bước / đã tìm lại) bị bỏ: `cancel()` tăng `generation` và huỷ yêu cầu còn bay; ảnh chọn xong mà bị bỏ không đè
// lên bìa người dùng đặt sau (máy chủ cũng kiểm thứ tự, 409 thì im lặng).
Item {
    id: root
    property string bookId: ""
    property string query: ""
    property var results: []              // [{provider, title, author, thumb, url}]
    property var failed: []               // tên nguồn không hỏi được
    property bool searched: false         // đã có lời đáp (kể cả rỗng)
    property bool searching: false
    property bool choosing: false
    property var chosenFound: null        // ảnh đang được đặt (vòng xoay trên ô ấy)
    property bool searchError: false
    property bool chooseError: false
    property var broken: ({})             // ảnh nhỏ tải lỗi: bỏ khỏi lưới, không để ô trống mà vẫn bấm được
    property int generation: 0
    property int searchRequest: 0
    property int chooseRequest: 0
    readonly property var shown: results.filter(found => !broken[found.thumb])
    readonly property bool hasGrid: !searching && !searchError && shown.length > 0
    readonly property bool hasEmpty: searched && !searching && !searchError && failed.length === 0 && shown.length === 0
    readonly property real gridWidth: width - 4
    readonly property int columns: Math.max(1, Math.floor((gridWidth + 12) / 132))
    readonly property real cell: (gridWidth - (columns - 1) * 12) / columns
    signal chosen()
    signal chooseFile()
    implicitHeight: form.height + 16 + area.height
    height: implicitHeight

    function request(method, path, body, done) {
        return Api.transport ? Api.transport.request(method, path, body, done) : 0
    }
    function begin(id, defaultQuery) {
        cancel()
        bookId = id; query = defaultQuery || ""
        results = []; failed = []; broken = ({}); searched = false; searchError = false; chooseError = false; chosenFound = null
        search()
    }
    // Rời bước (Back, ✕, quay lại): lượt tìm và lượt đặt bìa đang bay không được về sau đó.
    function cancel() {
        generation++
        if (searchRequest && Api.transport) Api.transport.cancel(searchRequest)
        if (chooseRequest && Api.transport) Api.transport.cancel(chooseRequest)
        searchRequest = 0; chooseRequest = 0
        searching = false; choosing = false
    }
    function search() {
        if (searchRequest && Api.transport) Api.transport.cancel(searchRequest)
        generation++
        const mine = generation
        searching = true; searchError = false
        searchRequest = request("GET", "/api/books/" + bookId + "/cover/search?q=" + encodeURIComponent(query), null, function(status, data) {
            if (mine !== root.generation) return
            root.searchRequest = 0; root.searching = false
            if (status < 200 || status >= 300) { root.searchError = true; return }
            root.results = data.results || []; root.failed = data.failed || []; root.broken = ({}); root.searched = true
        })
    }
    function choose(found) {
        if (choosing) return
        const mine = generation
        choosing = true; chooseError = false; chosenFound = found
        chooseRequest = request("PUT", "/api/books/" + bookId + "/cover", {url: found.url}, function(status, data) {
            if (mine !== root.generation) return
            root.chooseRequest = 0; root.choosing = false
            if (status === 409) { root.chosenFound = null; return }
            if (status < 200 || status >= 300) { root.chooseError = true; return }
            root.chosen()
        })
    }
    function markBroken(found) { const next = Object.assign({}, broken); next[found.thumb] = true; broken = next }
    Component.onDestruction: cancel()

    Item {
        id: form
        width: parent.width
        height: Math.max(40, queryField.height)
        FormField {
            id: queryField
            objectName: "coverQuery"
            width: parent.width - find.width - 8
            label: "Tên sách để tìm bìa"
            placeholderText: "Tên sách (tiếng Anh thường cho nhiều kết quả hơn)"
            text: root.query
            onTextChanged: root.query = text
            onAccepted: root.search()
        }
        Button {
            id: find
            objectName: "coverFind"
            x: parent.width - width
            text: "Tìm"
            icon: "search"
            busy: root.searching
            onActivated: root.search()
        }
    }

    // Khung kết quả: cao tối đa 55 % cửa sổ, cuộn trong khung (max-h-[55vh])
    Item {
        id: area
        y: form.height + 16
        width: parent.width
        height: Math.min(flick.contentHeight, (Window.window ? Window.window.height : 900) * 0.55)
        Flickable {
            id: flick
            anchors.fill: parent
            contentWidth: width
            contentHeight: stack.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: stack
                x: 2
                width: flick.width - 4
                Collapse {
                    width: parent.width
                    open: root.searching
                    EditBookSkeleton { width: parent.width; shape: "covers"; count: 4; label: "Đang tìm ảnh bìa" }
                }
                EditBookError {
                    width: parent.width
                    open: root.searchError && !root.searching
                    message: "Bạn hãy kiểm tra kết nối rồi tìm lại ảnh bìa."
                    onRetry: root.search()
                }
                Collapse {
                    width: parent.width
                    open: root.hasGrid
                    Flow {
                        id: grid
                        objectName: "coverGrid"
                        width: parent.width
                        spacing: 12
                        Repeater {
                            model: root.shown
                            Interactive {
                                id: tile
                                required property var modelData
                                width: root.cell
                                height: photo.height + caption.height + provider.height + 12 + 6 + 2
                                enabled: !root.choosing
                                opacity: enabled ? 1 : 0.5
                                Accessible.role: Accessible.Button
                                Accessible.name: Logic.coverTitle(modelData)
                                tip: Logic.coverTitle(modelData)
                                pressScaling: false
                                onClicked: root.choose(modelData)
                                Rectangle {
                                    anchors.fill: parent
                                    radius: Theme.radiusControl
                                    color: Theme.hover
                                    opacity: tile.hovered ? 1 : 0
                                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                                }
                                Rectangle {
                                    id: photo
                                    x: 6; y: 6
                                    width: parent.width - 12
                                    height: width * 1.5
                                    radius: Theme.radiusControl
                                    color: Theme.hover
                                    Image {
                                        anchors.fill: parent
                                        source: tile.modelData.thumb || ""
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        onStatusChanged: if (status === Image.Error) root.markBroken(tile.modelData)
                                    }
                                    // Ảnh đang được đặt: phủ tối + vòng xoay (bg-cover-overlay text-cover-ink)
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: Theme.radiusControl
                                        color: Qt.rgba(18 / 255, 17 / 255, 16 / 255, 0.72)
                                        opacity: root.choosing && root.chosenFound && root.chosenFound.url === tile.modelData.url ? 1 : 0
                                        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                                        Icon {
                                            anchors.centerIn: parent
                                            name: "loader-circle"
                                            size: 20
                                            color: "#ffffff"
                                            RotationAnimator on rotation { running: root.choosing && Nav.uiVisible && !Theme.reduceMotion; from: 0; to: 360; duration: 1000; loops: Animation.Infinite }
                                        }
                                    }
                                }
                                Text {
                                    id: caption
                                    x: 6; y: photo.y + photo.height + 6
                                    width: parent.width - 12
                                    text: tile.modelData.title
                                    color: Theme.text
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: Theme.sizeCaption
                                    font.weight: Theme.weightMedium
                                }
                                Text {
                                    id: provider
                                    x: 6; y: caption.y + caption.height + 2
                                    width: parent.width - 12
                                    text: tile.modelData.provider
                                    color: Theme.text3
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: 11
                                }
                            }
                        }
                    }
                }
                Collapse {
                    width: parent.width
                    open: root.hasEmpty
                    Column {
                        width: parent.width
                        topPadding: 32
                        bottomPadding: 32
                        spacing: 0
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 56; height: 56
                            radius: Theme.radiusCover
                            color: Theme.accentSoft
                            Icon { anchors.centerIn: parent; name: "search"; size: 28; color: Theme.accentText }
                        }
                        Item { width: 1; height: 16 }
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            text: "Bạn hãy chọn ảnh trên máy"
                            color: Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBody
                            font.weight: 600
                        }
                        Item { width: 1; height: 20 }
                        Button {
                            objectName: "coverPickFile"
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "Chọn ảnh"
                            kind: "ghost"
                            onClicked: { root.cancel(); root.chooseFile() }
                        }
                    }
                }
                EditBookError {
                    width: parent.width
                    open: root.failed.length > 0
                    message: "Bạn hãy kiểm tra kết nối rồi tìm lại các nguồn bìa."
                    onRetry: root.search()
                }
                EditBookError {
                    width: parent.width
                    open: root.chooseError
                    message: "Bạn hãy kiểm tra kết nối rồi đặt lại ảnh bìa."
                    onRetry: if (root.chosenFound) root.choose(root.chosenFound)
                }
            }
        }
        ScrollEdges { target: flick; color: Theme.panel; x: flick.x; y: flick.y; width: flick.width; height: flick.height }
        Scrollbar { target: flick }
    }
}
