import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 300; height: 100
    Component { id: missing; Text { text: "\udbff\udfff"; font.family: Theme.family; font.pixelSize: 20 } }
    Component { id: cap; LookKbd {} }
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
            wait(40)
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
            wait(100)
            qtGlyphAudit.scan()
        }
    }
}
