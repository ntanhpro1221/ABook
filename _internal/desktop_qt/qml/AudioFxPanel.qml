import "UiStrings.js" as S
import QtQuick
import ABook

Column {
    id: root
    property var fx: Player.audioFx
    width: parent.width
    spacing: Theme.s4
    Text { width: parent.width; text: S.s_copy_c1303271503d; color: Theme.text; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Text { width: parent.width; text: S.s_copy_d05a51c01f29; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: S.s_copy_0aedb2b2cf2b; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: S.s_copy_0aedb2b2cf2b; checked: root.fx.bookOnly; onToggled: value => Player.setAudioFx({bookOnly:value}) }
    }
    AudioFxSlider { objectName: "audioFxVolume"; width: parent.width; label: S.s_am_luong_5dafca26; value: Player.volume*100; from: 0; to: 100; suffix: "%"; onPicked: value => Player.setVolume(value/100) }
    AudioFxSlider { width: parent.width; label: S.s_copy_c77e16da718e; value: root.fx.boost; from: 0; onPicked: value => Player.setAudioFx({boost:value}) }
    AudioFxSlider { width: parent.width; label: S.s_copy_519c2d65ca4c; value: root.fx.pitch; from: -6; to: 6; step: 0.5; suffix: S.s_copy_e9d6329e8255; onPicked: value => Player.setAudioFx({pitch:value}) }
    TextLink { text: S.s_ve_mac_dinh_4eb6b300; accent: true; onClicked: Player.setAudioFx({pitch:0}) }
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
    AudioFxSlider { width: parent.width; label: S.s_copy_8e18e6dd7fd9; value: root.fx.silenceDb; from: -80; to: -45; suffix: " dBFS"; enabled: root.fx.skipSilence; onPicked: value => Player.setAudioFx({silenceDb:value}) }
    AudioFxSlider { width: parent.width; label: S.s_copy_19adc1b298a9; value: root.fx.silenceSeconds; from: 2; to: 10; step: 0.5; suffix: " s"; enabled: root.fx.skipSilence; onPicked: value => Player.setAudioFx({silenceSeconds:value}) }
    AudioFxSlider { width: parent.width; label: S.s_copy_483cdfec9d5f; value: root.fx.keepSeconds; from: 1.5; to: Math.min(3,root.fx.silenceSeconds); step: 0.1; suffix: " s"; enabled: root.fx.skipSilence; onPicked: value => Player.setAudioFx({keepSeconds:value}) }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: S.s_copy_71255f2b6855; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: S.s_copy_71255f2b6855; checked: root.fx.enabled; onToggled: value => Player.setAudioFx({enabled:value}) }
    }
    Text { text: S.s_copy_7252e7ce0085; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
    ChoiceRow {
        width: parent.width; label: S.s_copy_7252e7ce0085; value: root.fx.preset
        options: [{value:0,label:S.s_copy_0053dd90f780},{value:1,label:S.s_copy_bac2d68d2977},{value:2,label:S.s_copy_05798ad73e95},{value:3,label:S.s_copy_66823083cf09},{value:4,label:S.s_copy_47dbcad94daf},{value:-1,label:S.s_copy_e3518044ceec}]
        onPicked: value => Player.setAudioFx({enabled:true,preset:Number(value)})
    }
    Repeater {
        model: ["80 Hz","250 Hz","1 kHz","4 kHz","12 kHz"]
        AudioFxSlider {
            required property string modelData; required property int index
            width: root.width; label: modelData; value: root.fx.bands[index]; enabled: root.fx.enabled
            onPicked: value => { const bands=root.fx.bands.slice(); bands[index]=value; Player.setAudioFx({preset:-1,bands:bands}) }
        }
    }
    AudioFxSlider { width: parent.width; label: S.s_copy_eb4635c58f1d; value: root.fx.bass; from: 0; enabled: root.fx.enabled; onPicked: value => Player.setAudioFx({preset:-1,bass:value}) }
}
