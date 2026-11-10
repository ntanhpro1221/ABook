import QtQuick
import QtTest
import "VisualReady.js" as VisualReady

Item {
    id: host
    width: 360
    height: 780
    Rectangle {
        x: 20; y: 100; width: 200; height: 48
        color: "#d4912b"
        Accessible.role: Accessible.Button
        Text { x: 12; y: 12; text: "Play"; font.pixelSize: 16; color: "#1a1814" }
    }
    TestCase {
        name: "UiTreeCapture"
        when: windowShown
        function test_exports_the_rendered_frame() {
            host.Window.window.update()
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            const path = Qt.resolvedUrl("../../build/d2shots/design_lint_capture_probe.png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(host).save(path)
            verify(qtUiTree.save(path, host))
            const request = new XMLHttpRequest()
            request.open("GET", Qt.resolvedUrl("../../build/d2shots/design_lint_capture_probe.tree.json"), false)
            request.send()
            const tree = JSON.parse(request.responseText)
            compare(tree.schema, 1)
            compare(tree.width, 360)
            compare(tree.image_sha256.length, 64)
            const text = tree.nodes.find(n => n.text === "Play")
            verify(text !== undefined)
            compare(text.font_size, 16)
            compare(text.line_count, 1)
            compare(text.lines.length, 1)
            verify(tree.nodes.some(n => n.role === "button"))
        }
    }
}
