import QtQuick
import ABook

Column {
    id: root
    property var fx: Player.audioFx
    width: parent.width
    spacing: Theme.s4
    Text { width: parent.width; text: "Âm thanh"; color: Theme.text; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Text { width: parent.width; text: "Lưu cho toàn app. Chỉ chỉnh giọng đọc; nhạc nền có mức riêng."; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    AudioFxSlider { objectName: "audioFxVolume"; width: parent.width; label: "Âm lượng"; value: Player.volume*100; from: 0; to: 100; suffix: "%"; onPicked: value => Player.setVolume(value/100) }
    AudioFxSlider { width: parent.width; label: "Tăng âm"; value: root.fx.boost; from: 0; onPicked: value => Player.setAudioFx({boost:value}) }
    AudioFxSlider { width: parent.width; label: "Cao độ"; value: root.fx.pitch; from: -6; to: 6; step: 0.5; suffix: " bán âm"; onPicked: value => Player.setAudioFx({pitch:value}) }
    TextLink { text: "Về mặc định"; accent: true; onClicked: Player.setAudioFx({pitch:0}) }
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
