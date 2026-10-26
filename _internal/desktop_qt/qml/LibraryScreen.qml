import QtQuick
import ABook

// Thư viện: lưới bìa luôn mở (DESIGN.md mục 7). Số cột tự giãn để bìa rộng 160-200 px theo cửa sổ; bàn phím di chuyển giữa các ô,
// Enter mở trang sách, F5 tải lại. Lưới chỉ dựng ô đang thấy; bìa giải mã ngoài luồng giao diện đúng cỡ hiển thị.
FocusScope {
    id: root
    signal openBook(var book)

    readonly property real avail: width - 2 * Theme.margin
    readonly property int gap: Theme.s24
    readonly property int cols: Math.max(2, Math.ceil((avail + gap) / (Theme.coverMax + gap)))
    readonly property real coverW: Math.floor((avail - (cols - 1) * gap) / cols)
    readonly property real cellW: coverW + gap
    readonly property real cellH: Math.round(coverW * Theme.coverRatio) + 71 + gap
    readonly property bool failed: Backend.state === Backend.Failed
    readonly property bool loading: !failed && !Backend.libraryLoaded
    readonly property int count: Backend.library.count
    readonly property bool libraryError: Backend.library.error !== ""
    property alias grid: grid

    ScreenHeader {
        id: header
        x: Theme.margin
        width: parent.width - 2 * Theme.margin
        title: "Thư viện"
        subtitle: root.loading || root.failed || root.count === 0 ? "" : root.count + " cuốn"
    }

    GridView {
        id: grid
        anchors.top: header.bottom
        anchors.topMargin: Theme.s16
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        visible: !root.loading && !root.failed && root.count > 0
        focus: true
        clip: true
        model: Backend.library
        cellWidth: root.cellW
        cellHeight: root.cellH
        leftMargin: Theme.margin
        rightMargin: Theme.margin - root.gap
        bottomMargin: Theme.s32
        cacheBuffer: root.cellH            // một hàng mỗi phía: bìa đã giải mã chiếm RAM (cỡ ô x 4 byte), hàng thứ hai chỉ làm RAM nghỉ phình
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        highlightFollowsCurrentItem: false
        reuseItems: true
        currentIndex: 0

        delegate: Item {
            id: cell
            required property int index
            required property string title
            required property string subtitle
            required property string coverKey
            required property real progress
            required property string source
            width: root.cellW
            height: root.cellH
            BookCell {
                title: cell.title
                subtitle: cell.subtitle
                coverKey: cell.coverKey
                progress: cell.progress
                source: cell.source
                coverWidth: root.coverW
                externalFocus: cell.GridView.isCurrentItem && grid.activeFocus
                onClicked: {
                    grid.currentIndex = cell.index
                    grid.forceActiveFocus(Qt.MouseFocusReason)
                    root.openBook(Backend.library.book(cell.index))
                }
            }
        }
        Keys.onReturnPressed: root.openBook(Backend.library.book(currentIndex))
        Keys.onEnterPressed: root.openBook(Backend.library.book(currentIndex))
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_F5 || (event.key === Qt.Key_R && (event.modifiers & Qt.ControlModifier))) {
                Backend.refreshLibrary()
                event.accepted = true
            } else if (event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp) {
                const rows = Math.max(1, Math.floor(height / root.cellH) - 1)
                const delta = rows * root.cols * (event.key === Qt.Key_PageDown ? 1 : -1)
                currentIndex = Math.max(0, Math.min(count - 1, currentIndex + delta))
                event.accepted = true
            } else if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                currentIndex = event.key === Qt.Key_Home ? 0 : count - 1
                event.accepted = true
            }
        }
        SmoothWheel { flick: grid }
        Scrollbar { target: grid }
    }

    // Đang tải: khung xám đúng hình nội dung, nhịp mờ 0,6 <-> 1 chu kỳ 1,6 s (DESIGN.md 2). Không vòng xoay.
    Item {
        id: skeleton
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
            model: Math.max(0, root.cols * Math.ceil(skeleton.height / root.cellH))
            Item {
                required property int index
                x: Theme.margin + (index % root.cols) * root.cellW
                y: Math.floor(index / root.cols) * root.cellH
                width: root.coverW
                height: root.cellH
                Rectangle { width: parent.width; height: Math.round(root.coverW * Theme.coverRatio); radius: Theme.radiusCover; color: Theme.sunken }
                Rectangle { y: Math.round(root.coverW * Theme.coverRatio) + 14; width: parent.width * 0.85; height: 12; radius: 4; color: Theme.sunken }
                Rectangle { y: Math.round(root.coverW * Theme.coverRatio) + 34; width: parent.width * 0.5; height: 10; radius: 4; color: Theme.sunken }
            }
        }
    }

    // Trống / lỗi: một câu + một nút dẫn tới việc tiếp theo (DESIGN.md 2). Lỗi nói tại chỗ cách sửa, không hộp thoại chặn.
    Column {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 40
        spacing: Theme.s16
        visible: root.failed || root.libraryError || (!root.loading && root.count === 0)
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.failed ? "Chưa mở được ABook" : (root.libraryError ? "Chưa lấy được thư viện" : "Thư viện còn trống")
            color: Theme.text
            font.pixelSize: Theme.sizeSection
            font.weight: Theme.weightMedium
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(root.width - 2 * Theme.margin, 460)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: root.failed ? Backend.message : (root.libraryError ? Backend.library.error : "Sách bạn thêm sẽ nằm ở đây.")
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
        }
        Button {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.failed || root.libraryError
            text: "Thử lại"
            onClicked: root.failed ? Backend.restart() : Backend.refreshLibrary()
        }
    }

    Component.onCompleted: grid.forceActiveFocus()
    onVisibleChanged: if (visible) grid.forceActiveFocus()
}
