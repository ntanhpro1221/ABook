import "UiStrings.js" as S
import QtQuick
import ABook

// Trang Âm thanh, cùng thứ tự với Android / web: Giọng đọc 0-200 % (100 % = gốc) → Nhạc nền ngay dưới → Âm sắc một hàng
// (dải tần chỉ khi Tự chỉnh) → Mono, Cân bằng, Bỏ khoảng lặng → Riêng sách này → Cao độ ở cuối → Về mặc định (mọi thứ, áp ngay).
Column {
    id: root
    property var fx: Player.audioFx
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
        Player.setVolume(1)
        Player.setAudioFx({enabled:false,preset:0,bands:[0,0,0,0,0],bass:0,boost:0,pitch:0,mono:false,balance:0,skipSilence:false,silenceDb:-60,silenceSeconds:3,keepSeconds:1.5})
    }
    width: parent.width
    spacing: Theme.s4
    Text { width: parent.width; text: S.s_copy_c1303271503d; color: Theme.text; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    AudioFxSlider { objectName: "audioFxVoice"; width: parent.width; label: S.s_giong_doc_11f2548d; value: Math.round(root.voice*100); from: 0; to: 200; step: 5; suffix: "%"; onPicked: value => root.setVoice(value/100) }
    MenuRow { width: parent.width; visible: root.openMusic !== null && Music.hasMusic; text: S.s_nhac_nen_271fb292; icon: "eighth-note"; onClicked: root.openMusic() }
    Text { width: parent.width; topPadding: Theme.s8; text: S.s_am_sac_8c2f4e1a; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
    Flickable {
        width: parent.width; height: tones.height
        contentWidth: tones.width; clip: true
        flickableDirection: Flickable.HorizontalFlick; boundsBehavior: Flickable.StopAtBounds
        ChoiceRow {
            id: tones
            objectName: "audioFxTones"
            label: S.s_am_sac_8c2f4e1a; value: root.tone
            options: [{value:0,label:S.s_copy_0053dd90f780},{value:1,label:S.s_copy_bac2d68d2977},{value:2,label:S.s_copy_05798ad73e95},{value:3,label:S.s_copy_66823083cf09},{value:4,label:S.s_copy_47dbcad94daf},{value:-1,label:S.s_copy_e3518044ceec}]
            onPicked: value => root.setTone(Number(value))
        }
    }
    Column {
        width: parent.width; visible: root.tone < 0
        Repeater {
            model: ["80 Hz","250 Hz","1 kHz","4 kHz","12 kHz"]
            AudioFxSlider {
                required property string modelData; required property int index
                width: root.width; label: modelData; value: root.fx.bands[index]
                onPicked: value => { const bands=root.fx.bands.slice(); bands[index]=value; Player.setAudioFx({preset:-1,bands:bands}) }
            }
        }
        AudioFxSlider { width: parent.width; label: S.s_copy_eb4635c58f1d; value: root.fx.bass; from: 0; onPicked: value => Player.setAudioFx({preset:-1,bass:value}) }
    }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: S.s_copy_6f00156cec07; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: S.s_copy_6f00156cec07; checked: root.fx.mono; onToggled: value => Player.setAudioFx({mono:value}) }
    }
    AudioFxSlider { width: parent.width; label: S.s_can_bang_8b88211d; value: root.fx.balance*100; from: -100; to: 100; suffix: S.s_copy_9bf94b95eb12; onPicked: value => Player.setAudioFx({balance:value/100}) }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: S.s_copy_289e1cff4cbc; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: S.s_copy_289e1cff4cbc; checked: root.fx.skipSilence; onToggled: value => Player.setAudioFx({skipSilence:value}) }
    }
    Text { width: parent.width; text: S.s_copy_b09b5fb2264a; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    Column {
        width: parent.width; visible: root.fx.skipSilence
        AudioFxSlider { width: parent.width; label: S.s_copy_8e18e6dd7fd9; value: root.fx.silenceDb; from: -80; to: -45; suffix: " dBFS"; onPicked: value => Player.setAudioFx({silenceDb:value}) }
        AudioFxSlider { width: parent.width; label: S.s_copy_19adc1b298a9; value: root.fx.silenceSeconds; from: 2; to: 10; step: 0.5; suffix: " s"; onPicked: value => Player.setAudioFx({silenceSeconds:value}) }
        AudioFxSlider { width: parent.width; label: S.s_copy_483cdfec9d5f; value: root.fx.keepSeconds; from: 1.5; to: Math.min(3,root.fx.silenceSeconds); step: 0.1; suffix: " s"; onPicked: value => Player.setAudioFx({keepSeconds:value}) }
    }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: S.s_copy_0aedb2b2cf2b; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: S.s_copy_0aedb2b2cf2b; checked: root.fx.bookOnly; onToggled: value => Player.setAudioFx({bookOnly:value}) }
    }
    AudioFxSlider { objectName: "audioFxPitch"; width: parent.width; label: S.s_copy_519c2d65ca4c; value: root.fx.pitch; from: -6; to: 6; step: 0.5; suffix: S.s_copy_e9d6329e8255; onPicked: value => Player.setAudioFx({pitch:value}) }
    TextLink { objectName: "audioFxReset"; text: S.s_ve_mac_dinh_4eb6b300; accent: true; onClicked: root.reset() }
}
