import QtQuick
import ABook

// Người nhìn đồng hồ của bộ phát (thanh tua, nhãn giờ, văn bản chạy theo giọng): đặt một cái trong thành phần nào hiện giờ phát. Đồng hồ chỉ có nhịp
// khi có người nhìn VÀ đang phát; cửa sổ thu nhỏ thì không ai nhìn nên không có nhịp nào (giữ CPU gần 0 khi nghe với cửa sổ thu nhỏ).
Item {
    id: root
    width: 0
    height: 0
    property bool wanted: true
    property bool held: false
    readonly property bool watching: wanted && Window.window !== null && Window.visibility !== Window.Minimized && Window.visibility !== Window.Hidden

    function sync() {
        if (watching === held) return
        held = watching
        if (held) Player.clock.retain()
        else Player.clock.release()
    }
    onWatchingChanged: sync()
    Component.onCompleted: sync()
    Component.onDestruction: if (held) Player.clock.release()
}
