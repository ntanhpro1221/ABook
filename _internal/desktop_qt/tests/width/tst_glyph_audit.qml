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
