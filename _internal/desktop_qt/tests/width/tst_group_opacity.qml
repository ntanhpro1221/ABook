import QtQuick
import QtTest
import ABook

// Nút tắt mờ như MỘT nhóm (opacity của CSS, disabled:opacity-45 của web): chữ vẫn đậm trên khối nhạt. Mờ từng lớp thì chữ 45% chồng lên
// nền 45% thành chữ nâu nhạt trên khối nâu (Lead soát 0.4.151 lượt 2, "Lưu tên" ở hộp Sửa sách nền tối). Đo điểm ảnh: mực chữ phải gần
// màu web (45% accentInk trên nền) chứ không gần khối.
Item {
    id: host
    width: 320; height: 120
    Rectangle { id: ground; anchors.fill: parent; color: Theme.panel }
    Component { id: button; Button { x: 40; y: 40; text: "Lưu tên"; enabled: false } }
    TestCase {
        name: "GroupOpacity"
        when: windowShown
        function cleanup() { Theme.mode = "auto" }
        function sum(color) { return Math.round(255 * (color.r + color.g + color.b)) }
        function mix(top, under, a) { return Qt.rgba(a * top.r + (1 - a) * under.r, a * top.g + (1 - a) * under.g, a * top.b + (1 - a) * under.b, 1) }
        function inkAndFill(mode) {
            Theme.mode = mode
            const b = createTemporaryObject(button, host)
            tryCompare(b, "opacity", 0.45)
            waitForRendering(b)
            const img = grabImage(b)
            let darkest = 3 * 255, fill = 0
            // Trong lòng nút, tránh góc bo (góc lộ nền panel - tối cỡ mực web, sẽ cho qua oan)
            for (let y = 8; y < b.height - 8; y++)
                for (let x = 10; x < b.width - 10; x++) {
                    const v = sum(img.pixel(x, y))
                    darkest = mode === "dark" ? Math.min(darkest, v) : darkest
                    if (x === 10 && y === Math.round(b.height / 2)) fill = v
                }
            return {ink: darkest, fill: fill, b: b}
        }
        function test_disabledPrimaryKeepsItsInkOnTheFill() {
            const seen = inkAndFill("dark")
            const web = sum(mix(Theme.accentInk, Theme.panel, 0.45)), block = sum(mix(Theme.accent, Theme.panel, 0.45))
            fuzzyCompare(seen.fill, block, 6)
            // Mực chữ đậm nhất gần màu web, xa màu khối: mờ từng lớp cho ~ 45% mực trên khối 45% (tổng ~162, web ~65)
            verify(Math.abs(seen.ink - web) <= 24, "ink " + seen.ink + " vs web " + web + " (block " + block + ")")
            verify(seen.b.layer.enabled)
        }
        function test_enabledButtonDrawsWithoutALayer() {
            const b = createTemporaryObject(button, host, {enabled: true})
            tryCompare(b, "opacity", 1)
            verify(!b.layer.enabled)
        }
    }
}
