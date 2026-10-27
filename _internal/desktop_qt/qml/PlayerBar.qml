import QtQuick
import ABook

// Thanh phát ở đáy khung nội dung (chỉ khi có sách đang nạp). Bìa nhỏ · tên sách · tên chương (xuống dòng, thanh cao lên) · lùi 15 s · phát / dừng · tới 15 s.
// Tiến độ là đường mảnh ở mép trên thanh: rê chuột thì dày lên và hiện giờ ở chỗ con trỏ, bấm hay kéo là tua. Tốc độ, hẹn giờ, nhạc nền, giọng KHÔNG ở đây.
// Bấm vào thanh (ngoài các nút) mở "Đang nghe": bìa nhỏ lớn dần thành bìa lớn (NowPlaying.qml).
Item {
    id: root
    property alias thumb: thumb
    /// Phần chữ + nút mờ dần khi "Đang nghe" mở ra (0..1 = còn thấy).
    property real contentOpacity: 1
    property real contentShift: 0
    /// Bìa nhỏ ẩn khi bìa lớn của Đang nghe đã thế chỗ nó.
    property bool thumbShown: true
    readonly property real natural: Math.max(84, Math.max(titles.implicitHeight, thumb.height) + 2 * Theme.s12)
    property real appear: Player.loaded ? 1 : 0
    signal openRequested()

    height: Math.round(natural * appear)
    visible: height > 0
    Behavior on appear {
        NumberAnimation {
            duration: Theme.reduceMotion ? 0 : (Player.loaded ? Theme.motionMedium : Theme.motionMediumOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Player.loaded ? Theme.easeDecelerate : Theme.easeAccelerate
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.panel
        Rectangle { width: parent.width; height: 1; color: Theme.line }
    }

    // Vùng bấm mở "Đang nghe": bìa + chữ (không phủ lên nút phát)
    Interactive {
        id: openArea
        x: 0
        y: 6
        width: transport.x - Theme.s16
        height: parent.height - 6
        pressScaling: false
        ringRadius: 0
        ringMargin: -2
        Rectangle {
            anchors.fill: parent
            color: Theme.text
            opacity: openArea.pressed ? 0.06 : (openArea.hovered ? 0.03 : 0)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        }
        onClicked: root.openRequested()
    }

    Item {
        id: contents
        anchors.fill: parent
        opacity: root.contentOpacity
        transform: Translate { y: root.contentShift }

        CoverView {
            id: thumb
            x: Theme.margin
            anchors.verticalCenter: parent.verticalCenter
            width: 44
            height: Math.round(width * Theme.coverRatio)
            coverKey: Player.coverKey
            title: Player.bookTitle
            radius: Theme.radiusControl
            opacity: root.thumbShown ? 1 : 0
        }
        Column {
            id: titles
            x: thumb.x + thumb.width + Theme.s16
            anchors.verticalCenter: parent.verticalCenter
            width: transport.x - Theme.s24 - x
            spacing: 2
            Text {
                width: parent.width
                text: Player.bookTitle
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
            }
            Text {
                width: parent.width
                text: Player.error !== "" ? Player.error
                    : (Player.buffering ? "Đang tải âm thanh…"
                    : [Player.chapterTitle, Player.chapterSubtitle].filter(s => s !== "").join(" · "))
                color: Player.error !== "" ? Theme.danger : Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
        }
        Row {
            id: transport
            anchors.right: parent.right
            anchors.rightMargin: Theme.margin
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.s8
            SkipButton { forward: false; anchors.verticalCenter: parent.verticalCenter }
            PlayButton { size: 44; anchors.verticalCenter: parent.verticalCenter }
            SkipButton { forward: true; anchors.verticalCenter: parent.verticalCenter }
            IconButton {
                icon: "picture-in-picture-2"; tip: "Cửa sổ mini"
                enabled: Player.loaded
                anchors.verticalCenter: parent.verticalCenter
                onClicked: Nav.windowMode.enter()
            }
        }
    }

    // Đường tiến độ ở mép trên (vùng bấm cao 12 px, đường nằm đúng mép)
    SeekBar {
        compact: true
        x: 0
        y: -6
        width: parent.width
        height: 12
        z: 2
    }
}
