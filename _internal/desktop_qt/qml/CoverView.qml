import QtQuick
import ABook

// Bìa của một cuốn: ảnh thật (image://cover, giải mã ngoài luồng giao diện đúng cỡ hiển thị, đã bo góc) hoặc bìa vẽ từ tên.
// Trong lúc ảnh về là mặt chìm trung tính; ảnh hiện vào bằng mờ dần. Ảnh lỗi thì quay về bìa vẽ.
Item {
    id: root
    property string coverKey: ""
    property string title: ""
    property real radius: Theme.radiusCover
    readonly property real dpr: Screen.devicePixelRatio

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
        visible: root.coverKey !== "" && image.status !== Image.Ready && image.status !== Image.Error
    }
    Image {
        id: image
        anchors.fill: parent
        source: root.coverKey !== "" ? "image://cover/" + root.coverKey + "/" + Math.round(root.radius * root.dpr) : ""
        sourceSize: Qt.size(Math.round(root.width * root.dpr), Math.round(root.height * root.dpr))
        fillMode: Image.Stretch
        asynchronous: true
        cache: true
        opacity: status === Image.Ready ? 1 : 0
        onStatusChanged: if (status === Image.Ready) Bench.noteOnce("first_cover")
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    }
}
