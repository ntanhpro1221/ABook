import QtQuick
import QtTest
import "ShadowBand.js" as ShadowBand
import ABook

// Bóng lớp nổi mượt như box-shadow của web: dải ngoài mép khung giảm đều, không bậc (máy dò ShadowBand.js). Kiểm lực: cảnh bóng
// bậc thang cũ (hai Rectangle đen mờ) phải bị bắt; bóng chung ở mọi cỡ và hai giao diện, hộp thoại và bảng nổi thật phải qua.
Item {
    id: host
    width: 900
    height: 700
    Rectangle { anchors.fill: parent; color: Theme.bg }

    Component {
        id: frame
        Item {
            property alias kind: shadow.kind
            property alias panel: panel
            Item {
                id: panel
                x: 200; y: 120
                width: parent.width; height: parent.height
                Shadow { id: shadow; radius: panel.width === panel.height ? panel.width / 2 : Theme.radiusCover }
                Rectangle { anchors.fill: parent; radius: shadow.radius; color: Theme.panel; border.width: Theme.dark ? 1 : 0; border.color: Theme.line }
            }
        }
    }
    // Bóng giả của bản trước 0.4.151 (Modal/Popover/Toast), để chứng minh máy dò bắt được bậc
    Component {
        id: staircase
        Item {
            property alias panel: panel
            Item {
                id: panel
                x: 200; y: 120; width: 320; height: 200
                Rectangle { anchors.fill: parent; anchors.margins: -12; radius: Theme.radiusSheet + 12; color: "#000000"; opacity: 0.05 }
                Rectangle { anchors.fill: parent; anchors.margins: -4; anchors.topMargin: -2; anchors.bottomMargin: -8; radius: Theme.radiusSheet + 4; color: "#000000"; opacity: 0.08 }
                Rectangle { anchors.fill: parent; radius: Theme.radiusSheet; color: Theme.panel }
            }
        }
    }
    Component { id: modal; Modal { title: "Hộp thử"; Text { text: "Nội dung hộp"; color: Theme.text } } }
    Component { id: popover; Popover { Column { Repeater { model: 5; Text { text: "Dòng bảng thử " + index; color: Theme.text; height: 32 } } } } }
    Item { id: anchor; x: 420; y: 80; width: 40; height: 40 }

    TestCase {
        name: "Shadow"
        when: windowShown
        function cleanup() { Theme.mode = "auto"; Nav.layers = [] }

        function rectOf(item) {
            const p = item.mapToItem(host, 0, 0)
            return {x: p.x, y: p.y, width: item.width, height: item.height}
        }
        function shot() { host.Window.window.update(); waitForRendering(host); return grabImage(host.Window.window.contentItem) }
        // Ngưỡng: shadow-float dốc nhất ~1 mức/px; shadow-card có lớp 1 px (0 1px 2px) dốc ~5 mức/px như web.
        function verdictOf(kind, width, height) {
            const scene = createTemporaryObject(frame, host, {width: width, height: height, kind: kind})
            const image = shot()
            return ShadowBand.verdict(image, rectOf(scene.panel), kind === "card" ? 40 : 110, kind === "card" ? 8 : 3, Theme.dark ? 2 : 8)
        }

        function test_staircaseIsCaught() {
            Theme.mode = "light"
            const scene = createTemporaryObject(staircase, host)
            const why = ShadowBand.verdict(shot(), rectOf(scene.panel), 40, 3, 4)
            verify(why.indexOf("bậc") >= 0, "the old stacked-rectangle shadow must be caught: " + why)
        }
        function test_sharedShadowIsSmooth_data() {
            const rows = []
            for (const mode of ["light", "dark"]) {
                rows.push({tag: "float-dialog-" + mode, mode: mode, kind: "float", width: 480, height: 320})
                rows.push({tag: "float-menu-" + mode, mode: mode, kind: "float", width: 180, height: 120})
                // Thông báo hai dòng. Một dòng (48) thì shadow-float co -24 còn hình bóng cao 0: web cũng gần như không có bóng.
                rows.push({tag: "float-toast-" + mode, mode: mode, kind: "float", width: 360, height: 96})
                rows.push({tag: "card-round-" + mode, mode: mode, kind: "card", width: 44, height: 44})
            }
            return rows
        }
        function test_sharedShadowIsSmooth(data) {
            Theme.mode = data.mode
            const why = verdictOf(data.kind, data.width, data.height)
            verify(why === "", why)
        }
        // Lớp nổi thật trên nền phẳng: hộp thoại (có màn che) và bảng nổi
        function test_realLayersAreSmooth_data() {
            return [{tag: "modal-light", mode: "light", factory: modal}, {tag: "modal-dark", mode: "dark", factory: modal},
                    {tag: "popover-light", mode: "light", factory: popover}, {tag: "popover-dark", mode: "dark", factory: popover}]
        }
        function test_realLayersAreSmooth(data) {
            Theme.mode = data.mode
            const layer = createTemporaryObject(data.factory, host)
            if (layer.anchorItem !== undefined) { layer.anchorItem = anchor; layer.below = true }
            layer.show()
            tryCompare(layer, "shown", 1, 3000)
            const panel = layer.children.filter(child => child.objectName === "modalPanel" || child.objectName === "popoverPanel")[0]
            verify(panel !== undefined)
            const why = ShadowBand.verdict(shot(), rectOf(panel), 90, 3, Theme.dark ? 1 : 6)
            verify(why === "", data.tag + ": " + why)
        }
        // Chi phí: mỗi cỡ khung một lần tính (ảnh vào bộ đệm của Qt); hộp lớn nhất ở giao diện tối (bóng rộng nhất)
        function test_costOfTheLargestDialog() {
            Theme.mode = "dark"
            const started = Date.now()
            for (let i = 0; i < 10; ++i) createTemporaryObject(frame, host, {width: 720 + i, height: 640, kind: "float"})
            const each = (Date.now() - started) / 10
            console.log("SHADOW_COST_MS " + each.toFixed(2))
            verify(each < 8, "computing one dialog shadow took " + each + " ms")
        }
    }
}
