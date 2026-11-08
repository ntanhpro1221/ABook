import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

Item {
    id: host
    width: 1024; height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: factory; Popover { panelWidth: 360; maxHeight: 800; AudioFxPanel {} } }
    Item { id: anchor; x: 900; y: 30; width: 44; height: 44 }
    TestCase {
        name: "AudioFxUi"
        when: windowShown
        function test_settings_back_and_screenshots() {
            Nav.uiVisible=true
            Player.setAudioFx({enabled:true,preset:1,boost:6,pitch:-1.5})
            compare(Player.audioFx.bands[3],3)
            compare(Player.audioFx.pitch,-1.5)
            for(const mode of ["light","dark"]) {
                Theme.mode=mode
                const panel=createTemporaryObject(factory,host,{anchorItem:anchor})
                verify(panel)
                panel.show(); tryCompare(panel,"shown",1)
                verify(Nav.layers.length>0)
                VisualReady.render(this,host.Window.window,host,qtVisualReady)
                const path=Qt.resolvedUrl("../../build/d2shots/audiofx_"+mode+".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/,"$1").replace(/^file:\/\//,"")
                const image=grabImage(VisualReady.grabTarget(host.Window.window,host))
                verify(image.width>0)
                image.save(path)
                Nav.back();tryCompare(panel,"open",false)
                panel.destroy()
            }
            Player.setAudioFx({preset:0,pitch:0,boost:0,enabled:false})
            Theme.mode="auto"
        }
    }
}
