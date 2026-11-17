import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 1000; height: 800
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: modalFactory; Modal { title: "Hộp thử"; Text { text: "Nội dung"; color: Theme.text } } }
    Component { id: popoverFactory; Popover { Text { text: "Nội dung"; color: Theme.text; height: 120 } } }
    Item { id: anchor; x: 400; y: 100; width: 40; height: 40 }
    TestCase {
        name: "SurfaceMotion"
        when: windowShown
        function cleanup() { qtAnimationClock.end(); Theme.mode = "auto"; Nav.layers = [] }
        function test_surfaceMovesAsOneGroup_data() {
            return [{tag:"modal-light",mode:"light",factory:modalFactory,name:"modalPanel"},
                    {tag:"modal-dark",mode:"dark",factory:modalFactory,name:"modalPanel"},
                    {tag:"popover-light",mode:"light",factory:popoverFactory,name:"popoverPanel"},
                    {tag:"popover-dark",mode:"dark",factory:popoverFactory,name:"popoverPanel"}]
        }
        function test_surfaceMovesAsOneGroup(data) {
            Theme.mode = data.mode
            const window = createTemporaryObject(data.factory, host)
            if (window.anchorItem !== undefined) window.anchorItem = anchor
            waitForRendering(host)
            const panel = findChild(window, data.name)
            verify(panel !== null)
            compare(panel.composition.layer.enabled, false, "closed surfaces retain no compositing target")
            const folder = Qt.resolvedUrl("../../build/surface_frames/").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(host.Window.window.contentItem).save(folder + data.tag + "-baseline.png")
            qtAnimationClock.begin()
            window.show()
            verify(panel.composition.x <= -96, "layer must retain the shadow extent")
            const offsets = []
            const positions = []
            for (let i = 0; i < 16; ++i) {
                qtAnimationClock.step(16)
                waitForRendering(host)
                // The first animation tick may still be at shown 0: nothing paints then.
                compare(panel.composition.layer.enabled, panel.visible, "surface and shadow must fade as one group")
                if (!panel.visible) continue
                const shadow = panel.surfaceData.find(child => child.source !== undefined && String(child.source).indexOf("image://shadow/") === 0)
                verify(shadow !== undefined)
                const p = panel.mapToItem(host, 0, 0)
                const s = shadow.mapToItem(host, shadow.pad, shadow.pad)
                offsets.push(Math.abs(s.y - p.y) + Math.abs(s.x - p.x))
                positions.push(p.y)
                grabImage(host.Window.window.contentItem).save(folder + data.tag + "-" + i + ".png")
                console.log("SURFACE_FRAME " + JSON.stringify({tag:data.tag,frame:i,x:p.x,y:p.y,width:panel.width*panel.scale,height:panel.height*panel.scale,shown:window.shown,shadowX:s.x,shadowY:s.y}))
            }
            verify(Math.max.apply(null, offsets) < .01, "shadow detached from moving panel: " + offsets)
            verify(Math.max.apply(null, positions) - Math.min.apply(null, positions) > 1)
            window.close()
            for (let i = 0; i < 12; ++i) {
                qtAnimationClock.step(16)
                const shadow = panel.surfaceData.find(child => child.kind !== undefined && child.pad !== undefined)
                const p = panel.mapToItem(host, 0, 0), s = shadow.mapToItem(host, shadow.pad, shadow.pad)
                fuzzyCompare(s.x, p.x, .01); fuzzyCompare(s.y, p.y, .01)
            }
            compare(window.visible, false)
            compare(panel.composition.layer.enabled, false)
            window.show()
            for (let i = 0; i < 4 && !panel.visible; ++i) {
                compare(panel.composition.layer.enabled, false)
                qtAnimationClock.step(16)
            }
            verify(panel.visible)
            verify(panel.composition.layer.enabled, "reopening restores group composition before painting")
        }
    }
}
