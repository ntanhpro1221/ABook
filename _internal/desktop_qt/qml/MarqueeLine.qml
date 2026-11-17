import QtQuick
import ABook

// Tên trong ô MỘT DÒNG CỐ ĐỊNH (thanh phát thu nhỏ, trình phát - DESIGN.md 5.5 "Tên một dòng"; điện thoại MarqueeLine, web MarqueeLine): ô luôn
// cao đúng một dòng ở cỡ gốc nên bìa và nút phát không bao giờ dời vì tên dài ngắn. Vừa ở cỡ gốc thì giữ nguyên; không vừa thì thu cỡ tới
// Theme.oneLineMinScale cỡ gốc như OneLineFit; thu tới đó vẫn không vừa thì CHẠY CHỮ: đứng Theme.marqueeDelayMs ở đầu, trượt Theme.marqueeSpeed
// px/giây cho tới khi bản chép thứ hai (cách Theme.marqueeGap) về đúng chỗ bản đầu, rồi lại đứng. Giảm chuyển động: không trượt - nhảy từng đoạn,
// mỗi đoạn đứng Theme.marqueeDelayMs, tới cuối tên thì về đầu. Không bao giờ "…"; trợ năng đọc tên một lần.
// `still` (VisualReady.rest đặt khi chụp): đứng ở đầu cho ảnh tất định.
Item {
    id: root
    property string text: ""
    property int baseSize: Theme.sizeBody
    property int weight: Theme.weightRegular
    property color color: Theme.text
    property bool still: false
    // Canh khi tên vừa ô (Text.AlignLeft / AlignHCenter); khi chạy chữ luôn bắt đầu từ mép trái
    property int horizontalAlignment: Text.AlignLeft
    // Gạch chân khi rê chuột (tên sách là liên kết - PlayerSubtitle)
    property bool underline: false
    // Cho chuyển phần tử chung (NowPlaying.textFrame) đọc như một Text
    readonly property alias font: first.font
    readonly property real paintedWidth: Math.min(width, first.paintedWidth)
    readonly property real paintedHeight: first.paintedHeight
    property real offset: 0
    readonly property real phase: offset
    readonly property int minSize: Math.ceil(baseSize * Theme.oneLineMinScale)
    readonly property real naturalWidth: Math.ceil(probe.implicitWidth)
    // Cỡ thử đầu tiên theo tỉ lệ bề ngang; Text ẩn thứ hai xác nhận ở cỡ nguyên đó (chữ không co đúng tuyến tính theo cỡ) - như OneLineFit.qml
    readonly property int candidate: width <= 0 || naturalWidth <= width ? baseSize : Math.floor(baseSize * width / naturalWidth)
    readonly property int fitted: Math.ceil(probeFit.implicitWidth) <= width ? candidate : candidate - 1
    // "one": vừa ở cỡ gốc · "shrunk": thu cỡ vừa một dòng · "scroll": ở cỡ đáy, chạy chữ
    readonly property string fit: width <= 0 || naturalWidth <= width ? "one" : fitted >= minSize ? "shrunk" : "scroll"
    readonly property int shownSize: fit === "one" ? baseSize : fit === "shrunk" ? fitted : minSize
    readonly property real cycle: Math.ceil(first.implicitWidth) + Theme.marqueeGap
    readonly property bool moving: fit === "scroll" && !still && visible
    implicitHeight: Math.ceil(probe.implicitHeight)
    height: implicitHeight
    clip: true
    Accessible.role: Accessible.StaticText
    Accessible.name: text

    Text { id: probe; visible: false; text: root.text; textFormat: Text.PlainText; font.family: first.font.family; font.weight: root.weight; font.features: first.font.features; font.pixelSize: root.baseSize }
    Text { id: probeFit; visible: false; text: root.text; textFormat: Text.PlainText; font.family: first.font.family; font.weight: root.weight; font.features: first.font.features; font.pixelSize: Math.max(1, root.candidate) }

    Item {
        x: root.fit === "scroll" ? -root.offset : root.horizontalAlignment === Text.AlignHCenter ? Math.round((root.width - first.width) / 2)
            : root.horizontalAlignment === Text.AlignRight ? root.width - first.width : 0
        width: root.cycle * 2
        height: root.height
        Text {
            id: first
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            textFormat: Text.PlainText
            color: root.color
            font.pixelSize: root.shownSize
            font.weight: root.weight
            font.underline: root.underline
            Accessible.ignored: true
        }
        Text {
            x: root.cycle
            anchors.verticalCenter: parent.verticalCenter
            visible: root.fit === "scroll" && !Theme.reduceMotion
            text: root.text
            textFormat: Text.PlainText
            color: root.color
            font.pixelSize: root.shownSize
            font.weight: root.weight
            font.underline: root.underline
            Accessible.ignored: true
        }
    }
    SequentialAnimation {
        id: glide
        running: root.moving && !Theme.reduceMotion
        loops: Animation.Infinite
        PauseAnimation { duration: Theme.marqueeDelayMs }
        NumberAnimation { target: root; property: "offset"; from: 0; to: root.cycle; duration: Math.round(root.cycle * 1000 / Theme.marqueeSpeed) }
        PropertyAction { target: root; property: "offset"; value: 0 }
    }
    Timer {
        // Giảm chuyển động: mỗi nhịp nhảy một đoạn (bề ngang ô trừ khe), đoạn cuối canh cuối tên vào mép phải, rồi về đầu
        running: root.moving && Theme.reduceMotion
        interval: Theme.marqueeDelayMs
        repeat: true
        onTriggered: {
            const end = Math.ceil(first.implicitWidth) - root.width
            root.offset = root.offset >= end - 0.5 ? 0 : Math.min(end, root.offset + Math.max(1, root.width - Theme.marqueeGap))
        }
    }
    function restart() {
        offset = 0
        if (glide.running) glide.restart()
    }
    onMovingChanged: offset = 0
    onTextChanged: restart()
    onCycleChanged: restart()
}
