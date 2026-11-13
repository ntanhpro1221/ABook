import "UiStrings.js" as S
import "ToneLabels.js" as ToneLabels
import "PlayerLabels.js" as Labels
import "TextWrap.js" as TextWrap
import QtQuick
import QtQuick.Controls.Basic as C
import ABook

// Trang Âm sắc (cùng bố cục Android / web): đầu trang ← + tên; vùng chỉnh ở trên (tên đang dùng, đường cong trong khung có vạch 0 dB,
// năm thanh dọc) để chọn một âm sắc là thấy ngay đường cong đổi, không phải cuộn; danh sách Có sẵn / Của tôi ở dưới. Dòng: dấu chọn tròn,
// tên, đường cong nhỏ; dòng Của tôi có nút … (Đổi tên / Nhân bản / Xoá); "Tạo âm sắc" ở cuối nhóm.
Column {
    id: root
    property var library: Player.tones
    property var pending: null
    property var deleted: null; onDeletedChanged: if(deleted!==null)Later.call(root,showLast)
    property string form: ""
    property string target: ""
    property string menu: ""
    property bool afterName: false
    readonly property var current: library.selected
    readonly property string toneName: library.dirty || current.id === "draft" ? S.s_tone_draft : (library.preset.name || ToneLabels.label(current.id) || S.s_tat_3286064e)
    readonly property string suggest: S.s_tone_suggest(library.mine.length+1)
    signal backRequested()
    spacing: 0
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
    // Hàm của trang (không trong ToneRow): thành phần nội tuyến không thấy id undoLife của tệp.
    function deleteTone(id) { menu = ""; deleted = Player.toneAction("delete", {id: id}); undoLife.restart() }
    function namePreset(kind, id, value, thenLeave) { menu = ""; form = kind; target = id; nameField.text = value; afterName = thenLeave; nameField.forceActiveFocus() }
    function saveName() {
        if (!nameField.text.trim()) return
        Player.toneAction(form, {id:target, name:nameField.text})
        form = ""
        if (afterName) { afterName = false; finish() }
    }

    // Một đường cong âm sắc (lớn và nhỏ dùng chung): điểm i ở tâm cột i trong năm cột, ±12 dB chạm mép, nối mềm, hai đầu kéo phẳng ra mép.
    component ToneCurve: Canvas {
        property var bands: [0,0,0,0,0]
        property color ink: Theme.accent
        property real stroke: 2
        property bool dots: false
        property bool zeroLine: false
        onBandsChanged: requestPaint(); onInkChanged: requestPaint(); onWidthChanged: requestPaint(); onHeightChanged: requestPaint()
        onPaint: {
            const c=getContext("2d");c.clearRect(0,0,width,height)
            if(zeroLine){c.strokeStyle=Theme.line;c.lineWidth=1;c.setLineDash([4,4]);c.beginPath();c.moveTo(0,height/2);c.lineTo(width,height/2);c.stroke();c.setLineDash([])}
            const half=height/2-stroke,p=[];for(let i=0;i<5;i++)p.push([width*(i+.5)/5,height/2-bands[i]/12*half])
            c.strokeStyle=ink;c.lineWidth=stroke;c.lineCap="round";c.beginPath();c.moveTo(0,p[0][1]);c.lineTo(p[0][0],p[0][1])
            for(let i=1;i<5;i++){const mid=(p[i-1][0]+p[i][0])/2;c.bezierCurveTo(mid,p[i-1][1],mid,p[i][1],p[i][0],p[i][1])}
            c.lineTo(width,p[4][1]);c.stroke()
            if(dots){c.fillStyle=ink;for(const [x,y] of p){c.beginPath();c.arc(x,y,3,0,Math.PI*2);c.fill()}}
        }
    }
    // Một âm sắc: dấu chọn tròn (đầy khi đang dùng), tên, đường cong nhỏ; dòng Của tôi thêm nút … mở hàng Đổi tên / Nhân bản / Xoá ngay dưới.
    component ToneRow: Column {
        id: row
        required property var modelData
        readonly property var preset: modelData
        property bool mine: false
        readonly property bool chosen: root.current.id === preset.id
        readonly property string name: mine ? preset.name : ToneLabels.label(preset.id)
        width: root.width
        Item {
            width: parent.width; height: Math.max(56, label.implicitHeight + Theme.s16)
            Accessible.role: Accessible.RadioButton; Accessible.name: row.name; Accessible.checked: row.chosen
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Player.toneAction("select",{id:row.preset.id}) }
            Rectangle {
                width: 20; height: 20; radius: width / 2; anchors.verticalCenter: parent.verticalCenter
                color: "transparent"; border.width: 2; border.color: row.chosen ? Theme.accent : Theme.text2
                Rectangle { anchors.centerIn: parent; width: 10; height: 10; radius: width / 2; color: Theme.accent; scale: row.chosen ? 1 : 0; Behavior on scale { NumberAnimation { duration: Theme.motionFast } } }
            }
            Text { id: label; x: 32; width: thumb.x - x - Theme.s8; anchors.verticalCenter: parent.verticalCenter; text: TextWrap.keepDots(row.name); wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
            ToneCurve { id: thumb; x: parent.width - width - (row.mine ? 44 : 4); anchors.verticalCenter: parent.verticalCenter; width: 48; height: 24; bands: row.preset.bands; ink: row.chosen ? Theme.accent : Theme.text2; stroke: 1.5 }
            IconButton {
                objectName: row.mine ? "toneMore" : ""; Reveal { shown: row.mine } icon: "ellipsis"; ink: Theme.text2; x: parent.width - width + 10; anchors.verticalCenter: parent.verticalCenter
                tip: S.s_them_tuy_chon_cho_0_82a2cf4d(row.name); Accessible.name: S.s_them_tuy_chon_cho_0_82a2cf4d(row.name)
                onClicked: root.menu = root.menu === row.preset.id ? "" : row.preset.id
            }
        }
        Item { id: itemItem;
            width: parent.width; height: root.menu === row.preset.id ? actions.implicitHeight : 0; clip: true; Reveal { shown: row.mine && itemItem.height > 0 }
            Behavior on height { NumberAnimation { duration: Theme.motionFast } }
            Flow {
                id: actions; x: 32; width: parent.width - x; spacing: Theme.s24
                TextLink { accent: true; text: S.s_doi_ten_a2a0dc70; onClicked: root.namePreset("rename",row.preset.id,row.preset.name,false) }
                TextLink { accent: true; text: S.s_tone_duplicate; onClicked: root.namePreset("duplicate",row.preset.id,root.suggest,false) }
                TextLink { objectName: row.mine ? "toneDelete" : ""; danger: true; text: S.s_xoa_777195ab; onClicked: root.deleteTone(row.preset.id) }
            }
        }
        Rectangle { width: parent.width; height: 1; color: Theme.line }
    }
    component Group: Text { width: root.width; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; topPadding: Theme.s16; bottomPadding: Theme.s4 }

    Item {
        width: parent.width; height: 48
        IconButton { id: back; x: -10; anchors.verticalCenter: parent.verticalCenter; icon: "arrow-left"; tip: S.s_quay_lai_6d793582; Accessible.name: S.s_quay_lai_6d793582; onClicked: root.close() }
        Text { x: back.width - 10 + Theme.s8; width: parent.width - x; anchors.verticalCenter: parent.verticalCenter; text: S.s_am_sac_8c2f4e1a; color: Theme.text; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium; wrapMode: Text.Wrap }
    }
    Item {
        width: parent.width; height: Math.max(48, nowName.implicitHeight)
        Text { id: nowName; width: parent.width - (saveLink.visible ? saveLink.width + Theme.s12 : 0); anchors.verticalCenter: parent.verticalCenter; text: root.toneName; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium; wrapMode: Text.Wrap; Accessible.role: Accessible.StaticText }
        TextLink {
            id: saveLink; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; accent: true; text: S.s_tone_save
            visible: opacity > 0; opacity: root.current.id==="draft"||root.library.dirty ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            onClicked: root.namePreset("save","",root.suggest,false)
        }
    }
    Rectangle {
        width: parent.width; height: 104; radius: Theme.radiusControl; color: "transparent"; border.width: 1; border.color: Theme.line
        ToneCurve { y: Theme.s12; width: parent.width; height: parent.height - 2*Theme.s12; bands: root.current.bands; dots: true; zeroLine: true; Accessible.name: S.s_am_sac_8c2f4e1a }
    }
    Row {
        width: parent.width; topPadding: Theme.s8
        Repeater {
            model: [S.s_tone_band_0,S.s_tone_band_1,S.s_tone_band_2,S.s_tone_band_3,S.s_tone_band_4]
            Column {
                required property string modelData
                required property int index
                width: root.width/5
                ClockLabel { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: S.s_tone_db(Labels.signed(root.current.bands[index])); color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                C.Slider {
                    id: band
                    width: parent.width; height: 136; orientation: Qt.Vertical
                    from:-12;to:12;stepSize:1;value:root.current.bands[parent.index]
                    Accessible.name: parent.modelData
                    Accessible.description: S.s_tone_db(Labels.signed(value))
                    onMoved:Player.toneAction("edit",{index:parent.index,value:value})
                    readonly property real thumbY: 10+band.visualPosition*(height-20)
                    // Rãnh, vạch 0 giữa rãnh và đoạn tô từ 0 tới núm.
                    background: Item {
                        x: band.width/2-2; y: 10; width: 4; height: band.height-20
                        Rectangle { anchors.fill: parent; radius: width / 2; color: Theme.line }
                        Rectangle { x: -6; y: parent.height/2; width: 16; height: 1; color: Theme.text2 }
                        Rectangle { width: 4; radius: width / 2; color: Theme.accent; y: Math.min(band.thumbY, band.height/2)-10; height: Math.abs(band.thumbY-band.height/2) }
                    }
                    handle: Rectangle { x:band.width/2-7;y:band.thumbY-7;width:14;height:14;radius:height/2;color:Theme.accent }
                    TapHandler { onDoubleTapped:Player.toneAction("edit",{index:band.parent.index,value:0}) }
                }
                Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: parent.modelData; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
            }
        }
    }
    Text { width:parent.width;topPadding:Theme.s8;horizontalAlignment:Text.AlignHCenter;text:S.s_tone_reset;color:Theme.text2;font.pixelSize:Theme.sizeCaption;wrapMode:Text.Wrap }
    Group { text: S.s_tone_builtins }
    Repeater { model: root.library.builtins; ToneRow {} }
    Group { text: S.s_tone_mine }
    Repeater { model: root.library.mine; ToneRow { mine: true } }
    Interactive {
        objectName: "toneAdd"; width: addRow.width; height: 48; tip: S.s_tone_add; Accessible.name: S.s_tone_add
        onClicked: root.namePreset("save","",root.suggest,false)
        Row { id: addRow; height: parent.height; spacing: Theme.s12; Icon { anchors.verticalCenter: parent.verticalCenter; name: "plus"; color: Theme.accentText } Text { anchors.verticalCenter: parent.verticalCenter; text: S.s_tone_add; color: Theme.accentText; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium } }
    }
    Row {
        width: parent.width; height: Math.max(48, scopeLabel.implicitHeight)
        Text { id:scopeLabel;width:parent.width-48;anchors.verticalCenter:parent.verticalCenter;text:S.s_copy_0aedb2b2cf2b;color:Theme.text;font.pixelSize:Theme.sizeBodySmall;wrapMode:Text.Wrap }
        Switch { checked:root.library.scoped;label:S.s_copy_0aedb2b2cf2b;anchors.verticalCenter:parent.verticalCenter;onToggled:value=>Player.toneAction("scope",{enabled:value}) }
    }
    Column {
        width:parent.width;Reveal { shown: root.pending!==null }
        Text { width:parent.width;text:S.s_tone_leave;color:Theme.text;font.pixelSize:Theme.sizeBodySmall;wrapMode:Text.Wrap }
        TextLink { text:S.s_tone_overwrite;onClicked:{Player.toneAction("save",{name:root.library.preset.name,overwrite:true});root.finish()} }
        TextLink { text:S.s_tone_new;onClicked:root.namePreset("save","",root.suggest,true) }
        TextLink { text:S.s_tone_discard;onClicked:{Player.toneAction("discard");root.finish()} }
    }
    Column {
        width:parent.width;Reveal { shown: root.form!=="" }
        FormField { id:nameField;width:parent.width;label:S.s_tone_name;onAccepted:root.saveName() }
        Flow { width:parent.width;spacing:Theme.s16;TextLink { text:S.s_luu_e91f26c0;onClicked:root.saveName() } TextLink { text:S.s_tone_back;onClicked:{root.form="";root.afterName=false} } }
    }
    Row {
        width:parent.width;Reveal { shown: root.deleted!==null }spacing:Theme.s12
        Text { width:parent.width-undoAction.width-parent.spacing;text:S.s_tone_deleted;color:Theme.text;font.pixelSize:Theme.sizeBodySmall;wrapMode:Text.Wrap }
        TextLink { id:undoAction;objectName:"toneUndo";text:S.s_hoan_tac_e72ff675;onClicked:{Player.toneAction("undo",root.deleted);root.deleted=null} }
    }
    Timer { id:undoLife;interval:7000;onTriggered:root.deleted=null }
}
