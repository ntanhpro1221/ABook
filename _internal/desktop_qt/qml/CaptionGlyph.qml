import QtQuick
import QtQuick.Shapes
import ABook

// Nét chữ của nút cửa sổ, kiểu Segoe Fluent: hộp 10x10, nét 1 điểm ảnh, đầu nét phẳng (đường ngang / khung nằm trên nửa điểm ảnh nên sắc).
// Đổi qua lại phóng to <-> khôi phục: nét cũ mờ đi và thu nhỏ, nét mới hiện ra và phóng lên (không bật cứng).
Item {
    id: root
    property string kind: "minimize"      // minimize | maximize | restore | close
    property bool shown: true
    property color color: Theme.text
    readonly property var paths: ({
        "minimize": "M0 5.5 H10",
        "maximize": "M0.5 0.5 H9.5 V9.5 H0.5 Z",
        "restore": "M2.5 2.5 V0.5 H9.5 V7.5 H7.5 M0.5 2.5 H7.5 V9.5 H0.5 Z",
        "close": "M0 0 L10 10 M10 0 L0 10"
    })

    width: 10
    height: 10
    opacity: shown ? 1 : 0
    scale: shown ? 1 : 0.8
    Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    Behavior on scale {
        NumberAnimation {
            duration: Theme.reduceMotion ? 0 : Theme.motionFast
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }
    Behavior on color { ColorAnimation { duration: Theme.motionFast } }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.color
            strokeWidth: 1
            fillColor: "transparent"
            joinStyle: ShapePath.MiterJoin
            capStyle: ShapePath.FlatCap
            PathSvg { path: root.paths[root.kind] || "" }
        }
    }
}
