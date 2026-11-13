import "UiNumber.js" as UiNumber
import "UiStrings.js" as S
import "ToneLabels.js" as ToneLabels
import "ValuePickerLogic.js" as Logic
import QtQuick
import ABook

// Trang Âm thanh, cùng thứ tự với Android / web: Giọng đọc 0-200 % (100 % = gốc) → Nhạc nền ngay dưới → Âm sắc một hàng
// (dải tần chỉ khi Tự chỉnh) → Mono, Cân bằng, Bỏ khoảng lặng → Riêng sách này → Cao độ ở cuối → Về mặc định (mọi thứ, áp ngay).
Column {
    id: root
    property var fx: Player.audioFx
    property bool toneOpen: false
    property var library: Player.tones
    readonly property string toneName: library.dirty || library.selected.id === "draft" ? S.s_tone_draft : (library.preset.name || ToneLabels.label(library.selected.id) || S.s_tat_3286064e)
    function requestClose(action) { if(toneOpen)tonePage.leave(() => {root.toneOpen=false;action()});else action() }
    onToneOpenChanged: { if(toneOpen)Nav.openLayer(tonePage);else Nav.closedLayer(tonePage) }
    Component.onDestruction: Nav.closedLayer(tonePage)
    // Mở bảng Nhạc nền của cuốn (chọn bài, ghi công); null = không có đường ấy.
    property var openMusic: null
    readonly property real voice: root.fx.boost > 0 ? Math.pow(10, root.fx.boost/20) : Player.volume
    readonly property int tone: root.fx.enabled ? root.fx.preset : 0
    function setVoice(level) {
        if (level <= 1) { Player.setVolume(Math.max(0, level)); Player.setAudioFx({boost:0}) }
        else { Player.setVolume(1); Player.setAudioFx({boost:20*Math.log(Math.min(level, 2))/Math.LN10}) }
    }
    function setTone(index) {
        if (index === 0) Player.setAudioFx({enabled:false,preset:0})
        else Player.setAudioFx({enabled:true,preset:index})
    }
    function reset() {
        Player.toneAction("select",{id:"off"})
        Player.setVolume(1)
        Player.setAudioFx({enabled:false,preset:0,bands:[0,0,0,0,0],bass:0,boost:0,pitch:0,mono:false,balance:0,skipSilence:false,silenceDb:-60,silenceSeconds:3,keepSeconds:1.5})
    }
    width: parent.width
    spacing: Theme.s4
    TonePage {
        id:tonePage;width:root.width;Reveal { shown: root.toneOpen }
        onBackRequested:root.toneOpen=false
        onVisibleChanged:if(visible)slide.restart()
        NumberAnimation { id:slide;target:tonePage;property:"x";from:24;to:0;duration:Theme.reduceMotion?0:Theme.motionMedium }
    }
    Column {
    id:audioMain
    width:parent.width;Reveal { shown: !root.toneOpen }spacing:Theme.s4
    onVisibleChanged:if(visible)backSlide.restart()
    NumberAnimation { id:backSlide;target:audioMain;property:"x";from:-24;to:0;duration:Theme.reduceMotion?0:Theme.motionMedium }
    Text { width: parent.width; text: S.s_copy_c1303271503d; color: Theme.text; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    AudioFxSlider { objectName: "audioFxVoice"; width: parent.width; label: S.s_giong_doc_11f2548d; spec: Logic.SPECS.voice; value: Math.round(root.voice*100); suffix: "%"; onPicked: value => root.setVoice(value/100) }
    MenuRow { width: parent.width; Reveal { shown: root.openMusic !== null && Music.hasMusic } text: S.s_nhac_nen_271fb292; icon: "eighth-note"; onClicked: root.openMusic() }
    MenuRow { objectName:"audioFxTones";width:parent.width;valueLimit:width*.55;text:S.s_am_sac_8c2f4e1a;value:root.toneName+(root.library.scoped ? "\u00a0·\u00a0"+S.s_copy_0aedb2b2cf2b : "");icon:"sliders-horizontal";onClicked:root.toneOpen=true }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: S.s_copy_6f00156cec07; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: S.s_copy_6f00156cec07; checked: root.fx.mono; onToggled: value => Player.setAudioFx({mono:value}) }
    }
    AudioFxSlider { width: parent.width; label: S.s_can_bang_8b88211d; spec: Logic.SPECS.balance; value: Math.round(root.fx.balance*100); format: UiNumber.balance; onPicked: value => Player.setAudioFx({balance:value/100}) }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: S.s_copy_289e1cff4cbc; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: S.s_copy_289e1cff4cbc; checked: root.fx.skipSilence; onToggled: value => Player.setAudioFx({skipSilence:value}) }
    }
    Text { width: parent.width; text: S.s_copy_b09b5fb2264a; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    Column {
        width: parent.width; Reveal { shown: root.fx.skipSilence }
        AudioFxSlider { width: parent.width; label: S.s_copy_8e18e6dd7fd9; spec: Logic.SPECS.silenceDb; value: root.fx.silenceDb; suffix: " dBFS"; onPicked: value => Player.setAudioFx({silenceDb:value}) }
        AudioFxSlider { width: parent.width; label: S.s_copy_19adc1b298a9; spec: Logic.SPECS.silenceSeconds; value: root.fx.silenceSeconds; suffix: " s"; onPicked: value => Player.setAudioFx({silenceSeconds:value}) }
        AudioFxSlider { width: parent.width; label: S.s_copy_483cdfec9d5f; spec: Logic.capped(Logic.SPECS.keepSeconds, root.fx.silenceSeconds); value: root.fx.keepSeconds; suffix: " s"; onPicked: value => Player.setAudioFx({keepSeconds:value}) }
    }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: S.s_copy_0aedb2b2cf2b; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: S.s_copy_0aedb2b2cf2b; checked: root.fx.bookOnly; onToggled: value => Player.setAudioFx({bookOnly:value}) }
    }
    AudioFxSlider { objectName: "audioFxPitch"; width: parent.width; label: S.s_copy_519c2d65ca4c; spec: Logic.SPECS.pitch; value: root.fx.pitch; suffix: S.s_copy_e9d6329e8255; onPicked: value => Player.setAudioFx({pitch:value}) }
    TextLink { objectName: "audioFxReset"; text: S.s_ve_mac_dinh_4eb6b300; accent: true; onClicked: root.reset() }
    }
}
