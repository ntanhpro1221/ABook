import QtQuick
import QtQuick.Shapes
import "LucidePaths.js" as Lucide

// Biểu tượng lucide - ĐÚNG gói mà bản web và điện thoại dùng (DESIGN.md luật 8: cùng một việc, cùng một icon). Nét SVG trên lưới 24 do
// scripts/gen_lucide_icons.py sinh vào LucidePaths.js; vẽ bằng Shape (CurveRenderer: cong sắc ở mọi tỉ lệ màn hình), nét 2 đơn vị lưới co theo cỡ
// như lucide-react. `name` là tên file lucide (kebab-case: "arrow-left"). `solid` = tô đặc không viền (Play / Pause như bản web).
Item {
    id: root
    property string name: ""
    property int size: 20
    property color color: Theme.text
    property bool solid: name === "play" || name === "pause"

    width: size
    height: size

    readonly property string key: name.toUpperCase().split("-").join("_")
    readonly property string path: name === "" ? "" : (Lucide[key] || "")
    // Phần tô thêm của icon có chấm đặc (palette); icon không có thì rỗng
    readonly property string fillPath: name === "" ? "" : (Lucide[key + "_FILL"] || "")

    Shape {
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        visible: root.path !== ""
        ShapePath {
            strokeColor: root.solid ? "transparent" : root.color
            strokeWidth: root.solid ? -1 : 2
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            fillColor: root.solid ? root.color : "transparent"
            PathSvg { path: root.path }
        }
        ShapePath {
            strokeColor: "transparent"
            strokeWidth: -1
            fillColor: root.fillPath !== "" ? root.color : "transparent"
            PathSvg { path: root.fillPath }
        }
    }
}
