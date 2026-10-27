pragma Singleton
import QtQuick

// Điều hướng dùng chung: ngăn xếp màn, các lớp nổi (popover, hộp thoại), chú thích khi rê chuột.
// Back (Esc, Alt+Left, nút Back của chuột) đóng lớp nổi trên cùng trước, rồi mới lùi một màn; Back không bao giờ thoát app.
QtObject {
    property var stack: null          // ScreenStack, gán trong Main.qml
    property var layers: []           // lớp nổi đang mở, mới nhất ở cuối; mỗi lớp có close()

    // Studio của máy tính đã ghép đang mở ở màn Studio ("Mở Studio" ở Cài đặt › Thiết bị › Máy tính khác): mã máy (12 hex), "" = Studio của máy này
    property string studioPeer: ""
    function openPeerStudio(peer) {
        studioPeer = peer
        if (stack) stack.show(1)
    }
    // Đang xem máy kia thì CẢ app là của máy ấy (trang `?peer=` của web): Studio, Thư viện, thanh "Đang mở Studio của <máy>" ở trên cùng.
    // /api/app của máy ấy (peer.name, listenOnly) khi đã vào được, null khi chưa (StudioScreen hỏi và đặt).
    property var peerInfo: null
    // Một lời gọi qua cầu nối vừa gặp máy kia im (503 unreachable, PEER_SILENT_EVENT của web): câu của máy chủ; "" khi máy ấy đang trả lời
    property string peerSilent: ""
    // Máy kia trả lời lại sau khi im: các màn của máy ấy nạp lại (invalidateQueries của usePeerSilent)
    property int peerRevision: 0
    onStudioPeerChanged: { peerSilent = ""; if (!studioPeer) peerInfo = null }
    // "Về máy này" (homePage của web): thôi xem máy kia, về Thư viện của máy này
    function goHome() {
        studioPeer = ""
        showLibrary()
    }
    // "Về Thư viện" (navigate("/")): Thư viện của máy đang xem, ở gốc
    function showLibrary() {
        if (!stack) return
        stack.show(0)
        stack.popToRoot()
    }

    // Mép trên của vùng thông báo (px, toạ độ cửa sổ); 0 = chỗ thường dưới thanh tiêu đề. Màn đọc đặt nó dưới thanh đầu của mình (--toast-top của web).
    property real toastTop: 0

    function openLayer(layer) { layers = layers.concat([layer]) }
    // Cú bấm bắt đầu khi một lớp phủ cả cửa sổ (bảng nổi, hộp thoại: `coversWindow`) đang mở mà `item` không nằm trong lớp ấy: cú bấm ấy là để đóng
    // lớp / bấm trong lớp, không phải bấm vào `item` bên dưới. Qt 6 đưa cú bấm tới mọi TapHandler dưới điểm, kể cả handler nằm dưới lớp.
    function coveredFor(item) {
        for (const layer of layers) {
            if (!layer || !layer.coversWindow) continue
            let inside = false
            for (let node = item; node; node = node.parent) if (node === layer) { inside = true; break }
            if (!inside) return true
        }
        return false
    }
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
