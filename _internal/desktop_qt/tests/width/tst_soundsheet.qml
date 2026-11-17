import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

Item {
    id: host
    width: 360; height: 780
    Rectangle { anchors.fill: parent; color: Theme.panel }
    Component {
        id: factory
        Flickable {
            id: sheetScroll
            width: host.width; height: host.height; contentHeight: page.height; clip: true
            AudioFxPanel { id: page; width: parent.width - 40; x: 20; openMusic: () => {} }
            // Như khung thật của bảng (Modal: ScrollEdges trên nền panel) - ảnh chụp không cắt cứng dòng ở mép cuộn.
            ScrollEdges { parent: host; z: 1; target: sheetScroll; color: Theme.panel; width: host.width; height: host.height }
        }
    }
    TestCase {
        name: "SoundSheet"
        when: windowShown
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        function reply(on) {
            const data = {hasMusic:true,enabled:on,levelDb:-20}
            WidthNet.setAnswer("GET /api/books/width/music",data)
            WidthNet.setAnswer("PUT /api/books/width/music",data)
        }
        function init() {
            Nav.uiVisible = true; Nav.layers = []; Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            reply(true); Player.open("width",1,0,false); Music.reload("width")
            Player.setVolume(1); Player.setAudioFx({mono:false,balance:0,pitch:0,boost:0,skipSilence:false})
        }
        function cleanup() { Player.close(); WidthNet.resetAnswers(); Theme.mode = "auto"; Nav.layers = [] }
        function shot(name) {
            ready()
            const file = Qt.resolvedUrl("../../build/d2shots/soundsheet_"+name+".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/,"$1").replace(/^file:\/\//,"")
            const image = grabImage(VisualReady.grabTarget(host.Window.window,host))
            verify(image.width > 0); image.save(file); verify(qtUiTree.save(file,VisualReady.grabTarget(host.Window.window,host)))
        }
        function test_sections_and_music_dependencies_data() { return [{tag:"normal",scale:1,height:780},{tag:"large",scale:1.3,height:780},{tag:"full",scale:1,height:1200},{tag:"full-large",scale:1.3,height:1200}] }
        function scaleFonts(item, scale) {
            if (item.font !== undefined && item.text !== undefined) item.font.pixelSize *= scale
            for (const child of item.children || []) scaleFonts(child, scale)
        }
        function test_sections_and_music_dependencies(data) {
            host.height = data.height; host.Window.window.height = data.height
            tryCompare(Music,"hasMusic",true); tryCompare(Music,"enabled",true)
            for (const mode of ["light","dark"]) {
                Theme.mode = mode
                const view = createTemporaryObject(factory,host); verify(view)
                if (data.scale > 1) scaleFonts(view,data.scale)
                ready()
                const name = mode + (data.scale > 1 ? "_130" : "") + (data.height > 780 ? "_full" : "")
                const details = findChild(view,"audioFxMusicDetails")
                verify(details); compare(details.open,true)
                const slider = findChild(view,"audioFxMusicLevel")
                compare(slider.spec.min,-40); compare(slider.spec.max,-6); compare(slider.livePreview,false)
                shot(name)
                view.contentY = Math.max(0,view.contentHeight-view.height); shot(name+"_bottom")
                reply(false); Music.setEnabled(false); tryCompare(Music,"enabled",false); ready()
                compare(details.open,false); compare(details.height,0); shot(name+"_off")
                reply(true); Music.setEnabled(true); tryCompare(Music,"enabled",true); ready()
                compare(details.open,true)
                view.destroy()
            }
        }
    }
}
