import QtQuick
import QtQuick.Shapes
import "LucidePaths.js" as Lucide

// Biểu tượng lucide - ĐÚNG gói mà bản web và điện thoại dùng (DESIGN.md luật 8: cùng một việc, cùng một icon). Nét SVG trên lưới 24 do
// scripts/gen_lucide_icons.py sinh vào LucidePaths.js; vẽ bằng Shape (CurveRenderer: cong sắc ở mọi tỉ lệ màn hình), nét 2 đơn vị lưới co theo cỡ
// như lucide-react. `name` là tên file lucide (kebab-case: "arrow-left"). `solid` = tô đặc không viền (Play / Pause như bản web).
// "<tên>-filled" (vd "heart-filled"): cùng nét của <tên>, tô đầy bên trong bằng cùng màu - như web `fill="currentColor"` và điện thoại `fill`.
Item {
    id: root
    property string name: ""
    property int size: 20
    property color color: Theme.text
    property bool solid: name === "play" || name === "pause"

    width: size
    height: size

    readonly property bool filled: name.endsWith("-filled")
    readonly property string key: (filled ? name.slice(0, -7) : name).toUpperCase().split("-").join("_")
    readonly property string path: name === "" ? "" : (Lucide[key] || "")
    // Phần tô thêm của icon có chấm đặc (palette); icon tô đầy thì chính nét ấy; icon không có thì rỗng
    readonly property string fillPath: name === "" ? "" : filled ? path : (Lucide[key + "_FILL"] || "")

    // Empty and hidden state slots do not need vector geometry. Keep the item itself for layout and fades.
    Loader {
        active: root.visible && root.opacity > 0 && root.path !== ""
        sourceComponent: Shape {
            width: 24
            height: 24
            scale: root.size / 24
            transformOrigin: Item.TopLeft
            preferredRendererType: Shape.CurveRenderer
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
}
