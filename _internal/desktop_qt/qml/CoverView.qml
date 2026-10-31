import QtQuick
import ABook

// Bìa của một cuốn: ảnh thật (image://cover, giải mã ngoài luồng giao diện đúng cỡ hiển thị, đã bo góc) hoặc bìa vẽ từ tên.
// Trong lúc ảnh về là mặt chìm trung tính; ảnh hiện vào bằng mờ dần. Ảnh lỗi thì quay về bìa vẽ.
// Bìa đổi cỡ liên tục (cột tên cao lên khi dòng nhạc nền hiện, kéo cửa sổ): chỉ giải mã lại khi cỡ đứng yên 150 ms, trong lúc ấy ảnh cũ
// giãn theo khung - không giải mã mỗi khung, không nháy qua mặt chìm.
Item {
    id: root
    property string coverKey: ""
    property string title: ""
    property real radius: Theme.radiusCover
    readonly property real dpr: Screen.devicePixelRatio
    readonly property size wantSize: Qt.size(Math.round(width * dpr), Math.round(height * dpr))
    property size loadSize: Qt.size(0, 0)
    property bool shown: false           // đã có ảnh của cuốn này: giữ nó trong lúc giải mã lại cỡ khác

    onWantSizeChanged: {
        if (loadSize.width > 0 && wantSize.width > 0) settle.restart()
        else loadSize = wantSize
    }
    onCoverKeyChanged: shown = false
    Timer { id: settle; interval: 150; onTriggered: root.loadSize = root.wantSize }

    GeneratedCover {
        anchors.fill: parent
        title: root.title
        radius: root.radius
        visible: root.coverKey === "" || image.status === Image.Error
    }
    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: Theme.sunken
        visible: root.coverKey !== "" && !root.shown && image.status !== Image.Ready && image.status !== Image.Error
    }
    Image {
        id: image
        anchors.fill: parent
        source: root.coverKey !== "" && root.loadSize.width > 0 ? "image://cover/" + root.coverKey + "/" + Math.round(root.radius * root.dpr) : ""
        sourceSize: root.loadSize
        fillMode: Image.Stretch
        asynchronous: true
        retainWhileLoading: true      // Qt 6.8: ảnh cũ ở lại tới khi ảnh cỡ mới xong
        cache: true
        opacity: status === Image.Ready || (root.shown && status === Image.Loading) ? 1 : 0
        onStatusChanged: if (status === Image.Ready) { root.shown = true; Bench.noteOnce("first_cover") }
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    }
}
