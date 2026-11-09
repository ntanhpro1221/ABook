import QtQuick
import ABook

Column {
    id: root
    property var fx: Player.audioFx
    width: parent.width
    spacing: Theme.s4
    Text { width: parent.width; text: "Âm thanh"; color: Theme.text; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Text { width: parent.width; text: "Dùng chung mặc định. Chỉ chỉnh giọng đọc; nhạc nền có mức riêng."; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: "Riêng sách này"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: "Riêng sách này"; checked: root.fx.bookOnly; onToggled: value => Player.setAudioFx({bookOnly:value}) }
    }
    AudioFxSlider { objectName: "audioFxVolume"; width: parent.width; label: "Âm lượng"; value: Player.volume*100; from: 0; to: 100; suffix: "%"; onPicked: value => Player.setVolume(value/100) }
    AudioFxSlider { width: parent.width; label: "Tăng âm"; value: root.fx.boost; from: 0; onPicked: value => Player.setAudioFx({boost:value}) }
    AudioFxSlider { width: parent.width; label: "Cao độ"; value: root.fx.pitch; from: -6; to: 6; step: 0.5; suffix: " bán âm"; onPicked: value => Player.setAudioFx({pitch:value}) }
    TextLink { text: "Về mặc định"; accent: true; onClicked: Player.setAudioFx({pitch:0}) }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: "Mono"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: "Mono"; checked: root.fx.mono; onToggled: value => Player.setAudioFx({mono:value}) }
    }
    AudioFxSlider { width: parent.width; label: "Cân bằng"; value: root.fx.balance*100; from: -100; to: 100; suffix: "% (trái / phải)"; onPicked: value => Player.setAudioFx({balance:value/100}) }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: "Bỏ khoảng lặng"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: "Bỏ khoảng lặng"; checked: root.fx.skipSilence; onToggled: value => Player.setAudioFx({skipSilence:value}) }
    }
    Text { width: parent.width; text: "Giữ nhịp nghỉ; chỉ rút khoảng lặng dài."; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    AudioFxSlider { width: parent.width; label: "Ngưỡng lặng"; value: root.fx.silenceDb; from: -80; to: -45; suffix: " dBFS"; enabled: root.fx.skipSilence; onPicked: value => Player.setAudioFx({silenceDb:value}) }
    AudioFxSlider { width: parent.width; label: "Dài tối thiểu"; value: root.fx.silenceSeconds; from: 2; to: 10; step: 0.5; suffix: " s"; enabled: root.fx.skipSilence; onPicked: value => Player.setAudioFx({silenceSeconds:value}) }
    AudioFxSlider { width: parent.width; label: "Giữ khoảng nghỉ"; value: root.fx.keepSeconds; from: 1.5; to: Math.min(3,root.fx.silenceSeconds); step: 0.1; suffix: " s"; enabled: root.fx.skipSilence; onPicked: value => Player.setAudioFx({keepSeconds:value}) }
    Row {
        width: parent.width; height: 48
        Text { width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; text: "Equalizer"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Switch { anchors.verticalCenter: parent.verticalCenter; label: "Equalizer"; checked: root.fx.enabled; onToggled: value => Player.setAudioFx({enabled:value}) }
    }
    Text { text: "Preset"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
    ChoiceRow {
        width: parent.width; label: "Preset"; value: root.fx.preset
        options: [{value:0,label:"Phẳng"},{value:1,label:"Rõ lời"},{value:2,label:"Trầm ấm"},{value:3,label:"Bổng"},{value:4,label:"Giảm chói"},{value:-1,label:"Tự chỉnh"}]
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
    AudioFxSlider { width: parent.width; label: "Tăng trầm"; value: root.fx.bass; from: 0; enabled: root.fx.enabled; onPicked: value => Player.setAudioFx({preset:-1,bass:value}) }
}
