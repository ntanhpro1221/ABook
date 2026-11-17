import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 300; height: 100
    Component { id: missing; Text { text: "\udbff\udfff"; font.family: Theme.family; font.pixelSize: 20 } }
    Component { id: cap; LookKbd {} }
    Component {
        id: symbol
        Rectangle {
            width: 60; height: 44; color: "white"
            property alias text: label.text
            Text { id: label; anchors.centerIn: parent; color: "black"; font.family: Theme.family; font.pixelSize: 24 }
        }
    }
    TestCase {
        name: "GlyphRegression"
        when: windowShown
        function test_arrows_data() {
            let rows = []
            for (const mode of ["light", "dark"])
                for (const arrow of ["←", "→", "↑", "↓"])
                    rows.push({tag: mode + arrow, mode: mode, arrow: arrow})
            return rows
        }
        function test_arrows(d) {
            Theme.mode = d.mode
            const key = createTemporaryObject(cap, host, {text: d.arrow})
            verify(key !== null)
            const icon = findChild(key, "keyArrow")
            verify(icon !== null && icon.path !== "", "arrow must have vector geometry")
            compare(key.Accessible.name, d.arrow)
            host.Window.window.update(); waitForRendering(key)
            const image = grabImage(key)
            let ink = 0
            // The inner area excludes the border; an empty cap must fail here.
            for (let y = 4; y < key.height - 4; ++y)
                for (let x = 4; x < key.width - 4; ++x)
                    if (Math.abs(image.red(x, y) - image.red(3, 3)) > 25) ++ink
            verify(ink >= 4, "arrow cap is empty")
            Theme.mode = "auto"
        }
        function test_missing() {
            if (!qtGlyphProbe) skip("Opt-in negative control; runner must expect exit 1")
            const text = createTemporaryObject(missing, host)
            verify(text !== null)
            host.Window.window.update(); waitForRendering(text)
            qtGlyphAudit.scan()
        }
        // Tên sách / tác giả / nhân vật / nghệ sĩ tiếng Nhật, Trung, Hàn: font dự phòng CJK (font hệ thống Windows) phải vẽ ra mực
        // ở cả ba độ đậm của app; máy dò GLYPH_MISSING quét đúng các chữ này, không chuỗi nào được miễn.
        function test_cjkNames_data() {
            const names = [{tag: "book-zh", text: "斗破苍穹 第一卷"}, {tag: "author-zh", text: "天蚕土豆"},
                {tag: "book-ja", text: "夜明けの旅路「序章」"}, {tag: "character-ja", text: "カタリナ・クラエス"},
                {tag: "artist-ja", text: "魔王魂"}, {tag: "book-ko", text: "달빛 조각사"}, {tag: "character-ko", text: "이서준"},
                {tag: "mixed", text: "Tập 1 · 魔王魂 – 별빛 · ０１２"}]
            const rows = []
            for (const weight of [Font.Normal, Font.Medium, Font.Bold])
                for (const name of names) rows.push({tag: name.tag + "-" + weight, text: name.text, weight: weight})
            return rows
        }
        function test_cjkNames(d) {
            const item = createTemporaryObject(symbol, host, {text: d.text, width: 300})
            item.children[0].font.weight = d.weight
            host.Window.window.update(); waitForRendering(item)
            const image = grabImage(item)
            let ink = 0
            for (let y = 0; y < item.height; ++y)
                for (let x = 0; x < item.width; ++x)
                    if (image.red(x, y) < 128) ++ink
            verify(ink >= 40 * d.text.length / 3, d.tag + " must draw visible ink, got " + ink)
            qtGlyphAudit.scan()
        }
        function test_bundledSymbols_data() {
            return [{tag: "arrow", text: "\u2192"}, {tag: "play", text: "\u25b6"}]
        }
        function test_bundledSymbols(d) {
            const item = createTemporaryObject(symbol, host, {text: d.text})
            host.Window.window.update(); waitForRendering(item)
            const image = grabImage(item)
            let ink = 0
            for (let y = 0; y < item.height; ++y)
                for (let x = 0; x < item.width; ++x)
                    if (image.red(x, y) < 128) ++ink
            verify(ink >= 12, "bundled " + d.tag + " must draw visible ink")
            qtGlyphAudit.scan()
        }
    }
}
