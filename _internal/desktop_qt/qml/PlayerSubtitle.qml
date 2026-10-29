import QtQuick
import ABook

Column {
    id: root
    property int horizontalAlignment: Text.AlignLeft
    readonly property bool preparing: Player.speaking && Player.playing && Player.buffering
    property bool delayed: false
    onPreparingChanged: { delayed = false; if (preparing && Nav.uiVisible && visible) delay.restart(); else delay.stop() }
    onVisibleChanged: { if (visible && preparing && Nav.uiVisible) delay.restart(); else { delay.stop(); delayed = false } }
    Timer { id: delay; interval: 1500; onTriggered: root.delayed = root.preparing }
    Connections { target: Nav; function onUiVisibleChanged() { if (Nav.uiVisible && root.preparing && root.visible) delay.restart(); else { delay.stop(); root.delayed = false } } }
    Text { width: parent.width; horizontalAlignment: root.horizontalAlignment; wrapMode: Text.Wrap; visible: Player.purpose === "review"; text: "Nghe kiểm"; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    Text {
        objectName: "playerSubtitleText"; width: parent.width; wrapMode: Text.Wrap
        horizontalAlignment: root.horizontalAlignment
        text: root.delayed ? "Đang chuẩn bị giọng đọc…" : Player.atEnd === "caughtUp" ? "Đã nghe hết phần đã có" : Player.bookTitle
        color: Theme.text2; font.pixelSize: Theme.sizeCaption
    }
}
