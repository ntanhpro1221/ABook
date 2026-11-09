import "UiStrings.js" as S
import "ToneLabels.js" as ToneLabels
import QtQuick
import QtQuick.Controls.Basic as C
import ABook

Column {
    id: root
    property var library: Player.tones
    property var pending: null
    property var deleted: null; onDeletedChanged: if(deleted!==null)Later.call(root,showLast)
    property string form: ""
    property string target: ""
    property bool afterName: false
    readonly property var current: library.selected
    readonly property string toneName: library.dirty || current.id === "draft" ? S.s_tone_draft : (library.preset.name || ToneLabels.label(current.id) || S.s_tat_3286064e)
    signal backRequested()
    spacing: Theme.s4
    function leave(action) {
        if(form !== "") { form="";afterName=false;return }
        if(pending !== null) { pending=null;return }
        if (library.hasEdits) { Player.toneAction("prepareLeave"); pending = action } else action()
    }
    function showLast() { for(let item=parent;item;item=item.parent)if(item.contentY!==undefined&&item.contentHeight!==undefined){item.contentY=Math.max(0,item.contentHeight-item.height);break} }
    onPendingChanged: if(pending!==null)Later.call(root,showLast)
    onFormChanged: if(form!=="")Later.call(root,showLast)
    function close() { leave(() => root.backRequested()) }
    function finish() { if(Player.tones.hasEdits){Player.toneAction("prepareLeave");return} const action = pending; pending = null; if (action) action() }
    function namePreset(kind, id, value, thenLeave) { form = kind; target = id; nameField.text = value; afterName = thenLeave; nameField.forceActiveFocus() }
    function saveName() {
        if (!nameField.text.trim()) return
        Player.toneAction(form, {id:target, name:nameField.text})
        form = ""
        if (afterName) { afterName = false; finish() }
    }
    TextLink { text: S.s_tone_back; onClicked: root.close() }
    Text { width: parent.width; text: S.s_am_sac_8c2f4e1a; color: Theme.text; font.pixelSize: Theme.sizeSection; wrapMode: Text.Wrap }
    Text { width: parent.width; text: S.s_tone_builtins; color: Theme.text2; font.pixelSize: Theme.sizeCaption; topPadding: Theme.s12 }
    Repeater {
        model: root.library.builtins
        MenuRow { required property var modelData; width: root.width; height: Math.max(48, implicitHeight); text: ToneLabels.label(modelData.id); selected: root.current.id === modelData.id; icon: selected ? "check" : ""; onClicked: Player.toneAction("select",{id:modelData.id}) }
    }
    Text { width: parent.width; text: S.s_tone_mine; color: Theme.text2; font.pixelSize: Theme.sizeCaption; topPadding: Theme.s12 }
    Repeater {
        model: root.library.mine
        Row {
            id: userRow
            required property var modelData
            required property int index
            width: root.width; height: Math.max(48, choice.implicitHeight)
            MenuRow { id: choice; width: parent.width - 48; height: parent.height; text: userRow.modelData.name; selected: root.current.id === userRow.modelData.id; icon: selected ? "check" : ""; onClicked: Player.toneAction("select",{id:userRow.modelData.id}) }
            Item {
                width: 48; height: parent.height
                Accessible.name: S.s_tone_drag
                Canvas { anchors.centerIn: parent; width: 16; height: 16; onPaint: { const c=getContext("2d");c.clearRect(0,0,width,height);c.strokeStyle=Theme.text2;c.lineWidth=2;for(let i=0;i<3;i++){c.beginPath();c.moveTo(0,3+i*5);c.lineTo(16,3+i*5);c.stroke()} } }
                MouseArea { anchors.fill: parent; property real start: 0; onPressed: event => { start = mapToItem(root,0,event.y).y }; onReleased: event => { const distance=mapToItem(root,0,event.y).y-start;Player.toneAction("move",{id:userRow.modelData.id,to:userRow.index+Math.round(distance/userRow.height)}) } }
            }
        }
    }
    Flow {
        width: parent.width; spacing: Theme.s12; visible: root.current.id.indexOf("user:") === 0
        TextLink { text:S.s_doi_ten_a2a0dc70; onClicked:root.namePreset("rename",root.current.id,root.library.preset.name,false) }
        TextLink { text:S.s_tone_duplicate; onClicked:root.namePreset("duplicate",root.current.id,S.s_tone_suggest(root.library.mine.length+1),false) }
        TextLink { objectName:"toneDelete";text:S.s_xoa_777195ab; onClicked:{root.deleted=Player.toneAction("delete",{id:root.current.id});undoLife.restart()} }
    }
    Text { width: parent.width; text: root.toneName; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap; topPadding: Theme.s12 }
    Canvas {
        id: curve
        width: parent.width; height: 96
        property var bands: root.current.bands
        onBandsChanged: requestPaint()
        onPaint: {
            const c=getContext("2d");c.clearRect(0,0,width,height);c.strokeStyle=Theme.line;c.beginPath();c.moveTo(0,48);c.lineTo(width,48);c.stroke()
            c.strokeStyle=Theme.accent;c.lineWidth=2;c.beginPath()
            for(let i=0;i<5;i++){const x=12+(width-24)*i/4,y=48-bands[i]*3.4;if(i===0)c.moveTo(x,y);else c.lineTo(x,y)}c.stroke()
        }
    }
    Row {
        width: parent.width
        Repeater {
            model: [S.s_tone_band_0,S.s_tone_band_1,S.s_tone_band_2,S.s_tone_band_3,S.s_tone_band_4]
            Column {
                required property string modelData
                required property int index
                width: root.width/5
                ClockLabel { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: S.s_tone_db(root.current.bands[index]); color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                C.Slider {
                    id: band
                    width: parent.width; height: 144; orientation: Qt.Vertical
                    from:-12;to:12;stepSize:1;value:root.current.bands[parent.index]
                    Accessible.name: parent.modelData
                    onMoved:Player.toneAction("edit",{index:parent.index,value:value})
                    background: Rectangle { x:band.width/2-2;y:8;width:4;height:128;radius:width/2;color:Theme.line }
                    handle: Rectangle { x:band.width/2-7;y:8+band.visualPosition*(128-height);width:14;height:14;radius:height/2;color:Theme.accent }
                    TapHandler { onDoubleTapped:Player.toneAction("edit",{index:band.parent.index,value:0}) }
                }
                Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: parent.modelData; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
            }
        }
    }
    Text { width:parent.width;text:S.s_tone_reset;color:Theme.text2;font.pixelSize:Theme.sizeCaption;wrapMode:Text.Wrap }
    TextLink { visible:root.current.id==="draft"||root.library.dirty;text:S.s_tone_save;onClicked:root.namePreset("save","",S.s_tone_suggest(root.library.mine.length+1),false) }
    Row {
        width: parent.width; height: Math.max(48, scopeLabel.implicitHeight)
        Text { id:scopeLabel;width:parent.width-48;anchors.verticalCenter:parent.verticalCenter;text:S.s_tone_scope;color:Theme.text;font.pixelSize:Theme.sizeBodySmall;wrapMode:Text.Wrap }
        Switch { checked:root.library.scoped;label:S.s_tone_scope;anchors.verticalCenter:parent.verticalCenter;onToggled:value=>Player.toneAction("scope",{enabled:value}) }
    }
    Column {
        width:parent.width;visible:root.pending!==null
        Text { width:parent.width;text:S.s_tone_leave;color:Theme.text;font.pixelSize:Theme.sizeBodySmall;wrapMode:Text.Wrap }
        TextLink { text:S.s_tone_overwrite;onClicked:{Player.toneAction("save",{name:root.library.preset.name,overwrite:true});root.finish()} }
        TextLink { text:S.s_tone_new;onClicked:root.namePreset("save","",S.s_tone_suggest(root.library.mine.length+1),true) }
        TextLink { text:S.s_tone_discard;onClicked:{Player.toneAction("discard");root.finish()} }
    }
    Column {
        width:parent.width;visible:root.form!==""
        FormField { id:nameField;width:parent.width;label:S.s_tone_name;onAccepted:root.saveName() }
        Flow { width:parent.width;spacing:Theme.s16;TextLink { text:S.s_luu_e91f26c0;onClicked:root.saveName() } TextLink { text:S.s_tone_back;onClicked:{root.form="";root.afterName=false} } }
    }
    Row {
        width:parent.width;visible:root.deleted!==null;spacing:Theme.s12
        Text { width:parent.width-undoAction.width-parent.spacing;text:S.s_tone_deleted;color:Theme.text;font.pixelSize:Theme.sizeBodySmall;wrapMode:Text.Wrap }
        TextLink { id:undoAction;objectName:"toneUndo";text:S.s_hoan_tac_e72ff675;onClicked:{Player.toneAction("undo",root.deleted);root.deleted=null} }
    }
    Timer { id:undoLife;interval:7000;onTriggered:root.deleted=null }
}
