pragma Singleton
import QtQuick

// Điều hướng dùng chung: ngăn xếp màn, các lớp nổi (popover, hộp thoại), chú thích khi rê chuột.
// Back (Esc, Alt+Left, nút Back của chuột) đóng lớp nổi trên cùng trước, rồi mới lùi một màn; Back không bao giờ thoát app.
QtObject {
    property bool uiVisible: true
    property var stack: null          // ScreenStack, gán trong Main.qml
    property var windowMode: null
    property var layers: []           // lớp nổi đang mở, mới nhất ở cuối; mỗi lớp có close()

    // Studio của máy tính đã ghép đang mở ở màn Studio ("Mở Studio" ở Cài đặt › Thiết bị › Máy tính khác): mã máy (12 hex), "" = Studio của máy này
    property string studioPeer: ""
    function openPeerStudio(peer) {
        studioPeer = peer
        if (stack) stack.show(1)
    }

    // Mở trang một cuốn ở Thư viện ("Nghe trong Thư viện" của Studio); Main.qml nối với openBookId
    signal bookRequested(string id)

    function openLayer(layer) { layers = layers.concat([layer]) }
    function closedLayer(layer) { layers = layers.filter(l => l !== layer) }

    function back() {
        if (layers.length > 0) {
            layers[layers.length - 1].close()
            return true
        }
        if (stack && stack.canPop) {
            stack.pop()
            return true
        }
        return false
    }

    // ---- chú thích khi rê chuột (vẽ ở lớp phủ của cửa sổ, không bị cắt bởi khung cuộn) ----
    property string tipText: ""
    property rect tipAnchor: Qt.rect(0, 0, 0, 0)    // hộp của phần tử, toạ độ cửa sổ
    property bool tipShown: false
    property var tipOwner: null

    function showTip(owner, text) {
        if (!text) return
        const p = owner.mapToItem(null, 0, 0)
        tipOwner = owner
        tipText = text
        tipAnchor = Qt.rect(p.x, p.y, owner.width, owner.height)
        tipShown = true
    }
    function hideTip(owner) {
        if (owner === undefined || owner === tipOwner) {
            tipShown = false
            tipOwner = null
        }
    }
}
