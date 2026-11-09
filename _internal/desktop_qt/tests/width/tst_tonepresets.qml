import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import "../../qml/PlayerLabels.js" as PlayerLabels
import ABook

Item {
    id:host
    width:360;height:780
    Rectangle { anchors.fill:parent;color:Theme.panel }
    Component {
        id:factory
        Flickable {
            width:360;height:780;contentHeight:page.height;clip:true
            TonePage { id:page;objectName:"toneGalleryPage";width:parent.width-40;x:20 }
        }
    }
    TestCase {
        name:"TonePresetUi"
        when:windowShown
        function largeText(item) {
            if(item.font!==undefined && item.text!==undefined)item.font.pixelSize=item.font.pixelSize*1.3
            for(const child of item.children||[])largeText(child)
        }
        function hasText(item,text) {
            if(item.text===text)return true
            for(const child of item.children||[])if(hasText(child,text))return true
            return false
        }
        function shot(name) {
            VisualReady.render(this,host.Window.window,host,qtVisualReady)
            const file=Qt.resolvedUrl("../../build/d2shots/"+name+".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/,"$1").replace(/^file:\/\//,"")
            const image=grabImage(VisualReady.grabTarget(host.Window.window,host));verify(image.width>0);image.save(file)
        }
        function test_gallery360At130Percent() {
            // Như Android / web: hai dòng Của tôi, rồi chọn Giọng rõ.
            Player.toneAction("select",{id:"warm"});Player.toneAction("edit",{index:4,value:-5});Player.toneAction("save",{name:"Đêm khuya"})
            Player.toneAction("select",{id:"soft"});Player.toneAction("save",{name:"Tai nghe cũ"})
            const saved=Player.tones.mine.map(p=>p.id)
            Player.toneAction("select",{id:"clear"})
            for(const mode of ["light","dark"]) {
                Theme.mode=mode
                const view=createTemporaryObject(factory,host);verify(view)
                VisualReady.render(this,host.Window.window,host,qtVisualReady)
                largeText(view)
                compare(Player.tones.selected.id,"clear")
                compare(Player.tones.builtins.length,7)
                verify(findChild(view,"toneMore"))
                verify(hasText(view,"−4 dB"))
                shot("tone_360_130_"+mode+"_top")
                const more=findChild(view,"toneMore")
                view.contentY=Math.max(0,more.mapToItem(view.contentItem,0,0).y+more.height-view.height)
                shot("tone_360_130_"+mode+"_presets")
                mouseClick(more)
                VisualReady.render(this,host.Window.window,host,qtVisualReady)
                tryVerify(function(){return findChild(view,"toneDelete").height>0})
                view.contentY=Math.max(0,view.contentHeight-view.height)
                shot("tone_360_130_"+mode+"_mine")
                view.destroy()
            }
            for(const id of saved)Player.toneAction("delete",{id:id})
            Player.toneAction("select",{id:"off"});Theme.mode="auto"
        }
        // Số âm là dấu trừ thật (U+2212), dương có "+", 0 trơn - một hàm cho mọi số hai phía của Âm thanh / Âm sắc.
        function test_signedLabels() {
            compare(PlayerLabels.signed(-4),"−4");compare(PlayerLabels.signed(2),"+2");compare(PlayerLabels.signed(-0),"0")
            compare(PlayerLabels.signed(-1.5),"−1,5");compare(PlayerLabels.signed(0.5),"+0,5")
        }
        function test_deleteShowsUndoInTheViewport() {
            Player.toneAction("select",{id:"clear"});Player.toneAction("save",{name:"Undo"})
            const id=Player.tones.selected.id
            const view=createTemporaryObject(factory,host);verify(view)
            VisualReady.render(this,host.Window.window,host,qtVisualReady)
            const more=findChild(view,"toneMore");verify(more)
            view.contentY=Math.max(0,more.mapToItem(view.contentItem,0,0).y-100)
            VisualReady.render(this,host.Window.window,host,qtVisualReady)
            mouseClick(more)
            const remove=findChild(view,"toneDelete");verify(remove)
            tryVerify(function(){return remove.parent.parent.height>=remove.height})
            VisualReady.render(this,host.Window.window,host,qtVisualReady)
            mouseClick(remove)
            VisualReady.render(this,host.Window.window,host,qtVisualReady)
            const undo=findChild(view,"toneUndo");verify(undo)
            const point=undo.mapToItem(view,0,0)
            verify(point.y>=0 && point.y+undo.height<=view.height+.5)
            mouseClick(undo)
            compare(Player.tones.selected.id,id)
            Player.toneAction("delete",{id:id});Player.toneAction("select",{id:"off"});view.destroy()
        }
    }
}
