import QtQuick
import QtQuick.Shapes
import ABook

// Lớp phủ khi kéo file vào màn Thư viện (DropToAdd.tsx của bản web): nền --bg mờ 80 %, giữa là khung đứt nét hổ phách bo góc bìa, icon sách + "Thả để thêm sách" và
// một câu nói loại file. Hiện / ẩn: khung nổi lên từ 96 % cùng nền mờ dần trong motionMedium (giảm chuyển động: chỉ mờ). Không nhận chuột - DropArea bên dưới nhận.
Item {
    id: root
    property bool shown: false
    property real reveal: shown ? 1 : 0
    objectName: "importDrop"
    visible: reveal > 0
    enabled: false
    Behavior on reveal {
        NumberAnimation {
            duration: Theme.reduceMotion ? Theme.motionFast : (root.shown ? Theme.motionMedium : Theme.motionMediumOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.shown ? Theme.easeDecelerate : Theme.easeAccelerate
        }
    }
    Rectangle { anchors.fill: parent; color: Theme.bg; opacity: 0.8 * root.reveal }
    Item {
        id: box
        width: Math.min(448, root.width - 48)
        height: words.height + 96
        anchors.centerIn: parent
        opacity: root.reveal
        scale: Theme.reduceMotion ? 1 : 0.96 + 0.04 * root.reveal
        Rectangle { anchors.fill: parent; radius: Theme.radiusCover; color: Theme.accentSoft }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.accent
                strokeWidth: 2
                fillColor: "transparent"
                strokeStyle: ShapePath.DashLine
                dashPattern: [4, 3]
                PathRectangle { x: 1; y: 1; width: box.width - 2; height: box.height - 2; radius: Theme.radiusCover }
            }
        }
        Column {
            id: words
            x: 40
            y: 48
            width: parent.width - 80
            spacing: 12
            Icon { anchors.horizontalCenter: parent.horizontalCenter; name: "book-plus"; size: 40; color: Theme.accentText }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "Thả để thêm sách"
                color: Theme.text
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: 18
                font.weight: 600
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "EPUB, Word (DOCX), PDF có chữ, TXT hay file sách .abook. Thả nhiều file một lúc cũng được."
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
            }
        }
    }
}
