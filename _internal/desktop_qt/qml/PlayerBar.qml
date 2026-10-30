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
    signal settingsRequested(string group)
    Accessible.role: Accessible.Pane
    Accessible.name: "Trình phát"
    readonly property real transportHeight: Math.max(84, Math.max(titles.implicitHeight, thumb.height) + 2 * Theme.s12)
    readonly property real natural: transportHeight + alerts.height
    property real appear: Player.loaded ? 1 : 0
    signal openRequested()
    Connections {
        target: Player
        function onLoadedChanged() {
            if (!Player.loaded) { more.close(); sleep.close(); music.close(); voice.close(); output.close() }
        }
    }

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
        y: alerts.height + 6
        width: transport.x - Theme.s16
        height: root.transportHeight - 6
        pressScaling: false
        ringRadius: 0
        ringMargin: -2
        Accessible.name: "Mở màn hình đang nghe"
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
        width: parent.width; height: root.transportHeight; y: alerts.height
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
                objectName: "barChapterTitle"
                width: parent.width
                text: [Player.chapterTitle, Player.chapterSubtitle].filter(s => s !== "").join(" · ")
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
            }
            PlayerSubtitle {
                width: parent.width
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
            IconButton { id: moreButton; objectName: "barMore"; icon: "ellipsis"; tip: "Thêm tuỳ chọn"; anchors.verticalCenter: parent.verticalCenter; onClicked: more.toggle() }
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
    Column {
        id: alerts; x: Theme.margin; width: parent.width - 2 * Theme.margin
        PlayerFade { width: parent.width }
        PlayerAlert { width: parent.width; onVoiceRequested: { root.openRequested(); voice.fromAlert() } onSettingsRequested: root.settingsRequested("voice") }
    }
    // Bảng nổi của nút "…": Popover tự đặt ở gốc cửa sổ nên phủ cả bề mặt nội dung, Back / tiêu điểm khớp với các bảng của NowPlaying
    Popover {
        id: more; objectName: "barMoreMenu"; anchorItem: moreButton; panelWidth: 320
        Column {
            width: parent.width
            MenuRow { width: parent.width; text: "Hẹn giờ"; icon: "moon"; onClicked: { more.close(); sleep.show() } }
            MenuRow { width: parent.width; text: "Chương trước"; icon: "skip-back"; onClicked: { more.close(); Player.previous() } }
            MenuRow { width: parent.width; text: "Chương sau"; icon: "skip-forward"; onClicked: { more.close(); Player.next() } }
            MenuRow { width: parent.width; text: "Nhạc nền"; icon: "eighth-note"; visible: Music.hasMusic; onClicked: { more.close(); music.show() } }
            MenuRow { width: parent.width; text: "Giọng đọc"; icon: "audio-lines"; visible: Player.speaking && Api.voiceList.length > 0; onClicked: { more.close(); voice.show() } }
            MenuRow { width: parent.width; text: "Mở màn hình đang nghe"; icon: "maximize-2"; onClicked: { more.close(); root.openRequested() } }
            MenuRow { objectName: "barClose"; width: parent.width; text: "Đóng trình phát"; icon: "x"; onClicked: { more.close(); Player.close() } }
            MenuRow { objectName: "barOutput"; width: parent.width; text: "Thiết bị phát"; icon: "cast"; onClicked: { more.close(); output.show() } }
        }
    }
    SleepPopover { id: sleep; anchorItem: moreButton }
    MusicPopover { id: music; anchorItem: moreButton }
    PlayerVoicePopover { id: voice; anchorItem: moreButton; onSettingsRequested: root.settingsRequested("voice") }
    OutputPopover { id: output; anchorItem: moreButton }
}
