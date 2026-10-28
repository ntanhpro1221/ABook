import QtQuick
import QtTest
import ABook

// Bộ icon lucide của app (qml/Icon.qml): đo bằng điểm ảnh từng icon app đang dùng, ở cỡ thật 16 - 28.
// Mỗi icon: có mực; không chạm mép ô; tâm mực nằm trong 1/6 ô quanh giữa ô; Pause hai thanh không dính nhau (khe >= 1 điểm ảnh).
// Ngoài ra ghi tờ icon phóng to (sáng + tối) ra build/icon_sheet_*.png để mắt nhìn lại.
Item {
    id: host
    width: 900
    height: 600

    readonly property var names: ["library", "clapperboard", "settings", "panel-left-close", "panel-left-open", "arrow-left", "chevron-up", "chevron-down",
        "skip-back", "skip-forward", "list-ordered", "moon", "audio-lines", "check", "play", "pause", "rotate-ccw", "refresh-cw", "folder-open",
        "volume-1", "volume-2", "volume-x", "keyboard", "undo-2", "lightbulb", "laptop", "arrow-down-wide-narrow"]

    Component {
        id: probeFactory
        Rectangle {
            property string nm: ""
            property int sz: 24
            property color ink: "black"
            property bool dark: false
            width: sz + 8
            height: sz + 8
            color: dark ? "#141414" : "white"
            Icon { x: 4; y: 4; name: parent.nm; size: parent.sz; color: parent.ink }
        }
    }
    Component {
        id: sheetFactory
        Rectangle {
            property bool dark: false
            property var list: []
            width: 7 * 120 + 20
            height: Math.ceil(list.length / 7) * 120 + 20
            color: dark ? "#141414" : "#fbfaf8"
            Grid {
                x: 10
                y: 10
                columns: 7
                Repeater {
                    model: list
                    Item {
                        width: 120
                        height: 120
                        Icon { anchors.centerIn: parent; name: modelData; size: 96; color: dark ? "#f2efe9" : "#1d1b18" }
                    }
                }
            }
        }
    }

    TestCase {
        id: test
        name: "Icons"
        when: windowShown

        // mực: red < level trên nền trắng (250 = có dấu vết; 128 = phủ >= 50 %)
        function bounds(img, size, level) {
            let l = 1e9, r = -1, t = 1e9, b = -1, n = 0
            for (let y = 0; y < img.height; ++y)
                for (let x = 0; x < img.width; ++x) {
                    if (img.red(x, y) >= level) continue
                    ++n
                    l = Math.min(l, x); r = Math.max(r, x); t = Math.min(t, y); b = Math.max(b, y)
                }
            return { l: l, r: r, t: t, b: b, n: n }
        }

        function probe(nm, sz) {
            const item = createTemporaryObject(probeFactory, host, { nm: nm, sz: sz })
            waitForRendering(item)
            const img = grabImage(item)
            return img
        }

        function test_everyIconHasInkInsideItsBoxAndCentred_data() {
            const rows = []
            for (const nm of host.names)
                for (const sz of [16, 18, 20, 24, 28])
                    rows.push({ tag: nm + " " + sz, nm: nm, sz: sz })
            return rows
        }
        function test_everyIconHasInkInsideItsBoxAndCentred(d) {
            const img = probe(d.nm, d.sz)
            const any = bounds(img, d.sz, 250)
            verify(any.n > 0, d.nm + " không có mực (tên sai hoặc Shape không vẽ)")
            const b = bounds(img, d.sz, 128)
            verify(b.n > 0, d.nm + " không có mực đậm")
            // mép ô là [4, 4 + sz - 1]; mực đậm (phủ >= 50 %) không được chạm hàng / cột ngoài cùng (lucide chừa 1 đơn vị lưới: ở 16 px một điểm ảnh ngoài cùng chỉ phủ khoảng 1/3)
            verify(b.l > 4 && b.r < 4 + d.sz - 1 && b.t > 4 && b.b < 4 + d.sz - 1, d.nm + " " + d.sz + " chạm mép ô: " + JSON.stringify(b))
            // tâm mực lệch khỏi giữa ô không quá 1/6 ô
            const cx = (b.l + b.r) / 2 - 4 - (d.sz - 1) / 2, cy = (b.t + b.b) / 2 - 4 - (d.sz - 1) / 2
            verify(Math.abs(cx) <= d.sz / 6 && Math.abs(cy) <= d.sz / 6, d.nm + " " + d.sz + " lệch tâm " + cx.toFixed(2) + ", " + cy.toFixed(2))
        }

        function test_pauseBarsDoNotTouch_data() { return [{ tag: "20", sz: 20 }, { tag: "24", sz: 24 }, { tag: "28", sz: 28 }, { tag: "44", sz: 44 }] }
        function test_pauseBarsDoNotTouch(d) {
            const img = probe("pause", d.sz)
            const y = 4 + Math.round(d.sz / 2)
            const runs = []
            let start = -1
            for (let x = 4; x < 4 + d.sz; ++x) {
                const ink = img.red(x, y) < 128
                if (ink && start < 0) start = x
                if (!ink && start >= 0) { runs.push([start, x - 1]); start = -1 }
            }
            compare(runs.length, 2, "Pause phải có đúng hai thanh ở hàng giữa")
            const gap = runs[1][0] - runs[0][1] - 1
            verify(gap >= 1, "hai thanh dính nhau (khe " + gap + ")")
        }

        function test_playIsSolid() {
            const img = probe("play", 24)
            // điểm giữa tam giác phải đặc (tô, không chỉ viền)
            verify(img.red(4 + 11, 4 + 12) < 100, "Play không tô đặc")
        }

        function test_unknownNameDrawsNothing() {
            const img = probe("khong-co-icon-nay", 24)
            compare(bounds(img, 24, 250).n, 0)
        }

        function test_writeSheets() {
            for (const dark of [false, true]) {
                const sheet = createTemporaryObject(sheetFactory, host, { dark: dark, list: host.names })
                waitForRendering(sheet)
                const img = grabImage(sheet)
                const path = Qt.resolvedUrl("../../build/icon_sheet_" + (dark ? "dark" : "light") + ".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")   // D:/... trên Windows, /home/... trên Linux
                img.save(path)      // trả về void; có file hay không do người xem
            }
        }
    }
}
