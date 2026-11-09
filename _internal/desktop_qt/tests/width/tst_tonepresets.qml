import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
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
        function shot(name) {
            VisualReady.render(this,host.Window.window,host,qtVisualReady)
            const file=Qt.resolvedUrl("../../build/d2shots/"+name+".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/,"$1").replace(/^file:\/\//,"")
            const image=grabImage(VisualReady.grabTarget(host.Window.window,host));verify(image.width>0);image.save(file)
        }
        function test_gallery360At130Percent() {
            Player.toneAction("select",{id:"clear"})
            for(const mode of ["light","dark"]) {
                Theme.mode=mode
                const view=createTemporaryObject(factory,host);verify(view)
                VisualReady.render(this,host.Window.window,host,qtVisualReady)
                largeText(view)
                compare(Player.tones.selected.id,"clear")
                compare(Player.tones.builtins.length,7)
                shot("tone_360_130_"+mode+"_list")
                view.contentY=Math.max(0,view.contentHeight-view.height)
                shot("tone_360_130_"+mode+"_bands")
                view.destroy()
            }
            Player.toneAction("select",{id:"off"});Theme.mode="auto"
        }
        function test_deleteShowsUndoInTheViewport() {
            Player.toneAction("select",{id:"clear"});Player.toneAction("save",{name:"Undo"})
            const id=Player.tones.selected.id
            const view=createTemporaryObject(factory,host);verify(view)
            VisualReady.render(this,host.Window.window,host,qtVisualReady)
            const remove=findChild(view,"toneDelete");verify(remove)
            view.contentY=Math.max(0,remove.mapToItem(view.contentItem,0,0).y-100)
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
