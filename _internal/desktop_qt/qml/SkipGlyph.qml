import QtQuick

// Biểu tượng tua 15 giây, đúng hình của bản web (ui/src/listen/PlayerViews.tsx skipIcon): ô 24 đơn vị, nét 1,9, đầu nét và góc tròn.
// Cung nông ở trên (bán kính 8,5 từ (4,05; 9) tới (19,95; 9), tâm (12; 12,008), đáy nét y ~ 9,95), số 15 ở dưới (cỡ 14,5, nét 600, đáy chữ y 22,
// mực từ y ~ 11,8): nét và số cách nhau một khe, số không bao giờ chạm vòng. Bản "lùi" là ảnh lật ngang của cung + mũi tên, số không lật.
// Chỉ dùng QtQuick (không Theme, không thêm DLL Shapes) để bộ thử dựng được nó riêng và đo bằng điểm ảnh (tests/test_skipglyph.cpp).
Item {
    id: root
    property bool forward: true
    property real size: 24
    property color color: "black"
    property string family: ""
    property bool showStroke: true
    property bool showDigits: true
    readonly property real u: size / 24
    width: size
    height: size

    Canvas {
        id: stroke
        anchors.fill: parent
        visible: root.showStroke
        renderTarget: Canvas.Image
        renderStrategy: Canvas.Cooperative
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const u = root.u
            ctx.lineWidth = 1.9 * u
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
            ctx.strokeStyle = root.color
            if (!root.forward) {
                ctx.translate(width, 0)
                ctx.scale(-1, 1)
            }
            // cung: tâm (12; 12,008), bán kính 8,5, từ 200,73° quét 138,54° theo chiều kim đồng hồ
            const a0 = 200.73 * Math.PI / 180
            const a1 = (200.73 + 138.54) * Math.PI / 180
            ctx.beginPath()
            ctx.arc(12 * u, 12.008 * u, 8.5 * u, a0, a1, false)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(20.94 * u, 6.17 * u)
            ctx.lineTo(19.95 * u, 9 * u)
            ctx.lineTo(17.34 * u, 7.53 * u)
            ctx.stroke()
        }
        Connections {
            target: root
            function onColorChanged() { stroke.requestPaint() }
            function onForwardChanged() { stroke.requestPaint() }
            function onSizeChanged() { stroke.requestPaint() }
        }
    }
    Text {
        id: digits
        visible: root.showDigits
        text: "15"
        color: root.color
        anchors.horizontalCenter: parent.horizontalCenter
        y: 22 * root.u - baselineOffset
        font.family: root.family !== "" ? root.family : Qt.application.font.family
        font.pointSize: 14.5 * root.u * 0.75
        font.weight: Font.DemiBold
        font.letterSpacing: -0.2 * root.u
        font.features: { "tnum": 1 }
    }
}
